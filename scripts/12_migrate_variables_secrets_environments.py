#!/usr/bin/env python3

"""Step 7: Migrate GitLab variables to GitHub variables and identify secrets."""

import csv
import os
from pathlib import Path

from scripts.lib.github_client import (
    create_environment,
    create_repository_variable,
)
from scripts.lib.gitlab_client import (
    create_client,
    get_project_variables,
)
from scripts.lib.logging_utils import log
from scripts.lib.validators import is_secret_variable

RESULT_FIELDS = [
    "gitlab_project",
    "github_repo_full",
    "gitlab_key",
    "github_name",
    "destination",
    "action",
    "status",
]

SECRET_FIELDS = [
    "gitlab_project",
    "github_repo_full",
    "secret_name",
    "reason",
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
    plan = read_plan()

    github_account = os.environ["GITHUB_ACCOUNT"]
    migration_dir = Path(os.environ["MIGRATION_DIR"])

    result_file = migration_dir / "variables-result.csv"
    secret_file = migration_dir / "secrets-required.csv"

    results = []
    secrets_required = []

    for project in plan["projects"]:
        gitlab_project = project["gitlab_project"]
        github_repo = project["github_repo"]
        github_repo_full = f"{github_account}/{github_repo}"

        log(f"Migrating variables for: {gitlab_project}")

        gitlab_project_obj = client.projects.get(gitlab_project)
        variables = get_project_variables(gitlab_project_obj)

        if not dry_run:
            try:
                create_environment(
                    github_account,
                    github_repo,
                    "production",
                )
                log(f"Created or updated environment: production")
            except Exception as exc:
                log(f"Environment creation failed: {exc}")

        for variable in variables:
            key = variable["key"]
            value = variable["value"]

            if is_secret_variable(key):
                log(f"Secret-like variable detected: {key}")

                secrets_required.append(
                    {
                        "gitlab_project": gitlab_project,
                        "github_repo_full": github_repo_full,
                        "secret_name": key,
                        "reason": (
                            "Secret-like GitLab variable; value must be "
                            "recreated securely in GitHub"
                        ),
                        "action_required": (
                            "Create GitHub Actions secret manually"
                        ),
                    }
                )

                results.append(
                    {
                        "gitlab_project": gitlab_project,
                        "github_repo_full": github_repo_full,
                        "gitlab_key": key,
                        "github_name": key,
                        "destination": "github_secret",
                        "action": "manual_recreation_required",
                        "status": "pending_manual_action",
                    }
                )
                continue

            if dry_run:
                status = "dry_run"
                log(f"DRY RUN: Would create variable {key}")
            else:
                try:
                    create_repository_variable(
                        github_account,
                        github_repo,
                        key,
                        value,
                    )
                    status = "created_or_updated"
                    log(f"Created or updated GitHub variable: {key}")
                except Exception as exc:
                    status = "failed"
                    log(f"Failed to create variable {key}: {exc}")

            results.append(
                {
                    "gitlab_project": gitlab_project,
                    "github_repo_full": github_repo_full,
                    "gitlab_key": key,
                    "github_name": key,
                    "destination": "github_variable",
                    "action": "create_or_update",
                    "status": status,
                }
            )

    with open(result_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    with open(secret_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SECRET_FIELDS)
        writer.writeheader()
        writer.writerows(secrets_required)

    log(f"Variable migration complete: {result_file}")
    log(f"Secrets requiring manual creation: {secret_file}")


if __name__ == "__main__":
    main()