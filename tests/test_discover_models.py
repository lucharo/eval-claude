import json
import sys

from scripts import discover_models


def test_family_pattern_requires_versioned_model_id():
    assert discover_models.FAMILY_PATTERN.fullmatch("claude-sonnet-4-6")
    assert not discover_models.FAMILY_PATTERN.fullmatch("claude-sonnet-latest")
    assert not discover_models.FAMILY_PATTERN.fullmatch("claude-opus--")


def test_update_removes_explicitly_retired_models(tmp_path, monkeypatch):
    models_file = tmp_path / "models.json"
    models_file.write_text(json.dumps(["claude-current", "claude-retired"]))
    retired_file = tmp_path / "retired-models.json"
    retired_file.write_text(json.dumps(["claude-retired"]))
    output_file = tmp_path / "github-output"

    monkeypatch.setattr(discover_models, "MODELS_FILE", models_file)
    monkeypatch.setattr(discover_models, "RETIRED_MODELS_FILE", retired_file)
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


def test_update_retains_models_hidden_from_api_key_catalogue(tmp_path, monkeypatch):
    models_file = tmp_path / "models.json"
    models_file.write_text(json.dumps(["claude-oauth-only"]))
    retired_file = tmp_path / "retired-models.json"
    retired_file.write_text("[]")

    monkeypatch.setattr(discover_models, "MODELS_FILE", models_file)
    monkeypatch.setattr(discover_models, "RETIRED_MODELS_FILE", retired_file)
    monkeypatch.setattr(discover_models, "fetch_models", list)
    monkeypatch.setattr(sys, "argv", ["discover_models.py", "--update"])

    discover_models.main()

    assert json.loads(models_file.read_text()) == ["claude-oauth-only"]
