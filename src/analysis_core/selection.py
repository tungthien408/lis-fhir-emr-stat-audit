"""Sàng lọc dòng xét nghiệm và chọn mẫu.

- Sàng lọc cơ bản: `basic_screen_reason`, `screen_labevents` (dùng chung cho notebook 01, 04, 05).
- Chọn 40 dòng lõi: `select_core_40`, theo `docs/quy_tac_chon_mau_40.md`.
- Chọn 1.000 dòng cho E1: `select_round_robin`, theo `docs/quy_tac_chon_mau_1000.md`.

Các hàm ở đây là hàm thuần: không đọc file, không in ra màn hình.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping

import pandas as pd

NUMERIC = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
COMPARATOR = re.compile(r"^[<>]=?")

# Hạn mức ghi cứng, lấy từ danh sách 1.000 kết quả đã nạp vào LIS (xem docs/quy_tac_chon_mau_1000.md, Bước 3).
QUOTAS: dict[str, int] = {"50971": 210, "50912": 210, "51222": 210, "50802": 210, "51492": 160}


def clean(v: Any) -> str:
    """Đổi giá trị bất kỳ thành chuỗi đã cắt khoảng trắng; thiếu thì thành chuỗi rỗng."""
    return "" if pd.isna(v) else str(v).strip()


def dec(v: Any) -> Decimal | None:
    """Đổi chuỗi số thuần thành `Decimal`; không hợp lệ thì trả `None`."""
    v = clean(v)
    if not NUMERIC.fullmatch(v):
        return None
    try:
        x = Decimal(v)
        return x if x.is_finite() else None
    except InvalidOperation:
        return None


def valid_time(v: Any) -> bool:
    """Kiểm `charttime` có đúng dạng `YYYY-MM-DD HH:MM:SS` không."""
    try:
        datetime.strptime(clean(v), "%Y-%m-%d %H:%M:%S")
        return True
    except ValueError:
        return False


def basic_screen_reason(row: Mapping[str, Any], patient_ids: set[str], lab_ids: set[str]) -> str:
    """Lý do không đạt sàng lọc cơ bản đầu tiên; trả `"PASS"` nếu đạt (logic của notebook 04)."""
    if clean(row["subject_id"]) not in patient_ids:
        return "subject_id_khong_ton_tai"
    if clean(row["itemid"]) not in lab_ids:
        return "itemid_khong_ton_tai"
    raw = clean(row["value"])
    if not raw:
        return "thieu_value"
    if COMPARATOR.match(raw):
        return "value_co_dau_so_sanh"
    x = dec(raw)
    if x is None:
        return "value_khong_phai_so_thuan"
    y = dec(row["valuenum"])
    if y is None:
        return "valuenum_thieu_hoac_khong_hop_le"
    if x != y:
        return "value_va_valuenum_khong_khop"
    unit = clean(row["valueuom"])
    if not unit or unit in {"N/A", "?", "___"}:
        return "thieu_hoac_khong_hop_le_don_vi"
    if not valid_time(row["charttime"]):
        return "charttime_khong_hop_le"
    low, high = clean(row["ref_range_lower"]), clean(row["ref_range_upper"])
    if (low and dec(low) is None) or (high and dec(high) is None):
        return "can_tham_chieu_khong_hop_le"
    if low and high and dec(low) > dec(high):
        return "can_duoi_lon_hon_can_tren"
    if clean(row["comments"]):
        return "comments_can_xem_xet"
    return "PASS"


def screen_labevents(labevents: pd.DataFrame, patients: pd.DataFrame, d_labitems: pd.DataFrame) -> pd.Series:
    """Chạy `basic_screen_reason` cho từng dòng `labevents`; trả về Series cùng chỉ số, tên `basic_screen`."""
    patient_ids = set(patients["subject_id"].map(clean))
    lab_ids = set(d_labitems["itemid"].map(clean))
    reasons = [basic_screen_reason(r, patient_ids, lab_ids) for r in labevents.to_dict("records")]
    return pd.Series(reasons, index=labevents.index, name="basic_screen")


def allocate_quotas() -> dict[str, int]:
    """Hạn mức cố định theo tài liệu (không tính động). Trả về bản sao mới."""
    return dict(QUOTAS)


def select_round_robin(pool: pd.DataFrame, core_ids: set[str], quotas: dict[str, int]) -> pd.DataFrame:
    """Chọn mẫu: lấy dòng lõi trước, phần còn lại xoay vòng theo bệnh nhân (Bước 4–5).

    `pool` cần các cột `labevent_id, subject_id, itemid, charttime` (dạng chuỗi).
    Thêm cột `selection_reason` ("core_40" / "round_robin") và `round` (dòng lõi: trống).
    Kết quả xếp theo (itemid, labevent_id); không phụ thuộc thứ tự dòng đầu vào.
    """
    df = pool.copy()
    for col in ("labevent_id", "subject_id", "itemid"):
        df[col] = df[col].astype("string").str.strip().astype(object)
    if df["labevent_id"].duplicated().any():
        raise ValueError("pool có labevent_id trùng")
    core_ids = {str(i).strip() for i in core_ids}
    missing = core_ids - set(df["labevent_id"])
    if missing:
        raise ValueError(f"pool thiếu {len(missing)} dòng lõi: {sorted(missing, key=int)[:10]}")
    is_core = df["labevent_id"].isin(core_ids)
    stray = set(df.loc[is_core, "itemid"]) - set(quotas)
    if stray:
        raise ValueError(f"dòng lõi thuộc itemid không có hạn mức: {sorted(stray)}")

    df["_id"] = df["labevent_id"].astype(int)
    df["_sid"] = df["subject_id"].astype(int)
    df["_time"] = pd.to_datetime(df["charttime"], format="%Y-%m-%d %H:%M:%S")
    parts = []
    for item, quota in quotas.items():
        sub = df[df["itemid"] == item]
        core = sub[sub["labevent_id"].isin(core_ids)].copy()
        if len(core) > quota:
            raise ValueError(f"itemid {item}: {len(core)} dòng lõi vượt hạn mức {quota}")
        need = quota - len(core)
        rest = sub[~sub["labevent_id"].isin(core_ids)].sort_values(["_sid", "_time", "_id"]).copy()
        if len(rest) < need:
            raise ValueError(f"itemid {item}: cần thêm {need} dòng nhưng chỉ còn {len(rest)}")
        rest["round"] = rest.groupby("subject_id").cumcount().astype("Int64")
        rest = rest.sort_values(["round", "_sid", "_time", "_id"]).head(need)
        core["selection_reason"] = "core_40"
        core["round"] = pd.array([pd.NA] * len(core), dtype="Int64")
        rest["selection_reason"] = "round_robin"
        parts.append(pd.concat([core.drop(columns=["_sid", "_time"]), rest.drop(columns=["_sid", "_time"])]))
    out = pd.concat(parts).sort_values(["itemid", "_id"]).drop(columns=["_id"])
    out["round"] = out["round"].astype("Int64")
    return out.reset_index(drop=True)


def id_list_sha256(ids: Iterable[Any]) -> str:
    """SHA-256 của danh sách ID: xếp tăng dần theo số nguyên, mỗi ID một dòng kết thúc `\\n`."""
    text = "".join(f"{i}\n" for i in sorted(int(str(x).strip()) for x in ids))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Chọn 40 dòng lõi (5 loại x 8 dòng) - xem docs/quy_tac_chon_mau_40.md
# ---------------------------------------------------------------------------

CORE_ITEMIDS: tuple[str, ...] = ("50971", "50912", "51222", "50802", "51492")
CORE_ROWS_PER_ITEM = 8       # số dòng lấy cho mỗi loại
CORE_PATIENTS_PER_ITEM = 3   # số bệnh nhân cho mỗi loại
CORE_EARLIEST_PER_PATIENT = 2  # mỗi bệnh nhân lấy 2 kết quả sớm nhất

# Dòng ưu tiên của từng loại (mục 6.2 của báo cáo: "ưu tiên cặp cùng bệnh nhân và thời gian...,
# giá trị 0 và âm..., có và thiếu cận..., ít nhất 2 giá trị khác nhau").
PRIORITY_KINDS: dict[str, tuple[str, ...]] = {
    "50971": ("cap_cung_gio_khac_gia_tri",),
    "50912": ("cap_cung_gio_cung_gia_tri",),
    "51222": (),
    "50802": ("gia_tri_0", "gia_tri_am"),
    "51492": ("can_0_0", "gia_tri_khac_pho_bien_nhat"),
}
PRIORITY_TEXT: dict[str, str] = {
    "cap_cung_gio_khac_gia_tri": "ưu tiên: cặp cùng bệnh nhân, cùng giờ, khác giá trị",
    "cap_cung_gio_cung_gia_tri": "ưu tiên: cặp cùng bệnh nhân, cùng giờ, cùng giá trị",
    "gia_tri_0": "ưu tiên: kết quả bằng 0",
    "gia_tri_am": "ưu tiên: kết quả âm",
    "can_0_0": "ưu tiên: cận tham chiếu 0–0",
    "gia_tri_khac_pho_bien_nhat": "ưu tiên: giá trị khác giá trị phổ biến nhất của loại này",
}
CORE_NEEDED_COLUMNS = ("labevent_id", "subject_id", "itemid", "charttime", "valuenum",
                       "ref_range_lower", "ref_range_upper")


def _priority_ids(kind: str, df: pd.DataFrame) -> list[int]:
    """`labevent_id` (số nguyên) của dòng ưu tiên loại `kind`; trống nếu không có dòng nào thỏa."""
    df = df.sort_values("_id")
    if kind in ("cap_cung_gio_khac_gia_tri", "cap_cung_gio_cung_gia_tri"):
        want_same = kind == "cap_cung_gio_cung_gia_tri"
        best: list[int] = []
        for _, grp in df.groupby(["_sid", "_time"]):
            if len(grp) < 2:
                continue
            same = grp["_num"].nunique() == 1
            if same == want_same:
                ids = sorted(grp["_id"])[:2]
                if not best or ids[0] < best[0]:
                    best = ids
        return best
    if kind == "gia_tri_0":
        hit = df[df["_num"] == 0]
    elif kind == "gia_tri_am":
        hit = df[df["_num"] < 0]
    elif kind == "can_0_0":
        hit = df[(df["_low"] == 0) & (df["_high"] == 0)]
    elif kind == "gia_tri_khac_pho_bien_nhat":
        counts = df["_num"].value_counts()
        top = min(v for v, c in counts.items() if c == counts.max())  # trùng số lần thì lấy giá trị nhỏ hơn
        hit = df[df["_num"] != top]
    else:
        raise ValueError(f"Loại ưu tiên không biết: {kind}")
    return [int(hit["_id"].iloc[0])] if len(hit) else []


def select_core_40(pool: pd.DataFrame, itemids: Iterable[str] = CORE_ITEMIDS) -> pd.DataFrame:
    """Chọn 8 dòng cho mỗi loại xét nghiệm (5 loại -> 40 dòng) theo `docs/quy_tac_chon_mau_40.md`.

    `pool` là các dòng ĐÃ đạt sàng lọc cơ bản và thuộc loại xét nghiệm chỉ có một đơn vị,
    gồm các cột `CORE_NEEDED_COLUMNS` (dạng chuỗi). Với từng loại:
      1. Dòng ưu tiên (`PRIORITY_KINDS`): dòng có `labevent_id` nhỏ nhất thỏa điều kiện.
      2. Chọn 3 bệnh nhân: bệnh nhân của các dòng ưu tiên, rồi bệnh nhân có `subject_id`
         nhỏ nhất (trong số dòng của loại này) cho đủ 3.
      3. Mỗi bệnh nhân lấy 2 kết quả sớm nhất (`charttime`, trùng thì `labevent_id` nhỏ hơn).
      4. Chưa đủ 8: lấy tiếp dòng còn lại của 3 bệnh nhân đó theo `labevent_id` tăng dần.
    Trả về cột `labevent_id, subject_id, itemid, charttime, buoc, ly_do`; xếp theo (itemid, labevent_id).
    `buoc` là 1, 3 hoặc 4 (bước đã chọn dòng đó). Không phụ thuộc thứ tự dòng đầu vào.
    """
    missing_cols = [c for c in CORE_NEEDED_COLUMNS if c not in pool.columns]
    if missing_cols:
        raise ValueError(f"pool thiếu cột: {missing_cols}")
    df = pool[list(CORE_NEEDED_COLUMNS)].copy()
    for col in CORE_NEEDED_COLUMNS:
        df[col] = df[col].map(clean).astype(object)
    if df["labevent_id"].duplicated().any():
        raise ValueError("pool có labevent_id trùng")
    df["_id"] = df["labevent_id"].astype(int)
    df["_sid"] = df["subject_id"].astype(int)
    df["_time"] = pd.to_datetime(df["charttime"], format="%Y-%m-%d %H:%M:%S")
    df["_num"] = df["valuenum"].map(dec)
    df["_low"] = df["ref_range_lower"].map(dec)
    df["_high"] = df["ref_range_upper"].map(dec)
    if df["_num"].isna().any():
        raise ValueError("pool có valuenum không phải số; cần lọc bằng sàng lọc cơ bản trước")

    parts = []
    for item in itemids:
        sub = df[df["itemid"] == item]
        if sub.empty:
            raise ValueError(f"itemid {item}: pool không có dòng nào")
        chosen: dict[int, tuple[int, str]] = {}  # _id -> (bước, lý do)
        for kind in PRIORITY_KINDS.get(item, ()):
            for i in _priority_ids(kind, sub):
                chosen.setdefault(i, (1, PRIORITY_TEXT[kind]))
        patients: list[int] = []
        for i in chosen:
            s = int(sub.loc[sub["_id"] == i, "_sid"].iloc[0])
            if s not in patients:
                patients.append(s)
        if len(patients) > CORE_PATIENTS_PER_ITEM:
            raise ValueError(f"itemid {item}: dòng ưu tiên thuộc {len(patients)} bệnh nhân, quá {CORE_PATIENTS_PER_ITEM}")
        for s in sorted(sub["_sid"].unique()):
            if len(patients) >= CORE_PATIENTS_PER_ITEM:
                break
            if s not in patients:
                patients.append(s)
        if len(patients) < CORE_PATIENTS_PER_ITEM:
            raise ValueError(f"itemid {item}: chỉ có {len(patients)} bệnh nhân, cần {CORE_PATIENTS_PER_ITEM}")
        for s in sorted(patients):
            earliest = sub[sub["_sid"] == s].sort_values(["_time", "_id"]).head(CORE_EARLIEST_PER_PATIENT)
            for i in earliest["_id"]:
                chosen.setdefault(int(i), (3, f"{CORE_EARLIEST_PER_PATIENT} kết quả sớm nhất của bệnh nhân {s}"))
        if len(chosen) > CORE_ROWS_PER_ITEM:
            raise ValueError(f"itemid {item}: đã chọn {len(chosen)} dòng, vượt {CORE_ROWS_PER_ITEM}")
        rest = sub[sub["_sid"].isin(patients) & ~sub["_id"].isin(chosen)].sort_values("_id")
        need = CORE_ROWS_PER_ITEM - len(chosen)
        if len(rest) < need:
            raise ValueError(f"itemid {item}: cần thêm {need} dòng nhưng chỉ còn {len(rest)}")
        for i in rest["_id"].head(need):
            chosen[int(i)] = (4, "bổ sung: labevent_id nhỏ nhất còn lại của 3 bệnh nhân")
        part = sub[sub["_id"].isin(chosen)].copy()
        part["buoc"] = part["_id"].map(lambda i: chosen[i][0]).astype(int)
        part["ly_do"] = part["_id"].map(lambda i: chosen[i][1])
        parts.append(part)
    out = pd.concat(parts).sort_values(["itemid", "_id"])
    return out[["labevent_id", "subject_id", "itemid", "charttime", "buoc", "ly_do"]].reset_index(drop=True)
