"""Check for new Claude models via the Anthropic API and update models.json.

Usage:
    # Check what's new (dry run)
    uv run python scripts/discover_models.py

    # Update models.json with new models
    uv run python scripts/discover_models.py --update

Requires ANTHROPIC_API_KEY environment variable.
Falls back to CLAUDE_CODE_OAUTH_TOKEN if available.
"""

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

MODELS_FILE = Path(__file__).parent.parent / "models.json"
API_URL = "https://api.anthropic.com/v1/models?limit=100"

# Only benchmark these model families
FAMILY_PATTERN = re.compile(r"^claude-(haiku|sonnet|opus)-\d")


def fetch_models() -> list[str]:
    """Fetch available model IDs from the Anthropic API."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("ANTHROPIC_API_KEY not set, cannot query models API", file=sys.stderr)
        sys.exit(1)

    req = urllib.request.Request(
        API_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())

    return [m["id"] for m in data.get("data", []) if FAMILY_PATTERN.match(m["id"])]


def load_current() -> list[str]:
    """Load current models from models.json."""
    with open(MODELS_FILE) as f:
        return json.load(f)


def main():
    update = "--update" in sys.argv

    current = set(load_current())
    available = set(fetch_models())

    new_models = sorted(available - current)
    removed = sorted(current - available)

    if new_models:
        print(f"New models found: {', '.join(new_models)}")
    if removed:
        print(f"Models no longer available: {', '.join(removed)}")
    if not new_models and not removed:
        print("No changes — all models up to date")
        return

    if update and new_models:
        updated = sorted(current | set(new_models))
        with open(MODELS_FILE, "w") as f:
            json.dump(updated, f, indent=2)
            f.write("\n")
        print(f"Updated {MODELS_FILE} with {len(new_models)} new model(s)")
    elif new_models:
        print("Run with --update to add them to models.json")


if __name__ == "__main__":
    main()
