"""MIMIC-IV Demo CSV profiling, not a clinical interpretation or dataset cleanser."""
from __future__ import annotations
from pathlib import Path
import pandas as pd
from .metrics import require_columns


def load_csv(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"CSV absent: {path} (set real paths explicitly)")
    return pd.read_csv(path, low_memory=False)


def missingness(df: pd.DataFrame, table_name: str) -> pd.DataFrame:
    return pd.DataFrame({"table": table_name, "column": df.columns,
                         "missing_count": df.isna().sum().to_numpy(),
                         "total_rows": len(df)})


def profile_mimic_like(patients: pd.DataFrame, labevents: pd.DataFrame,
                       d_labitems: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Three explicit outputs: table counts, missing values, and referential/data issues.

    Diagnostic only: do not silently drop unmatched records or fix data types.
    """
    require_columns(patients, ["subject_id"], "patients")
    require_columns(labevents, ["subject_id", "itemid", "labevent_id", "valuenum"], "labevents")
    require_columns(d_labitems, ["itemid", "label"], "d_labitems")
    tables = {"patients": patients, "labevents": labevents, "d_labitems": d_labitems}
    summary = pd.DataFrame([
        {"table": name, "rows": len(df),
         "unique_subject_id": df["subject_id"].nunique(dropna=True) if "subject_id" in df else None,
         "unique_itemid": df["itemid"].nunique(dropna=True) if "itemid" in df else None}
        for name, df in tables.items()
    ])
    missing = pd.concat([missingness(df, name) for name, df in tables.items()], ignore_index=True)
    valuenum = labevents["valuenum"]
    invalid_numbers = (valuenum.notna() & pd.to_numeric(valuenum, errors="coerce").isna()).sum()
    issues = pd.DataFrame([
        {"check": "duplicate_patient_subject_id", "count": int(patients["subject_id"].duplicated(keep="first").sum())},
        {"check": "duplicate_labevent_id", "count": int(labevents["labevent_id"].duplicated(keep="first").sum())},
        {"check": "duplicate_d_labitems_itemid", "count": int(d_labitems["itemid"].duplicated(keep="first").sum())},
        {"check": "labevents_patient_not_found", "count": int((~labevents["subject_id"].isin(patients["subject_id"])).sum())},
        {"check": "labevents_itemid_not_found", "count": int((~labevents["itemid"].isin(d_labitems["itemid"])).sum())},
        {"check": "labevents_invalid_nonempty_valuenum", "count": int(invalid_numbers)},
    ])
    return summary, missing, issues
