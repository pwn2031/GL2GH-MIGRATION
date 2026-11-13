#!/usr/bin/env python3

"""Step 10: Migrate GitLab merge requests to GitHub pull requests.

Migration rules:
- GitLab opened MR -> GitHub open PR
- GitLab merged MR -> GitHub closed PR
- GitLab closed MR -> GitHub closed PR
- No historical GitHub issue is created
- Missing source branches are recreated when a head commit SHA is available
- Duplicate PR creation is avoided on reruns
"""

import csv
import json
import os
from pathlib import Path
from urllib.parse import quote

from scripts.lib.github_client import github_request
from scripts.lib.gitlab_client import create_client
from scripts.lib.logging_utils import log

RESULT_FIELDS = [
    "gitlab_project",
    "gitlab_mr_iid",
    "github_repo_full",
    "github_pr_number",
    "gitlab_state",
    "github_state",
    "source_branch",
    "target_branch",
    "title",
    "status",
    "error",
]

STATE_MAP = {
    "opened": "open",
    "updated": "open",
    "locked": "open",
    "merged": "closed",
    "closed": "closed",
}


def read_plan():
    plan_file = Path(os.environ["MIGRATION_DIR"]) / "migration-plan.json"

    with open(plan_file, encoding="utf-8") as f:
        return json.load(f)


def get_existing_pr(owner, repo, head, base):
    """Return an existing GitHub PR for the same head/base pair, if present."""

    query = (
        f"head={quote(f'{owner}:{head}', safe=':')}"
        f"&base={quote(base, safe='')}"
        f"&state=all"
        f"&per_page=100"
    )

    response = github_request(
        "GET",
        f"/repos/{owner}/{repo}/pulls?{query}",
    )

    if isinstance(response, list) and response:
        return response[0]

    return None


def branch_exists(owner, repo, branch):
    """Check whether a branch exists in the GitHub repository."""

    try:
        github_request(
            "GET",
            f"/repos/{owner}/{repo}/branches/{quote(branch, safe='')}",
        )
        return True
    except Exception:
        return False


def get_mr_head_sha(mr):
    """Return the best available head commit SHA for a GitLab MR."""

    diff_refs = getattr(mr, "diff_refs", None)

    if diff_refs and getattr(diff_refs, "head_sha", None):
        return diff_refs.head_sha

    return getattr(mr, "sha", None)


def recreate_source_branch(owner, repo, branch, head_sha):
    """Recreate a missing GitHub branch and add an empty migration marker commit.

    GitHub cannot create a pull request when the head branch has no commits
    that are not already present in the base branch. For an already-merged
    GitLab MR, we recreate the source branch and add an empty commit so that
    GitHub can create a historical closed PR.
    """

    log(
        f"Source branch {branch} is missing. "
        f"Recreating it from commit {head_sha}"
    )

    github_request(
        "POST",
        f"/repos/{owner}/{repo}/git/refs",
        {
            "ref": f"refs/heads/{branch}",
            "sha": head_sha,
        },
        expected_status=(201, 422),
    )

    head_commit = github_request(
        "GET",
        f"/repos/{owner}/{repo}/git/commits/{head_sha}",
    )

    tree_sha = head_commit["tree"]["sha"]

    marker_commit = github_request(
        "POST",
        f"/repos/{owner}/{repo}/git/commits",
        {
            "message": (
                "Migration marker: preserve historical GitLab merge request\n\n"
                "This empty commit allows GitHub to create a historical "
                "pull request for a GitLab merge request that was already "
                "merged before migration."
            ),
            "tree": tree_sha,
            "parents": [head_sha],
        },
        expected_status=(201,),
    )

    marker_sha = marker_commit["sha"]

    github_request(
        "PATCH",
        f"/repos/{owner}/{repo}/git/refs/heads/{quote(branch, safe='')}",
        {
            "sha": marker_sha,
            "force": True,
        },
        expected_status=(200,),
    )

    log(
        f"Added empty migration marker commit {marker_sha} "
        f"to recreated branch {branch}"
    )


def build_pr_body(mr):
    """Build a GitHub PR body that preserves important GitLab MR metadata."""

    lines = [
        mr.description or "",
        "",
        "---",
        "",
        f"**Migrated from GitLab merge request !{mr.iid}**",
        f"**GitLab MR state:** `{mr.state}`",
        f"**Source branch:** `{mr.source_branch}`",
        f"**Target branch:** `{mr.target_branch}`",
        f"**Created at:** `{mr.created_at}`",
        f"**Updated at:** `{mr.updated_at}`",
    ]

    if getattr(mr, "merged_at", None):
        lines.append(f"**Merged in GitLab at:** `{mr.merged_at}`")

    if getattr(mr, "closed_at", None):
        lines.append(f"**Closed in GitLab at:** `{mr.closed_at}`")

    if getattr(mr, "web_url", None):
        lines.append("")
        lines.append(f"**Original GitLab MR:** {mr.web_url}")

    if mr.state == "merged":
        lines.append("")
        lines.append(
            "> This pull request was migrated from a GitLab merge request "
            "that was already merged before migration. It is intentionally "
            "closed in GitHub and is not marked as merged."
        )

    return "\n".join(lines).strip()


def create_pull_request(owner, repo, mr):
    """Create a GitHub pull request from a GitLab merge request."""

    payload = {
        "title": mr.title,
        "head": mr.source_branch,
        "base": mr.target_branch,
        "body": build_pr_body(mr),
        "maintainer_can_modify": True,
    }

    return github_request(
        "POST",
        f"/repos/{owner}/{repo}/pulls",
        payload,
        expected_status=(201, 422),
    )


def migrate_mr_labels(owner, repo, pr_number, mr):
    """Apply GitLab MR labels to the GitHub pull request."""

    labels = []

    for label in mr.labels or []:
        if isinstance(label, dict):
            name = label.get("name")
        else:
            name = label

        if name:
            labels.append(name)

    if not labels:
        return

    github_request(
        "POST",
        f"/repos/{owner}/{repo}/issues/{pr_number}/labels",
        {"labels": labels},
        expected_status=(200, 201),
    )


def migrate_mr_comments(owner, repo, pr_number, mr):
    """Migrate GitLab MR notes/discussions as GitHub PR comments."""

    notes = mr.notes.list(
        get_all=True,
        sort="asc",
        order_by="created_at",
    )

    for note in notes:
        if note.system:
            continue

        author = note.author

        if isinstance(author, dict):
            author_username = author.get("username", "unknown")
        else:
            author_username = getattr(author, "username", "unknown")

        body = (
            "**Migrated GitLab MR comment**\n\n"
            f"**Original author:** `{author_username}`\n\n"
            f"**Original created at:** `{note.created_at}`\n\n"
            "---\n\n"
            f"{note.body}"
        )

        github_request(
            "POST",
            f"/repos/{owner}/{repo}/issues/{pr_number}/comments",
            {"body": body},
            expected_status=(201,),
        )


def close_pull_request(owner, repo, pr_number):
    """Close a GitHub pull request without merging it."""

    github_request(
        "PATCH",
        f"/repos/{owner}/{repo}/pulls/{pr_number}",
        {"state": "closed"},
        expected_status=(200,),
    )


def append_result(
    results,
    project,
    mr,
    github_repo_full,
    pr_number,
    status,
    error="",
):
    results.append(
        {
            "gitlab_project": project["gitlab_project"],
            "gitlab_mr_iid": mr.iid if mr else "",
            "github_repo_full": github_repo_full,
            "github_pr_number": pr_number or "",
            "gitlab_state": mr.state if mr else "",
            "github_state": STATE_MAP.get(mr.state, "unknown") if mr else "",
            "source_branch": mr.source_branch if mr else "",
            "target_branch": mr.target_branch if mr else "",
            "title": mr.title if mr else "",
            "status": status,
            "error": error,
        }
    )


def main():
    dry_run = os.environ["DRY_RUN"].lower() == "true"

    client = create_client()
    plan = read_plan()

    github_account = os.environ["GITHUB_ACCOUNT"]
    migration_dir = Path(os.environ["MIGRATION_DIR"])

    result_file = migration_dir / "merge-request-migration-result.csv"
    results = []

    for project in plan["projects"]:
        gitlab_project = project["gitlab_project"]
        github_repo = project["github_repo"]
        owner = github_account
        github_repo_full = f"{owner}/{github_repo}"

        log(
            f"Migrating merge requests for: "
            f"{gitlab_project} → {github_repo_full}"
        )

        try:
            gitlab_project_obj = client.projects.get(gitlab_project)
        except Exception as exc:
            log(f"Could not access GitLab project {gitlab_project}: {exc}")
            continue

        merge_requests = gitlab_project_obj.mergerequests.list(
            get_all=True,
            order_by="created_at",
            sort="asc",
        )

        log(f"Found {len(merge_requests)} GitLab merge requests")

        for mr in merge_requests:
            log(
                f"Processing MR !{mr.iid}: {mr.title} "
                f"({mr.state}) {mr.source_branch} → {mr.target_branch}"
            )

            if dry_run:
                append_result(
                    results,
                    project,
                    mr,
                    github_repo_full,
                    "",
                    "dry_run",
                )
                continue

            try:
                existing_pr = get_existing_pr(
                    owner,
                    github_repo,
                    mr.source_branch,
                    mr.target_branch,
                )

                if existing_pr:
                    pr_number = existing_pr["number"]
                    log(
                        f"PR already exists for MR !{mr.iid}: "
                        f"GitHub PR #{pr_number}"
                    )

                    if mr.state in ("merged", "closed"):
                        close_pull_request(owner, github_repo, pr_number)

                    append_result(
                        results,
                        project,
                        mr,
                        github_repo_full,
                        pr_number,
                        "already_exists",
                    )
                    continue

                source_branch_exists = branch_exists(
                    owner,
                    github_repo,
                    mr.source_branch,
                )

                if not source_branch_exists:
                    head_sha = get_mr_head_sha(mr)

                    if not head_sha:
                        raise RuntimeError(
                            f"Source branch {mr.source_branch} is missing and "
                            "no head SHA is available to recreate it"
                        )

                    recreate_source_branch(
                        owner,
                        github_repo,
                        mr.source_branch,
                        head_sha,
                    )

                pr_response = create_pull_request(owner, github_repo, mr)

                if not (
                    isinstance(pr_response, dict)
                    and "number" in pr_response
                ):
                    raise RuntimeError(
                        "GitHub did not return a valid pull request response"
                    )

                pr_number = pr_response["number"]

                log(
                    f"Created GitHub PR #{pr_number} "
                    f"for GitLab MR !{mr.iid}"
                )

                migrate_mr_labels(
                    owner,
                    github_repo,
                    pr_number,
                    mr,
                )

                migrate_mr_comments(
                    owner,
                    github_repo,
                    pr_number,
                    mr,
                )

                if mr.state in ("merged", "closed"):
                    close_pull_request(owner, github_repo, pr_number)

                    log(
                        f"GitLab MR !{mr.iid} was {mr.state}. "
                        f"Created GitHub PR #{pr_number} as closed."
                    )

                append_result(
                    results,
                    project,
                    mr,
                    github_repo_full,
                    pr_number,
                    "migrated",
                )

            except Exception as exc:
                log(f"MR migration failed for !{mr.iid}: {exc}")

                append_result(
                    results,
                    project,
                    mr,
                    github_repo_full,
                    "",
                    "failed",
                    str(exc),
                )

    with open(result_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    log(f"Merge request migration complete: {result_file}")


if __name__ == "__main__":
    main()