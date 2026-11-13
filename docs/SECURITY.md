# Security Guide

This toolkit migrates repositories, permissions, metadata, and CI/CD configuration. Handle tokens and secrets carefully.

## Never commit

Do not commit:

- `config.env`
- GitLab tokens
- GitHub tokens
- Deploy key private keys
- Secret values
- Generated migration reports containing variable values
- Temporary Git clones
- Runner registration tokens

The included `.gitignore` blocks these files.

## Token hygiene

Use separate tokens for GitLab and GitHub.

### GitLab token

Use the minimum required scopes:

- `api`
- `read_api`
- `read_repository`
- `write_repository`

### GitHub token

Use the minimum required scopes:

- `repo`
- `workflow`
- `read:org`

GitHub recommends granting only the scopes required for the task; `repo` is needed for repository command-line access. [320]

## Rotate exposed tokens

If a token appears in terminal output, a screenshot, a log file, or chat, rotate it immediately.

```bash
gh auth refresh -h github.com -s workflow
```

For GitLab, revoke the old token from:

```text
GitLab → User Settings → Access Tokens
```

## Secrets migration

The toolkit does **not** automatically copy secret-like GitLab variables.

It detects variables whose names contain terms such as:

```text
SECRET
PASSWORD
TOKEN
PRIVATE
CREDENTIAL
API_KEY
ACCESS_KEY
```

It creates:

```text
migration/secrets-required.csv
```

Then recreate each secret manually in GitHub:

```text
GitHub → Repository → Settings → Secrets and variables → Actions → New repository secret
```

GitHub Actions secrets are encrypted and cannot be read back through the API after creation.

## Deploy keys

The toolkit inventories GitLab deploy keys but does not automatically export private keys.

For each deploy key:

1. Locate the corresponding public key.
2. Add the public key as a GitHub deploy key.
3. Grant write access only if the GitLab key had `can_push=true`.
4. Store private keys in a secure secret manager.

## Runner security

Self-hosted runners can persist state between jobs and may be compromised by untrusted workflow code. GitHub specifically warns that self-hosted runners should almost never be used for public repositories. [321]

Follow these rules:

- Use self-hosted runners only for trusted private repositories.
- Do not store long-lived tokens, SSH keys, or secrets on runner machines.
- Restrict EC2 security groups and outbound network access.
- Use ephemeral runners where possible.
- Use runner groups to limit which repositories can use a runner.
- Rotate or destroy runners after migration testing.

## Repository visibility

Start with private repositories.

```bash
export GITHUB_TARGET_MODE="personal_account"
```

Only make migrated repositories public after reviewing:

- Source code
- Git history
- CI/CD files
- Issues
- Releases
- Embedded credentials
- Sensitive configuration

## Audit outputs

Review these files before sharing or publishing anything:

```text
inventory/gitlab-variables.csv
migration/variables-result.csv
migration/secrets-required.csv
reports/migration-report.json
reports/migration-report.html
logs/*.log
```

If any real secret value appears in these files, delete the files, rotate the secret, and rerun the migration with secret detection enabled.