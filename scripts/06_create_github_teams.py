#!/usr/bin/env python3

"""Create GitHub organization teams from GitLab groups and subgroups."""

import csv
import os
from pathlib import Path

from scripts.lib.github_client import github_request
from scripts.lib.logging_utils import log

RESULT_FIELDS = [
    "gitlab_group_path",
    "github_org",
    "github_team_name",
    "github_team_slug",
    "status",
]


def read_plan():
    plan_file = (
        Path(os.environ["MIGRATION_DIR"]) / "gitlab-teams-plan.csv"
    )

    with open(plan_file, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def team_exists(org, team_slug):
    try:
        github_request("GET", f"/orgs/{org}/teams/{team_slug}")
        return True
    except RuntimeError:
        return False


def main():
    dry_run = os.environ["DRY_RUN"].lower() == "true"

    org = os.environ["GITHUB_ORG"]
    privacy = os.environ.get("GITHUB_TEAM_PRIVACY", "closed")

    rows = read_plan()

    migration_dir = Path(os.environ["MIGRATION_DIR"])
    result_file = migration_dir / "github-teams-result.csv"

    results = []

    for row in rows:
        gitlab_group_path = row["gitlab_group_path"]
        team_name = row["github_team_name"]
        team_slug = row["github_team_slug"]

        log(f"Processing GitHub team: {team_slug}")

        if team_exists(org, team_slug):
            status = "already_exists"
            log(f"Team already exists: {team_slug}")

        elif dry_run:
            status = "dry_run"
            log(f"DRY RUN: Would create team {team_slug}")

        else:
            try:
                github_request(
                    "POST",
                    f"/orgs/{org}/teams",
                    {
                        "name": team_name,
                        "description": (
                            f"Migrated from GitLab group "
                            f"{gitlab_group_path}"
                        ),
                        "privacy": privacy,
                    },
                    expected_status=(201,),
                )

                status = "created"
                log(f"Created GitHub team: {team_slug}")

            except Exception as exc:
                status = "failed"
                log(f"Failed to create team {team_slug}: {exc}")

        results.append(
            {
                "gitlab_group_path": gitlab_group_path,
                "github_org": org,
                "github_team_name": team_name,
                "github_team_slug": team_slug,
                "status": status,
            }
        )

    with open(result_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    log(f"GitHub team creation complete: {result_file}")


if __name__ == "__main__":
    main()