#!/usr/bin/env python3

"""Steps 1-2: Create GitHub repositories from the migration plan."""

import csv
import os
from pathlib import Path

from scripts.lib.github_client import create_repository, repo_exists
from scripts.lib.logging_utils import log
from scripts.lib.validators import validate_repository_name

RESULT_FIELDS = [
    "gitlab_project",
    "github_repo",
    "github_repo_full",
    "action",
    "status",
]


def read_plan():
    plan_file = Path(os.environ["MIGRATION_DIR"]) / "migration-plan.json"

    if not plan_file.exists():
        raise FileNotFoundError(
            f"Migration plan not found: {plan_file}. "
            "Run ./run.sh plan first."
        )

    import json

    with open(plan_file, encoding="utf-8") as f:
        return json.load(f)


def main():
    dry_run = os.environ["DRY_RUN"].lower() == "true"
    plan = read_plan()

    github_account = os.environ["GITHUB_ACCOUNT"]
    migration_dir = Path(os.environ["MIGRATION_DIR"])

    result_file = migration_dir / "github-targets-result.csv"

    results = []

    log(f"Creating GitHub targets. Dry run: {dry_run}")

    for project in plan["projects"]:
        gitlab_project = project["gitlab_project"]
        github_repo = project["github_repo"]
        github_repo_full = project["github_repo_full"]

        validate_repository_name(github_repo)

        if repo_exists(github_account, github_repo):
            action = "already_exists"
            status = "skipped"

            log(f"GitHub repository already exists: {github_repo_full}")
        elif dry_run:
            action = "would_create"
            status = "dry_run"

            log(f"DRY RUN: Would create {github_repo_full}")
        else:
            create_repository(
                owner=github_account,
                repo_name=github_repo,
                private=True,
                description=f"Migrated from GitLab project {gitlab_project}",
            )

            action = "created"
            status = "success"

            log(f"Created GitHub repository: {github_repo_full}")

        results.append(
            {
                "gitlab_project": gitlab_project,
                "github_repo": github_repo,
                "github_repo_full": github_repo_full,
                "action": action,
                "status": status,
            }
        )

    with open(result_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    log(f"GitHub target creation complete: {result_file}")


if __name__ == "__main__":
    main()