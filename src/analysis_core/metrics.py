"""M1-M8, M12-M13 calculations grounded in experiment plan sections 11 and 14.

M9-M11 are durations, not proportions; see timing.py.
A single row represents one logical case/result, NOT one retry attempt.
The expected outcomes and comparison rules must be fixed BEFORE running an experiment.
"""

from __future__ import annotations

from dataclasses import dataclass
import pandas as pd


@dataclass(frozen=True)
class Metric:
    metric_id: str
    numerator: int
    denominator: int | None
    percentage: float | None
    note: str = ""

    def as_dict(self) -> dict:
        return {
            "metric_id": self.metric_id,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "percentage": self.percentage,
            "note": self.note,
        }


def require_columns(df: pd.DataFrame, columns: list[str] | tuple[str, ...], label: str) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(f"{label}: missing required column(s): {missing}")


def require_non_null(df: pd.DataFrame, cols: list[str], label: str) -> None:
    require_columns(df, cols, label)
    missing = [col for col in cols if df[col].isna().any()]
    if missing:
        raise ValueError(f"{label}: NULL in denominator-defining/key column(s): {missing}")


def check_unique(df: pd.DataFrame, keys: list[str], label: str) -> None:
    require_non_null(df, keys, label)
    duplicates = df.duplicated(subset=keys, keep=False)
    if bool(duplicates.any()):
        raise ValueError(f"{label}: duplicate logical keys {keys}; do not count retries as cases")


def _is_true(series: pd.Series) -> pd.Series:
    # Never coerce bool(np.nan) to True. A missing check is NOT a pass.
    return series.eq(True).fillna(False)


def _count(metric_id: str, numerator: int, denominator: int, note: str = "") -> Metric:
    if denominator < 0 or numerator < 0 or numerator > denominator:
        raise ValueError(f"{metric_id}: invalid numerator/denominator")
    return Metric(
        metric_id,
        numerator,
        denominator,
        None if denominator == 0 else 100.0 * numerator / denominator,
        note if denominator else (note + "; " if note else "") + "N/A: denominator is zero",
    )


def m1_e2e(cases: pd.DataFrame) -> Metric:
    """Valid scheduled logical results with verified E2E result within deadline / N."""
    cols = ["run_id", "case_id", "is_valid_input", "delivered", "readback_verified",
            "patient_match", "all_fields_match", "within_deadline"]
    require_columns(cases, cols, "M1/cases")
    check_unique(cases, ["run_id", "case_id"], "M1/cases")
    require_non_null(cases, ["is_valid_input"], "M1/cases")
    selected = cases.loc[_is_true(cases["is_valid_input"])]
    passed = pd.Series(True, index=selected.index)
    for col in ["delivered", "readback_verified", "patient_match", "all_fields_match", "within_deadline"]:
        passed &= _is_true(selected[col])
    return _count("M1", int(passed.sum()), len(selected), "HTTP 2xx alone does not pass")


def m2_field_accuracy(comparisons: pd.DataFrame) -> pd.DataFrame:
    """Return M2 per comparison stage, not an unlabelled pooled percentage."""
    cols = ["run_id", "case_id", "stage", "rule_id", "field_path", "applicable", "matches"]
    require_columns(comparisons, cols, "M2/comparisons")
    check_unique(comparisons, ["run_id", "case_id", "stage", "rule_id", "field_path"], "M2/comparisons")
    require_non_null(comparisons, ["applicable"], "M2/comparisons")
    stages = ["source_fhir", "fhir_target", "source_target"]
    unknown = set(comparisons["stage"].dropna().unique()) - set(stages)
    if unknown:
        raise ValueError(f"M2: unknown comparison stages {sorted(unknown)}")
    rows = []
    for stage in stages:
        applicable = comparisons.loc[comparisons["stage"].eq(stage) & _is_true(comparisons["applicable"])]
        result = _count("M2", int(_is_true(applicable["matches"]).sum()), len(applicable), f"stage={stage}")
        rows.append({**result.as_dict(), "stage": stage})
    return pd.DataFrame(rows)


def m3_completeness(comparisons: pd.DataFrame) -> Metric:
    """Presence at target / fields required from source. Zero is a PRESENT value."""
    cols = ["stage", "required_by_source", "target_present"]
    require_non_null(comparisons, cols, "M3/comparisons")
    rows = comparisons.loc[comparisons["stage"].eq("source_target") & _is_true(comparisons["required_by_source"])]
    return _count("M3", int(_is_true(rows["target_present"]).sum()), len(rows), "Presence, not semantic correctness")


def m4_wrong_patient(target_records: pd.DataFrame) -> int:
    cols = ["created_or_updated", "expected_patient_key", "patient_key"]
    require_columns(target_records, cols, "M4/target_records")
    rows = target_records.loc[_is_true(target_records["created_or_updated"])]
    if rows["expected_patient_key"].isna().any():
        raise ValueError("M4: independent oracle patient key missing")
    return int(rows["patient_key"].ne(rows["expected_patient_key"]).sum())


def m5_duplicate_target_records(target_records: pd.DataFrame) -> int:
    cols = ["run_id", "source_system", "source_result_id"]
    require_columns(target_records, cols, "M5/target_records")
    if target_records[cols].isna().any().any():
        raise ValueError("M5: missing business-key element")
    counts = target_records.groupby(cols, dropna=False).size()
    return int((counts - 1).clip(lower=0).sum())


def m6_false_success(transactions: pd.DataFrame) -> int:
    cols = ["run_id", "exchange_id", "ever_delivered", "oracle_match_at_confirmation"]
    require_columns(transactions, cols, "M6/transactions")
    check_unique(transactions, ["run_id", "exchange_id"], "M6/transactions")
    return int((_is_true(transactions["ever_delivered"]) & ~_is_true(transactions["oracle_match_at_confirmation"])).sum())


def m7_exception_handling(error_cases: pd.DataFrame) -> Metric:
    cols = ["run_id", "case_id", "is_error_case", "all_expected_behaviors_met"]
    require_columns(error_cases, cols, "M7/error_cases")
    check_unique(error_cases, ["run_id", "case_id"], "M7/error_cases")
    require_non_null(error_cases, ["is_error_case"], "M7/error_cases")
    rows = error_cases.loc[_is_true(error_cases["is_error_case"])]
    return _count("M7", int(_is_true(rows["all_expected_behaviors_met"]).sum()), len(rows), "Correct rejection counts as passing an error scenario")


def m8_fhir_validity(validations: pd.DataFrame) -> tuple[Metric, int]:
    cols = ["run_id", "case_id", "valid_input", "generated", "passed_all_scope_rules"]
    require_columns(validations, cols, "M8/validations")
    check_unique(validations, ["run_id", "case_id"], "M8/validations")
    require_non_null(validations, ["valid_input", "generated"], "M8/validations")
    eligible = validations.loc[_is_true(validations["valid_input"])]
    generated = eligible.loc[_is_true(eligible["generated"])]
    not_generated = len(eligible) - len(generated)
    return _count("M8", int(_is_true(generated["passed_all_scope_rules"]).sum()), len(generated), "Also report valid inputs with no generated resource"), not_generated


def m12_recovery(recovery_cases: pd.DataFrame) -> Metric:
    cols = ["run_id", "case_id", "recovery_required", "recovered_e2e"]
    require_columns(recovery_cases, cols, "M12/recovery_cases")
    check_unique(recovery_cases, ["run_id", "case_id"], "M12/recovery_cases")
    require_non_null(recovery_cases, ["recovery_required"], "M12/recovery_cases")
    rows = recovery_cases.loc[_is_true(recovery_cases["recovery_required"])]
    return _count("M12", int(_is_true(rows["recovered_e2e"]).sum()), len(rows), "Exhausted-budget scenarios must be reported separately")


def m13_requirement_coverage(requirements: pd.DataFrame) -> Metric:
    cols = ["requirement_id", "is_core", "evidence_verified_pass"]
    require_columns(requirements, cols, "M13/requirements")
    check_unique(requirements, ["requirement_id"], "M13/requirements")
    require_non_null(requirements, ["is_core"], "M13/requirements")
    rows = requirements.loc[_is_true(requirements["is_core"])]
    return _count("M13", int(_is_true(rows["evidence_verified_pass"]).sum()), len(rows), "Missing evidence is not a pass")


def audit_summary(cases: pd.DataFrame, comparisons: pd.DataFrame,
                  targets: pd.DataFrame, transactions: pd.DataFrame,
                  error_cases: pd.DataFrame, validations: pd.DataFrame,
                  recovery_cases: pd.DataFrame, requirements: pd.DataFrame) -> pd.DataFrame:
    """Example summary only. Does not infer validity or independently verify the oracle."""
    m8, not_generated = m8_fhir_validity(validations)
    collected = [m1_e2e(cases), m3_completeness(comparisons),
                 Metric("M4", m4_wrong_patient(targets), None, None, "Count; required zero"),
                 Metric("M5", m5_duplicate_target_records(targets), None, None, "Excess target rows; required zero"),
                 Metric("M6", m6_false_success(transactions), None, None, "Count; required zero"),
                 m7_exception_handling(error_cases), m8, m12_recovery(recovery_cases),
                 m13_requirement_coverage(requirements)]
    result = pd.DataFrame([x.as_dict() for x in collected])
    result.loc[result["metric_id"].eq("M8"), "note"] += f"; input without Observation={not_generated}"
    return result
