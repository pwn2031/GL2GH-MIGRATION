#!/usr/bin/env python3

"""Step 4: Apply GitHub branch rulesets to migrated repositories."""

import csv
import os
from pathlib import Path

from scripts.lib.github_client import github_request
from scripts.lib.logging_utils import log

RESULT_FIELDS = [
    "github_repo_full",
    "ruleset_name",
    "branch",
    "enforcement",
    "status",
]


def read_plan():
    plan_file = Path(os.environ["MIGRATION_DIR"]) / "migration-plan.json"

    import json

    with open(plan_file, encoding="utf-8") as f:
        return json.load(f)


def build_ruleset_payload(repo_name, default_branch):
    return {
        "name": f"protect-{default_branch}",
        "target": "branch",
        "enforcement": "active",
        "conditions": {
            "ref_name": {
                "include": [f"~DEFAULT_BRANCH"],
                "exclude": [],
            }
        },
        "rules": [
            {
                "type": "deletion"
            },
            {
                "type": "non_fast_forward"
            },
            {
                "type": "pull_request",
                "parameters": {
                    "required_approving_review_count": int(
                        os.environ.get("REQUIRED_APPROVALS", "1")
                    ),
                    "dismiss_stale_reviews_on_push": True,
                    "require_code_owner_review": False,
                    "require_last_push_approval": False,
                    "required_review_thread_resolution": False,
                    "allowed_merge_methods": ["merge", "squash", "rebase"]
                }
            }
        ]
    }


def main():
    dry_run = os.environ["DRY_RUN"].lower() == "true"

    if os.environ.get("PROTECT_DEFAULT_BRANCH", "true").lower() != "true":
        log("Branch protection disabled. Skipping ruleset creation.")
        return

    plan = read_plan()

    github_account = os.environ["GITHUB_ACCOUNT"]
    migration_dir = Path(os.environ["MIGRATION_DIR"])

    result_file = migration_dir / "branch-rulesets-result.csv"
    results = []

    for project in plan["projects"]:
        github_repo = project["github_repo"]
        github_repo_full = f"{github_account}/{github_repo}"
        default_branch = project["default_branch"]

        ruleset_name = f"protect-{default_branch}"

        log(f"Applying branch ruleset to: {github_repo_full}")

        payload = build_ruleset_payload(github_repo, default_branch)

        if dry_run:
            status = "dry_run"
            log(f"DRY RUN: Would create ruleset {ruleset_name}")
        else:
            try:
                github_request(
                    "POST",
                    f"/repos/{github_repo_full}/rulesets",
                    payload,
                    expected_status=(201, 200, 422),
                )

                status = "created_or_already_exists"
                log(f"Ruleset ready: {ruleset_name} on {github_repo_full}")
            except Exception as exc:
                status = "failed"
                log(f"Failed to create ruleset on {github_repo_full}: {exc}")

        results.append(
            {
                "github_repo_full": github_repo_full,
                "ruleset_name": ruleset_name,
                "branch": default_branch,
                "enforcement": "active",
                "status": status,
            }
        )

    with open(result_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    log(f"Branch ruleset migration complete: {result_file}")


if __name__ == "__main__":
    main()