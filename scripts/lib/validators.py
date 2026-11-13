"""Configuration, identity, role, and secret validation helpers."""

import os
import re
from pathlib import Path

from .csv_utils import read_csv, required_columns

GITLAB_ROLE_MAP = {
    10: "Guest",
    20: "Reporter",
    30: "Developer",
    40: "Maintainer",
    50: "Owner",
}

GITLAB_TO_GITHUB_PERMISSION = {
    "Owner": "admin",
    "Maintainer": "maintain",
    "Developer": "push",
    "Reporter": "pull",
    "Guest": "pull",
}

SECRET_KEYWORDS = [
    "SECRET",
    "PASSWORD",
    "TOKEN",
    "PRIVATE",
    "CREDENTIAL",
    "API_KEY",
    "ACCESS_KEY",
]


def gitlab_role_name(access_level):
    return GITLAB_ROLE_MAP.get(int(access_level), str(access_level))


def github_permission_for_gitlab_role(role_name, override=None):
    if override:
        return override.strip().lower()

    return GITLAB_TO_GITHUB_PERMISSION.get(role_name, "pull")


def is_secret_variable(key):
    key_upper = key.upper()
    return any(keyword in key_upper for keyword in SECRET_KEYWORDS)


def validate_environment(required_keys):
    missing = [key for key in required_keys if not os.environ.get(key)]

    if missing:
        raise ValueError(
            "Missing required environment variables: "
            + ", ".join(missing)
        )


def validate_identity_mapping(path):
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Identity mapping file not found: {path}"
        )

    rows = read_csv(path)

    required_columns(
        rows,
        [
            "gitlab_username",
            "gitlab_email",
            "github_username",
            "github_role_override",
            "include",
        ],
    )

    mapping = {}
    github_names = set()
    errors = []

    for index, row in enumerate(rows, start=2):
        gitlab_username = row["gitlab_username"].strip()
        github_username = row["github_username"].strip()
        include = row["include"].strip().lower()
        override = row["github_role_override"].strip()

        if not gitlab_username:
            errors.append(f"Line {index}: gitlab_username is empty")
            continue

        if gitlab_username in mapping:
            errors.append(
                f"Line {index}: duplicate gitlab_username "
                f"'{gitlab_username}'"
            )
            continue

        if include not in ("true", "false"):
            errors.append(
                f"Line {index}: include must be true or false"
            )
            continue

        if include == "true":
            if not github_username:
                errors.append(
                    f"Line {index}: github_username is required "
                    f"when include=true"
                )
                continue

            if github_username in github_names:
                errors.append(
                    f"Line {index}: duplicate github_username "
                    f"'{github_username}'"
                )
                continue

            github_names.add(github_username)

        mapping[gitlab_username] = {
            "gitlab_username": gitlab_username,
            "gitlab_email": row["gitlab_email"].strip(),
            "github_username": github_username,
            "github_role_override": override or None,
            "include": include == "true",
        }

    if errors:
        raise ValueError(
            "Identity mapping validation failed:\n- "
            + "\n- ".join(errors)
        )

    return mapping


def validate_github_username(username):
    if not re.match(r"^[A-Za-z\d](?:[A-Za-z\d]|-(?=[A-Za-z\d])){0,38}$", username):
        raise ValueError(f"Invalid GitHub username: {username}")

    return username


def validate_repository_name(name):
    if not re.match(r"^[A-Za-z0-9._-]+$", name):
        raise ValueError(f"Invalid repository name: {name}")

    return name