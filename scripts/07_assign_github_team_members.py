#!/usr/bin/env python3

"""Assign mapped GitLab group members to GitHub organization teams."""

import csv
import os
from pathlib import Path

from scripts.lib.github_client import github_request
from scripts.lib.logging_utils import log

RESULT_FIELDS = [
    "gitlab_group_path",
    "github_org",
    "github_team_slug",
    "gitlab_username",
    "github_username",
    "gitlab_role",
    "status",
]


def read_plan():
    plan_file = (
        Path(os.environ["MIGRATION_DIR"])
        / "gitlab-team-members-plan.csv"
    )

    with open(plan_file, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    dry_run = os.environ["DRY_RUN"].lower() == "true"

    org = os.environ["GITHUB_ORG"]
    rows = read_plan()

    migration_dir = Path(os.environ["MIGRATION_DIR"])
    result_file = migration_dir / "github-team-members-result.csv"

    results = []
    processed = set()

    for row in rows:
        if row["mapping_status"] != "mapped":
            log(f"Skipping unmapped user: {row['gitlab_username']}")
            continue

        github_username = row["github_username"]
        team_slug = row["github_team_slug"]
        gitlab_username = row["gitlab_username"]

        key = (github_username, team_slug)

        if key in processed:
            continue

        processed.add(key)

        if dry_run:
            status = "dry_run"
            log(
                f"DRY RUN: Add {github_username} to team {team_slug}"
            )

        else:
            try:
                github_request(
                    "PUT",
                    f"/orgs/{org}/teams/{team_slug}/memberships/{github_username}",
                    {"role": "member"},
                    expected_status=(200, 201),
                )

                status = "assigned"
                log(
                    f"Assigned {github_username} to team {team_slug}"
                )

            except Exception as exc:
                status = "failed"
                log(
                    f"Failed to assign {github_username} to "
                    f"{team_slug}: {exc}"
                )

        results.append(
            {
                "gitlab_group_path": row["gitlab_group_path"],
                "github_org": org,
                "github_team_slug": team_slug,
                "gitlab_username": gitlab_username,
                "github_username": github_username,
                "gitlab_role": row["gitlab_role"],
                "status": status,
            }
        )

    with open(result_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    log(f"GitHub team member assignment complete: {result_file}")


if __name__ == "__main__":
    main()