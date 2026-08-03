import json
import sys

from scripts import discover_models


def test_update_removes_unavailable_models(tmp_path, monkeypatch):
    models_file = tmp_path / "models.json"
    models_file.write_text(json.dumps(["claude-current", "claude-retired"]))
    output_file = tmp_path / "github-output"

    monkeypatch.setattr(discover_models, "MODELS_FILE", models_file)
    monkeypatch.setattr(discover_models, "fetch_models", lambda: ["claude-current"])
    monkeypatch.setattr(sys, "argv", ["discover_models.py", "--update"])
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

    discover_models.main()

    assert json.loads(models_file.read_text()) == ["claude-current"]
    outputs = output_file.read_text()
    assert "has_changes" in outputs
    assert "true" in outputs
    assert "removed_models" in outputs
    assert '"claude-retired"' in outputs
