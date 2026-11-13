#!/usr/bin/env python3

"""Step 8: Validate GitHub-hosted runners and prepare EC2 runner setup."""

import csv
import os
from pathlib import Path

from scripts.lib.github_client import (
    create_runner_registration_token,
    github_request,
)
from scripts.lib.logging_utils import log, write_json

RESULT_FIELDS = [
    "github_repo_full",
    "runner_type",
    "runner_label",
    "status",
    "details",
]


def read_plan():
    plan_file = Path(os.environ["MIGRATION_DIR"]) / "migration-plan.json"

    import json

    with open(plan_file, encoding="utf-8") as f:
        return json.load(f)


def main():
    dry_run = os.environ["DRY_RUN"].lower() == "true"

    plan = read_plan()

    github_account = os.environ["GITHUB_ACCOUNT"]
    migration_dir = Path(os.environ["MIGRATION_DIR"])

    hosted_runner = os.environ["GITHUB_HOSTED_RUNNER"]
    ec2_label = os.environ["EC2_RUNNER_LABEL"]

    result_file = migration_dir / "runner-validation.csv"
    setup_file = migration_dir / "runner-setup.json"

    results = []

    for project in plan["projects"]:
        github_repo = project["github_repo"]
        github_repo_full = f"{github_account}/{github_repo}"

        log(f"Validating runners for: {github_repo_full}")

        results.append(
            {
                "github_repo_full": github_repo_full,
                "runner_type": "github_hosted",
                "runner_label": hosted_runner,
                "status": "available",
                "details": "GitHub-hosted runner label configured",
            }
        )

        if dry_run:
            results.append(
                {
                    "github_repo_full": github_repo_full,
                    "runner_type": "ec2_self_hosted",
                    "runner_label": ec2_label,
                    "status": "dry_run",
                    "details": "EC2 runner registration skipped in dry-run",
                }
            )
            continue

        try:
            token_response = create_runner_registration_token(
                github_account,
                github_repo,
            )

            registration_token = token_response["token"]

            log(
                "EC2 runner registration token generated. "
                "Token is short-lived and must not be stored."
            )

            runner_status = "registration_token_generated"
            details = (
                "Use this token on the EC2 instance to register a runner "
                "with label: " + ec2_label
            )

        except Exception as exc:
            registration_token = None
            runner_status = "failed"
            details = str(exc)

            log(f"Runner registration token generation failed: {exc}")

        results.append(
            {
                "github_repo_full": github_repo_full,
                "runner_type": "ec2_self_hosted",
                "runner_label": ec2_label,
                "status": runner_status,
                "details": details,
            }
        )

        try:
            runners = github_request(
                "GET",
                f"/repos/{github_repo_full}/actions/runners",
            )

            online_runners = [
                runner
                for runner in runners.get("runners", [])
                if runner.get("status") == "online"
            ]

            log(f"Online self-hosted runners: {len(online_runners)}")

        except Exception as exc:
            log(f"Unable to list runners: {exc}")

    with open(result_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    setup = {
        "github_hosted_runner": hosted_runner,
        "ec2_runner_label": ec2_label,
        "ec2_setup_commands": [
            "sudo dnf update -y",
            "sudo dnf install -y git curl tar jq",
            "mkdir ~/actions-runner && cd ~/actions-runner",
            "curl -s https://api.github.com/repos/actions/runner/releases/latest | jq -r '.assets[].browser_download_url' | grep 'linux-x64-.*\\.tar\\.gz$' | head -n 1",
            "./config.sh --url https://github.com/<owner>/<repo> --token <REGISTRATION_TOKEN> --labels ec2",
            "./run.sh",
        ],
        "security_notes": [
            "Do not store the runner registration token.",
            "Do not store GitHub tokens on the EC2 instance.",
            "Allow SSH only from trusted administrator IPs.",
            "Use a dedicated EC2 instance or autoscaling group for runners.",
        ],
    }

    write_json(setup_file, setup)

    log(f"Runner validation complete: {result_file}")
    log(f"EC2 runner setup guide created: {setup_file}")


if __name__ == "__main__":
    main()