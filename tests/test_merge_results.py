import pytest

from scripts.merge_results import historical_lower_bound


def test_historical_lower_bound_uses_sample_standard_deviation():
    mean, lower_bound = historical_lower_bound([0.7, 0.9])

    assert mean == pytest.approx(0.8)
    assert lower_bound == pytest.approx(0.8 - 1.96 * (0.02**0.5))


def test_historical_lower_bound_requires_two_points():
    with pytest.raises(ValueError, match="at least two"):
        historical_lower_bound([0.8])
