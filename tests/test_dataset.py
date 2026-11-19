from pathlib import Path
import pandas as pd
import pytest
from analysis_core.dataset import load_csv, profile_mimic_like

DATA = Path(__file__).resolve().parents[1] / "data" / "sample_synthetic"


def test_synthetic_data_flags_known_issues():
    tables = [load_csv(DATA / name) for name in ["patients.csv", "labevents.csv", "d_labitems.csv"]]
    summary, missing, issues = profile_mimic_like(*tables)
    assert summary.set_index("table").loc["labevents", "rows"] == 6
    by_check = issues.set_index("check")["count"]
    assert by_check["duplicate_labevent_id"] == 1
    assert by_check["labevents_patient_not_found"] == 1
    assert by_check["labevents_itemid_not_found"] == 1
    assert by_check["labevents_invalid_nonempty_valuenum"] == 1
    assert missing.loc[(missing["table"] == "labevents") & (missing["column"] == "valuenum"), "missing_count"].iloc[0] == 1


def test_absent_real_csv_is_explicit_error():
    with pytest.raises(FileNotFoundError):
        load_csv(DATA / "no-such-dataset.csv")
