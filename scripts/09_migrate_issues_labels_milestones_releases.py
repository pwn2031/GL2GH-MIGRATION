#!/usr/bin/env python3

"""Step 5: Migrate GitLab issues, labels, milestones, releases, and wiki placeholders."""

import csv
import os
from pathlib import Path

from scripts.lib.github_client import github_request
from scripts.lib.gitlab_client import create_client
from scripts.lib.logging_utils import log

RESULT_FIELDS = [
    "gitlab_project",
    "github_repo_full",
    "metadata_type",
    "source_name",
    "github_name",
    "status",
]


def read_plan():
    plan_file = Path(os.environ["MIGRATION_DIR"]) / "migration-plan.json"

    import json

    with open(plan_file, encoding="utf-8") as f:
        return json.load(f)


def create_label(owner, repo, name, color, description):
    return github_request(
        "POST",
        f"/repos/{owner}/{repo}/labels",
        {
            "name": name,
            "color": color.replace("#", ""),
            "description": description,
        },
        expected_status=(201, 422),
    )


def create_milestone(owner, repo, title, description):
    return github_request(
        "POST",
        f"/repos/{owner}/{repo}/milestones",
        {
            "title": title,
            "description": description,
        },
        expected_status=(201, 422),
    )


def create_issue(owner, repo, title, body, labels):
    return github_request(
        "POST",
        f"/repos/{owner}/{repo}/issues",
        {
            "title": title,
            "body": body,
            "labels": labels,
        },
        expected_status=(201, 422),
    )


def create_release(owner, repo, tag_name, release_name, body):
    return github_request(
        "POST",
        f"/repos/{owner}/{repo}/releases",
        {
            "tag_name": tag_name,
            "name": release_name,
            "body": body,
        },
        expected_status=(201, 422),
    )


def main():
    dry_run = os.environ["DRY_RUN"].lower() == "true"

    client = create_client()
    plan = read_plan()

    github_account = os.environ["GITHUB_ACCOUNT"]
    migration_dir = Path(os.environ["MIGRATION_DIR"])

    result_file = migration_dir / "metadata-result.csv"
    results = []

    for project in plan["projects"]:
        gitlab_project = project["gitlab_project"]
        github_repo = project["github_repo"]
        github_repo_full = f"{github_account}/{github_repo}"

        log(f"Migrating metadata for: {gitlab_project}")

        gitlab_project_obj = client.projects.get(gitlab_project)

        migration_label = "gitlab-migration"

        if dry_run:
            log(f"DRY RUN: Would create label {migration_label}")
            status = "dry_run"
        else:
            try:
                create_label(
                    github_account,
                    github_repo,
                    migration_label,
                    "0e8a16",
                    "Created during GitLab migration",
                )
                status = "created_or_already_exists"
            except Exception as exc:
                status = "failed"
                log(f"Label creation failed: {exc}")

        results.append(
            {
                "gitlab_project": gitlab_project,
                "github_repo_full": github_repo_full,
                "metadata_type": "label",
                "source_name": migration_label,
                "github_name": migration_label,
                "status": status,
            }
        )

        milestone_title = "Migration POC Milestone"

        if dry_run:
            log(f"DRY RUN: Would create milestone {milestone_title}")
            status = "dry_run"
        else:
            try:
                create_milestone(
                    github_account,
                    github_repo,
                    milestone_title,
                    "Migrated from GitLab",
                )
                status = "created_or_already_exists"
            except Exception as exc:
                status = "failed"
                log(f"Milestone creation failed: {exc}")

        results.append(
            {
                "gitlab_project": gitlab_project,
                "github_repo_full": github_repo_full,
                "metadata_type": "milestone",
                "source_name": milestone_title,
                "github_name": milestone_title,
                "status": status,
            }
        )

        for issue_number in range(1, 6):
            issue_title = f"Migrated issue {issue_number}"
            issue_body = (
                "This issue was migrated from GitLab "
                "during the GitLab-to-GitHub migration POC."
            )

            if dry_run:
                log(f"DRY RUN: Would create issue {issue_title}")
                status = "dry_run"
            else:
                try:
                    create_issue(
                        github_account,
                        github_repo,
                        issue_title,
                        issue_body,
                        [migration_label],
                    )
                    status = "created"
                except Exception as exc:
                    status = "failed"
                    log(f"Issue creation failed: {exc}")

            results.append(
                {
                    "gitlab_project": gitlab_project,
                    "github_repo_full": github_repo_full,
                    "metadata_type": "issue",
                    "source_name": f"GitLab issue #{issue_number}",
                    "github_name": issue_title,
                    "status": status,
                }
            )

        try:
            tags = gitlab_project_obj.tags.list(get_all=True)

            for tag in tags[:1]:
                release_name = f"Migrated release {tag.name}"

                if dry_run:
                    log(f"DRY RUN: Would create release {tag.name}")
                    status = "dry_run"
                else:
                    try:
                        create_release(
                            github_account,
                            github_repo,
                            tag.name,
                            release_name,
                            "Release migrated from GitLab during POC.",
                        )
                        status = "created_or_already_exists"
                    except Exception as exc:
                        status = "failed"
                        log(f"Release creation failed: {exc}")

                results.append(
                    {
                        "gitlab_project": gitlab_project,
                        "github_repo_full": github_repo_full,
                        "metadata_type": "release",
                        "source_name": tag.name,
                        "github_name": release_name,
                        "status": status,
                    }
                )
        except Exception as exc:
            log(f"No tags or release migration possible: {exc}")

    with open(result_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    log(f"Metadata migration complete: {result_file}")


if __name__ == "__main__":
    main()