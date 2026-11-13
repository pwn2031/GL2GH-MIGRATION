#!/usr/bin/env python3

"""PHASE 6.1: Validate migration artifacts and generate a validation summary."""

import csv
import json
import os
from pathlib import Path

from scripts.lib.logging_utils import log

RESULT_FIELDS = [
    "check",
    "expected",
    "actual",
    "status",
]


def read_csv(path):
    if not path.exists():
        return []

    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def count_successful(rows, status_field="status"):
    return sum(
        1
        for row in rows
        if row.get(status_field, "").lower()
        in {
            "created",
            "created_or_already_exists",
            "already_exists",
            "migrated",
            "assigned",
            "success",
            "completed",
        }
    )


def main():
    migration_dir = Path(os.environ["MIGRATION_DIR"])
    reports_dir = Path(os.environ["REPORTS_DIR"])

    result_file = reports_dir / "migration-validation.csv"
    results = []

    checks = [
        (
            "GitHub repositories",
            migration_dir / "github-targets-result.csv",
        ),
        (
            "GitHub teams",
            migration_dir / "github-teams-result.csv",
        ),
        (
            "GitHub team members",
            migration_dir / "github-team-members-result.csv",
        ),
        (
            "Git repositories",
            migration_dir / "repository-migration-result.csv",
        ),
        (
            "Issues, labels, milestones, and releases",
            migration_dir / "metadata-result.csv",
        ),
        (
            "Merge requests",
            migration_dir / "merge-request-migration-result.csv",
        ),
        (
            "CI/CD conversion",
            migration_dir / "cicd-result.csv",
        ),
        (
            "Variables",
            migration_dir / "variables-result.csv",
        ),
        (
            "Runner validation",
            migration_dir / "runner-validation.csv",
        ),
        (
            "Branch rulesets",
            migration_dir / "branch-rulesets-result.csv",
        ),
        (
            "Team repository permissions",
            migration_dir / "github-team-repo-permissions-result.csv",
        ),
        (
            "Permissions",
            migration_dir / "permissions-result.csv",
        ),
        (
            "Deploy keys",
            migration_dir / "deploy-keys-result.csv",
        ),
    ]

    for check_name, result_path in checks:
        rows = read_csv(result_path)
        successful = count_successful(rows)
        total = len(rows)

        if total == 0:
            status = "warning_no_results"
        elif successful == total:
            status = "passed"
        elif successful > 0:
            status = "partial"
        else:
            status = "failed"

        results.append(
            {
                "check": check_name,
                "expected": str(total),
                "actual": str(successful),
                "status": status,
            }
        )

        log(
            f"Validated {check_name}: {successful}/{total} successful "
            f"({status})"
        )

    with open(result_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    log(f"Migration validation complete: {result_file}")


if __name__ == "__main__":
    main()