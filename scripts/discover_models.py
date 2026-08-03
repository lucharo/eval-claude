"""Sync available Claude models from the Anthropic API into models.json.

Usage:
    # Check what changed (dry run)
    uv run python scripts/discover_models.py

    # Update models.json with the currently available models
    uv run python scripts/discover_models.py --update

Requires ANTHROPIC_API_KEY environment variable.
Models are removed only when listed in retired-models.json because the API-key
catalogue can differ from the Claude Code OAuth catalogue used by benchmarks.
"""

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

MODELS_FILE = Path(__file__).parent.parent / "models.json"
RETIRED_MODELS_FILE = Path(__file__).parent.parent / "retired-models.json"
API_BASE = "https://api.anthropic.com/v1/models"

# Only benchmark these model families
FAMILY_PATTERN = re.compile(r"^claude-(haiku|sonnet|opus)-\d[a-z0-9-]*$")


def fetch_models() -> list[str]:
    """Fetch available model IDs from the Anthropic API, handling pagination."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ANTHROPIC_API_KEY not set, cannot query models API", file=sys.stderr)
        sys.exit(1)

    all_models: list[str] = []
    url = f"{API_BASE}?{urllib.parse.urlencode({'limit': 100})}"

    while url:
        req = urllib.request.Request(
            url,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())

        for m in data.get("data", []):
            if FAMILY_PATTERN.fullmatch(m["id"]):
                all_models.append(m["id"])

        # Handle pagination
        if data.get("has_more") and data.get("last_id"):
            query = urllib.parse.urlencode({"limit": 100, "after_id": data["last_id"]})
            url = f"{API_BASE}?{query}"
        else:
            url = None

    return all_models


def load_current() -> list[str]:
    """Load current models from models.json."""
    with open(MODELS_FILE) as f:
        return json.load(f)


def load_retired() -> list[str]:
    """Load explicitly retired models confirmed unavailable to Claude Code."""
    with open(RETIRED_MODELS_FILE) as f:
        return json.load(f)


def write_github_output(key: str, value: str) -> None:
    """Write a newline-safe value to $GITHUB_OUTPUT if running in CI."""
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        delimiter = "eval_claude_output"
        if delimiter in value:
            raise ValueError("GitHub output value contains the output delimiter")
        with open(output_file, "a") as f:
            f.write(f"{key}<<{delimiter}\n{value}\n{delimiter}\n")


def main():
    update = "--update" in sys.argv

    current = set(load_current())
    available = set(fetch_models())
    retired = set(load_retired())

    new_models = sorted(available - current - retired)
    removed = sorted(current & retired)
    api_key_hidden = sorted(current - available - retired)

    if new_models:
        print(f"New models found: {', '.join(new_models)}")
    if removed:
        print(f"Explicitly retired models: {', '.join(removed)}")
    if api_key_hidden:
        print(
            "Models absent from the API-key catalogue but retained for the "
            f"Claude Code OAuth benchmark: {', '.join(api_key_hidden)}"
        )
    if not new_models and not removed:
        print("No changes — all models up to date")
        write_github_output("has_changes", "false")
        return

    if update:
        updated = sorted((current | set(new_models)) - retired)
        with open(MODELS_FILE, "w") as f:
            json.dump(updated, f, indent=2)
            f.write("\n")
        print(f"Updated {MODELS_FILE}: {len(new_models)} added, {len(removed)} removed")
        write_github_output("has_changes", "true")
        write_github_output("new_models", json.dumps(new_models))
        write_github_output("removed_models", json.dumps(removed))
    else:
        print("Run with --update to sync models.json")
        write_github_output("has_changes", "false")


if __name__ == "__main__":
    main()
