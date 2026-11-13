#!/usr/bin/env python3

"""Step 3: Migrate repository permissions and deploy keys."""

import csv
import os
from pathlib import Path

from scripts.lib.github_client import (
    set_collaborator_permission,
)
from scripts.lib.gitlab_client import (
    create_client,
    get_project_deploy_keys,
    get_project_members,
)
from scripts.lib.logging_utils import log
from scripts.lib.validators import (
    github_permission_for_gitlab_role,
    validate_identity_mapping,
)

PERMISSION_FIELDS = [
    "gitlab_project",
    "github_repo_full",
    "gitlab_username",
    "github_username",
    "gitlab_role",
    "github_permission",
    "status",
]

DEPLOY_KEY_FIELDS = [
    "gitlab_project",
    "github_repo_full",
    "gitlab_key_id",
    "gitlab_title",
    "can_push",
    "status",
    "action_required",
]


def read_plan():
    plan_file = Path(os.environ["MIGRATION_DIR"]) / "migration-plan.json"

    import json

    with open(plan_file, encoding="utf-8") as f:
        return json.load(f)


def main():
    dry_run = os.environ["DRY_RUN"].lower() == "true"

    client = create_client()

    identity_mapping = validate_identity_mapping(
        os.environ["IDENTITY_MAPPING_FILE"]
    )

    plan = read_plan()

    github_account = os.environ["GITHUB_ACCOUNT"]
    migration_dir = Path(os.environ["MIGRATION_DIR"])

    permission_result_file = migration_dir / "permissions-result.csv"
    deploy_key_result_file = migration_dir / "deploy-keys-result.csv"

    permission_results = []
    deploy_key_results = []

    for project in plan["projects"]:
        gitlab_project = project["gitlab_project"]
        github_repo = project["github_repo"]
        github_repo_full = f"{github_account}/{github_repo}"

        log(f"Migrating permissions for: {gitlab_project}")

        gitlab_project_obj = client.projects.get(gitlab_project)
        members = get_project_members(gitlab_project_obj)

        for member in members:
            gitlab_username = member["username"]
            identity = identity_mapping.get(gitlab_username)

            if not identity or not identity["include"]:
                log(
                    f"Skipping unmapped or excluded user: {gitlab_username}"
                )
                continue

            github_username = identity["github_username"]

            github_permission = github_permission_for_gitlab_role(
                member["role"],
                identity["github_role_override"],
            )

            if dry_run:
                status = "dry_run"
                log(
                    f"DRY RUN: {github_username} → "
                    f"{github_permission} on {github_repo_full}"
                )
            else:
                try:
                    set_collaborator_permission(
                        github_account,
                        github_repo,
                        github_username,
                        github_permission,
                    )

                    status = "assigned"
                    log(
                        f"Assigned: {github_username} → "
                        f"{github_permission} on {github_repo_full}"
                    )
                except Exception as exc:
                    status = "failed"
                    log(
                        f"Failed to assign {github_username} on "
                        f"{github_repo_full}: {exc}"
                    )

            permission_results.append(
                {
                    "gitlab_project": gitlab_project,
                    "github_repo_full": github_repo_full,
                    "gitlab_username": gitlab_username,
                    "github_username": github_username,
                    "gitlab_role": member["role"],
                    "github_permission": github_permission,
                    "status": status,
                }
            )

        log(f"Migrating deploy keys for: {gitlab_project}")

        deploy_keys = get_project_deploy_keys(gitlab_project_obj)

        for key in deploy_keys:
            if dry_run:
                status = "dry_run"
                action_required = "generate_or_supply_public_key"
            else:
                status = "manual_action_required"
                action_required = (
                    "Create GitHub deploy key using the same public key"
                )

            log(
                f"Deploy key requires manual handling: "
                f"{key['title']} on {github_repo_full}"
            )

            deploy_key_results.append(
                {
                    "gitlab_project": gitlab_project,
                    "github_repo_full": github_repo_full,
                    "gitlab_key_id": key["id"],
                    "gitlab_title": key["title"],
                    "can_push": key["can_push"],
                    "status": status,
                    "action_required": action_required,
                }
            )

    with open(permission_result_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PERMISSION_FIELDS)
        writer.writeheader()
        writer.writerows(permission_results)

    with open(deploy_key_result_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=DEPLOY_KEY_FIELDS)
        writer.writeheader()
        writer.writerows(deploy_key_results)

    log(f"Permission migration complete: {permission_result_file}")
    log(f"Deploy key migration complete: {deploy_key_result_file}")


if __name__ == "__main__":
    main()