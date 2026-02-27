"""Parse an inspect_ai eval log and output JSON result."""

import json
import sys
from pathlib import Path

from inspect_ai.log import read_eval_log


def parse_log(log_path: str) -> dict:
    log = read_eval_log(log_path)

    # Extract accuracy and stderr from scores
    accuracy = None
    stderr = None
    for score in log.results.scores:
        if "accuracy" in score.metrics:
            accuracy = score.metrics["accuracy"].value
        if "stderr" in score.metrics:
            stderr = score.metrics["stderr"].value

    # Extract timing
    started = log.stats.started_at
    completed = log.stats.completed_at

    # Calculate duration in seconds
    from datetime import datetime, timezone

    start_dt = datetime.fromisoformat(started)
    end_dt = datetime.fromisoformat(completed)
    duration_seconds = (end_dt - start_dt).total_seconds()

    # Extract token usage
    total_tokens = 0
    for usage in log.stats.model_usage.values():
        total_tokens += usage.total_tokens

    return {
        "date": start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": log.eval.model,
        "task": log.eval.task,
        "accuracy": accuracy,
        "stderr": stderr,
        "duration_seconds": int(duration_seconds),
        "total_tokens": total_tokens,
        "samples": log.results.completed_samples,
    }


def find_latest_log(logs_dir: str = "logs") -> str | None:
    logs = sorted(Path(logs_dir).glob("*.eval"))
    return str(logs[-1]) if logs else None


if __name__ == "__main__":
    if len(sys.argv) > 1:
        log_path = sys.argv[1]
    else:
        log_path = find_latest_log()
        if not log_path:
            print("No eval logs found", file=sys.stderr)
            sys.exit(1)

    result = parse_log(log_path)
    print(json.dumps(result))
