#!/usr/bin/env python3

"""Automatically convert the GitLab group tree into GitHub teams."""

import csv
import os
from pathlib import Path

from scripts.lib.csv_utils import write_csv
from scripts.lib.github_client import github_request
from scripts.lib.gitlab_client import create_client
from scripts.lib.logging_utils import log, write_json
from scripts.lib.validators import (
    gitlab_role_name,
    validate_identity_mapping,
)

TEAM_FIELDS = [
    "gitlab_group_id",
    "gitlab_group_name",
    "gitlab_group_path",
    "gitlab_parent_group_path",
    "github_org",
    "github_team_name",
    "github_team_slug",
    "member_count",
    "status",
]

MEMBER_FIELDS = [
    "gitlab_group_path",
    "gitlab_username",
    "gitlab_email",
    "gitlab_role",
    "access_level",
    "github_username",
    "github_team_slug",
    "mapping_status",
]


def slugify(value):
    slug = value.strip().lower()

    replacements = {
        " ": "-",
        "_": "-",
        "/": "-",
    }

    for old, new in replacements.items():
        slug = slug.replace(old, new)

    slug = "".join(
        character
        for character in slug
        if character.isalnum() or character == "-"
    )

    while "--" in slug:
        slug = slug.replace("--", "-")

    return slug.strip("-")


def collect_group_tree(client, root_group):
    groups = []

    def walk(group, parent_path=None):
        groups.append(
            {
                "id": group.id,
                "name": group.name,
                "full_path": group.full_path,
                "parent_group_path": parent_path,
            }
        )

        try:
            subgroups = group.subgroups.list(
                get_all=True,
                include_subgroups=True,
            )
        except Exception as exc:
            log(
                f"Unable to list subgroups for {group.full_path}: {exc}"
            )
            subgroups = []

        for subgroup_summary in subgroups:
            try:
                subgroup = client.groups.get(subgroup_summary.id)
                walk(subgroup, group.full_path)
            except Exception as exc:
                log(
                    f"Unable to process subgroup "
                    f"{subgroup_summary.full_path}: {exc}"
                )

    walk(root_group)

    return groups


def main():
    dry_run = os.environ["DRY_RUN"].lower() == "true"

    include_empty = (
        os.environ.get("INCLUDE_EMPTY_GITLAB_GROUPS", "true").lower()
        == "true"
    )

    client = create_client()

    root_group_paths = [
        group.strip()
        for group in os.environ["GITLAB_TEAM_ROOT_GROUPS"].split(",")
        if group.strip()
    ]

    github_org = os.environ["GITHUB_ORG"]

    identity_mapping = validate_identity_mapping(
        os.environ["IDENTITY_MAPPING_FILE"]
    )

    if not root_group_paths:
        raise ValueError(
            "GITLAB_TEAM_ROOT_GROUPS is empty. "
            "Provide one or more comma-separated GitLab group paths."
        )

    gitlab_groups = []
    seen_group_ids = set()

    for root_group_path in root_group_paths:
        log(
            f"Collecting full GitLab group tree from: "
            f"{root_group_path}"
        )

        try:
            root_group = client.groups.get(root_group_path)
        except Exception as exc:
            log(
                f"ERROR: Unable to access GitLab group "
                f"{root_group_path}: {exc}"
            )
            continue

        discovered_groups = collect_group_tree(client, root_group)

        for group in discovered_groups:
            if group["id"] not in seen_group_ids:
                seen_group_ids.add(group["id"])
                gitlab_groups.append(group)

    log(
        f"Discovered {len(gitlab_groups)} unique GitLab "
        f"groups/subgroups."
    )

    migration_dir = Path(os.environ["MIGRATION_DIR"])
    migration_dir.mkdir(parents=True, exist_ok=True)

    team_rows = []
    member_rows = []

    for gitlab_group in gitlab_groups:
        group_path = gitlab_group["full_path"]
        group_name = gitlab_group["name"]

        team_name = group_name
        team_slug = slugify(group_name)

        if os.environ.get("GITHUB_TEAM_PREFIX"):
            team_slug = (
                f"{os.environ['GITHUB_TEAM_PREFIX']}-{team_slug}"
            )

        try:
            gitlab_group_obj = client.groups.get(group_path)
            members = gitlab_group_obj.members_all.list(get_all=True)
        except Exception as exc:
            log(f"Unable to list members for {group_path}: {exc}")
            members = []

        member_count = len(members)

        if member_count == 0 and not include_empty:
            log(f"Skipping empty GitLab group: {group_path}")
            continue

        log(
            f"Planning GitLab group → GitHub team: "
            f"{group_path} → {team_slug} "
            f"({member_count} members)"
        )

        team_exists = False

        if not dry_run:
            try:
                github_request(
                    "GET",
                    f"/orgs/{github_org}/teams/{team_slug}",
                )
                team_exists = True
            except RuntimeError:
                team_exists = False
            except Exception as exc:
                log(
                    f"Unable to check GitHub team {team_slug}: {exc}"
                )
                team_exists = False

        team_rows.append(
            {
                "gitlab_group_id": gitlab_group["id"],
                "gitlab_group_name": group_name,
                "gitlab_group_path": group_path,
                "gitlab_parent_group_path": gitlab_group[
                    "parent_group_path"
                ],
                "github_org": github_org,
                "github_team_name": team_name,
                "github_team_slug": team_slug,
                "member_count": member_count,
                "status": (
                    "already_exists"
                    if team_exists
                    else ("dry_run" if dry_run else "to_create")
                ),
            }
        )

        for member in members:
            gitlab_username = member.username
            identity = identity_mapping.get(gitlab_username)

            if not identity or not identity["include"]:
                member_rows.append(
                    {
                        "gitlab_group_path": group_path,
                        "gitlab_username": gitlab_username,
                        "gitlab_email": getattr(member, "email", ""),
                        "gitlab_role": gitlab_role_name(
                            member.access_level
                        ),
                        "access_level": member.access_level,
                        "github_username": "",
                        "github_team_slug": team_slug,
                        "mapping_status": "unmapped",
                    }
                )
                continue

            member_rows.append(
                {
                    "gitlab_group_path": group_path,
                    "gitlab_username": gitlab_username,
                    "gitlab_email": identity["gitlab_email"],
                    "gitlab_role": gitlab_role_name(
                        member.access_level
                    ),
                    "access_level": member.access_level,
                    "github_username": identity["github_username"],
                    "github_team_slug": team_slug,
                    "mapping_status": "mapped",
                }
            )

    write_csv(
        migration_dir / "gitlab-teams-plan.csv",
        team_rows,
        TEAM_FIELDS,
    )

    write_csv(
        migration_dir / "gitlab-team-members-plan.csv",
        member_rows,
        MEMBER_FIELDS,
    )

    write_json(
        migration_dir / "gitlab-teams-plan.json",
        {
            "gitlab_root_groups": root_group_paths,
            "github_org": github_org,
            "include_empty_groups": include_empty,
            "discovered_group_count": len(gitlab_groups),
            "planned_team_count": len(team_rows),
            "member_mapping_count": len(member_rows),
            "teams": team_rows,
            "members": member_rows,
        },
    )

    log("GitLab group tree converted into GitHub team migration plan.")
    log(f"Planned GitHub teams: {len(team_rows)}")
    log(f"Planned member mappings: {len(member_rows)}")


if __name__ == "__main__":
    main()