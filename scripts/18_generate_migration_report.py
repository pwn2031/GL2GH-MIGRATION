#!/usr/bin/env python3

"""Final: Generate migration report from all Step 0-8 outputs."""

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from scripts.lib.logging_utils import log, write_json

RESULT_FILES = [
    "github-targets-result.csv",
    "repository-migration-result.csv",
    "permissions-result.csv",
    "deploy-keys-result.csv",
    "branch-rulesets-result.csv",
    "metadata-result.csv",
    "cicd-result.csv",
    "variables-result.csv",
    "runner-validation.csv",
]


def read_csv(path):
    path = Path(path)

    if not path.exists():
        return []

    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def summarize(rows, status_field="status"):
    summary = {}

    for row in rows:
        status = row.get(status_field, "unknown")
        summary[status] = summary.get(status, 0) + 1

    return summary


def main():
    migration_dir = Path(os.environ["MIGRATION_DIR"])
    reports_dir = Path(os.environ["REPORTS_DIR"])
    reports_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "gitlab_url": os.environ["GITLAB_URL"],
            "gitlab_group": os.environ["GITLAB_GROUP"],
        },
        "target": {
            "github_account": os.environ["GITHUB_ACCOUNT"],
            "target_mode": os.environ["GITHUB_TARGET_MODE"],
        },
        "controls": {
            "dry_run": os.environ["DRY_RUN"].lower() == "true",
            "auto_approve": os.environ["AUTO_APPROVE"].lower() == "true",
            "fail_fast": os.environ["FAIL_FAST"].lower() == "true",
            "unmapped_user_policy": os.environ["UNMAPPED_USER_POLICY"],
        },
        "steps": {},
    }

    for filename in RESULT_FILES:
        rows = read_csv(migration_dir / filename)
        step_name = filename.replace("-result.csv", "")

        report["steps"][step_name] = {
            "file": str(migration_dir / filename),
            "total_records": len(rows),
            "status_summary": summarize(rows),
            "records": rows,
        }

    json_report = reports_dir / "migration-report.json"
    write_json(json_report, report)

    html_rows = []

    for step_name, step_data in report["steps"].items():
        html_rows.append(
            f"<tr><td>{step_name}</td>"
            f"<td>{step_data['total_records']}</td>"
            f"<td>{json.dumps(step_data['status_summary'])}</td></tr>"
        )

    html = f"""<!doctype html>
<html>
<head>
<title>GitLab to GitHub Migration Report</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 40px; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
th {{ background: #f4f4f4; }}
</style>
</head>
<body>
<h1>GitLab to GitHub Migration Report</h1>
<p>Generated: {report['generated_at_utc']}</p>
<p>GitLab group: {report['source']['gitlab_group']}</p>
<p>GitHub account: {report['target']['github_account']}</p>
<p>Dry run: {report['controls']['dry_run']}</p>
<h2>Step Summary</h2>
<table>
<tr><th>Step</th><th>Total records</th><th>Status summary</th></tr>
{''.join(html_rows)}
</table>
</body>
</html>
"""

    html_report = reports_dir / "migration-report.html"

    with open(html_report, "w", encoding="utf-8") as f:
        f.write(html)

    log(f"JSON migration report: {json_report}")
    log(f"HTML migration report: {html_report}")


if __name__ == "__main__":
    main()