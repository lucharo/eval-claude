"""Export benchmark workflow run history for the static dashboard.

Usage:
    python scripts/export_run_ledger.py

This script reads GitHub Actions benchmark runs via the gh CLI and writes a
static ledger to docs/runs.json so the dashboard can show both valid benchmark
results and the runs that produced no publishable data.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_FILE = Path(__file__).parent.parent / "docs" / "data.json"
OUTPUT_FILE = Path(__file__).parent.parent / "docs" / "runs.json"
PURGE_COMMIT = "7d183e60dc91ef6709e4acf4397cbcf1ee3aeb40"


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def get_label(model: str) -> str:
    model_id = model.replace("claude-code/", "").replace("claude-", "")
    parts = model_id.split("-")
    if len(parts) >= 3 and parts[0] in {"haiku", "sonnet", "opus"}:
        return f"{parts[0].title()} {parts[1]}.{parts[2]}"
    if model_id in {"haiku", "sonnet", "opus"}:
        return model_id.title()
    return model_id


def gh_json(endpoint: str) -> dict[str, Any]:
    output = subprocess.check_output(["gh", "api", endpoint], text=True)
    return json.loads(output)


def git_json(rev: str) -> list[dict[str, Any]]:
    output = subprocess.check_output(["git", "show", rev], text=True)
    return json.loads(output)


def load_removed_rows() -> list[dict[str, Any]]:
    before = git_json(f"{PURGE_COMMIT}^:docs/data.json")
    after = git_json(f"{PURGE_COMMIT}:docs/data.json")
    after_keys = {(row["model"], row["date"]) for row in after}
    return [row for row in before if (row["model"], row["date"]) not in after_keys]


def assign_rows_to_runs(
    runs: list[dict[str, Any]], rows: list[dict[str, Any]]
) -> dict[int, list[dict[str, Any]]]:
    ordered_runs = sorted(runs, key=lambda run: parse_dt(run["created_at"]))
    ordered_rows = sorted(rows, key=lambda row: parse_dt(row["date"]))
    assignments = {run["run_number"]: [] for run in ordered_runs}

    run_index = 0
    for row in ordered_rows:
        row_dt = parse_dt(row["date"])
        while run_index + 1 < len(ordered_runs) and row_dt >= parse_dt(
            ordered_runs[run_index + 1]["created_at"]
        ):
            run_index += 1
        if row_dt >= parse_dt(ordered_runs[run_index]["created_at"]):
            assignments[ordered_runs[run_index]["run_number"]].append(row)

    return assignments


def classify_run(
    *,
    conclusion: str | None,
    artifact_count: int,
    persisted_row_count: int,
    purged_invalid_row_count: int,
    eval_job_count: int,
) -> str:
    expected_rows = (
        eval_job_count
        or artifact_count
        or persisted_row_count
        or purged_invalid_row_count
    )

    if purged_invalid_row_count and persisted_row_count == 0:
        return "purged-invalid"
    if persisted_row_count and expected_rows and persisted_row_count >= expected_rows:
        return "captured"
    if persisted_row_count:
        return "partial"
    if conclusion == "success" and artifact_count == 0:
        return "missing"
    if conclusion == "cancelled":
        return "cancelled"
    if conclusion == "failure":
        return "failed"
    return "unknown"


def build_summary(
    runs: list[dict[str, Any]],
    action_rows: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    states = [run["capture_state"] for run in runs]
    return {
        "total_runs": len(runs),
        "successful_runs": sum(1 for run in runs if run["conclusion"] == "success"),
        "failed_runs": sum(1 for run in runs if run["conclusion"] == "failure"),
        "cancelled_runs": sum(1 for run in runs if run["conclusion"] == "cancelled"),
        "captured_runs": states.count("captured"),
        "partial_runs": states.count("partial"),
        "missing_runs": states.count("missing"),
        "purged_invalid_runs": states.count("purged-invalid"),
        "total_persisted_rows": len(action_rows),
        "total_persisted_samples": sum(row["samples"] for row in action_rows),
        "baseline_rows": len(baseline_rows),
        "baseline_samples": sum(row["samples"] for row in baseline_rows),
    }


def export(repo: str, workflow: str, output_file: Path) -> None:
    data = json.loads(DATA_FILE.read_text())
    removed_rows = load_removed_rows()

    runs_payload = gh_json(
        f"repos/{repo}/actions/workflows/{workflow}/runs?per_page=100"
    )
    raw_runs = sorted(runs_payload["workflow_runs"], key=lambda run: run["run_number"])

    action_start = parse_dt(raw_runs[0]["created_at"])
    action_rows = [row for row in data if parse_dt(row["date"]) >= action_start]
    baseline_rows = [row for row in data if parse_dt(row["date"]) < action_start]

    assigned_rows = assign_rows_to_runs(raw_runs, action_rows)
    assigned_removed_rows = assign_rows_to_runs(raw_runs, removed_rows)

    runs: list[dict[str, Any]] = []
    for run in raw_runs:
        run_id = run["id"]
        jobs_payload = gh_json(f"repos/{repo}/actions/runs/{run_id}/jobs")
        artifacts_payload = gh_json(f"repos/{repo}/actions/runs/{run_id}/artifacts")

        jobs = jobs_payload.get("jobs", [])
        eval_jobs = [job for job in jobs if job["name"].startswith("eval")]
        collect_job = next((job for job in jobs if job["name"] == "collect"), None)

        persisted_rows = assigned_rows[run["run_number"]]
        purged_rows = assigned_removed_rows[run["run_number"]]
        capture_state = classify_run(
            conclusion=run.get("conclusion"),
            artifact_count=artifacts_payload.get("total_count", 0),
            persisted_row_count=len(persisted_rows),
            purged_invalid_row_count=len(purged_rows),
            eval_job_count=len(eval_jobs),
        )

        runs.append(
            {
                "run_number": run["run_number"],
                "run_id": run_id,
                "created_at": run["created_at"],
                "updated_at": run["updated_at"],
                "status": run["status"],
                "conclusion": run.get("conclusion"),
                "event": run["event"],
                "head_sha": run["head_sha"],
                "html_url": run["html_url"],
                "artifact_count": artifacts_payload.get("total_count", 0),
                "artifact_names": sorted(
                    artifact["name"]
                    for artifact in artifacts_payload.get("artifacts", [])
                ),
                "eval_job_count": len(eval_jobs),
                "eval_success_count": sum(
                    1 for job in eval_jobs if job["conclusion"] == "success"
                ),
                "eval_failure_count": sum(
                    1 for job in eval_jobs if job["conclusion"] == "failure"
                ),
                "collect_conclusion": collect_job["conclusion"]
                if collect_job
                else None,
                "persisted_row_count": len(persisted_rows),
                "persisted_samples": sum(row["samples"] for row in persisted_rows),
                "persisted_models": sorted(row["model"] for row in persisted_rows),
                "display_models": sorted(
                    {get_label(row["model"]) for row in persisted_rows}
                ),
                "purged_invalid_row_count": len(purged_rows),
                "capture_state": capture_state,
            }
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo": repo,
        "workflow": workflow,
        "summary": build_summary(runs, action_rows, baseline_rows),
        "runs": list(reversed(runs)),
    }
    output_file.write_text(json.dumps(payload, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="lucharo/eval-claude")
    parser.add_argument("--workflow", default="benchmark.yml")
    parser.add_argument("--output", type=Path, default=OUTPUT_FILE)
    args = parser.parse_args()
    export(args.repo, args.workflow, args.output)


if __name__ == "__main__":
    main()
