# GitLab to GitHub Migration Toolkit

A configuration-driven automation toolkit for migrating GitLab groups, repositories, users, permissions, CI/CD pipelines, metadata, variables, and runner configuration to GitHub.

## What it migrates

- GitLab group and project inventory
- Git repositories with full history, branches, and tags
- GitHub repositories
- User and permission mappings
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

## License

MIT License.