"""Reusable GitLab API client helpers."""

import os

import gitlab

from .logging_utils import log
from .validators import gitlab_role_name


def create_client():
    gitlab_url = os.environ["GITLAB_URL"]
    gitlab_token = os.environ["GITLAB_TOKEN"]

    client = gitlab.Gitlab(
        gitlab_url,
        private_token=gitlab_token,
        per_page=100,
        timeout=30,
        retry_transient_errors=True,
    )

    client.auth()

    log(f"Connected to GitLab as: {client.user.username}")

    return client


def get_group(client, group_path):
    return client.groups.get(group_path)


def get_project(client, project_path):
    return client.projects.get(project_path)


def list_group_projects(client, group_path, include_archived=False):
    group = get_group(client, group_path)

    projects = group.projects.list(
        include_subgroups=True,
        get_all=True,
        archived=include_archived,
    )

    return projects


def get_project_members(project):
    members = []

    for member in project.members_all.list(get_all=True):
        members.append(
            {
                "id": member.id,
                "username": member.username,
                "name": member.name,
                "email": getattr(member, "email", ""),
                "access_level": member.access_level,
                "role": gitlab_role_name(member.access_level),
                "inherited": getattr(member, "inherited", False),
            }
        )

    return members


def get_project_variables(project):
    variables = []

    for variable in project.variables.list(get_all=True):
        variables.append(
            {
                "key": variable.key,
                "value": variable.value,
                "protected": getattr(variable, "protected", False),
                "masked": getattr(variable, "masked", False),
            }
        )

    return variables


def get_group_variables(group):
    variables = []

    for variable in group.variables.list(get_all=True):
        variables.append(
            {
                "key": variable.key,
                "value": variable.value,
                "protected": getattr(variable, "protected", False),
                "masked": getattr(variable, "masked", False),
            }
        )

    return variables


def get_project_deploy_keys(project):
    keys = []

    try:
        for key in project.keys.list(get_all=True):
            keys.append(
                {
                    "id": key.id,
                    "title": key.title,
                    "can_push": getattr(key, "can_push", False),
                    "created_at": getattr(key, "created_at", ""),
                    "expires_at": getattr(key, "expires_at", ""),
                }
            )
    except Exception as exc:
        log(f"Unable to list deploy keys for {project.path_with_namespace}: {exc}")

    return keys