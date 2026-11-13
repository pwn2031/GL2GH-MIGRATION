#!/usr/bin/env python3

"""Assign GitHub teams to migrated repositories based on GitLab group access."""

import csv
import os
from pathlib import Path

from scripts.lib.github_client import github_request
from scripts.lib.gitlab_client import create_client
from scripts.lib.logging_utils import log
from scripts.lib.validators import github_permission_for_gitlab_role

RESULT_FIELDS = [
    "gitlab_project",
    "github_repo_full",
    "gitlab_group_path",
    "github_team_slug",
    "gitlab_role",
    "github_permission",
    "status",
]


def read_plan():
    plan_file = Path(os.environ["MIGRATION_DIR"]) / "migration-plan.json"

    import json

    with open(plan_file, encoding="utf-8") as f:
        return json.load(f)


def read_team_plan():
    plan_file = (
        Path(os.environ["MIGRATION_DIR"])
        / "gitlab-teams-plan.csv"
    )

    with open(plan_file, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    dry_run = os.environ["DRY_RUN"].lower() == "true"

    client = create_client()

    org = os.environ["GITHUB_ORG"]
    default_permission = os.environ.get(
        "DEFAULT_GITHUB_TEAM_PERMISSION",
        "pull",
    )

    plan = read_plan()
    team_plan = read_team_plan()

    team_by_group_path = {
        row["gitlab_group_path"]: row["github_team_slug"]
        for row in team_plan
    }

    migration_dir = Path(os.environ["MIGRATION_DIR"])
    result_file = migration_dir / "github-team-repo-permissions-result.csv"

    results = []

    for project in plan["projects"]:
        gitlab_project = project["gitlab_project"]
        github_repo = project["github_repo"]
        github_repo_full = f"{org}/{github_repo}"

        log(f"Mapping project access: {gitlab_project}")

        gitlab_project_obj = client.projects.get(gitlab_project)

        try:
            groups_with_access = (
                gitlab_project_obj.groups_with_access.list(get_all=True)
            )
        except Exception as exc:
            log(
                f"Unable to list groups with access for "
                f"{gitlab_project}: {exc}"
            )
            continue

        for group_access in groups_with_access:
            group_path = group_access.full_path
            team_slug = team_by_group_path.get(group_path)

            if not team_slug:
                log(
                    f"No GitHub team found for GitLab group: {group_path}"
                )
                continue

            access_level = getattr(
                group_access,
                "access_level",
                20,
            )

            role_name = {
                10: "Guest",
                20: "Reporter",
                30: "Developer",
                40: "Maintainer",
                50: "Owner",
            }.get(int(access_level), "Reporter")

            github_permission = github_permission_for_gitlab_role(
                role_name,
                None,
            )

            if dry_run:
                status = "dry_run"
                log(
                    f"DRY RUN: Team {team_slug} → "
                    f"{github_permission} on {github_repo_full}"
                )

            else:
                try:
                    github_request(
                        "PUT",
                        f"/orgs/{org}/teams/{team_slug}/repos/{github_repo}",
                        {"permission": github_permission},
                        expected_status=(204,),
                    )

                    status = "assigned"
                    log(
                        f"Assigned team {team_slug} → "
                        f"{github_permission} on {github_repo_full}"
                    )

                except Exception as exc:
                    status = "failed"
                    log(
                        f"Failed to assign {team_slug} to "
                        f"{github_repo_full}: {exc}"
                    )

            results.append(
                {
                    "gitlab_project": gitlab_project,
                    "github_repo_full": github_repo_full,
                    "gitlab_group_path": group_path,
                    "github_team_slug": team_slug,
                    "gitlab_role": role_name,
                    "github_permission": github_permission,
                    "status": status,
                }
            )

    with open(result_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    log(f"Team repository permissions complete: {result_file}")


if __name__ == "__main__":
    main()