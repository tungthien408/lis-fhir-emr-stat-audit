"""Tính lại các con số của báo cáo khảo sát (mục 1–4, mục 6, phụ lục A, B) từ 4 file MIMIC-IV Demo 2.2.

Các hàm ở đây là hàm thuần (chỉ `read_raw` và `file_sha256` đọc file). Mọi hàm nhận bảng đọc dạng chuỗi
(`read_raw`), nên không làm mất số 0, `N/A`, `___`, dấu so sánh. Ô "thiếu" là ô rỗng hoặc chỉ có khoảng trắng.

`compute_survey_entries` trả về danh sách `Entry`; `compare_with_report` so với số trong báo cáo.
Số trong báo cáo được đọc từ `data/external/bao_cao_*.csv` (xem `scripts/trich_so_lieu_bao_cao.py`).
Dữ liệu gốc là chuẩn: số lệch được ghi là "không khớp", không sửa code cho khớp báo cáo.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from .selection import COMPARATOR, CORE_ITEMIDS, NUMERIC, dec, select_core_40

TABLES = ("patients", "admissions", "d_labitems", "labevents")
UNIT_PLACEHOLDERS = {"N/A", "?", "___"}


@dataclass(frozen=True)
class Entry:
    """Một con số do code tính ra."""
    muc: str      # mục trong báo cáo, ví dụ "2.3"
    ten: str      # tên số liệu (duy nhất trong cùng mục)
    value: Any    # giá trị tính được (số hoặc chuỗi)
    noi_tinh: str  # notebook và hàm tính ra số này


def read_raw(path: str | Path) -> pd.DataFrame:
    """Đọc CSV/CSV.GZ dạng chuỗi, giữ nguyên mọi ký hiệu (không biến ô rỗng thành NaN)."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy {path}")
    return pd.read_csv(path, dtype="string", keep_default_na=False, na_filter=False, low_memory=False)


def file_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_missing(series: pd.Series) -> pd.Series:
    """True nếu ô rỗng hoặc chỉ có khoảng trắng."""
    return series.str.strip().eq("")


def n_missing(df: pd.DataFrame, col: str) -> int:
    return int(is_missing(df[col]).sum())


def pure_number_mask(series: pd.Series) -> pd.Series:
    """True nếu chuỗi (đã cắt khoảng trắng) là số thuần: cùng quy tắc `selection.NUMERIC`."""
    return series.str.strip().str.fullmatch(NUMERIC.pattern).fillna(False).astype(bool)


def comparator_mask(series: pd.Series) -> pd.Series:
    return series.str.strip().str.match(COMPARATOR.pattern).fillna(False).astype(bool)


def unit_counts_text(units: pd.Series) -> str:
    """Các đơn vị không rỗng và số dòng, dạng `đơn vị (số dòng); ...`, xếp theo số dòng giảm dần.

    Không có đơn vị nào thì trả "Không có".
    """
    u = units.str.strip()
    u = u[u != ""]
    if u.empty:
        return "Không có"
    counts = u.value_counts()
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return "; ".join(f"{k} ({v})" for k, v in ordered)


def to_datetime(series: pd.Series) -> pd.Series:
    """Đổi chuỗi `YYYY-MM-DD HH:MM:SS` thành ngày giờ; ô rỗng hoặc sai dạng thành NaT."""
    return pd.to_datetime(series.str.strip().replace("", pd.NA).astype(object), format="%Y-%m-%d %H:%M:%S", errors="coerce")


def _dec_series(series: pd.Series) -> pd.Series:
    return series.map(dec)


def _round_half_up(x: float, digits: int) -> float:
    q = Decimal(1).scaleb(-digits)
    return float(Decimal(repr(float(x))).quantize(q, rounding=ROUND_HALF_UP))


# ---------------------------------------------------------------------------
# Các nhóm số liệu của mục 1–4 và 6. Mỗi hàm trả danh sách Entry.
# ---------------------------------------------------------------------------

def _entries(fn: Callable[..., list[tuple[str, str, Any]]]) -> Callable[..., list[Entry]]:
    """Gắn tên hàm vào `noi_tinh` của từng Entry."""
    def wrapper(*args, **kwargs) -> list[Entry]:
        return [Entry(m, t, v, f"notebook 01 → analysis_core.survey.{fn.__name__}") for m, t, v in fn(*args, **kwargs)]
    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper


@_entries
def muc_mo_dau_va_1(t: dict[str, pd.DataFrame], hashes: dict[str, str]):
    """Kết quả chính và mục 1: số bản ghi, số cột, mã SHA-256 của 4 file."""
    out = [("1", f"{name}: số bản ghi", len(t[name])) for name in TABLES]
    out += [("1", f"{name}: số cột", len(t[name].columns)) for name in TABLES]
    out += [("1.1", f"SHA-256 {name}.csv.gz", hashes[name]) for name in TABLES]
    lab = t["labevents"]
    out += [("Kết quả chính", "số kết quả đã kiểm tra", len(lab)),
            ("Kết quả chính", "số bệnh nhân", lab["subject_id"].nunique())]
    return out


@_entries
def muc_2_mo_ta_bang(t: dict[str, pd.DataFrame]):
    """Mục 2.1–2.4: số dòng, số mã khác nhau, số ô thiếu của từng cột."""
    pat, dl, lab, adm = t["patients"], t["d_labitems"], t["labevents"], t["admissions"]
    out: list[tuple[str, str, Any]] = []
    out += [("2.1", "patients: số dòng", len(pat)), ("2.1", "patients: số subject_id khác nhau", pat["subject_id"].nunique())]
    out += [("2.1", f"patients.{c}: thiếu", n_missing(pat, c)) for c in pat.columns]
    old = pd.to_numeric(pat["anchor_age"], errors="coerce")
    out.append(("2.1", "patients: số bệnh nhân có anchor_age > 89 nhưng khác 91", int(((old > 89) & (old != 91)).sum())))

    in_lab = set(lab["itemid"])
    out += [("2.2", "d_labitems: số itemid khác nhau", dl["itemid"].nunique()),
            ("2.2", "d_labitems: số itemid có trong labevents", len(set(dl["itemid"]) & in_lab)),
            ("2.2", "d_labitems: số itemid không có kết quả trong labevents", len(set(dl["itemid"]) - in_lab))]
    out += [("2.2", f"d_labitems.{c}: thiếu", n_missing(dl, c)) for c in dl.columns]
    blank_ids = set(dl.loc[is_missing(dl["label"]), "itemid"])
    out.append(("2.2", "số kết quả xét nghiệm dùng itemid có label rỗng", int(lab["itemid"].isin(blank_ids).sum())))

    out += [("2.3", "labevents: số dòng", len(lab)), ("2.3", "labevents: số subject_id khác nhau", lab["subject_id"].nunique())]
    out += [("2.3", f"labevents.{c}: thiếu", n_missing(lab, c)) for c in lab.columns]

    out += [("2.4", "admissions: số dòng", len(adm)), ("2.4", "admissions: số hadm_id khác nhau", adm["hadm_id"].nunique())]
    out += [("2.4", f"admissions.{c}: thiếu", n_missing(adm, c)) for c in adm.columns]
    out.append(("2.4", "admissions.language: số dòng ghi dấu ?", int((adm["language"].str.strip() == "?").sum())))
    return out


@_entries
def muc_3_quan_he_bang(t: dict[str, pd.DataFrame]):
    """Mục 3 và 3.1: nối bảng, hadm_id thiếu, mã trùng, dòng trùng, mẫu bệnh phẩm."""
    pat, dl, lab, adm = t["patients"], t["d_labitems"], t["labevents"], t["admissions"]
    out: list[tuple[str, str, Any]] = []
    ok_pat = lab["subject_id"].isin(pat["subject_id"])
    ok_item = lab["itemid"].isin(dl["itemid"])
    out += [("3", "labevents → patients: nối được", int(ok_pat.sum())), ("3", "labevents → patients: không nối được", int((~ok_pat).sum())),
            ("3", "labevents → d_labitems: nối được", int(ok_item.sum())), ("3", "labevents → d_labitems: không nối được", int((~ok_item).sum()))]
    has_hadm = ~is_missing(lab["hadm_id"])
    hadm_ok = lab["hadm_id"].isin(adm["hadm_id"])
    out += [("3", "labevents → admissions (khi có hadm_id): nối được", int((has_hadm & hadm_ok).sum())),
            ("3", "labevents → admissions (khi có hadm_id): mã không tìm thấy", int((has_hadm & ~hadm_ok).sum()))]
    owner = adm.drop_duplicates("hadm_id").set_index("hadm_id")["subject_id"]
    other_patient = has_hadm & hadm_ok & (lab["hadm_id"].map(owner) != lab["subject_id"])
    out.append(("3", "hadm_id có nhưng thuộc bệnh nhân khác", int(other_patient.sum())))
    out += [("3", "hadm_id thiếu: số dòng", int((~has_hadm).sum())),
            ("3", "hadm_id thiếu: tỷ lệ (%)", _round_half_up(100 * (~has_hadm).mean(), 2))]
    merged = lab.merge(adm[["hadm_id"]].drop_duplicates(), on="hadm_id", how="left")
    out.append(("3", "nối trái labevents với admissions: số dòng", len(merged)))
    ok_adm_pat = adm["subject_id"].isin(pat["subject_id"])
    out += [("3", "admissions → patients: nối được", int(ok_adm_pat.sum())), ("3", "admissions → patients: không nối được", int((~ok_adm_pat).sum()))]

    keys = {"patients": "subject_id", "admissions": "hadm_id", "d_labitems": "itemid", "labevents": "labevent_id"}
    for name, key in keys.items():
        df = t[name]
        out += [("3.1", f"{name}.{key}: giá trị thiếu", n_missing(df, key)),
                ("3.1", f"{name}.{key}: dòng lặp mã", int(df[key].duplicated().sum())),
                ("3.1", f"{name}: dòng trùng toàn bộ", int(df.duplicated().sum()))]
    out += [("3.1", "dòng vượt quá dòng đầu trong nhóm (subject_id, itemid, charttime)",
             int(lab.duplicated(["subject_id", "itemid", "charttime"]).sum())),
            ("3.1", "dòng vượt quá dòng đầu trong nhóm (subject_id, itemid, charttime, value, valueuom)",
             int(lab.duplicated(["subject_id", "itemid", "charttime", "value", "valueuom"]).sum()))]
    ex = lab[lab["labevent_id"].isin(["171", "184"])]
    same = len(ex) == 2 and ex[["subject_id", "itemid", "charttime", "value"]].nunique().eq(1).all()
    out += [("3.1", "ví dụ 171 và 184: cùng subject_id, itemid, charttime và value", "có" if same else "không"),
            ("3.1", "ví dụ 171 và 184: subject_id", ex["subject_id"].iloc[0] if len(ex) else ""),
            ("3.1", "ví dụ 171 và 184: charttime", ex["charttime"].iloc[0] if len(ex) else ""),
            ("3.1", "ví dụ 171 và 184: value", ex["value"].iloc[0] if len(ex) else "")]
    out += [("3.1", "số specimen_id khác nhau", lab["specimen_id"].nunique()),
            ("3.1", "số specimen_id thuộc nhiều subject_id", int((lab.groupby("specimen_id")["subject_id"].nunique() > 1).sum())),
            ("3.1", "số cặp (subject_id, itemid) có nhiều kết quả", int((lab.groupby(["subject_id", "itemid"]).size() > 1).sum()))]
    return out


@_entries
def muc_3_2_kieu_du_lieu(t: dict[str, pd.DataFrame]):
    """Mục 3.2: kiểu số, ngày giờ, ô đơn vị chỉ có khoảng trắng, nhãn có khoảng trắng."""
    dl, lab, adm = t["d_labitems"], t["labevents"], t["admissions"]
    out: list[tuple[str, str, Any]] = []
    bad_num = 0
    for c in ("valuenum", "ref_range_lower", "ref_range_upper"):
        s = lab.loc[~is_missing(lab[c]), c]
        bad_num += int((~s.map(lambda v: dec(v) is not None)).sum())
    out.append(("3.2", "ô valuenum và cận không phải số hữu hạn (vô hạn, NaN, sai dạng)", bad_num))
    low, high = _dec_series(lab["ref_range_lower"]), _dec_series(lab["ref_range_upper"])
    both = low.notna() & high.notna()
    out.append(("3.2", "dòng có cận dưới lớn hơn cận trên", int(sum(a > b for a, b in zip(low[both], high[both])))))
    bad_dt = 0
    for c in ("charttime", "storetime"):
        s = lab[c]
        bad_dt += int((~is_missing(s) & to_datetime(s).isna()).sum())
    for c in ("admittime", "dischtime", "deathtime", "edregtime", "edouttime"):
        s = adm[c]
        bad_dt += int((~is_missing(s) & to_datetime(s).isna()).sum())
    out.append(("3.2", "ô ngày giờ có mặt nhưng không phân tích được", bad_dt))
    out.append(("3.2", "lượt nhập viện có dischtime sớm hơn admittime", int((to_datetime(adm["dischtime"]) < to_datetime(adm["admittime"])).sum())))

    unit = lab["valueuom"]
    ws_only = (unit != "") & (unit.str.strip() == "")
    out += [("3.2", "valueuom: số dòng chỉ chứa khoảng trắng", int(ws_only.sum())),
            ("3.2", "valueuom: số dòng ô rỗng", int((unit == "").sum())),
            ("3.2", "valueuom: tổng số thiếu đơn vị", int(is_missing(unit).sum()))]
    lab_ws = dl["label"] != dl["label"].str.strip()
    out += [("3.2", "d_labitems.label: số nhãn có khoảng trắng ở đầu hoặc cuối", int(lab_ws.sum())),
            ("3.2", "d_labitems.label: số nhãn chỉ gồm khoảng trắng", int(((dl["label"] != "") & (dl["label"].str.strip() == "")).sum())),
            ("2.2", "d_labitems: số dòng có label rỗng hoặc chỉ khoảng trắng", int(is_missing(dl["label"]).sum()))]
    return out


@_entries
def muc_4_1_loai_xet_nghiem(t: dict[str, pd.DataFrame]):
    """Mục 4.1: số loại xét nghiệm, nhóm, loại mẫu và 12 loại có nhiều kết quả nhất."""
    dl, lab = t["d_labitems"], t["labevents"]
    cat = dl.drop_duplicates("itemid").set_index("itemid")
    used = lab["itemid"].unique()
    info = cat.reindex(used)
    out: list[tuple[str, str, Any]] = [("4.1", "số itemid xuất hiện trong labevents", len(used)),
                                       ("4.1", "số loại mẫu (fluid)", info["fluid"].nunique()),
                                       ("4.1", "số nhóm xét nghiệm (category)", info["category"].nunique()),
                                       ("4.1", "số itemid tra được đúng một dòng d_labitems", int(pd.Series(used).map(dl["itemid"].value_counts()).eq(1).sum()))]
    cats = lab["itemid"].map(cat["category"]).value_counts()
    out += [("4.1", f"nhóm {k}: số kết quả", int(v)) for k, v in cats.items()]
    fluids = lab["itemid"].map(cat["fluid"]).value_counts()
    out += [("4.1", f"loại mẫu {k}: số kết quả", int(v)) for k, v in fluids.items()]
    per = lab.groupby("itemid").agg(n=("labevent_id", "size"), p=("subject_id", "nunique")).reset_index()
    per["_id"] = per["itemid"].astype(int)
    top = per.sort_values(["n", "_id"], ascending=[False, True]).head(12)
    for rank, row in enumerate(top.itertuples(), start=1):
        out += [("4.1", f"hạng {rank}: itemid", row.itemid), ("4.1", f"hạng {rank}: tên", cat.loc[row.itemid, "label"]),
                ("4.1", f"hạng {rank}: mẫu và nhóm", f"{cat.loc[row.itemid, 'fluid']} / {cat.loc[row.itemid, 'category']}"),
                ("4.1", f"hạng {rank}: số kết quả", int(row.n)), ("4.1", f"hạng {rank}: số bệnh nhân", int(row.p))]
    return out


@_entries
def muc_4_2_do_day_du(t: dict[str, pd.DataFrame]):
    """Mục 4.2: số dòng có dữ liệu, thiếu, tỷ lệ có của từng trường; khoảng tham chiếu."""
    lab = t["labevents"]
    out: list[tuple[str, str, Any]] = []
    for c in ("value", "valuenum", "valueuom", "ref_range_lower", "ref_range_upper", "charttime", "storetime", "flag", "comments"):
        miss = n_missing(lab, c)
        out += [("4.2", f"{c}: có dữ liệu", len(lab) - miss), ("4.2", f"{c}: thiếu", miss),
                ("4.2", f"{c}: tỷ lệ có (%)", _round_half_up(100 * (len(lab) - miss) / len(lab), 2))]
    lo, hi = ~is_missing(lab["ref_range_lower"]), ~is_missing(lab["ref_range_upper"])
    out += [("4.2", "khoảng tham chiếu: đủ hai cận", int((lo & hi).sum())),
            ("4.2", "khoảng tham chiếu: thiếu cả hai cận", int((~lo & ~hi).sum())),
            ("4.2", "khoảng tham chiếu: chỉ một cận", int((lo ^ hi).sum()))]
    low, high = _dec_series(lab["ref_range_lower"]), _dec_series(lab["ref_range_upper"])
    both = low.notna() & high.notna()
    out.append(("4.2", "khoảng tham chiếu: cận dưới lớn hơn cận trên", int(sum(a > b for a, b in zip(low[both], high[both])))))
    return out


@_entries
def muc_4_3_gia_tri(t: dict[str, pd.DataFrame]):
    """Mục 4.3: dạng của `value`, `value` và `valuenum`, số 0 và số âm, Glucose."""
    dl, lab = t["d_labitems"], t["labevents"]
    v = lab["value"].str.strip()
    empty, comp = v == "", comparator_mask(lab["value"])
    pure = pure_number_mask(lab["value"]) & ~comp
    text = ~empty & ~comp & ~pure
    n = len(lab)
    out: list[tuple[str, str, Any]] = []
    for name, mask in (("số thuần", pure), ("có dấu so sánh", comp), ("có chữ hoặc ký hiệu, không có dấu so sánh", text), ("rỗng", empty)):
        out += [("4.3", f"value {name}: số dòng", int(mask.sum())), ("4.3", f"value {name}: tỷ lệ (%)", _round_half_up(100 * mask.mean(), 2))]
    out.append(("4.3", "tổng bốn dạng value", int(pure.sum() + comp.sum() + text.sum() + empty.sum())))
    vn = lab["valuenum"]
    num_dec, val_dec = _dec_series(vn), _dec_series(lab["value"])
    mismatch = [a is None or b is None or a != b for a, b in zip(val_dec[pure], num_dec[pure])]
    out.append(("4.3", "value số thuần nhưng valuenum không bằng về số học", int(sum(mismatch))))
    out.append(("4.3", "value không phải số thuần nhưng valuenum có số", int(((~pure) & num_dec.notna()).sum())))
    out.append(("4.3", "value = ___: số dòng", int((v == "___").sum())))
    ex = lab[lab["labevent_id"] == "172082"]
    out += [("4.3", "labevent 172082: value", ex["value"].iloc[0] if len(ex) else ""),
            ("4.3", "labevent 172082: valuenum", ex["valuenum"].iloc[0] if len(ex) else ""),
            ("4.3", "labevent 172082: tên xét nghiệm", dl.set_index("itemid")["label"].get(ex["itemid"].iloc[0], "") if len(ex) else ""),
            ("4.3", "labevent 172082: comments không rỗng", "có" if len(ex) and ex["comments"].iloc[0].strip() else "không")]
    glu = lab[lab["itemid"] == "50931"]
    out += [("4.3", "itemid 50931 (Glucose máu): số dòng", len(glu)),
            ("4.3", "itemid 50931: số dòng có value = ___", int((glu["value"].str.strip() == "___").sum())),
            ("4.3", "itemid 50931: số dòng có comments", int((~is_missing(glu["comments"])).sum()))]
    out += [("4.3", "value có dấu so sánh: các chuỗi khác nhau", " | ".join(sorted(set(v[comp])))),
            ("4.3", "value có dấu so sánh: số chuỗi khác nhau", int(v[comp].nunique()))]
    ex = lab[lab["labevent_id"] == "150770"]
    out += [("4.3", "labevent 150770: value", ex["value"].iloc[0] if len(ex) else ""),
            ("4.3", "labevent 150770: valueuom", ex["valueuom"].iloc[0] if len(ex) else "")]
    out += [("4.3", "valuenum bằng 0: số dòng", int(sum(x == 0 for x in num_dec.dropna()))),
            ("4.3", "valuenum âm: số dòng", int(sum(x < 0 for x in num_dec.dropna())))]
    return out


@_entries
def muc_4_4_don_vi_ghi_chu(t: dict[str, pd.DataFrame], screen: pd.Series):
    """Mục 4.4: itemid nhiều đơn vị, đơn vị N/A, ghi chú."""
    dl, lab = t["d_labitems"], t["labevents"]
    cat = dl.drop_duplicates("itemid").set_index("itemid")["label"]
    u = lab["valueuom"].str.strip()
    nonempty = lab[u != ""]
    n_units = nonempty.assign(u=u[u != ""]).groupby("itemid")["u"].nunique()
    multi = sorted(n_units[n_units > 1].index, key=int)
    out: list[tuple[str, str, Any]] = [("4.4", "số itemid có nhiều hơn một chuỗi đơn vị không rỗng", len(multi))]
    for itemid in multi:
        txt = unit_counts_text(lab.loc[lab["itemid"] == itemid, "valueuom"])
        out.append(("4.4", f"{itemid} {cat[itemid]}: đơn vị và số dòng", txt.replace(" (", ": ").replace(")", "")))
    out.append(("4.4", "valueuom = N/A: số dòng", int((u == "N/A").sum())))
    passed = screen == "PASS"
    out.append(("4.4", "dòng đạt sàng lọc cơ bản có đơn vị N/A, ? hoặc ___", int(u[passed].isin(UNIT_PLACEHOLDERS).sum())))
    c = lab["comments"].str.strip()
    out += [("4.4", "comments có nội dung: số dòng", int((c != "").sum())),
            ("4.4", "comments đúng ___: số dòng", int((c == "___").sum())),
            ("4.4", "comments có nội dung nhưng value rỗng: số dòng", int(((c != "") & (lab["value"].str.strip() == "")).sum())),
            ("4.4", "value số thuần đồng thời có comments", int((pure_number_mask(lab["value"]) & ~comparator_mask(lab["value"]) & (c != "")).sum()))]
    return out


@_entries
def muc_4_5_thoi_gian(t: dict[str, pd.DataFrame]):
    """Mục 4.5: khoảng thời gian, độ trễ storetime - charttime (phút)."""
    lab = t["labevents"]
    ct, st = to_datetime(lab["charttime"]), to_datetime(lab["storetime"])
    out: list[tuple[str, str, Any]] = [
        ("4.5", "charttime: có dữ liệu", int(ct.notna().sum())), ("4.5", "charttime: nhỏ nhất", ct.min().strftime("%Y-%m-%d %H:%M:%S")),
        ("4.5", "charttime: lớn nhất", ct.max().strftime("%Y-%m-%d %H:%M:%S")),
        ("4.5", "storetime: có dữ liệu", int(st.notna().sum())), ("4.5", "storetime: nhỏ nhất", st.min().strftime("%Y-%m-%d %H:%M:%S")),
        ("4.5", "storetime: lớn nhất", st.max().strftime("%Y-%m-%d %H:%M:%S")),
        ("4.5", "storetime: thiếu", int(st.isna().sum())),
    ]
    both = ct.notna() & st.notna()
    gap = (st[both] - ct[both]).dt.total_seconds() / 60
    out += [("4.5", "có đủ hai mốc: số dòng", int(both.sum())),
            ("4.5", "hai mốc bằng nhau: số dòng", int((gap == 0).sum())),
            ("4.5", "storetime sau charttime: số dòng", int((gap > 0).sum())),
            ("4.5", "storetime trước charttime: số dòng", int((gap < 0).sum())),
            ("4.5", "độ trễ: trung vị (phút)", _round_half_up(float(np.median(gap)), 1)),
            ("4.5", "độ trễ: phân vị 95 (phút, nội suy tuyến tính)", _round_half_up(float(np.percentile(gap, 95)), 1)),
            ("4.5", "độ trễ: lớn nhất (phút)", _round_half_up(float(gap.max()), 1))]
    return out


@_entries
def muc_4_6_sang_loc(t: dict[str, pd.DataFrame], screen: pd.Series):
    """Mục 4.6: số dòng qua sàng lọc cơ bản và lý do bị loại."""
    lab = t["labevents"]
    passed = screen == "PASS"
    u = lab["valueuom"].str.strip()
    nu = lab[passed].assign(u=u[passed]).groupby("itemid")["u"].nunique()
    multi_ids = set(nu[nu > 1].index)
    in_multi = int(lab.loc[passed, "itemid"].isin(multi_ids).sum())
    out: list[tuple[str, str, Any]] = [
        ("4.6", "số thuần đủ trường cơ bản (qua sàng lọc)", int(passed.sum())),
        ("4.6", "trong nhóm trên có itemid nhiều đơn vị", in_multi),
        ("4.6", "ứng viên có itemid chỉ một đơn vị", int(passed.sum()) - in_multi),
        ("4.6", "không đạt sàng lọc số cơ bản", int((~passed).sum())),
        ("4.6", "loại vì thiếu value", int((screen == "thieu_value").sum())),
        ("4.6", "loại vì value không phải số thuần (không tính dấu so sánh)", int((screen == "value_khong_phai_so_thuan").sum())),
        ("4.6", "loại vì value dạng số nhưng thiếu đơn vị", int((screen == "thieu_hoac_khong_hop_le_don_vi").sum())),
        ("4.6", "loại vì giá trị có dấu so sánh", int((screen == "value_co_dau_so_sanh").sum())),
        ("4.6", "tổng các lý do bị loại", int((~passed).sum())),
    ]
    return out


@_entries
def muc_6_tap_thuc_nghiem(t: dict[str, pd.DataFrame], screen: pd.Series, core: pd.DataFrame, expected40: pd.DataFrame | None):
    """Mục 6: thống kê 5 loại xét nghiệm, 40 kết quả, so với danh sách 6.3 (nếu có)."""
    dl, lab, pat = t["d_labitems"], t["labevents"], t["patients"]
    cat = dl.drop_duplicates("itemid").set_index("itemid")
    passed = screen == "PASS"
    out: list[tuple[str, str, Any]] = []
    chosen = lab[lab["labevent_id"].isin(core["labevent_id"])]
    for item in CORE_ITEMIDS:
        sub = lab[lab["itemid"] == item]
        cand = sub[passed.loc[sub.index]]
        ch = chosen[chosen["itemid"] == item]
        name = f"{item} {cat.loc[item, 'label']}"
        out += [("6.1", f"{name}: số kết quả trong nguồn", len(sub)), ("6.1", f"{name}: số bệnh nhân trong nguồn", sub["subject_id"].nunique()),
                ("6.1", f"{name}: số ứng viên qua sàng lọc", len(cand)),
                ("6.1", f"{name}: mẫu", cat.loc[item, "fluid"]), ("6.1", f"{name}: nhóm", cat.loc[item, "category"]),
                ("6.1", f"{name}: số đơn vị duy nhất của ứng viên", cand["valueuom"].str.strip().nunique()),
                ("6.1", f"{name}: đơn vị", cand["valueuom"].str.strip().iloc[0]),
                ("6.1", f"{name}: số kết quả được chọn", len(ch)), ("6.1", f"{name}: số bệnh nhân được chọn", ch["subject_id"].nunique()),
                ("6.1", f"{name}: số giá trị valuenum (chuỗi) khác nhau trong mẫu", ch["valuenum"].nunique())]
    lo, hi = ~is_missing(chosen["ref_range_lower"]), ~is_missing(chosen["ref_range_upper"])
    nums = _dec_series(chosen["valuenum"])
    out += [("6.1", "toàn tập: số labevent_id khác nhau", chosen["labevent_id"].nunique()),
            ("6.1", "toàn tập: số bệnh nhân", chosen["subject_id"].nunique()),
            ("6.1", "toàn tập: số loại xét nghiệm", chosen["itemid"].nunique()),
            ("6.1", "toàn tập: kết quả đủ hai cận", int((lo & hi).sum())),
            ("6.1", "toàn tập: kết quả thiếu cả hai cận", int((~lo & ~hi).sum())),
            ("6.1", "toàn tập: kết quả chỉ một cận", int((lo ^ hi).sum())),
            ("6.1", "toàn tập: kết quả bằng 0", int(sum(x == 0 for x in nums))),
            ("6.1", "toàn tập: kết quả âm", int(sum(x < 0 for x in nums)))]
    out += [("6.2", "số ứng viên sau sàng lọc", int(passed.sum())), ("6.2", "số dòng vào mẫu", len(chosen)),
            ("6.2", "số ứng viên không được chọn", int(passed.sum()) - len(chosen))]
    if expected40 is not None:
        out += _doi_chieu_6_3(lab, expected40, core)
    out.append(("6.4", "số subject_id của bảng chuẩn bệnh nhân có trong patients",
                int(pd.Series(sorted(chosen["subject_id"].unique())).isin(pat["subject_id"]).sum())))
    r1 = lab[lab["labevent_id"] == "150770"]
    r2 = lab[lab["labevent_id"] == "172081"]
    out += [("6.5", "labevent 150770: value có dấu so sánh", "có" if len(r1) and bool(comparator_mask(r1["value"]).iloc[0]) else "không"),
            ("6.5", "labevent 172081: kết quả nằm trong comments (value rỗng, comments không rỗng)",
             "có" if len(r2) and r2["value"].str.strip().iloc[0] == "" and r2["comments"].str.strip().iloc[0] != "" else "không")]
    return out


def _doi_chieu_6_3(lab: pd.DataFrame, expected: pd.DataFrame, core: pd.DataFrame) -> list[tuple[str, str, Any]]:
    """So 40 dòng ở mục 6.3 với CSV gốc từng trường, và với 40 dòng do quy tắc chọn ra."""
    rec = pd.Series(range(2, len(lab) + 2), index=lab.index)
    by_id = lab.assign(csv_record=rec.astype(str)).drop_duplicates("labevent_id").set_index("labevent_id")
    fields = ("subject_id", "itemid", "charttime", "valueuom", "ref_range_lower", "ref_range_upper", "csv_record")
    n_ok = 0
    for row in expected.itertuples(index=False):
        actual = by_id.loc[row.labevent_id] if row.labevent_id in by_id.index else None
        if actual is None:
            continue
        same = all(str(getattr(row, f)).strip() == str(actual[f]).strip() for f in fields[:4] + fields[6:])
        for f in ("ref_range_lower", "ref_range_upper"):
            a, b = str(getattr(row, f)).strip(), str(actual[f]).strip()
            same &= (a == b) if a == "" or b == "" else (dec(a) == dec(b))
        same &= dec(row.valuenum) is not None and dec(row.valuenum) == dec(actual["value"]) == dec(actual["valuenum"])
        n_ok += bool(same)
    return [("6.3", "số dòng khớp CSV gốc ở mọi trường (kể cả số thứ tự bản ghi CSV)", n_ok),
            ("6.3", "số dòng của danh sách 6.3 trùng với kết quả của quy tắc chọn", len(set(expected["labevent_id"]) & set(core["labevent_id"]))),
            ("6.3", "số dòng trong danh sách 6.3", len(expected))]


# ---------------------------------------------------------------------------
# Phụ lục A và B
# ---------------------------------------------------------------------------

def appendix_a(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Phụ lục A: thống kê từng loại xét nghiệm (cùng cách tính với báo cáo)."""
    dl, lab = t["d_labitems"], t["labevents"]
    cat = dl.drop_duplicates("itemid").set_index("itemid")
    value = lab["value"].str.strip()
    rows = []
    for itemid, g in lab.groupby("itemid", sort=False):
        v = value.loc[g.index]
        per_patient = g.groupby("subject_id").size()
        rows.append({
            "itemid": itemid, "nhom": f"{cat.loc[itemid, 'fluid']} {cat.loc[itemid, 'category']}", "label": cat.loc[itemid, "label"],
            "ket_qua": len(g), "benh_nhan": g["subject_id"].nunique(),
            "moc_do": len(g.drop_duplicates(["subject_id", "charttime"])), "gia_tri": int(v[v != ""].nunique()),
            "do_lap": int((per_patient > 1).sum()), "don_vi": unit_counts_text(g["valueuom"]),
        })
    out = pd.DataFrame(rows)
    out["_id"] = out["itemid"].astype(int)
    return out.sort_values(["nhom", "_id"]).drop(columns="_id").reset_index(drop=True)


def appendix_b(t: dict[str, pd.DataFrame], screen: pd.Series) -> pd.DataFrame:
    """Phụ lục B: chất lượng từng loại xét nghiệm (cùng cách tính với báo cáo)."""
    dl, lab = t["d_labitems"], t["labevents"]
    cat = dl.drop_duplicates("itemid").set_index("itemid")
    has = lambda c: ~is_missing(lab[c])
    lab = lab.assign(_value=has("value"), _num=has("valuenum"), _unit=has("valueuom"),
                     _lo=has("ref_range_lower"), _hi=has("ref_range_upper"), _comment=has("comments"), _pass=screen == "PASS")
    rows = []
    for itemid, g in lab.groupby("itemid", sort=False):
        rows.append({
            "itemid": itemid, "nhom": f"{cat.loc[itemid, 'fluid']} {cat.loc[itemid, 'category']}", "label": cat.loc[itemid, "label"],
            "tong": len(g), "co_value": int(g["_value"].sum()), "co_so": int(g["_num"].sum()), "co_don_vi": int(g["_unit"].sum()),
            "hai_can": int((g["_lo"] & g["_hi"]).sum()), "khong_can": int((~g["_lo"] & ~g["_hi"]).sum()),
            "ghi_chu": int(g["_comment"].sum()), "ung_vien": int(g["_pass"].sum()),
        })
    out = pd.DataFrame(rows)
    out["_id"] = out["itemid"].astype(int)
    return out.sort_values(["nhom", "_id"]).drop(columns="_id").reset_index(drop=True)


def appendix_b_one_bound(t: dict[str, pd.DataFrame]) -> int:
    """Số dòng chỉ có một cận (báo cáo: bằng 0 ở mọi loại)."""
    lab = t["labevents"]
    return int((~is_missing(lab["ref_range_lower"]) ^ ~is_missing(lab["ref_range_upper"])).sum())


# ---------------------------------------------------------------------------
# Gom và so sánh
# ---------------------------------------------------------------------------

def compute_survey_entries(t: dict[str, pd.DataFrame], screen: pd.Series, hashes: dict[str, str],
                           expected40: pd.DataFrame | None = None) -> list[Entry]:
    """Tính mọi số liệu dạng đơn lẻ của mục 1–4 và 6.

    `screen` là kết quả `screen_labevents` (cùng chỉ số với `t["labevents"]`).
    """
    pool = t["labevents"][(screen == "PASS") & t["labevents"]["itemid"].isin(CORE_ITEMIDS)]
    core = select_core_40(pool)
    entries: list[Entry] = []
    entries += muc_mo_dau_va_1(t, hashes)
    entries += muc_2_mo_ta_bang(t)
    entries += muc_3_quan_he_bang(t)
    entries += muc_3_2_kieu_du_lieu(t)
    entries += muc_4_1_loai_xet_nghiem(t)
    entries += muc_4_2_do_day_du(t)
    entries += muc_4_3_gia_tri(t)
    entries += muc_4_4_don_vi_ghi_chu(t, screen)
    entries += muc_4_5_thoi_gian(t)
    entries += muc_4_6_sang_loc(t, screen)
    entries += muc_6_tap_thuc_nghiem(t, screen, core, expected40)
    keys = [(e.muc, e.ten) for e in entries]
    if len(keys) != len(set(keys)):
        dup = sorted({k for k in keys if keys.count(k) > 1})
        raise ValueError(f"Có số liệu trùng tên trong cùng mục: {dup[:5]}")
    return entries


def _parse_report_number(text: str) -> Decimal | None:
    try:
        x = Decimal(text.strip())
        return x if x.is_finite() else None
    except Exception:
        return None


def values_match(report: str, code: Any) -> bool:
    """So giá trị trong báo cáo (chuỗi) với giá trị code tính ra.

    - Số nguyên: phải bằng nhau tuyệt đối.
    - Số thực: so sau khi làm tròn giá trị code (làm tròn lên ở .5) theo số chữ số thập phân của báo cáo.
    - Chuỗi (mã SHA-256, ngày giờ, tên...): so đúng từng ký tự. Ô trống của báo cáo không khớp với bất kỳ giá trị nào.
    """
    r = _parse_report_number(str(report))
    if r is not None and isinstance(code, (int, np.integer)) and not isinstance(code, bool):
        return Decimal(int(code)) == r
    if r is not None and isinstance(code, (float, np.floating)):
        if math.isnan(code) or math.isinf(code):
            return False
        digits = max(0, -r.as_tuple().exponent)
        q = Decimal(1).scaleb(-digits)
        return Decimal(repr(float(code))).quantize(q, rounding=ROUND_HALF_UP) == r.quantize(q)
    return str(report).strip() == str(code).strip() and str(report).strip() != ""


def format_value(v: Any) -> str:
    """Chuỗi để ghi ra CSV: số nguyên không có dấu tách nghìn, số thực bỏ số 0 thừa."""
    if isinstance(v, (float, np.floating)):
        return format(Decimal(repr(float(v))).normalize(), "f")
    return str(v)


def compare_with_report(entries: list[Entry], report: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """So số trong báo cáo với số code tính ra.

    `report` có cột `muc_bao_cao, ten_so_lieu, gia_tri_trong_bao_cao`. Trả về hai bảng:
      - bảng chính (mỗi số trong báo cáo một dòng): `muc_bao_cao, ten_so_lieu, gia_tri_trong_bao_cao,
        gia_tri_tu_code, khop ("có"/"không"), noi_tinh`. Số có trong báo cáo mà code không tính ra
        được ghi `khop = "không"`, `gia_tri_tu_code` để trống, `noi_tinh = "chưa có hàm tính"`.
      - bảng phụ (số code tính được nhưng báo cáo không nêu): `muc_bao_cao, ten_so_lieu, gia_tri_tu_code, noi_tinh`.
    """
    by_key = {(e.muc, e.ten): e for e in entries}
    rows, seen = [], set()
    for r in report.itertuples(index=False):
        key = (r.muc_bao_cao, r.ten_so_lieu)
        seen.add(key)
        e = by_key.get(key)
        if e is None:
            rows.append((key[0], key[1], r.gia_tri_trong_bao_cao, "", "không", "chưa có hàm tính"))
        else:
            rows.append((key[0], key[1], r.gia_tri_trong_bao_cao, format_value(e.value),
                         "có" if values_match(r.gia_tri_trong_bao_cao, e.value) else "không", e.noi_tinh))
    main = pd.DataFrame(rows, columns=["muc_bao_cao", "ten_so_lieu", "gia_tri_trong_bao_cao", "gia_tri_tu_code", "khop", "noi_tinh"])
    extra = pd.DataFrame([(e.muc, e.ten, format_value(e.value), e.noi_tinh) for e in entries if (e.muc, e.ten) not in seen],
                         columns=["muc_bao_cao", "ten_so_lieu", "gia_tri_tu_code", "noi_tinh"])
    return main, extra


def _canon_unit_text(text: str) -> str:
    """Chuẩn hóa chuỗi đơn vị của phụ lục: bỏ dấu tách nghìn trong số dòng (1.555 -> 1555)."""
    import re
    return re.sub(r"\((\d{1,3}(?:\.\d{3})+)\)", lambda m: "(" + m.group(1).replace(".", "") + ")", text.strip())


def compare_appendix(code: pd.DataFrame, report: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """So phụ lục (dạng dài): mỗi ô của mỗi itemid một dòng.

    Cả hai bảng có cột `itemid`, `nhom`, `label` và các cột trong `columns`; số trong `report` có thể ghi dạng chuỗi.
    """
    c = code.set_index("itemid")
    r = report.drop_duplicates("itemid").set_index("itemid")
    rows = []
    for itemid in sorted(set(c.index) | set(r.index), key=int):
        for col in ["nhom", "label"] + columns:
            rv = "" if itemid not in r.index else str(r.at[itemid, col])
            cv = "" if itemid not in c.index else str(c.at[itemid, col])
            if col == "don_vi":
                rv, cv = _canon_unit_text(rv), _canon_unit_text(cv)
            elif col not in ("nhom", "label"):
                rv, cv = rv.replace(".", ""), cv.replace(".", "")
            rows.append((itemid, c.at[itemid, "label"] if itemid in c.index else r.at[itemid, "label"], col, rv, cv, "có" if rv == cv and rv != "" else "không"))
    return pd.DataFrame(rows, columns=["itemid", "label", "ten_cot", "gia_tri_trong_bao_cao", "gia_tri_tu_code", "khop"])
