"""Create intentionally synthetic, deliberately imperfect sample evidence (never research data)."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sample_synthetic"
OUT.mkdir(parents=True, exist_ok=True)


def save(filename, rows):
    pd.DataFrame(rows).to_csv(OUT / filename, index=False)


save("patients.csv", [
    {"subject_id": 101, "gender": "F", "anchor_age": 60},
    {"subject_id": 102, "gender": "M", "anchor_age": 55},
    {"subject_id": 103, "gender": "F", "anchor_age": 70},
])
save("d_labitems.csv", [
    {"itemid": 501, "label": "SYNTHETIC_TEST_A", "fluid": "Blood", "category": "Chemistry"},
    {"itemid": 502, "label": "SYNTHETIC_TEST_B", "fluid": "Blood", "category": "Chemistry"},
])
save("labevents.csv", [
    {"labevent_id": 1, "subject_id": 101, "itemid": 501, "valuenum": "0", "valueuom": "unit-A", "charttime": "2026-10-01 10:00:00"},
    {"labevent_id": 2, "subject_id": 101, "itemid": 501, "valuenum": "12.3", "valueuom": "unit-A", "charttime": "2026-10-01 10:01:00"},
    {"labevent_id": 3, "subject_id": 102, "itemid": 502, "valuenum": "", "valueuom": "unit-B", "charttime": "2026-10-01 10:02:00"},
    {"labevent_id": 4, "subject_id": 999, "itemid": 501, "valuenum": "5", "valueuom": "unit-A", "charttime": "2026-10-01 10:03:00"},
    {"labevent_id": 5, "subject_id": 103, "itemid": 999, "valuenum": "3.2", "valueuom": "unit-B", "charttime": "2026-10-01 10:04:00"},
    {"labevent_id": 5, "subject_id": 103, "itemid": 502, "valuenum": "not-a-number", "valueuom": "unit-B", "charttime": "2026-10-01 10:05:00"},
])
save("cases.csv", [
    {"run_id": "demo-r1", "case_id": "E1-01", "scenario": "E1", "is_valid_input": True, "delivered": True, "readback_verified": True, "patient_match": True, "all_fields_match": True, "within_deadline": True},
    {"run_id": "demo-r1", "case_id": "E1-02", "scenario": "E1", "is_valid_input": True, "delivered": True, "readback_verified": True, "patient_match": False, "all_fields_match": False, "within_deadline": True},
    {"run_id": "demo-r1", "case_id": "E1-03", "scenario": "E1", "is_valid_input": True, "delivered": False, "readback_verified": False, "patient_match": False, "all_fields_match": False, "within_deadline": False},
    {"run_id": "demo-r1", "case_id": "E2-01", "scenario": "E2", "is_valid_input": False, "delivered": False, "readback_verified": False, "patient_match": False, "all_fields_match": False, "within_deadline": True},
    {"run_id": "demo-r1", "case_id": "E5a-01", "scenario": "E5", "is_valid_input": False, "delivered": False, "readback_verified": False, "patient_match": False, "all_fields_match": False, "within_deadline": True},
])
comps = []
for case in ["E1-01", "E1-02", "E1-03"]:
    for stage in ["source_fhir", "fhir_target", "source_target"]:
        for rule, field in [("MR01", "subject.identifier"), ("MR02", "value.value"), ("MR03", "value.unit")]:
            match = case == "E1-01" or (case == "E1-02" and rule != "MR01")
            if case == "E1-03": match = False
            present = (case != "E1-03")
            comps.append({"run_id":"demo-r1", "case_id":case,"stage":stage,
                          "rule_id":rule,"field_path":field,"applicable":True,
                          "matches":match,"required_by_source":True,"target_present":present})
save("comparisons.csv", comps)
save("target_records.csv", [
    {"run_id":"demo-r1", "source_system":"synthetic-lis", "source_result_id":"E1-01", "expected_patient_key":"patient-101", "patient_key":"patient-101", "created_or_updated":True},
    {"run_id":"demo-r1", "source_system":"synthetic-lis", "source_result_id":"E1-02", "expected_patient_key":"patient-102", "patient_key":"patient-103", "created_or_updated":True},
    {"run_id":"demo-r1", "source_system":"synthetic-lis", "source_result_id":"E1-02", "expected_patient_key":"patient-102", "patient_key":"patient-103", "created_or_updated":True},
])
save("transactions.csv", [
    {"run_id":"demo-r1","exchange_id":"x1","ever_delivered":True,"oracle_match_at_confirmation":True},
    {"run_id":"demo-r1","exchange_id":"x2","ever_delivered":True,"oracle_match_at_confirmation":False},
    {"run_id":"demo-r1","exchange_id":"x3","ever_delivered":False,"oracle_match_at_confirmation":False},
])
save("error_cases.csv", [
    {"run_id":"demo-r1", "case_id":"E2-01", "variant":"missing_patient", "is_error_case":True, "all_expected_behaviors_met":True},
    {"run_id":"demo-r1", "case_id":"E5a-01", "variant":"invalid_value", "is_error_case":True, "all_expected_behaviors_met":False},
])
save("fhir_validation.csv", [
    {"run_id":"demo-r1", "case_id":"E1-01","valid_input":True,"generated":True,"passed_all_scope_rules":True},
    {"run_id":"demo-r1", "case_id":"E1-02","valid_input":True,"generated":True,"passed_all_scope_rules":False},
    {"run_id":"demo-r1", "case_id":"E1-03","valid_input":True,"generated":False,"passed_all_scope_rules":False},
])
save("recovery_cases.csv", [
    {"run_id":"demo-r1", "case_id":"E4c-01","scenario":"E4", "recovery_required":True,"recovered_e2e":True},
    {"run_id":"demo-r1", "case_id":"E7a-01","scenario":"E7", "recovery_required":True,"recovered_e2e":True},
    {"run_id":"demo-r1", "case_id":"E8c-01","scenario":"E8", "recovery_required":True,"recovered_e2e":False},
    {"run_id":"demo-r1", "case_id":"E8d-01","scenario":"E8", "recovery_required":False,"recovered_e2e":False},
])
save("requirements.csv", [
    {"requirement_id":"REQ-DATA-01", "is_core":True,"evidence_verified_pass":True,"evidence_status":"PASS"},
    {"requirement_id":"REQ-OUTBOX-01", "is_core":True,"evidence_verified_pass":False,"evidence_status":"INSUFFICIENT_EVIDENCE"},
    {"requirement_id":"REQ-WORKER-01", "is_core":True,"evidence_verified_pass":False,"evidence_status":"FAIL"},
    {"requirement_id":"REQ-OPTIONAL-01", "is_core":False,"evidence_verified_pass":True,"evidence_status":"PASS"},
])

start = datetime(2026, 10, 19, 1, 0, 0, tzinfo=timezone.utc)
e6 = []
for ri in range(1, 4):
    for idx in range(1, 11):
        warmup = idx <= 5
        case_id = f"{'W' if warmup else 'M'}-{idx:02d}"
        t0 = start + timedelta(hours=ri, minutes=idx)
        outcome = "TIMEOUT" if ri == 3 and idx == 10 else "SUCCESS"
        ms = 125 + 7 * ri + 12 * idx
        end = t0 + timedelta(milliseconds=ms) if outcome == "SUCCESS" else None
        map_start = t0 + timedelta(milliseconds=10)
        map_end = map_start + timedelta(milliseconds=3 + ri)
        e6.append({"run_id":f"e6-r{ri}","case_id":case_id,"scenario":"E6", "is_warmup":warmup,
                   "run_status":"VALID", "outcome":outcome,
                   "t0_publish_committed":t0.isoformat(),
                   "t1_verified_readback":end.isoformat() if end else "",
                   "mapping_started_at":map_start.isoformat() if outcome == "SUCCESS" else "",
                   "transformed_at":map_end.isoformat() if outcome == "SUCCESS" else ""})
save("e6_timings.csv", e6)
recovery_timings = []
for i,(scenario, ms) in enumerate([("E4",1000),("E7",2200),("E8",3000)]):
    recovered = start + timedelta(hours=7, minutes=i)
    verified = recovered + timedelta(milliseconds=ms)
    recovery_timings.append({"run_id":"recovery-r1", "case_id":f"{scenario}-demo", "scenario":scenario,
                             "component_recovered_at": recovered.isoformat(),
                             "t1_verified_readback": verified.isoformat(),
                             "t0_publish_committed": (recovered - timedelta(seconds=15)).isoformat()})
save("recovery_timings.csv", recovery_timings)
print(f"Generated sample synthetic fixtures in {OUT}")
