from types import SimpleNamespace

import pytest

from scripts import parse_eval


def test_parse_log_rejects_large_zero_accuracy_run(monkeypatch, capsys):
    score = SimpleNamespace(
        metrics={"accuracy": SimpleNamespace(value=0.0)},
    )
    log = SimpleNamespace(
        status="success",
        results=SimpleNamespace(scores=[score], completed_samples=10),
    )
    monkeypatch.setattr(parse_eval, "read_eval_log", lambda _: log)

    with pytest.raises(SystemExit) as exc:
        parse_eval.parse_log("result.eval")

    assert exc.value.code == 2
    assert "0% accuracy on 10 samples" in capsys.readouterr().err
