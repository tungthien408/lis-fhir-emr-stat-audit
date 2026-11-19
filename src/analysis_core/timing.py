"""M9-M11 timing calculations and descriptive statistics for E6 (plan 10.8, 11.1-11.2)."""
from __future__ import annotations

from math import ceil
import numpy as np
import pandas as pd
from .metrics import require_columns, check_unique


def nearest_rank(values, percentile: float = 0.95) -> float | None:
    """Nearest-rank: sorted X[ceil(p*n) - 1], p in (0, 1]. No interpolation."""
    if not 0 < percentile <= 1:
        raise ValueError("Percentile must lie in (0, 1]")
    numbers = np.asarray(list(values), dtype=float)
    if not np.isfinite(numbers).all():
        raise ValueError("Nearest-rank requires finite observations; remove missing after classifying")
    if len(numbers) == 0:
        return None
    return float(np.sort(numbers)[ceil(percentile * len(numbers)) - 1])


def duration_ms(start: pd.Series, end: pd.Series) -> pd.Series:
    """Parse offset-aware ISO8601 timestamps, normalize to UTC; never mix raw clinical charttime."""
    # Measured wall-clock timestamps MUST contain a timezone; no silent local/UTC assumption.
    for label, values in [("start", start), ("end", end)]:
        if not values.astype(str).str.match(r"^.*(?:Z|[+-][0-9]{2}:[0-9]{2})$").all():
            raise ValueError(f"{label}: missing timezone offset or timestamp; expected ISO8601 with Z/±HH:MM")
    start_utc = pd.to_datetime(start, errors="raise", utc=True, format="ISO8601")
    end_utc = pd.to_datetime(end, errors="raise", utc=True, format="ISO8601")
    if start_utc.isna().any() or end_utc.isna().any():
        raise ValueError("Successful measurement has missing start/end timestamp")
    delta = (end_utc - start_utc).dt.total_seconds() * 1000.0
    if (delta < 0).any():
        raise ValueError("Negative duration suggests clock or event-order error")
    return delta


def summarize(values) -> dict:
    v = np.asarray(list(values), dtype=float)
    if not np.isfinite(v).all():
        raise ValueError("Do not silently include NaNs/infinities in latency statistics")
    if len(v) == 0:
        return {"n": 0, "min_ms": None, "median_ms": None, "mean_ms": None,
                "p95_nearest_rank_ms": None, "max_ms": None}
    return {"n": int(len(v)), "min_ms": float(v.min()),
            "median_ms": float(np.median(v)), "mean_ms": float(v.mean()),
            "p95_nearest_rank_ms": nearest_rank(v, 0.95), "max_ms": float(v.max())}


def e6_run_summary(measurements: pd.DataFrame) -> pd.DataFrame:
    """Separate 3 repeated runs; ignore warmup in statistics but show counts.

    Failures/timeouts remain in their counts, not in latency as zero.
    INVALID_RUN requires a separately logged justification; is never a normal timeout.
    """
    fields = ["run_id", "case_id", "scenario", "is_warmup", "run_status",
              "outcome", "t0_publish_committed", "t1_verified_readback"]
    require_columns(measurements, fields, "E6/measurements")
    check_unique(measurements, ["run_id", "case_id"], "E6/measurements")
    if measurements[["run_id", "case_id", "scenario", "is_warmup"]].isna().any().any():
        raise ValueError("E6: missing scenario, warmup or logical identity")
    subset = measurements.loc[measurements["scenario"].eq("E6")].copy()
    if subset[["run_status", "outcome"]].isna().any().any():
        raise ValueError("E6: missing run status/outcome cannot silently disappear")
    allowed = {"SUCCESS", "FAIL", "TIMEOUT"}
    unknown = set(subset["outcome"].dropna().unique()) - allowed
    if unknown:
        raise ValueError(f"E6: unknown outcomes: {unknown}")
    if set(subset["run_status"].dropna().unique()) - {"VALID", "INVALID_RUN"}:
        raise ValueError("E6: unknown run_status")
    result = []
    for run_id, group in subset.groupby("run_id", sort=True):
        n_warmup = int(group["is_warmup"].eq(True).sum())
        recorded = group.loc[group["is_warmup"].eq(False)]
        n_invalid = int(recorded["run_status"].eq("INVALID_RUN").sum())
        valid = recorded.loc[recorded["run_status"].eq("VALID")]
        succeeded = valid.loc[valid["outcome"].eq("SUCCESS")]
        latencies = duration_ms(succeeded["t0_publish_committed"], succeeded["t1_verified_readback"])
        stat = summarize(latencies)
        result.append({"run_id": run_id, "warmup_excluded": n_warmup,
                       "n_scheduled_valid_runs": len(valid), "n_invalid_cases_excluded": n_invalid,
                       "n_success": len(succeeded), "n_fail": int(valid["outcome"].eq("FAIL").sum()),
                       "n_timeout": int(valid["outcome"].eq("TIMEOUT").sum()), **stat})
    return pd.DataFrame(result)


def m10_mapping_durations(measurements: pd.DataFrame) -> pd.Series:
    require_columns(measurements, ["mapping_started_at", "transformed_at"], "M10")
    return duration_ms(measurements["mapping_started_at"], measurements["transformed_at"])


def m11_recovery_durations(measurements: pd.DataFrame) -> pd.Series:
    require_columns(measurements, ["component_recovered_at", "t1_verified_readback"], "M11")
    return duration_ms(measurements["component_recovered_at"], measurements["t1_verified_readback"])
