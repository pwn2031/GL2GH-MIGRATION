# GitLab to GitHub Migration Toolkit

A configuration-driven automation toolkit for migrating GitLab groups, repositories, users, permissions, CI/CD pipelines, metadata, variables, and runner configuration to GitHub.

## What it migrates

- GitLab group and project inventory
- Git repositories with full history, branches, and tags
- GitHub repositories
- User and permission mappings
- Merge Requests
- Deploy key inventory
- Branch protection rulesets
- Issues, labels, milestones, and releases
- GitLab CI/CD pipelines to GitHub Actions
- Non-secret CI/CD variables
- GitHub environments
- GitHub-hosted and EC2 self-hosted runner configuration

## Requirements

- Python 3.10+
- Git
- GitHub CLI (`gh`)
- GitLab personal access token
- GitHub personal access token

Use a **classic GitHub PAT** for this POC, since the GitHub organization is new and repositories will be created during migration.

## GitLab PAT

```text
read_api
read_repository
write_repository
```

## GitHub PAT — classic

```text
repo
workflow
admin:org
```

## Why

| Token | Permission | Purpose |
|---|---|---|
| GitLab PAT | `read_api` | Read groups, projects, members, MRs, variables, runners, and deploy keys |
| GitLab PAT | `read_repository` | Clone and read Git repositories |
| GitLab PAT | `write_repository` | Push migrated Git history, branches, and tags |
| GitHub PAT | `repo` | Create/manage repositories, code, PRs, issues, secrets, variables, environments, and deploy keys |
| GitHub PAT | `workflow` | Create and update GitHub Actions workflow files |
| GitHub PAT | `admin:org` | Create and manage teams, members, and organization-level migration resources |

For this POC, use **classic PAT**, not fine-grained, because you need broad organization and repository-creation permissions while repositories do not yet exist.

## Quick start

1. Clone this repository:

   ```bash
   git clone https://github.com/pwn2031/GL2GH-MIGRATION.git
   cd GL2GH-MIGRATION
   ```

2. Create a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Create your local configuration:

   ```bash
   cp config.env.example config.env
   cp inputs/identity-mapping.csv.example inputs/identity-mapping.csv
   ```

4. Edit only these files:

   ```text
   config.env
   inputs/identity-mapping.csv
   ```

5. Validate the setup:

   ```bash
   ./run.sh validate
   ```

6. Run a dry-run migration:

   ```bash
   ./run.sh migrate-all
   ```

7. For a real migration, set:

   ```bash
   DRY_RUN=false
   AUTO_APPROVE=true
   ```

   Then run:

   ```bash
   ./run.sh migrate-all
   ```

## One-click migration

```bash
./run.sh migrate-all
```

The toolkit executes:

```text
Step 0  Validate configuration and inventory GitLab
Step 1  Create GitHub repositories
Step 2  Migrate repositories with full Git history
Step 3  Migrate permissions and deploy-key plan
Step 4  Apply branch rulesets
Step 5  Migrate metadata
Step 6  Convert GitLab CI/CD to GitHub Actions
Step 7  Migrate variables and identify secrets
Step 8  Validate runners and generate EC2 setup instructions
Final   Generate migration report
```

## Security

Never commit:

- `config.env`
- GitLab tokens
- GitHub tokens
- deploy key private keys
- secret values
- cloned repositories
- migration reports containing variable values

The repository includes `.gitignore` protection for these files.

## Outputs

```text
inventory/       GitLab source inventory
migration/       Migration plans and result reports
reports/         Final JSON and HTML migration reports
logs/            Timestamped migration logs
```

## End-to-end migration flow

The migration runs in a fixed order. Each numbered script performs one migration task, writes a result file, and passes its output to the next step.

```text
config.env + identity-mapping.csv
              ↓
        01_validate_config.py
              ↓
        02_inventory_gitlab.py
              ↓
        03_generate_migration_plan.py
              ↓
        04_create_github_repositories.py
              ↓
        05_convert_gitlab_groups_to_teams.py
              ↓
        06_create_github_teams.py
              ↓
        07_assign_github_team_members.py
              ↓
        08_migrate_git_repositories.py
              ↓
        09_migrate_issues_labels_milestones_releases.py
              ↓
        10_migrate_merge_requests.py
              ↓
        11_convert_cicd_pipelines.py
              ↓
        12_migrate_variables_secrets_environments.py
              ↓
        13_setup_validate_runners.py
              ↓
        14_apply_branch_rulesets.py
              ↓
        15_apply_team_repo_permissions.py
              ↓
        16_migrate_permissions_deploy_keys.py
              ↓
        17_validate_migration.py
              ↓
        18_generate_migration_report.py
```

## What each file does

| File | What it migrates or creates | How it works |
|---|---|---|
| `config.env` | Migration configuration | Stores GitLab/GitHub URLs, tokens, organization, source group, workspace paths, and migration settings. |
| `inputs/identity-mapping.csv` | GitLab-to-GitHub user mapping | Maps each GitLab username to the correct GitHub username and optional permission override. |
| `scripts/01_validate_config.py` | Configuration validation | Validates required settings, tokens, GitLab/GitHub connectivity, source group, and identity mapping before migration starts. |
| `scripts/02_inventory_gitlab.py` | GitLab source inventory | Uses the GitLab API to discover groups, projects, members, branches, tags, variables, runners, deploy keys, and webhooks. |
| `scripts/03_generate_migration_plan.py` | Migration plan | Converts GitLab inventory into a GitHub migration plan, including repository, team, user, and permission mappings. |
| `scripts/04_create_github_repositories.py` | GitHub repositories | Creates or verifies target GitHub repositories before Git content migration. |
| `scripts/05_convert_gitlab_groups_to_teams.py` | Team mapping | Maps GitLab groups to GitHub team names and prepares the GitHub team plan. |
| `scripts/06_create_github_teams.py` | GitHub teams | Creates GitHub teams that represent GitLab groups. |
| `scripts/07_assign_github_team_members.py` | Team members | Maps GitLab users to GitHub users and adds them to the correct GitHub teams. |
| `scripts/08_migrate_git_repositories.py` | Git history, branches, tags | Clones each GitLab repository as a mirror and pushes the complete Git history to GitHub. |
| `scripts/09_migrate_issues_labels_milestones_releases.py` | Collaboration metadata | Creates GitHub labels, milestones, issues, and releases corresponding to GitLab metadata. |
| `scripts/10_migrate_merge_requests.py` | Merge requests | Converts GitLab merge requests into GitHub pull requests; open MRs become open PRs, while merged or closed MRs become closed PRs. |
| `scripts/11_convert_cicd_pipelines.py` | CI/CD pipelines | Reads `.gitlab-ci.yml`, maps jobs, stages, scripts, rules, artifacts, and runner tags, then generates GitHub Actions workflows. |
| `scripts/12_migrate_variables_secrets_environments.py` | CI/CD configuration | Creates GitHub variables and environments; secret-like GitLab variables are flagged for secure manual creation. |
| `scripts/13_setup_validate_runners.py` | Runners | Generates GitHub Actions runner registration instructions and validates whether required self-hosted runners are online. |
| `scripts/14_apply_branch_rulesets.py` | Branch protection | Creates GitHub branch rulesets based on GitLab protected-branch settings. |
| `scripts/15_apply_team_repo_permissions.py` | Team repository access | Maps GitLab group access to GitHub team repository permissions. |
| `scripts/16_migrate_permissions_deploy_keys.py` | User permissions and deploy keys | Maps GitLab project members and roles to GitHub collaborators and migrates deploy keys. |
| `scripts/17_validate_migration.py` | Migration validation | Reads all migration result files, identifies successful, warning, and failed items, and writes a validation report. |
| `scripts/18_generate_migration_report.py` | Final migration report | Creates a final migration report summarizing completed work, warnings, failures, and manual actions. |

## Shared library files

| File | Purpose | How it works |
|---|---|---|
| `scripts/lib/gitlab_client.py` | GitLab connection layer | Creates the GitLab API client and provides reusable functions for groups, projects, members, MRs, variables, runners, and deploy keys. |
| `scripts/lib/github_client.py` | GitHub connection layer | Sends authenticated GitHub REST API requests and provides reusable helpers for repositories, teams, PRs, permissions, and deploy keys. |
| `scripts/lib/csv_utils.py` | CSV output layer | Reads and writes consistent migration result CSV files. |
| `scripts/lib/logging_utils.py` | Logging layer | Creates timestamped migration logs and consistent progress messages. |
| `scripts/lib/validators.py` | Validation layer | Validates configuration, maps GitLab roles to GitHub permissions, detects secret-like variables, and validates names and URLs. |

## Output files

| Folder / file | What it contains | Created by |
|---|---|---|
| `inventory/` | GitLab source inventory | `02_inventory_gitlab.py` |
| `migration/migration-plan.json` | GitHub migration plan | `03_generate_migration_plan.py` |
| `migration/github-targets-result.csv` | GitHub repository creation results | `04_create_github_repositories.py` |
| `migration/github-teams-result.csv` | GitHub team creation results | `06_create_github_teams.py` |
| `migration/github-team-members-result.csv` | Team membership results | `07_assign_github_team_members.py` |
| `migration/repository-migration-result.csv` | Git repository migration results | `08_migrate_git_repositories.py` |
| `migration/metadata-result.csv` | Issues, labels, milestones, and releases results | `09_migrate_issues_labels_milestones_releases.py` |
| `migration/merge-request-migration-result.csv` | GitLab MR to GitHub PR results | `10_migrate_merge_requests.py` |
| `migration/cicd-result.csv` | GitLab CI/CD conversion results | `11_convert_cicd_pipelines.py` |
| `migration/variables-result.csv` | Variables, secrets, and environment results | `12_migrate_variables_secrets_environments.py` |
| `migration/runner-validation.csv` | GitHub runner validation results | `13_setup_validate_runners.py` |
| `migration/branch-rulesets-result.csv` | Branch ruleset results | `14_apply_branch_rulesets.py` |
| `migration/github-team-repo-permissions-result.csv` | Team repository permission results | `15_apply_team_repo_permissions.py` |
| `migration/permissions-result.csv` | User permission migration results | `16_migrate_permissions_deploy_keys.py` |
| `migration/deploy-keys-result.csv` | Deploy key migration results | `16_migrate_permissions_deploy_keys.py` |
| `reports/migration-validation.csv` | Migration validation summary | `17_validate_migration.py` |
| `reports/` | Final migration report | `18_generate_migration_report.py` |
| `logs/` | Timestamped migration logs | `run.sh` and logging utilities |
| `working-clones/` | Temporary local Git clones | `08_migrate_git_repositories.py` |

## Migration rules

- Every script is idempotent, so rerunning it should not create duplicate GitHub resources.
- Git history, branches, and tags are migrated using Git mirror clone and mirror push.
- Open GitLab merge requests become open GitHub pull requests.
- Merged or closed GitLab merge requests become closed GitHub pull requests, preserving the original GitLab merge information in the PR description.
- Secret-like GitLab variables are never exported or copied in plaintext; they are flagged for manual creation in GitHub Secrets.
- GitLab runners are not transferred directly; equivalent GitHub Actions runners are created and configured.
- Branch rulesets, team permissions, deploy keys, and runner setup may require manual action depending on GitHub plan, organization policy, or infrastructure access.

## Simple migration summary

```text
GitLab inventory → migration plan → GitHub repositories → teams and members
→ Git history → metadata and MRs → CI/CD → variables and runners
→ branch protection and permissions → validation → final report
```

## License

MIT License.