from pathlib import Path
import importlib.util


SPEC = importlib.util.spec_from_file_location(
    "export_run_ledger",
    Path(__file__).parent.parent / "scripts" / "export_run_ledger.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_get_label_harmonizes_alias_and_full_id() -> None:
    assert MODULE.get_label("claude-code/sonnet") == "Sonnet"
    assert MODULE.get_label("claude-code/claude-sonnet-4-5-20250929") == "Sonnet 4.5"


def test_assign_rows_to_runs_uses_run_windows() -> None:
    runs = [
        {"run_number": 1, "created_at": "2026-04-01T06:00:00Z"},
        {"run_number": 2, "created_at": "2026-04-01T18:00:00Z"},
    ]
    rows = [
        {
            "date": "2026-04-01T06:10:00Z",
            "model": "claude-code/claude-sonnet-4-6",
            "samples": 50,
        },
        {
            "date": "2026-04-01T17:59:59Z",
            "model": "claude-code/claude-opus-4-6",
            "samples": 50,
        },
        {
            "date": "2026-04-01T18:10:00Z",
            "model": "claude-code/claude-haiku-4-5-20251001",
            "samples": 50,
        },
    ]

    assignments = MODULE.assign_rows_to_runs(runs, rows)

    assert [row["model"] for row in assignments[1]] == [
        "claude-code/claude-sonnet-4-6",
        "claude-code/claude-opus-4-6",
    ]
    assert [row["model"] for row in assignments[2]] == [
        "claude-code/claude-haiku-4-5-20251001"
    ]


def test_classify_run_distinguishes_capture_states() -> None:
    assert (
        MODULE.classify_run(
            conclusion="success",
            artifact_count=5,
            persisted_row_count=5,
            purged_invalid_row_count=0,
            eval_job_count=5,
        )
        == "captured"
    )
    assert (
        MODULE.classify_run(
            conclusion="success",
            artifact_count=0,
            persisted_row_count=0,
            purged_invalid_row_count=0,
            eval_job_count=5,
        )
        == "missing"
    )
    assert (
        MODULE.classify_run(
            conclusion="success",
            artifact_count=0,
            persisted_row_count=0,
            purged_invalid_row_count=2,
            eval_job_count=5,
        )
        == "purged-invalid"
    )
