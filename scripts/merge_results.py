"""Merge new benchmark results into docs/data.json and check for regressions.

Usage:
    python scripts/merge_results.py /tmp/results

Reads result JSON files from the given directory (glob: */result.json),
appends them to docs/data.json, and prints GitHub Actions warnings if
any model's latest accuracy falls below its historical 95% CI.
"""

import json
import re
import sys
from pathlib import Path

DATA_FILE = Path(__file__).parent.parent / "docs" / "data.json"


def get_label(model: str) -> str:
    """Canonical label from model ID: 'claude-code/claude-sonnet-4-6' -> 'Sonnet 4.6'."""
    model_id = model.replace("claude-code/", "").replace("claude-", "")
    m = re.match(r"^(haiku|sonnet|opus)-(\d+)-(\d+)(?:-\d+)?$", model_id)
    if m:
        return f"{m.group(1).title()} {m.group(2)}.{m.group(3)}"
    if model_id in ("haiku", "sonnet", "opus"):
        return model_id.title()
    return model_id


def historical_lower_bound(accuracies: list[float]) -> tuple[float, float]:
    """Return the historical mean and its 95% lower prediction bound."""
    if len(accuracies) < 2:
        raise ValueError("at least two historical accuracies are required")

    mean_accuracy = sum(accuracies) / len(accuracies)
    variance = sum((accuracy - mean_accuracy) ** 2 for accuracy in accuracies) / (
        len(accuracies) - 1
    )
    standard_deviation = variance**0.5
    return mean_accuracy, mean_accuracy - 1.96 * standard_deviation


def merge(results_dir: str) -> None:
    with open(DATA_FILE) as f:
        data = json.load(f)

    existing_count = len(data)

    new_results = []
    for path in sorted(Path(results_dir).glob("*/result.json")):
        with open(path) as f:
            new_results.append(json.load(f))

    if not new_results:
        print("No new results to merge")
        return

    # Deduplicate: skip results with same (model, date) as existing entries
    existing_keys = {(d["model"], d["date"]) for d in data}
    deduped = [r for r in new_results if (r["model"], r["date"]) not in existing_keys]
    if len(deduped) < len(new_results):
        print(f"Skipped {len(new_results) - len(deduped)} duplicate result(s)")
    if not deduped:
        print("All results already exist in data.json")
        return

    data.extend(deduped)

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

    print(f"Merged {len(deduped)} new result(s) into {DATA_FILE}")

    # --- Nerf detection ---
    if existing_count < 2:
        return

    historical = data[:existing_count]
    by_label: dict[str, list[dict]] = {}
    for d in historical:
        label = get_label(d["model"])
        by_label.setdefault(label, []).append(d)

    for result in deduped:
        label = get_label(result["model"])
        prev = by_label.get(label, [])
        if len(prev) < 2:
            continue

        accs = [p["accuracy"] for p in prev]
        mean_acc, lower_bound = historical_lower_bound(accs)
        drop_pct = (
            (mean_acc - result["accuracy"]) / mean_acc * 100 if mean_acc > 0 else 0
        )

        if result["accuracy"] < lower_bound:
            print(
                f"::warning::{label} may be nerfed: "
                f"{result['accuracy'] * 100:.1f}% vs historical {mean_acc * 100:.1f}% "
                f"(drop of {drop_pct:.1f}%, below 95% CI lower bound {lower_bound * 100:.1f}%)"
            )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: merge_results.py <results-dir>", file=sys.stderr)
        sys.exit(1)
    merge(sys.argv[1])
