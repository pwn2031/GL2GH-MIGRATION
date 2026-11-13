# User Mapping Guide

The toolkit uses `inputs/identity-mapping.csv` to map GitLab users to GitHub users.

## File location

```text
inputs/identity-mapping.csv
```

## Required format

```csv
gitlab_username,gitlab_email,github_username,github_role_override,include
alice,alice@example.com,alice-github,,true
bob,bob@example.com,bob-github,,true
service-account,service@example.com,,false
```

## Column reference

| Column | Required | Description |
|---|---|---|
| `gitlab_username` | Yes | Exact GitLab username |
| `gitlab_email` | Yes | GitLab email address |
| `github_username` | Conditional | Required when `include=true` |
| `github_role_override` | No | Overrides the GitHub permission derived from GitLab |
| `include` | Yes | `true` to migrate permissions, `false` to skip |

## How mapping works

```text
GitLab project membership
        ↓
GitLab username and role
        ↓
identity-mapping.csv
        ↓
GitHub username
        ↓
GitHub repository permission
```

GitLab exposes project membership and effective access levels through its members API. [327]

## Role conversion

| GitLab role | GitLab access level | GitHub permission |
|---|---:|---|
| Owner | 50 | `admin` |
| Maintainer | 40 | `maintain` |
| Developer | 30 | `push` |
| Reporter | 20 | `pull` |
| Guest | 10 | `pull` |

## Override examples

Force a user to receive read-only access:

```csv
bob,bob@example.com,bob-github,pull,true
```

Force admin access:

```csv
alice,alice@example.com,alice-github,admin,true
```

## Skip a user

```csv
old-user,old@example.com,,false
```

The user is recorded in `migration/unmapped-users.csv`, but no GitHub permission is assigned.

## Unmapped users

If a GitLab member is not present in the identity mapping file, the toolkit records it in:

```text
migration/unmapped-users.csv
```

Control the behavior with:

```bash
export UNMAPPED_USER_POLICY="skip"
```

Options:

| Value | Behavior |
|---|---|
| `skip` | Skip and record unmapped users |
| `fail` | Stop migration when an unmapped user is found |
| `prompt` | Pause for manual decision |

For one-click automation, use `skip` or `fail`.

## Validation rules

The toolkit validates:

- Required columns
- Unique GitLab usernames
- Unique GitHub usernames for included users
- Non-empty GitHub username when `include=true`
- Valid `include` values
- Valid GitHub username format

## Security rule

Never put GitHub tokens, GitLab tokens, passwords, or private keys in this CSV.