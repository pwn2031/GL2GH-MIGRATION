# Troubleshooting Guide

## 1. `KeyError: 'GITLAB_URL'`

### Cause

`config.env` variables are not exported to Python.

### Fix

Run:

```bash
set -a
source config.env
set +a
```

Or ensure every variable in `config.env` starts with `export`:

```bash
export GITLAB_URL="[https://gitlab.com](https://gitlab.com)"
```

## 2. `ModuleNotFoundError: No module named 'yaml'`

### Cause

Python dependencies are not installed.

### Fix

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. `Repository not found` when cloning GitHub repository

### Cause

The GitHub token lacks permission, the repository name is wrong, or Git is using SSH without a configured key.

### Fix

Check authentication:

```bash
gh auth status
```

Ensure the token has:

```text
repo
workflow
```

Switch GitHub CLI to HTTPS:

```bash
gh config set git_protocol https
gh auth setup-git
```

Test direct access:

```bash
git ls-remote [https://github.com/](https://github.com/)<owner>/<repository>.git
```

Clone directly:

```bash
git clone [https://github.com/](https://github.com/)<owner>/<repository>.git
```

## 4. `fatal: not a git repository`

### Cause

You are inside a bare mirror clone such as:

```text
mirror-clones/app-service.git
```

Bare clones cannot be checked out or edited directly.

### Fix

Use a normal working clone:

```bash
git clone [https://github.com/](https://github.com/)<owner>/<repository>.git
cd <repository>
```

## 5. GitHub Actions test job fails on `test -f build/app.txt`

### Cause

The build artifact was not downloaded in the later job.

### Fix

Ensure every job after `build_job` contains:

```yaml
- name: Download build artifact
  uses: actions/download-artifact@v4
  with:
    name: migrated-build-artifact
    path: build
```

## 6. `workflow_dispatch: null` causes workflow issues

### Cause

Some YAML serializers write `null` for an empty workflow dispatch trigger.

### Fix

Use:

```yaml
on:
  workflow_dispatch: {}
```

## 7. Permission denied when assigning collaborators

### Cause

The GitHub token does not have sufficient repository permission.

### Fix

Ensure the token has:

```text
repo
```

For organization repositories, the token owner must also have permission to manage collaborators.

## 8. Branch ruleset creation fails

### Cause

The repository may already have a ruleset with the same name, or the token lacks ruleset permissions.

### Fix

Check existing rulesets:

```bash
gh api repos/<owner>/<repository>/rulesets
```

Use a unique ruleset name or update the existing ruleset.

## 9. EC2 runner remains queued

### Cause

No self-hosted runner with the configured label is online.

### Fix

Check:

```bash
gh api repos/<owner>/<repository>/actions/runners \
  --jq '.runners[] | {name, status, labels: [.labels[].name]}'
```

Ensure:

- The runner is running.
- The runner label matches `EC2_RUNNER_LABEL`.
- The workflow uses `runs-on: ec2`.

## 10. Secret is not available in workflow

### Cause

The secret name does not match, or the workflow does not map it into `env`.

### Fix

In the workflow:

```yaml
env:
  MY_SECRET: ${{ secrets.MY_SECRET }}
```

Then use:

```bash
echo "Secret is available: $([ -n "$MY_SECRET" ] && echo yes || echo no)"
```

Never print the secret value.

## 11. Migration stopped at unmapped user

### Cause

`UNMAPPED_USER_POLICY=fail` and a GitLab member is missing from the identity mapping.

### Fix

Either add the user to:

```text
inputs/identity-mapping.csv
```

Or change:

```bash
export UNMAPPED_USER_POLICY="skip"
```

## 12. Where are the migration results?

```text
inventory/       GitLab source inventory
migration/       Plans and migration results
reports/         Final JSON and HTML reports
logs/            Execution logs
```

Open the final report:

```bash
open reports/migration-report.html
```