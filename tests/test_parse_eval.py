from types import SimpleNamespace

import pytest

from scripts import parse_eval


def make_log(accuracy=0.0, samples=None):
    score = SimpleNamespace(
        metrics={"accuracy": SimpleNamespace(value=accuracy)},
    )
    return SimpleNamespace(
        status="success",
        results=SimpleNamespace(
            scores=[score],
            completed_samples=10,
            total_samples=10,
        ),
        samples=samples or [],
        stats=SimpleNamespace(
            started_at="2026-08-03T10:00:00+00:00",
            completed_at="2026-08-03T10:10:00+00:00",
            model_usage={
                "claude": SimpleNamespace(
                    input_tokens=1000,
                    output_tokens=10000,
                    total_tokens=11000,
                )
            },
        ),
        eval=SimpleNamespace(model="claude-code/sonnet", task="gpqa"),
    )


def test_parse_log_preserves_large_zero_accuracy_run(monkeypatch):
    monkeypatch.setattr(parse_eval, "read_eval_log", lambda _: make_log())

    result = parse_eval.parse_log("result.eval")

    assert result["accuracy"] == 0.0


def test_parse_log_rejects_explicit_sample_error(monkeypatch, capsys):
    failed_sample = SimpleNamespace(error="scorer failed", invalidation=None)
    log = make_log(samples=[failed_sample])
    monkeypatch.setattr(parse_eval, "read_eval_log", lambda _: log)

    with pytest.raises(SystemExit) as exc:
        parse_eval.parse_log("result.eval")

    assert exc.value.code == 2
    assert "explicit errors" in capsys.readouterr().err


def test_parse_log_rejects_explicit_sample_invalidation(monkeypatch, capsys):
    invalid_sample = SimpleNamespace(error=None, invalidation="invalid scorer output")
    log = make_log(samples=[invalid_sample])
    monkeypatch.setattr(parse_eval, "read_eval_log", lambda _: log)

    with pytest.raises(SystemExit) as exc:
        parse_eval.parse_log("result.eval")

    assert exc.value.code == 2
    assert "invalidation signals" in capsys.readouterr().err


def test_parse_log_rejects_incomplete_run(monkeypatch, capsys):
    log = make_log()
    log.results.completed_samples = 9
    monkeypatch.setattr(parse_eval, "read_eval_log", lambda _: log)

    with pytest.raises(SystemExit) as exc:
        parse_eval.parse_log("result.eval")

    assert exc.value.code == 2
    assert "9 of 10 samples completed" in capsys.readouterr().err
