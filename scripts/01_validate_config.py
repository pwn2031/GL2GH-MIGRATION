#!/usr/bin/env python3

"""Step 0: Validate migration configuration and access."""

import os
import shutil
from pathlib import Path

from scripts.lib.github_client import get_authenticated_user, github_request
from scripts.lib.gitlab_client import create_client, get_group
from scripts.lib.logging_utils import ensure_dir, log, write_json
from scripts.lib.validators import validate_environment, validate_identity_mapping

REQUIRED_ENV = [
    "GITLAB_URL",
    "GITLAB_TOKEN",
    "GITLAB_GROUP",
    "GITHUB_ACCOUNT",
    "GITHUB_TOKEN",
    "GITHUB_TARGET_MODE",
    "IDENTITY_MAPPING_FILE",
    "WORKSPACE_DIR",
    "INPUTS_DIR",
    "INVENTORY_DIR",
    "MIGRATION_DIR",
    "REPORTS_DIR",
    "LOG_DIR",
    "WORKING_CLONES_DIR",
    "DRY_RUN",
    "AUTO_APPROVE",
    "GITHUB_USER",
    "GITHUB_ORG",
    "FAIL_FAST",
    "UNMAPPED_USER_POLICY",
    "GITHUB_HOSTED_RUNNER",
    "EC2_RUNNER_LABEL",
]


def validate_tools():
    tools = {}

    for tool in ["git", "gh", "python3"]:
        tools[tool] = shutil.which(tool) is not None

        if not tools[tool]:
            raise RuntimeError(f"Required tool not found: {tool}")

    return tools


def validate_gitlab():
    client = create_client()
    group = get_group(client, os.environ["GITLAB_GROUP"])

    return {
        "authenticated_user": client.user.username,
        "gitlab_group": group.full_path,
        "gitlab_group_id": group.id,
    }


def validate_github():
    user = get_authenticated_user()

    expected_user = os.environ.get("GITHUB_USER", "")
    actual_user = user["login"]

    if expected_user and actual_user.lower() != expected_user.lower():
        raise RuntimeError(
            f"GitHub user mismatch: expected {expected_user}, "
            f"but token belongs to {actual_user}"
        )

    github_org = os.environ.get("GITHUB_ORG", "")

    org_status = {
        "authenticated_user": actual_user,
        "expected_user": expected_user,
        "organization": github_org,
        "organization_access": "not_checked",
    }

    if github_org:
        try:
            org = github_request("GET", f"/orgs/{github_org}")
            org_status["organization_access"] = "verified"
            org_status["organization_login"] = org["login"]
        except Exception as exc:
            raise RuntimeError(
                f"GitHub token cannot access organization "
                f"{github_org}: {exc}"
            )

    return org_status


def validate_paths():
    paths = {}

    for key in [
        "WORKSPACE_DIR",
        "INPUTS_DIR",
        "INVENTORY_DIR",
        "MIGRATION_DIR",
        "REPORTS_DIR",
        "LOG_DIR",
        "WORKING_CLONES_DIR",
    ]:
        path = ensure_dir(os.environ[key])
        paths[key] = str(path)

    return paths


def validate_migration_controls():
    dry_run = os.environ["DRY_RUN"].lower()
    auto_approve = os.environ["AUTO_APPROVE"].lower()
    fail_fast = os.environ["FAIL_FAST"].lower()
    unmapped_policy = os.environ["UNMAPPED_USER_POLICY"].lower()

    if dry_run not in ("true", "false"):
        raise ValueError("DRY_RUN must be true or false")

    if auto_approve not in ("true", "false"):
        raise ValueError("AUTO_APPROVE must be true or false")

    if fail_fast not in ("true", "false"):
        raise ValueError("FAIL_FAST must be true or false")

    if unmapped_policy not in ("fail", "skip", "prompt"):
        raise ValueError(
            "UNMAPPED_USER_POLICY must be fail, skip, or prompt"
        )

    if dry_run == "false" and auto_approve == "false":
        log(
            "WARNING: DRY_RUN=false and AUTO_APPROVE=false; "
            "migration will pause for manual approval."
        )

    return {
        "dry_run": dry_run == "true",
        "auto_approve": auto_approve == "true",
        "fail_fast": fail_fast == "true",
        "unmapped_user_policy": unmapped_policy,
    }


def main():
    log("Validating migration configuration...")

    validate_environment(REQUIRED_ENV)

    tools = validate_tools()
    gitlab_status = validate_gitlab()
    github_status = validate_github()
    paths = validate_paths()
    controls = validate_migration_controls()

    identity_mapping = validate_identity_mapping(
        os.environ["IDENTITY_MAPPING_FILE"]
    )

    report = {
        "status": "passed",
        "tools": tools,
        "gitlab": gitlab_status,
        "github": github_status,
        "paths": paths,
        "migration_controls": controls,
        "identity_mapping": {
            "file": os.environ["IDENTITY_MAPPING_FILE"],
            "total_users": len(identity_mapping),
            "included_users": sum(
                1 for user in identity_mapping.values() if user["include"]
            ),
            "excluded_users": sum(
                1 for user in identity_mapping.values() if not user["include"]
            ),
        },
    }

    output_file = Path(os.environ["REPORTS_DIR"]) / "00-config-validation.json"
    write_json(output_file, report)

    log(f"Configuration validation passed: {output_file}")


if __name__ == "__main__":
    main()