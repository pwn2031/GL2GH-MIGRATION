#!/usr/bin/env python3

"""Step 6: Convert GitLab CI pipelines to GitHub Actions workflows."""

import csv
import os
import shutil
import subprocess
from pathlib import Path

import yaml

from scripts.lib.github_client import run_git, run_gh
from scripts.lib.logging_utils import log

RUNNER_TAG_MAP = {
    "poc-runner": "ubuntu-latest",
    "docker": "ubuntu-latest",
    "shell": "ubuntu-latest",
    "ec2": "ec2",
    "linux": "ec2",
}

RESULT_FIELDS = [
    "gitlab_project",
    "github_repo_full",
    "gitlab_ci_file",
    "github_workflow_file",
    "converted_jobs",
    "status",
]


def read_plan():
    plan_file = Path(os.environ["MIGRATION_DIR"]) / "migration-plan.json"

    import json

    with open(plan_file, encoding="utf-8") as f:
        return json.load(f)


def clone_repository(gitlab_project, github_repo, clone_dir):
    github_account = os.environ["GITHUB_ACCOUNT"]
    github_token = os.environ["GITHUB_TOKEN"]
    gitlab_token = os.environ["GITLAB_TOKEN"]
    gitlab_url = os.environ["GITLAB_URL"].replace("https://", "")

    github_repo_full = f"{github_account}/{github_repo}"

    if clone_dir.exists():
        shutil.rmtree(clone_dir)

    gitlab_url_authenticated = (
        f"https://oauth2:{gitlab_token}@{gitlab_url}/{gitlab_project}.git"
    )

    github_url_authenticated = (
        f"https://x-access-token:{github_token}@github.com/"
        f"{github_repo_full}.git"
    )

    run_git(
        [
            "clone",
            gitlab_url_authenticated,
            str(clone_dir),
        ]
    )

    run_git(
        [
            "remote",
            "add",
            "github",
            github_url_authenticated,
        ],
        cwd=clone_dir,
    )

    run_git(
        ["fetch", "github"],
        cwd=clone_dir,
    )

    run_git(
        ["checkout", "-B", "main", "github/main"],
        cwd=clone_dir,
    )

    return github_repo_full


def convert_gitlab_ci(gitlab_ci_file):
    with open(gitlab_ci_file, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    ignored = {
        "stages",
        "variables",
        "default",
        "include",
        "workflow",
        "before_script",
        "after_script",
    }

    jobs = {
        key: value
        for key, value in config.items()
        if key not in ignored
        and isinstance(value, dict)
        and "script" in value
    }

    workflow_jobs = {}
    previous_job = None

    for job_name, job in jobs.items():
        tags = job.get("tags", [])
        runner = RUNNER_TAG_MAP.get(tags[0], "ubuntu-latest") if tags else "ubuntu-latest"

        steps = [
            {
                "name": "Checkout repository",
                "uses": "actions/checkout@v4",
            }
        ]

        if previous_job:
            steps.append(
                {
                    "name": "Download build artifact",
                    "uses": "actions/download-artifact@v4",
                    "with": {
                        "name": "migrated-build-artifact",
                        "path": "build",
                    },
                }
            )

        scripts = job.get("script", [])

        if scripts:
            steps.append(
                {
                    "name": "Run migrated GitLab CI script",
                    "run": "\n".join(scripts),
                }
            )

        artifacts = job.get("artifacts", {}).get("paths", [])

        if artifacts:
            steps.append(
                {
                    "name": "Upload build artifact",
                    "uses": "actions/upload-artifact@v4",
                    "with": {
                        "name": "migrated-build-artifact",
                        "path": "\n".join(artifacts),
                    },
                }
            )

        github_job = {
            "name": job_name.replace("_", " ").title(),
            "runs-on": runner,
            "steps": steps,
        }

        if previous_job:
            github_job["needs"] = previous_job

        if job.get("when") == "manual":
            github_job["environment"] = "production"

        workflow_jobs[job_name] = github_job
        previous_job = job_name

    workflow = {
        "name": "Migrated GitLab CI/CD Pipeline",
        "on": {
            "push": {
                "branches": ["main"]
            },
            "pull_request": {
                "branches": ["main"]
            },
            "workflow_dispatch": {},
        },
        "jobs": workflow_jobs,
    }

    return workflow, list(jobs.keys())


def write_workflow(workflow, output_file):
    output_file.parent.mkdir(parents=True, exist_ok=True)

    class Dumper(yaml.SafeDumper):
        pass

    def represent_str(dumper, data):
        if "\n" in data:
            return dumper.represent_scalar(
                "tag:yaml.org,2002:str",
                data,
                style="|",
            )

        return dumper.represent_scalar(
            "tag:yaml.org,2002:str",
            data,
        )

    Dumper.add_representer(str, represent_str)

    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(
            workflow,
            f,
            Dumper=Dumper,
            sort_keys=False,
            default_flow_style=False,
        )


def main():
    dry_run = os.environ["DRY_RUN"].lower() == "true"

    plan = read_plan()

    working_clones_dir = Path(os.environ["WORKING_CLONES_DIR"])
    migration_dir = Path(os.environ["MIGRATION_DIR"])

    result_file = migration_dir / "cicd-result.csv"
    results = []

    for project in plan["projects"]:
        gitlab_project = project["gitlab_project"]
        github_repo = project["github_repo"]

        clone_dir = working_clones_dir / github_repo

        log(f"Converting CI/CD for: {gitlab_project}")

        if dry_run:
            results.append(
                {
                    "gitlab_project": gitlab_project,
                    "github_repo_full": f"{os.environ['GITHUB_ACCOUNT']}/{github_repo}",
                    "gitlab_ci_file": str(clone_dir / ".gitlab-ci.yml"),
                    "github_workflow_file": str(
                        clone_dir / ".github/workflows/ci.yml"
                    ),
                    "converted_jobs": 0,
                    "status": "dry_run",
                }
            )
            continue

        github_repo_full = clone_repository(
            gitlab_project,
            github_repo,
            clone_dir,
        )

        gitlab_ci_file = clone_dir / ".gitlab-ci.yml"

        if not gitlab_ci_file.exists():
            log(f"No GitLab CI file found: {gitlab_ci_file}")

            results.append(
                {
                    "gitlab_project": gitlab_project,
                    "github_repo_full": github_repo_full,
                    "gitlab_ci_file": str(gitlab_ci_file),
                    "github_workflow_file": "",
                    "converted_jobs": 0,
                    "status": "no_gitlab_ci_file",
                }
            )
            continue

        workflow, converted_jobs = convert_gitlab_ci(gitlab_ci_file)

        workflow_file = clone_dir / ".github/workflows/ci.yml"
        write_workflow(workflow, workflow_file)

        run_git(
            ["add", ".github/workflows/ci.yml"],
            cwd=clone_dir,
        )

        run_git(
            [
                "commit",
                "-m",
                "Add GitHub Actions workflow migrated from GitLab CI",
            ],
            cwd=clone_dir,
        )

        run_git(
            ["push", "github", "main"],
            cwd=clone_dir,
        )

        log(f"Pushed GitHub Actions workflow: {workflow_file}")

        results.append(
            {
                "gitlab_project": gitlab_project,
                "github_repo_full": github_repo_full,
                "gitlab_ci_file": str(gitlab_ci_file),
                "github_workflow_file": str(workflow_file),
                "converted_jobs": len(converted_jobs),
                "status": "success",
            }
        )

    with open(result_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    log(f"CI/CD conversion complete: {result_file}")


if __name__ == "__main__":
    main()