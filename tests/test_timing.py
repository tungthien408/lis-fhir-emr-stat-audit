from pathlib import Path
import pandas as pd
import pytest
from analysis_core.timing import nearest_rank, summarize, e6_run_summary, duration_ms, m10_mapping_durations, m11_recovery_durations

DATA = Path(__file__).resolve().parents[1] / "data" / "sample_synthetic"


def test_nearest_rank_p95_not_linear_interpolation():
    values = list(range(1, 11))
    assert nearest_rank(values) == 10.0
    assert pd.Series(values).quantile(.95) != nearest_rank(values)
    assert nearest_rank([]) is None


def test_nearest_rank_rejects_missing():
    with pytest.raises(ValueError, match="finite"):
        nearest_rank([1.0, float("nan")])


def test_e6_reports_three_independent_runs_and_keeps_timeout():
    inputs = pd.read_csv(DATA / "e6_timings.csv")
    summary = e6_run_summary(inputs)
    assert len(summary) == 3
    assert summary["warmup_excluded"].tolist() == [5, 5, 5]
    assert summary["n_success"].tolist() == [5, 5, 4]
    assert summary["n_timeout"].tolist() == [0, 0, 1]
    assert summary["n"].tolist() == [5, 5, 4]
    assert summary["n_scheduled_valid_runs"].tolist() == [5, 5, 5]
    assert (summary["min_ms"] > 0).all()


def test_invalid_order_timestamps_raise_error():
    start = pd.Series(["2026-10-19T10:00:01+00:00"])
    end = pd.Series(["2026-10-19T10:00:00+00:00"])
    with pytest.raises(ValueError, match="Negative"):
        duration_ms(start, end)


def test_m10_and_m11_use_respective_clocks():
    e6 = pd.read_csv(DATA / "e6_timings.csv")
    valid = e6.loc[e6["outcome"].eq("SUCCESS") & ~e6["is_warmup"]]
    mapping = m10_mapping_durations(valid)
    assert len(mapping) == 14
    assert float(mapping.min()) >= 4
    recovery = pd.read_csv(DATA / "recovery_timings.csv")
    assert m11_recovery_durations(recovery).round().tolist() == [1000, 2200, 3000]


def test_naive_timestamps_are_rejected_instead_of_assuming_utc():
    with pytest.raises(ValueError, match="timezone"):
        duration_ms(pd.Series(["2026-10-19 10:00:00"]), pd.Series(["2026-10-19 10:00:01"]))
