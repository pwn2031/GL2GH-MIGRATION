#!/usr/bin/env python3

"""Step 0: Inventory GitLab groups, users, projects, members, variables, and deploy keys."""

import os
from pathlib import Path

from scripts.lib.csv_utils import write_csv
from scripts.lib.gitlab_client import (
    create_client,
    get_group,
    get_project_deploy_keys,
    get_project_members,
    get_project_variables,
    list_group_projects,
)
from scripts.lib.logging_utils import log, write_json

INVENTORY_FILES = {
    "groups": "gitlab-groups.csv",
    "projects": "gitlab-projects.csv",
    "members": "gitlab-members.csv",
    "variables": "gitlab-variables.csv",
    "deploy_keys": "gitlab-deploy-keys.csv",
}


def main():
    log("Starting GitLab inventory...")

    client = create_client()

    group_path = os.environ["GITLAB_GROUP"]
    group = get_group(client, group_path)

    include_archived = (
        os.environ.get("INCLUDE_ARCHIVED", "false").lower() == "true"
    )

    projects = list_group_projects(
        client,
        group_path,
        include_archived=include_archived,
    )

    log(f"Found {len(projects)} projects in GitLab group: {group_path}")

    inventory = {
        "generated_at": None,
        "gitlab_url": os.environ["GITLAB_URL"],
        "gitlab_group": group_path,
        "group": {
            "id": group.id,
            "name": group.name,
            "full_path": group.full_path,
        },
        "project_count": len(projects),
        "projects": [],
    }

    group_rows = [
        {
            "gitlab_group_id": group.id,
            "gitlab_group_name": group.name,
            "gitlab_group_path": group.full_path,
        }
    ]

    project_rows = []
    member_rows = []
    variable_rows = []
    deploy_key_rows = []

    for summary in projects:
        project = client.projects.get(summary.id)

        log(f"Inventorying project: {project.path_with_namespace}")

        members = get_project_members(project)
        variables = get_project_variables(project)
        deploy_keys = get_project_deploy_keys(project)

        project_record = {
            "id": project.id,
            "name": project.name,
            "path": project.path,
            "path_with_namespace": project.path_with_namespace,
            "default_branch": project.default_branch,
            "visibility": project.visibility,
            "archived": project.archived,
            "http_url": project.http_url_to_repo,
            "ssh_url": project.ssh_url_to_repo,
            "member_count": len(members),
            "variable_count": len(variables),
            "deploy_key_count": len(deploy_keys),
        }

        inventory["projects"].append(project_record)
        project_rows.append(project_record)

        for member in members:
            member_rows.append(
                {
                    "gitlab_project": project.path_with_namespace,
                    "gitlab_username": member["username"],
                    "gitlab_email": member["email"],
                    "gitlab_role": member["role"],
                    "access_level": member["access_level"],
                    "membership_type": (
                        "inherited" if member["inherited"] else "direct"
                    ),
                }
            )

        for variable in variables:
            variable_rows.append(
                {
                    "gitlab_project": project.path_with_namespace,
                    "variable_key": variable["key"],
                    "variable_value": variable["value"],
                    "protected": variable["protected"],
                    "masked": variable["masked"],
                }
            )

        for key in deploy_keys:
            deploy_key_rows.append(
                {
                    "gitlab_project": project.path_with_namespace,
                    "deploy_key_id": key["id"],
                    "title": key["title"],
                    "can_push": key["can_push"],
                    "created_at": key["created_at"],
                    "expires_at": key["expires_at"],
                }
            )

    inventory_dir = Path(os.environ["INVENTORY_DIR"])

    write_json(inventory_dir / "gitlab-inventory.json", inventory)

    write_csv(
        inventory_dir / INVENTORY_FILES["groups"],
        group_rows,
        ["gitlab_group_id", "gitlab_group_name", "gitlab_group_path"],
    )

    write_csv(
        inventory_dir / INVENTORY_FILES["projects"],
        project_rows,
        [
            "id",
            "name",
            "path",
            "path_with_namespace",
            "default_branch",
            "visibility",
            "archived",
            "http_url",
            "ssh_url",
            "member_count",
            "variable_count",
            "deploy_key_count",
        ],
    )

    write_csv(
        inventory_dir / INVENTORY_FILES["members"],
        member_rows,
        [
            "gitlab_project",
            "gitlab_username",
            "gitlab_email",
            "gitlab_role",
            "access_level",
            "membership_type",
        ],
    )

    write_csv(
        inventory_dir / INVENTORY_FILES["variables"],
        variable_rows,
        [
            "gitlab_project",
            "variable_key",
            "variable_value",
            "protected",
            "masked",
        ],
    )

    write_csv(
        inventory_dir / INVENTORY_FILES["deploy_keys"],
        deploy_key_rows,
        [
            "gitlab_project",
            "deploy_key_id",
            "title",
            "can_push",
            "created_at",
            "expires_at",
        ],
    )

    log("GitLab inventory complete.")


if __name__ == "__main__":
    main()