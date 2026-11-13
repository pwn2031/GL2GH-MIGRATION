#!/usr/bin/env python3

"""Step 0: Generate GitLab-to-GitHub migration plan and identity mapping."""

import os
from pathlib import Path

from scripts.lib.csv_utils import read_csv, write_csv
from scripts.lib.github_client import repo_exists
from scripts.lib.gitlab_client import create_client, get_project_members
from scripts.lib.logging_utils import log, write_json
from scripts.lib.validators import (
    github_permission_for_gitlab_role,
    validate_identity_mapping,
    validate_repository_name,
)

PLAN_FIELDS = [
    "gitlab_project",
    "github_repo",
    "github_owner",
    "github_repo_full",
    "github_repo_exists",
    "migration_decision",
    "default_branch",
    "visibility",
    "member_count",
    "variable_count",
    "deploy_key_count",
]

USER_MAPPING_FIELDS = [
    "gitlab_project",
    "gitlab_username",
    "gitlab_email",
    "gitlab_role",
    "github_username",
    "github_permission",
    "mapping_status",
]

UNMAPPED_FIELDS = [
    "gitlab_project",
    "gitlab_username",
    "gitlab_email",
    "gitlab_role",
    "status",
]


def sanitize_repo_name(name):
    return name.strip().replace(" ", "-").lower()


def main():
    log("Generating GitLab-to-GitHub migration plan...")

    client = create_client()

    identity_mapping = validate_identity_mapping(
        os.environ["IDENTITY_MAPPING_FILE"]
    )

    github_account = os.environ["GITHUB_ACCOUNT"]
    unmapped_policy = os.environ["UNMAPPED_USER_POLICY"].lower()

    inventory_file = (
        Path(os.environ["INVENTORY_DIR"]) / "gitlab-inventory.json"
    )

    if not inventory_file.exists():
        raise FileNotFoundError(
            f"GitLab inventory not found: {inventory_file}. "
            "Run ./run.sh inventory first."
        )

    inventory = read_json_safe(inventory_file)

    migration_dir = Path(os.environ["MIGRATION_DIR"])
    migration_dir.mkdir(parents=True, exist_ok=True)

    plan_projects = []
    user_mapping_rows = []
    unmapped_rows = []

    for project in inventory["projects"]:
        gitlab_project = project["path_with_namespace"]
        github_repo = sanitize_repo_name(project["path"])

        validate_repository_name(github_repo)

        github_repo_full = f"{github_account}/{github_repo}"
        exists = repo_exists(github_account, github_repo)

        log(
            f"Planning {gitlab_project} → {github_repo_full} "
            f"(GitHub repository exists: {exists})"
        )

        plan_projects.append(
            {
                "gitlab_project": gitlab_project,
                "github_repo": github_repo,
                "github_owner": github_account,
                "github_repo_full": github_repo_full,
                "github_repo_exists": exists,
                "migration_decision": "migrate",
                "default_branch": project["default_branch"],
                "visibility": project["visibility"],
                "member_count": project["member_count"],
                "variable_count": project["variable_count"],
                "deploy_key_count": project["deploy_key_count"],
            }
        )

        gitlab_project_obj = client.projects.get(gitlab_project)
        members = get_project_members(gitlab_project_obj)

        for member in members:
            gitlab_username = member["username"]
            identity = identity_mapping.get(gitlab_username)

            if not identity or not identity["include"]:
                unmapped_rows.append(
                    {
                        "gitlab_project": gitlab_project,
                        "gitlab_username": gitlab_username,
                        "gitlab_email": member["email"],
                        "gitlab_role": member["role"],
                        "status": "unmapped",
                    }
                )

                if unmapped_policy == "fail":
                    raise RuntimeError(
                        f"Unmapped GitLab user: {gitlab_username} "
                        f"in {gitlab_project}"
                    )

                continue

            github_permission = github_permission_for_gitlab_role(
                member["role"],
                identity["github_role_override"],
            )

            user_mapping_rows.append(
                {
                    "gitlab_project": gitlab_project,
                    "gitlab_username": gitlab_username,
                    "gitlab_email": identity["gitlab_email"],
                    "gitlab_role": member["role"],
                    "github_username": identity["github_username"],
                    "github_permission": github_permission,
                    "mapping_status": "mapped",
                }
            )

    migration_plan = {
        "source": {
            "gitlab_url": os.environ["GITLAB_URL"],
            "gitlab_group": os.environ["GITLAB_GROUP"],
        },
        "target": {
            "github_account": github_account,
            "target_mode": os.environ["GITHUB_TARGET_MODE"],
        },
        "controls": {
            "dry_run": os.environ["DRY_RUN"].lower() == "true",
            "auto_approve": os.environ["AUTO_APPROVE"].lower() == "true",
            "fail_fast": os.environ["FAIL_FAST"].lower() == "true",
            "unmapped_user_policy": unmapped_policy,
        },
        "project_count": len(plan_projects),
        "mapped_user_count": len(
            {row["github_username"] for row in user_mapping_rows}
        ),
        "unmapped_user_count": len(unmapped_rows),
        "projects": plan_projects,
        "user_mappings": user_mapping_rows,
        "unmapped_users": unmapped_rows,
    }

    write_json(migration_dir / "migration-plan.json", migration_plan)

    write_csv(
        migration_dir / "group-mapping.csv",
        plan_projects,
        PLAN_FIELDS,
    )

    write_csv(
        migration_dir / "user-mapping.csv",
        user_mapping_rows,
        USER_MAPPING_FIELDS,
    )

    write_csv(
        migration_dir / "unmapped-users.csv",
        unmapped_rows,
        UNMAPPED_FIELDS,
    )

    log("Migration plan generated.")
    log(f"Projects planned: {len(plan_projects)}")
    log(f"User mappings generated: {len(user_mapping_rows)}")
    log(f"Unmapped users: {len(unmapped_rows)}")


def read_json_safe(path):
    import json

    with open(path, encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    main()