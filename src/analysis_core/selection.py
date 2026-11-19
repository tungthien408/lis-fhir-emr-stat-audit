"""Chọn tập 1.000 kết quả cho E1 theo `docs/quy_tac_chon_mau_1000.md`.

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
