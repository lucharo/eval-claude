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
    id = model.replace("claude-code/", "").replace("claude-", "")
    m = re.match(r"^(haiku|sonnet|opus)-(\d+)-(\d+)(?:-\d+)?$", id)
    if m:
        return f"{m.group(1).title()} {m.group(2)}.{m.group(3)}"
    if id in ("haiku", "sonnet", "opus"):
        return id.title()
    return id


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

    data.extend(new_results)

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

    print(f"Merged {len(new_results)} new result(s) into {DATA_FILE}")

    # --- Nerf detection ---
    if existing_count < 2:
        return

    historical = data[:existing_count]
    by_label: dict[str, list[dict]] = {}
    for d in historical:
        label = get_label(d["model"])
        by_label.setdefault(label, []).append(d)

    for result in new_results:
        label = get_label(result["model"])
        prev = by_label.get(label, [])
        if len(prev) < 2:
            continue

        accs = [p["accuracy"] for p in prev]
        mean_acc = sum(accs) / len(accs)
        stderrs = [p.get("stderr", 0) for p in prev]
        avg_stderr = sum(stderrs) / len(stderrs)

        lower_bound = mean_acc - 1.96 * avg_stderr
        drop_pct = (mean_acc - result["accuracy"]) / mean_acc * 100 if mean_acc > 0 else 0

        if result["accuracy"] < lower_bound:
            print(
                f"::warning::{label} may be nerfed: "
                f"{result['accuracy']*100:.1f}% vs historical {mean_acc*100:.1f}% "
                f"(drop of {drop_pct:.1f}%, below 95% CI lower bound {lower_bound*100:.1f}%)"
            )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: merge_results.py <results-dir>", file=sys.stderr)
        sys.exit(1)
    merge(sys.argv[1])
