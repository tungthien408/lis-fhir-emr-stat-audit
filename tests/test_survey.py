"""Test tính lại số liệu báo cáo, dùng bảng nhỏ tự tạo (không dùng dữ liệu MIMIC thật)."""
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from analysis_core import survey

ROOT = Path(__file__).resolve().parents[1]

LAB_COLS = ["labevent_id", "subject_id", "hadm_id", "specimen_id", "itemid", "order_provider_id", "charttime", "storetime",
            "value", "valuenum", "valueuom", "ref_range_lower", "ref_range_upper", "flag", "priority", "comments"]
ADM_COLS = ["subject_id", "hadm_id", "admittime", "dischtime", "deathtime", "admission_type", "admit_provider_id",
            "admission_location", "discharge_location", "insurance", "language", "marital_status", "race", "edregtime",
            "edouttime", "hospital_expire_flag"]


def lab_row(**over):
    row = dict.fromkeys(LAB_COLS, "")
    row.update(labevent_id="1", subject_id="1", hadm_id="10", specimen_id="5", itemid="100", charttime="2100-01-01 08:00:00",
               storetime="2100-01-01 09:00:00", value="4.1", valuenum="4.1", valueuom="mEq/L")
    row.update(over)
    return row


def tables():
    patients = pd.DataFrame({"subject_id": ["1", "2"], "gender": ["F", "M"], "anchor_age": ["40", "91"],
                             "anchor_year": ["2100", "2100"], "anchor_year_group": ["2008 - 2010"] * 2, "dod": ["", "2105-01-01"]})
    adm_row = dict.fromkeys(ADM_COLS, "x")
    admissions = pd.DataFrame([{**adm_row, "subject_id": "1", "hadm_id": "10", "admittime": "2100-01-01 00:00:00",
                                "dischtime": "2100-01-05 00:00:00", "deathtime": "", "language": "?"},
                               {**adm_row, "subject_id": "2", "hadm_id": "11", "admittime": "2100-02-01 00:00:00",
                                "dischtime": "2100-02-02 00:00:00", "deathtime": "", "language": "ENGLISH"}])
    d_labitems = pd.DataFrame({"itemid": ["100", "200", "300"], "label": ["Potassium", "Protein", " "],
                               "fluid": ["Blood", "Urine", "Blood"], "category": ["Chemistry", "Hematology", "Chemistry"]})
    labevents = pd.DataFrame([
        lab_row(labevent_id="1"),
        lab_row(labevent_id="2", valueuom=" ", storetime=""),                       # đơn vị chỉ có khoảng trắng
        lab_row(labevent_id="3", valueuom="N/A", value="___", valuenum="", hadm_id="", comments="___"),
        lab_row(labevent_id="4", itemid="200", subject_id="2", hadm_id="11", value=">300", valuenum="300", valueuom="mg/dL"),
        lab_row(labevent_id="5", itemid="200", subject_id="2", hadm_id="11", value="30", valuenum="30", valueuom="mg/dL",
                ref_range_lower="0", ref_range_upper="0"),
        lab_row(labevent_id="6", value="-2", valuenum="-2"),
    ], columns=LAB_COLS).astype("string")
    return {"patients": patients.astype("string"), "admissions": admissions.astype("string"),
            "d_labitems": d_labitems.astype("string"), "labevents": labevents}


def entry(entries, muc, ten):
    return next(e.value for e in entries if e.muc == muc and e.ten == ten)


def test_missing_counts_whitespace_but_not_placeholders():
    t = tables()
    assert survey.n_missing(t["labevents"], "valueuom") == 1          # chỉ ô " "; "N/A" không tính là thiếu
    assert survey.n_missing(t["labevents"], "storetime") == 1
    assert survey.n_missing(t["d_labitems"], "label") == 1            # label " "


def test_unit_counts_text_orders_by_count_and_handles_none():
    s = pd.Series(["mg/dL", "N/A", "mg/dL", " ", ""], dtype="string")
    assert survey.unit_counts_text(s) == "mg/dL (2); N/A (1)"
    assert survey.unit_counts_text(pd.Series(["", " "], dtype="string")) == "Không có"


def test_muc_2_numbers():
    e = survey.muc_2_mo_ta_bang(tables())
    assert entry(e, "2.2", "d_labitems.label: thiếu") == 1
    assert entry(e, "2.2", "d_labitems: số itemid có trong labevents") == 2
    assert entry(e, "2.2", "d_labitems: số itemid không có kết quả trong labevents") == 1
    assert entry(e, "2.3", "labevents.valueuom: thiếu") == 1
    assert entry(e, "2.3", "labevents.hadm_id: thiếu") == 1
    assert entry(e, "2.4", "admissions.language: số dòng ghi dấu ?") == 1
    assert entry(e, "2.1", "patients.dod: thiếu") == 1
    assert entry(e, "2.1", "patients: số bệnh nhân có anchor_age > 89 nhưng khác 91") == 0


def test_value_kinds_and_zero_negative():
    e = survey.muc_4_3_gia_tri(tables())
    assert entry(e, "4.3", "value số thuần: số dòng") == 4      # 4.1, 4.1, 30, -2
    assert entry(e, "4.3", "value có dấu so sánh: số dòng") == 1
    assert entry(e, "4.3", "value có chữ hoặc ký hiệu, không có dấu so sánh: số dòng") == 1
    assert entry(e, "4.3", "value rỗng: số dòng") == 0
    assert entry(e, "4.3", "tổng bốn dạng value") == 6
    assert entry(e, "4.3", "valuenum âm: số dòng") == 1
    assert entry(e, "4.3", "value = ___: số dòng") == 1


def test_values_match_rules():
    assert survey.values_match("91.10", 91.1)
    assert survey.values_match("296.3", 296.34)
    assert survey.values_match("0.01", 0.005)               # làm tròn lên ở .5
    assert survey.values_match("14381", 14381)
    assert not survey.values_match("16203", 14381)          # số nguyên phải bằng nhau tuyệt đối
    assert not survey.values_match("296.3", 296.4)          # số thực: khác ở chữ số thập phân báo cáo ghi
    assert not survey.values_match("", 4)                   # ô trống của báo cáo không khớp
    assert survey.values_match("abc", "abc") and not survey.values_match("abc", "abd")


def test_compare_with_report_flags_mismatch_and_extras():
    entries = [survey.Entry("2.3", "valueuom: thiếu", 14381, "survey.f"), survey.Entry("2.2", "label: thiếu", 4, "survey.f"),
               survey.Entry("4.2", "chỉ có trong code", 7, "survey.g")]
    report = pd.DataFrame({"muc_bao_cao": ["2.3", "2.2", "9", "2.3"], "ten_so_lieu": ["valueuom: thiếu", "label: thiếu", "không có hàm", "x"],
                           "gia_tri_trong_bao_cao": ["16203", "", "5", "1"]})
    main, extra = survey.compare_with_report(entries, report)
    assert list(main.columns) == ["muc_bao_cao", "ten_so_lieu", "gia_tri_trong_bao_cao", "gia_tri_tu_code", "khop", "noi_tinh"]
    assert list(main["khop"]) == ["không", "không", "không", "không"]
    assert main.loc[0, "gia_tri_tu_code"] == "14381" and main.loc[1, "gia_tri_tu_code"] == "4"
    assert main.loc[2, "noi_tinh"] == "chưa có hàm tính" and main.loc[2, "gia_tri_tu_code"] == ""
    assert list(extra["ten_so_lieu"]) == ["chỉ có trong code"]
    ok, _ = survey.compare_with_report(entries[:1], report.iloc[:1].assign(gia_tri_trong_bao_cao="14381"))
    assert list(ok["khop"]) == ["có"]


def test_appendix_a_and_b_counts():
    t = tables()
    screen = pd.Series(["PASS", "thieu_hoac_khong_hop_le_don_vi", "thieu_value", "value_co_dau_so_sanh", "PASS", "PASS"])
    a = survey.appendix_a(t).set_index("itemid")
    assert a.loc["100", "ket_qua"] == 4 and a.loc["100", "benh_nhan"] == 1
    assert a.loc["100", "moc_do"] == 1                       # cả 4 dòng cùng (subject_id, charttime)
    assert a.loc["100", "gia_tri"] == 3                      # "4.1", "___", "-2"
    assert a.loc["100", "do_lap"] == 1
    assert a.loc["100", "don_vi"] == "mEq/L (2); N/A (1)"
    assert a.loc["200", "nhom"] == "Urine Hematology"
    b = survey.appendix_b(t, screen).set_index("itemid")
    assert b.loc["100", "tong"] == 4 and b.loc["100", "co_don_vi"] == 3 and b.loc["100", "ghi_chu"] == 1
    assert b.loc["200", "hai_can"] == 1 and b.loc["200", "khong_can"] == 1 and b.loc["100", "khong_can"] == 4
    assert b.loc["100", "ung_vien"] == 2 and b.loc["200", "ung_vien"] == 1
    assert survey.appendix_b_one_bound(t) == 0


def test_compare_appendix_detects_changed_cell():
    t = tables()
    code = survey.appendix_a(t)
    cols = ["ket_qua", "benh_nhan", "moc_do", "gia_tri", "do_lap", "don_vi"]
    assert set(survey.compare_appendix(code, code.copy(), cols)["khop"]) == {"có"}
    rep = code.astype(str)
    rep.loc[rep["itemid"] == "100", "ket_qua"] = "5"
    bad = survey.compare_appendix(code, rep, cols)
    assert list(bad.loc[bad["khop"] == "không", ["itemid", "ten_cot"]].itertuples(index=False, name=None)) == [("100", "ket_qua")]


def test_compare_appendix_ignores_thousand_separator_only():
    code = pd.DataFrame({"itemid": ["1"], "nhom": ["Blood Chemistry"], "label": ["X"], "ket_qua": [1555], "don_vi": ["g/dL (1555); % (1205)"]})
    rep = pd.DataFrame({"itemid": ["1"], "nhom": ["Blood Chemistry"], "label": ["X"], "ket_qua": ["1.555"], "don_vi": ["g/dL (1.555); % (1.205)"]})
    assert set(survey.compare_appendix(code, rep, ["ket_qua", "don_vi"])["khop"]) == {"có"}
    rep["ket_qua"] = "1.556"
    assert "không" in set(survey.compare_appendix(code, rep, ["ket_qua", "don_vi"])["khop"])


def test_core_section_6_3_check_counts_matching_rows():
    t = tables()
    lab = t["labevents"]
    expected = pd.DataFrame([{"labevent_id": "1", "subject_id": "1", "itemid": "100", "charttime": "2100-01-01 08:00:00",
                              "valuenum": "4.1", "valueuom": "mEq/L", "ref_range_lower": "", "ref_range_upper": "", "csv_record": "2"},
                             {"labevent_id": "5", "subject_id": "2", "itemid": "200", "charttime": "2100-01-01 08:00:00",
                              "valuenum": "30", "valueuom": "mg/dL", "ref_range_lower": "0", "ref_range_upper": "0", "csv_record": "7"}])
    core = pd.DataFrame({"labevent_id": ["1", "5"]})
    rows = {name: v for _, name, v in survey._doi_chieu_6_3(lab, expected, core)}
    assert rows["số dòng khớp CSV gốc ở mọi trường (kể cả số thứ tự bản ghi CSV)"] == 1   # dòng 5 sai csv_record (đúng là 6)
    assert rows["số dòng của danh sách 6.3 trùng với kết quả của quy tắc chọn"] == 2


# ---- file kết quả đã commit và script trích số liệu ----
def test_committed_report_csv_is_self_consistent():
    path = ROOT / "docs" / "so_lieu_bao_cao" / "so_lieu_bao_cao.csv"
    if not path.is_file():
        pytest.skip("chưa chạy notebook 01 trên dữ liệu thật")
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    assert list(df.columns) == ["muc_bao_cao", "ten_so_lieu", "gia_tri_trong_bao_cao", "gia_tri_tu_code", "khop", "noi_tinh"]
    assert set(df["khop"]) <= {"có", "không"}
    assert (df["noi_tinh"] != "").all()
    scalar = df[~df["muc_bao_cao"].str.startswith("Phụ lục")]
    again = [survey.values_match(r.gia_tri_trong_bao_cao, _typed(r.gia_tri_tu_code)) if r.gia_tri_tu_code != "" else False
             for r in scalar.itertuples()]
    assert list(scalar["khop"] == "có") == again


def _typed(text):
    """Chuỗi trong CSV -> giá trị có kiểu như khi tính (số nguyên, số thực hoặc chuỗi)."""
    if text.lstrip("-").isdigit() and not (len(text) > 1 and text.startswith("0")) and len(text) < 15:
        return int(text)
    try:
        return float(text) if "." in text and text.replace(".", "", 1).lstrip("-").isdigit() else text
    except ValueError:
        return text


def _load_script():
    spec = importlib.util.spec_from_file_location("trich", ROOT / "scripts" / "trich_so_lieu_bao_cao.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("raw,expected", [("107.727", "107727"), ("26,38%", "26.38"), ("296,3", "296.3"), ("16.203", "16203"),
                                          ("0.4", "0.4"), ("107.727.", "107727"), ("100,00%", "100.00"), ("12", "12")])
def test_script_num(raw, expected):
    assert _load_script().num(raw) == expected


def test_script_parse_tables_skips_header_and_separator():
    mod = _load_script()
    text = "|  |  |\n| :-: | :-: |\n| \\*\\*Cột\\*\\* | \\*\\*Thiếu\\*\\* |\n| subject\\\\\\_id | 0 |\n| dod | 69 |\n"
    assert mod.parse_tables(text) == [[["subject_id", "0"], ["dod", "69"]]]
