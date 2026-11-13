#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ ! -f "$SCRIPT_DIR/config.env" ]]; then
  echo "ERROR: config.env not found at $SCRIPT_DIR/config.env"
  exit 1
fi

set -a
source "$SCRIPT_DIR/config.env"
set +a

mkdir -p \
  "$INPUTS_DIR" \
  "$INVENTORY_DIR" \
  "$MIGRATION_DIR" \
  "$REPORTS_DIR" \
  "$LOG_DIR" \
  "$WORKING_CLONES_DIR"

RUN_ID="$(date +%Y-%m-%d-%H%M%S)"
LOG_FILE="$LOG_DIR/migration-$RUN_ID.log"

exec > >(tee -a "$LOG_FILE") 2>&1

echo "============================================================"
echo "GitLab to GitHub Migration Automation"
echo "Run ID: $RUN_ID"
echo "Log file: $LOG_FILE"
echo "GitLab group: $GITLAB_GROUP"
echo "GitHub target: $GITHUB_ACCOUNT"
echo "Target mode: $GITHUB_TARGET_MODE"
echo "Dry run: $DRY_RUN"
echo "Auto approve: $AUTO_APPROVE"
echo "Fail fast: $FAIL_FAST"
echo "============================================================"

for tool in python3 git gh; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "ERROR: Required tool not found: $tool"
    exit 1
  fi
done

if [[ ! -f "$IDENTITY_MAPPING_FILE" ]]; then
  echo "ERROR: Identity mapping file not found: $IDENTITY_MAPPING_FILE"
  exit 1
fi

run_step() {
  local step_name="$1"
  local script_name="$2"
  local script_path="$SCRIPT_DIR/scripts/$script_name"

  if [[ ! -f "$script_path" ]]; then
    echo "ERROR: Migration script not found: $script_path"
    exit 1
  fi

  echo ""
  echo "============================================================"
  echo "START: $step_name"
  echo "Script: scripts/$script_name"
  echo "============================================================"

  PYTHONPATH="$SCRIPT_DIR" python3 "$script_path"

  echo ""
  echo "COMPLETE: $step_name"
}

run_phase() {
  echo ""
  echo "============================================================"
  echo "$1"
  echo "============================================================"
}

case "${1:-}" in
  validate)
    run_phase "PHASE 0 — PRE-MIGRATION"
    run_step "PHASE 0.1 — Validate configuration" "01_validate_config.py"
    ;;

  inventory)
    run_phase "PHASE 0 — PRE-MIGRATION"
    run_step "PHASE 0.2 — Inventory GitLab" "02_inventory_gitlab.py"
    ;;

  plan)
    run_phase "PHASE 0 — PRE-MIGRATION"
    run_step "PHASE 0.3 — Generate migration plan" "03_generate_migration_plan.py"
    ;;

  inventory-gitlab-teams)
    run_phase "PHASE 1 — PROVISION GITHUB TARGETS"
    run_step "PHASE 1.2 — Convert GitLab groups to GitHub team plan" "05_convert_gitlab_groups_to_teams.py"
    ;;

  create-github-teams)
    run_phase "PHASE 1 — PROVISION GITHUB TARGETS"
    run_step "PHASE 1.3 — Create GitHub teams" "06_create_github_teams.py"
    ;;

  assign-github-team-members)
    run_phase "PHASE 1 — PROVISION GITHUB TARGETS"
    run_step "PHASE 1.4 — Assign GitHub team members" "07_assign_github_team_members.py"
    ;;

  assign-team-repo-permissions)
    run_phase "PHASE 5 — APPLY GOVERNANCE"
    run_step "PHASE 5.2 — Apply team repository permissions" "15_apply_team_repo_permissions.py"
    ;;

  migrate-merge-requests)
    run_phase "PHASE 3 — MIGRATE COLLABORATION"
    run_step "PHASE 3.2 — Migrate GitLab merge requests to GitHub pull requests" "10_migrate_merge_requests.py"
    ;;

  migrate-all)
    run_phase "PHASE 0 — PRE-MIGRATION"

    run_step "PHASE 0.1 — Validate configuration" "01_validate_config.py"
    run_step "PHASE 0.2 — Inventory GitLab" "02_inventory_gitlab.py"
    run_step "PHASE 0.3 — Generate migration plan" "03_generate_migration_plan.py"

    if [[ "$AUTO_APPROVE" != "true" ]]; then
      echo ""
      read -rp "Review migration/migration-plan.json. Continue? (yes/no): " answer
      if [[ "$answer" != "yes" ]]; then
        echo "Migration stopped by user."
        exit 0
      fi
    fi

    run_phase "PHASE 1 — PROVISION GITHUB TARGETS"

    run_step "PHASE 1.1 — Create GitHub repositories" "04_create_github_repositories.py"

    run_step "PHASE 1.2 — Convert GitLab groups to GitHub team plan" "05_convert_gitlab_groups_to_teams.py"
    run_step "PHASE 1.3 — Create GitHub teams" "06_create_github_teams.py"
    run_step "PHASE 1.4 — Assign GitHub team members" "07_assign_github_team_members.py"

    run_phase "PHASE 2 — MIGRATE REPOSITORY CONTENT"

    run_step "PHASE 2.1 — Migrate Git repositories" "08_migrate_git_repositories.py"

    run_phase "PHASE 3 — MIGRATE COLLABORATION"

    run_step "PHASE 3.1 — Create GitHub migration-test issues, labels, milestones, and releases" "09_migrate_issues_labels_milestones_releases.py"
    run_step "PHASE 3.2 — Migrate GitLab merge requests to GitHub pull requests" "10_migrate_merge_requests.py"

    run_phase "PHASE 4 — MIGRATE AUTOMATION"

    run_step "PHASE 4.1 — Convert GitLab CI/CD to GitHub Actions" "11_convert_cicd_pipelines.py"
    run_step "PHASE 4.2 — Migrate variables, secrets, and environments" "12_migrate_variables_secrets_environments.py"
    run_step "PHASE 4.4 — Setup and validate runners" "13_setup_validate_runners.py"

    run_phase "PHASE 5 — APPLY GOVERNANCE"

    run_step "PHASE 5.1 — Apply branch rulesets" "14_apply_branch_rulesets.py"
    run_step "PHASE 5.2 — Apply team repository permissions" "15_apply_team_repo_permissions.py"
    run_step "PHASE 5.3 — Migrate permissions and deploy keys" "16_migrate_permissions_deploy_keys.py"

    run_phase "PHASE 6 — VALIDATE AND CUTOVER"
    run_step "PHASE 6.1 — Validate migration results" "17_validate_migration.py"
    run_step "PHASE 6.2 — Generate migration report" "18_generate_migration_report.py"
    ;;

  report)
    run_phase "PHASE 6 — VALIDATE AND CUTOVER"
    run_step "PHASE 6.2 — Generate migration report" "18_generate_migration_report.py"
    ;;

  *)
    cat <<'EOF'
Usage:

  ./run.sh validate                       PHASE 0.1 — Validate configuration
  ./run.sh inventory                      PHASE 0.2 — Inventory GitLab
  ./run.sh plan                           PHASE 0.3 — Generate migration plan
  ./run.sh inventory-gitlab-teams         PHASE 1.2 — Convert GitLab groups to GitHub team plan
  ./run.sh create-github-teams            PHASE 1.3 — Create GitHub teams
  ./run.sh assign-github-team-members     PHASE 1.4 — Assign GitHub team members
  ./run.sh assign-team-repo-permissions   PHASE 5.2 — Apply team repository permissions
  ./run.sh migrate-merge-requests         PHASE 3.2 — Migrate GitLab merge requests to GitHub pull requests
  ./run.sh migrate-all                    Run the complete migration hierarchy
  ./run.sh report                         PHASE 6.2 — Generate migration report
EOF
    exit 1
    ;;
esac

echo ""
echo "============================================================"
echo "Migration run finished"
echo "Run ID: $RUN_ID"
echo "Log file: $LOG_FILE"
echo "============================================================"