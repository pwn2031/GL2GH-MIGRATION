"""Reusable GitHub API and GitHub CLI helpers."""

import json
import os
import subprocess

import requests

from .logging_utils import log

GITHUB_API = "https://api.github.com"


def github_headers():
    token = os.environ["GITHUB_TOKEN"]

    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

def get_organization(org):
    return github_request("GET", f"/orgs/{org}")


def github_request(method, endpoint, payload=None, expected_status=(200, 201)):
    url = f"{GITHUB_API}{endpoint}"

    response = requests.request(
        method,
        url,
        headers=github_headers(),
        json=payload,
        timeout=30,
    )

    if response.status_code not in expected_status:
        raise RuntimeError(
            f"GitHub API {method} {endpoint} failed: "
            f"{response.status_code} {response.text}"
        )

    if response.text:
        return response.json()

    return {}


def get_authenticated_user():
    return github_request("GET", "/user")


def repo_exists(owner, repo):
    try:
        github_request("GET", f"/repos/{owner}/{repo}")
        return True
    except RuntimeError:
        return False


def create_repository(owner, repo_name, private=True, description=""):
    payload = {
        "name": repo_name,
        "private": private,
        "description": description,
        "has_issues": True,
        "has_projects": True,
        "has_wiki": True,
        "auto_init": False,
    }

    if owner:
        endpoint = f"/orgs/{owner}/repos"
    else:
        endpoint = "/user/repos"

    return github_request("POST", endpoint, payload)


def set_collaborator_permission(owner, repo, username, permission):
    endpoint = f"/repos/{owner}/{repo}/collaborators/{username}"

    return github_request(
        "PUT",
        endpoint,
        {"permission": permission},
        expected_status=(201, 204),
    )


def create_environment(owner, repo, environment_name):
    endpoint = f"/repos/{owner}/{repo}/environments/{environment_name}"

    return github_request(
        "PUT",
        endpoint,
        {},
        expected_status=(200, 201),
    )


def create_repository_variable(owner, repo, name, value):
    endpoint = f"/repos/{owner}/{repo}/actions/variables"

    return github_request(
        "POST",
        endpoint,
        {"name": name, "value": value},
        expected_status=(201, 409),
    )


def create_runner_registration_token(owner, repo):
    endpoint = f"/repos/{owner}/{repo}/actions/runners/registration-token"

    return github_request(
        "POST",
        endpoint,
        {},
        expected_status=(201,),
    )


def run_gh(arguments, check=True):
    command = ["gh"] + arguments

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    if check and result.returncode != 0:
        raise RuntimeError(
            f"GitHub CLI command failed: {' '.join(command)}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    return result


def run_git(arguments, cwd=None, check=True):
    command = ["git"] + arguments

    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
    )

    if check and result.returncode != 0:
        raise RuntimeError(
            f"Git command failed: {' '.join(command)}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    return result