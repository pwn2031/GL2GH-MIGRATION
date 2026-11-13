# Setup Guide

This guide explains how to set up and run the GitLab-to-GitHub Migration Toolkit.

## Prerequisites

Install the following:

- Python 3.10 or later
- Git
- GitHub CLI (`gh`)
- A GitLab personal access token
- A GitHub personal access token

Verify installations:

```bash
python3 --version
git --version
gh --version
```

## Create tokens

### GitLab token

Create a GitLab personal access token with:

- `api`
- `read_api`
- `read_repository`
- `write_repository`

Store it securely. Do not commit it.

### GitHub token

Create a GitHub personal access token with:

- `repo`
- `workflow`
- `read:org`

The `repo` scope is required for private repository access, while `workflow` is required to create or update GitHub Actions workflow files. [320][314]

## Clone the toolkit

```bash
git clone [https://github.com/](https://github.com/)<your-account>/gitlab-to-github-migration-toolkit.git
cd gitlab-to-github-migration-toolkit
```

## Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Create local configuration

```bash
cp config.env.example config.env
cp inputs/identity-mapping.csv.example inputs/identity-mapping.csv
```

Edit:

```text
config.env
inputs/identity-mapping.csv
```

## Configure `config.env`

Minimum required values:

```bash
export GITLAB_URL="[https://gitlab.com](https://gitlab.com)"
export GITLAB_TOKEN="glpat-your-gitlab-token"
export GITLAB_GROUP="your-gitlab-group"

export GITHUB_ACCOUNT="your-github-username-or-org"
export GITHUB_TOKEN="ghp-your-github-token"
export GITHUB_TARGET_MODE="personal_account"
```

For an organization target, set:

```bash
export GITHUB_TARGET_MODE="organization"
```

## Configure identity mapping

Edit:

```bash
inputs/identity-mapping.csv
```

Example:

```csv
gitlab_username,gitlab_email,github_username,github_role_override,include
alice,alice@example.com,alice-github,,true
bob,bob@example.com,bob-github,,true
service-account,service@example.com,,false
```

## Validate configuration

```bash
./run.sh validate
```

This checks:

- Required environment variables
- Required tools
- GitLab authentication
- GitHub authentication
- Identity mapping format
- Workspace directories

## Run migration

### Dry run

Keep:

```bash
DRY_RUN=true
AUTO_APPROVE=false
```

Run:

```bash
./run.sh migrate-all
```

### Real migration

After reviewing:

```bash
migration/migration-plan.json
migration/group-mapping.csv
migration/user-mapping.csv
```

Set:

```bash
DRY_RUN=false
AUTO_APPROVE=true
```

Run:

```bash
./run.sh migrate-all
```

## View results

```bash
open reports/migration-report.html
```

Or:

```bash
gh run list --repo <github-account>/<repository>
```

## Clean up

After migration, remove temporary clones if desired:

```bash
rm -rf working-clones/*
```

Never remove `inventory/`, `migration/`, or `reports/` until the migration has been validated and accepted.