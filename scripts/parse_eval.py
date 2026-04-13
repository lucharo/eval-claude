"""Parse an inspect_ai eval log and output JSON result.

Exits with code 2 if the run hit usage limits or produced no valid results.
CI should check the exit code and skip publishing on failure.
"""

import json
import sys
from pathlib import Path

from inspect_ai.log import read_eval_log


def parse_log(log_path: str) -> dict:
    log = read_eval_log(log_path)

    # Check for eval-level errors (rate limits, auth failures, etc.)
    if log.status != "success":
        error_msg = getattr(log, "error", None) or log.status
        print(f"SKIP: eval status is '{log.status}': {error_msg}", file=sys.stderr)
        sys.exit(2)

    if not log.results or not log.results.scores:
        print("SKIP: no results/scores in eval log", file=sys.stderr)
        sys.exit(2)

    # Extract accuracy and stderr from scores
    accuracy = None
    stderr = None
    for score in log.results.scores:
        if "accuracy" in score.metrics:
            accuracy = score.metrics["accuracy"].value
        if "stderr" in score.metrics:
            stderr = score.metrics["stderr"].value

    if accuracy is None:
        print("SKIP: no accuracy metric found", file=sys.stderr)
        sys.exit(2)

    completed = log.results.completed_samples or 0
    if completed == 0:
        print("SKIP: 0 completed samples", file=sys.stderr)
        sys.exit(2)

    # Sanity check: if accuracy is 0% with many samples, likely an auth/limit failure
    if accuracy == 0.0 and completed >= 10:
        print(f"SKIP: 0% accuracy on {completed} samples — likely auth or rate limit failure", file=sys.stderr)
        sys.exit(2)

    # Extract timing
    started = log.stats.started_at
    completed_at = log.stats.completed_at

    from datetime import datetime

    start_dt = datetime.fromisoformat(started)
    end_dt = datetime.fromisoformat(completed_at)
    duration_seconds = (end_dt - start_dt).total_seconds()

    # Extract token usage
    input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    for usage in log.stats.model_usage.values():
        input_tokens += usage.input_tokens
        output_tokens += usage.output_tokens
        total_tokens += usage.total_tokens

    # Guard against hidden failure modes (weekly usage-cap hits, auth errors
    # returned as short text content, etc.). Real gpqa_diamond runs produce
    # ~2000+ output tokens per sample with CoT reasoning; anything below ~1000
    # almost always indicates the CLI short-circuited and should not be
    # captured as a legitimate benchmark result.
    MIN_OUTPUT_TOKENS_PER_SAMPLE = 1000
    out_per_sample = output_tokens / completed
    if out_per_sample < MIN_OUTPUT_TOKENS_PER_SAMPLE:
        print(
            f"SKIP: {out_per_sample:.0f} output tokens/sample < "
            f"{MIN_OUTPUT_TOKENS_PER_SAMPLE} — likely usage limit or auth failure",
            file=sys.stderr,
        )
        sys.exit(2)

    return {
        "date": start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": log.eval.model,
        "task": log.eval.task,
        "accuracy": accuracy,
        "stderr": stderr,
        "duration_seconds": int(duration_seconds),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "samples": completed,
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
