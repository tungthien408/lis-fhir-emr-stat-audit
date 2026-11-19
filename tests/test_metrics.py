from pathlib import Path
import pandas as pd
import pytest
from analysis_core.metrics import (
    m1_e2e, m2_field_accuracy, m3_completeness, m4_wrong_patient,
    m5_duplicate_target_records, m6_false_success, m7_exception_handling,
    m8_fhir_validity, m12_recovery, m13_requirement_coverage,
)

DATA = Path(__file__).resolve().parents[1] / "data" / "sample_synthetic"

def read(name):
    return pd.read_csv(DATA / name)


def test_m1_denominator_is_valid_logical_results_not_attempts():
    metric = m1_e2e(read("cases.csv"))
    assert (metric.numerator, metric.denominator, round(metric.percentage, 6)) == (1, 3, round(100/3, 6))


def test_m1_duplicate_logical_case_is_error():
    cases = read("cases.csv")
    cases = pd.concat([cases, cases.iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate"):
        m1_e2e(cases)


def test_m2_stages_are_not_silently_combined():
    result = m2_field_accuracy(read("comparisons.csv"))
    assert set(result["stage"]) == {"source_fhir", "fhir_target", "source_target"}
    assert (result["numerator"] == 5).all()
    assert (result["denominator"] == 9).all()


def test_m3_presence_is_separate_from_correctness():
    comp = read("comparisons.csv")
    metric = m3_completeness(comp)
    assert (metric.numerator, metric.denominator) == (6, 9)
    # A present but wrong patient field is counted present for M3, but wrong for M2.
    wrong_patient = comp.loc[(comp["case_id"] == "E1-02") & (comp["stage"] == "source_target") & (comp["rule_id"] == "MR01")]
    assert wrong_patient["target_present"].iloc[0] == True
    assert wrong_patient["matches"].iloc[0] == False


def test_m4_m5_m6_count_separate_failures():
    assert m4_wrong_patient(read("target_records.csv")) == 2  # two bad rows
    assert m5_duplicate_target_records(read("target_records.csv")) == 1  # one excess row
    assert m6_false_success(read("transactions.csv")) == 1


def test_error_and_fhir_and_recovery_rates():
    m7 = m7_exception_handling(read("error_cases.csv"))
    assert (m7.numerator, m7.denominator) == (1, 2)
    m8, absent = m8_fhir_validity(read("fhir_validation.csv"))
    assert (m8.numerator, m8.denominator, absent) == (1, 2, 1)
    m12 = m12_recovery(read("recovery_cases.csv"))
    assert (m12.numerator, m12.denominator) == (2, 3)
    m13 = m13_requirement_coverage(read("requirements.csv"))
    assert (m13.numerator, m13.denominator) == (1, 3)


def test_empty_denominator_returns_na_not_zero_percent():
    empty = read("cases.csv").iloc[0:0]
    result = m1_e2e(empty)
    assert result.denominator == 0
    assert result.percentage is None
    assert "N/A" in result.note


def test_unknown_denominator_classification_is_not_silently_excluded():
    cases = read("cases.csv")
    cases["is_valid_input"] = cases["is_valid_input"].astype(object)
    cases.loc[0, "is_valid_input"] = None
    with pytest.raises(ValueError, match="NULL"):
        m1_e2e(cases)
