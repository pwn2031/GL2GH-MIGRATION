#!/usr/bin/env python3

"""Step 2: Mirror GitLab repositories with complete Git history to GitHub."""

import csv
import os
import shutil
import subprocess
from pathlib import Path

from scripts.lib.logging_utils import log
from scripts.lib.validators import validate_repository_name

RESULT_FIELDS = [
    "gitlab_project",
    "github_repo_full",
    "mirror_path",
    "branches",
    "tags",
    "status",
]


def read_plan():
    plan_file = Path(os.environ["MIGRATION_DIR"]) / "migration-plan.json"

    with open(plan_file, encoding="utf-8") as f:
        import json

        return json.load(f)


def run(command, cwd=None):
    log(f"Running: {' '.join(command)}")

    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(command)}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    return result


def count_refs(mirror_path, ref_type):
    result = run(
        ["git", "for-each-ref", f"refs/{ref_type}", "--format=%(refname)"],
        cwd=mirror_path,
    )

    return len([line for line in result.stdout.splitlines() if line.strip()])


def main():
    dry_run = os.environ["DRY_RUN"].lower() == "true"

    plan = read_plan()

    github_token = os.environ["GITHUB_TOKEN"]
    github_account = os.environ["GITHUB_ACCOUNT"]

    gitlab_token = os.environ["GITLAB_TOKEN"]
    gitlab_url = os.environ["GITLAB_URL"].replace("https://", "")

    working_clones_dir = Path(os.environ["WORKING_CLONES_DIR"])
    working_clones_dir.mkdir(parents=True, exist_ok=True)

    result_file = Path(os.environ["MIGRATION_DIR"]) / "repository-migration-result.csv"

    results = []

    for project in plan["projects"]:
        gitlab_project = project["gitlab_project"]
        github_repo = project["github_repo"]
        github_repo_full = f"{github_account}/{github_repo}"

        validate_repository_name(github_repo)

        mirror_path = working_clones_dir / f"{github_repo}.git"

        log(f"Processing repository: {gitlab_project} → {github_repo_full}")

        if dry_run:
            results.append(
                {
                    "gitlab_project": gitlab_project,
                    "github_repo_full": github_repo_full,
                    "mirror_path": str(mirror_path),
                    "branches": 0,
                    "tags": 0,
                    "status": "dry_run",
                }
            )
            continue

        if mirror_path.exists():
            shutil.rmtree(mirror_path)

        gitlab_authenticated_url = (
            f"https://oauth2:{gitlab_token}@{gitlab_url}/{gitlab_project}.git"
        )

        github_authenticated_url = (
            f"https://x-access-token:{github_token}@github.com/"
            f"{github_repo_full}.git"
        )

        run(
            [
                "git",
                "clone",
                "--mirror",
                gitlab_authenticated_url,
                str(mirror_path),
            ]
        )

        run(
            [
                "git",
                "remote",
                "add",
                "github",
                github_authenticated_url,
            ],
            cwd=mirror_path,
        )

        run(
            ["git", "push", "--mirror", "github"],
            cwd=mirror_path,
        )

        branches = count_refs(mirror_path, "heads")
        tags = count_refs(mirror_path, "tags")

        log(
            f"Migration complete: {github_repo_full} "
            f"({branches} branches, {tags} tags)"
        )

        results.append(
            {
                "gitlab_project": gitlab_project,
                "github_repo_full": github_repo_full,
                "mirror_path": str(mirror_path),
                "branches": branches,
                "tags": tags,
                "status": "success",
            }
        )

    with open(result_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    log(f"Repository migration complete: {result_file}")


if __name__ == "__main__":
    main()