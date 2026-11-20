"""Test sàng lọc, chọn 40 dòng lõi và chọn 1.000 kết quả, dùng bảng nhỏ tự tạo (không dùng dữ liệu MIMIC thật)."""
import pandas as pd
import pytest

from analysis_core.selection import (
    CORE_ITEMIDS, allocate_quotas, basic_screen_reason, id_list_sha256, screen_labevents,
    select_core_40, select_round_robin,
)


def make_pool(rows):
    """rows: (labevent_id, subject_id, itemid, charttime)."""
    return pd.DataFrame(rows, columns=["labevent_id", "subject_id", "itemid", "charttime"], dtype="string")


# 3 bệnh nhân, mỗi người 3 kết quả cho itemid "A"
POOL = make_pool([
    (str(100 + s * 10 + k), str(s), "A", f"2100-01-0{k + 1} 08:00:00")
    for s in (3, 1, 2) for k in range(3)
])


def ids(df):
    return list(df["labevent_id"])


def test_round_robin_order():
    out = select_round_robin(POOL, set(), {"A": 4})
    assert len(out) == 4
    # Lượt 0: cả 3 bệnh nhân (kết quả sớm nhất); lượt 1: chỉ bệnh nhân nhỏ nhất.
    assert sorted(out.loc[out["round"] == 0, "subject_id"]) == ["1", "2", "3"]
    assert list(out.loc[out["round"] == 1, "subject_id"]) == ["1"]
    assert set(out.loc[out["round"] == 0, "labevent_id"]) == {"110", "120", "130"}
    assert list(out.loc[out["round"] == 1, "labevent_id"]) == ["111"]
    assert set(out["selection_reason"]) == {"round_robin"}


def test_tie_on_charttime_uses_smaller_labevent_id():
    pool = make_pool([("20", "1", "A", "2100-01-01 08:00:00"), ("9", "1", "A", "2100-01-01 08:00:00"),
                      ("30", "1", "A", "2100-01-02 08:00:00")])
    out = select_round_robin(pool, set(), {"A": 1})
    assert ids(out) == ["9"]  # so sánh dạng số: 9 < 20 (dạng chuỗi sẽ sai)


def test_core_rows_always_present_and_counted_in_quota():
    out = select_round_robin(POOL, {"131", "132"}, {"A": 4})
    assert len(out) == 4
    assert {"131", "132"} <= set(ids(out))
    core = out[out["labevent_id"].isin({"131", "132"})]
    assert set(core["selection_reason"]) == {"core_40"}
    assert core["round"].isna().all()
    assert (out["selection_reason"] == "round_robin").sum() == 2


def test_deterministic_and_input_order_independent():
    first = select_round_robin(POOL, {"110"}, {"A": 5})
    again = select_round_robin(POOL, {"110"}, {"A": 5})
    shuffled = select_round_robin(POOL.sample(frac=1, random_state=7), {"110"}, {"A": 5})
    reversed_ = select_round_robin(POOL.iloc[::-1], {"110"}, {"A": 5})
    pd.testing.assert_frame_equal(first, again)
    pd.testing.assert_frame_equal(first, shuffled)
    pd.testing.assert_frame_equal(first, reversed_)


def test_not_enough_rows_raises():
    with pytest.raises(ValueError, match="itemid A"):
        select_round_robin(POOL, set(), {"A": 10})


def test_missing_core_row_raises():
    with pytest.raises(ValueError, match="thiếu"):
        select_round_robin(POOL, {"999"}, {"A": 4})


def test_quotas_fixed_and_sum_1000():
    q = allocate_quotas()
    assert q == {"50971": 210, "50912": 210, "51222": 210, "50802": 210, "51492": 160}
    assert sum(q.values()) == 1000
    q["50971"] = 1  # sửa bản sao không ảnh hưởng lần gọi sau
    assert allocate_quotas()["50971"] == 210


def test_id_list_sha256_hand_value():
    # printf '1\n2\n3\n' | sha256sum
    expected = "14c5e74c4b96ccef41cd94db73a9ec3348038ac094feca4fd897cecffa07cdae"
    assert id_list_sha256(["3", "1", "2"]) == expected
    assert id_list_sha256([2, 3, 1]) == expected
    # sắp xếp theo số nguyên, không theo chuỗi: "10" đứng sau "9"
    assert id_list_sha256(["10", "9"]) == id_list_sha256(["9", "10"])


# ---- sàng lọc cơ bản ----
PATIENTS, LABS = {"1"}, {"50971"}


def good_row(**over):
    row = {"subject_id": "1", "itemid": "50971", "value": "4.1", "valuenum": "4.10", "valueuom": "mEq/L",
           "charttime": "2100-01-01 08:00:00", "ref_range_lower": "3.3", "ref_range_upper": "5.1", "comments": ""}
    row.update(over)
    return row


@pytest.mark.parametrize("over,expected", [
    ({}, "PASS"),
    ({"value": "<0.5", "valuenum": "0.5"}, "value_co_dau_so_sanh"),
    ({"valueuom": ""}, "thieu_hoac_khong_hop_le_don_vi"),
    ({"comments": "hemolyzed"}, "comments_can_xem_xet"),
    ({"subject_id": "9"}, "subject_id_khong_ton_tai"),
    ({"valuenum": "4.2"}, "value_va_valuenum_khong_khop"),
    ({"ref_range_lower": "6", "ref_range_upper": "5"}, "can_duoi_lon_hon_can_tren"),
    ({"ref_range_lower": "", "ref_range_upper": ""}, "PASS"),
])
def test_basic_screen_reason(over, expected):
    assert basic_screen_reason(good_row(**over), PATIENTS, LABS) == expected


def test_screen_labevents_matches_row_function():
    patients = pd.DataFrame({"subject_id": ["1"]})
    labs = pd.DataFrame({"itemid": ["50971"]})
    events = pd.DataFrame([good_row(), good_row(valueuom=""), good_row(subject_id="9")], index=[5, 6, 7])
    out = screen_labevents(events, patients, labs)
    assert list(out) == ["PASS", "thieu_hoac_khong_hop_le_don_vi", "subject_id_khong_ton_tai"]
    assert list(out.index) == [5, 6, 7] and out.name == "basic_screen"


# ---- chọn 40 dòng lõi ----
def core_pool(rows):
    """rows: (labevent_id, subject_id, itemid, charttime, valuenum[, low, high])."""
    full = [tuple(r) + ("", "") * ((7 - len(r)) // 2) for r in rows]
    return pd.DataFrame(full, columns=["labevent_id", "subject_id", "itemid", "charttime", "valuenum",
                                       "ref_range_lower", "ref_range_upper"], dtype="string")


def days(sid, n, item, first_id, value="1", start_day=1):
    """n kết quả của bệnh nhân sid, mỗi ngày một kết quả, labevent_id tăng dần từ first_id."""
    return [(str(first_id + k), str(sid), item, f"2100-01-{start_day + k:02d} 08:00:00", value) for k in range(n)]


def chosen_ids(out, item=None):
    sub = out if item is None else out[out["itemid"] == item]
    return sorted(int(i) for i in sub["labevent_id"])


def test_core_no_priority_takes_two_earliest_per_patient_then_smallest_ids():
    # Không có dòng ưu tiên (loại 51222): 2 sớm nhất mỗi bệnh nhân, rồi labevent_id nhỏ nhất còn lại.
    rows = days(1, 5, "51222", 10) + days(2, 3, "51222", 20) + days(3, 3, "51222", 30) + days(4, 3, "51222", 1)
    out = select_core_40(core_pool(rows), ["51222"])
    # BN 1,2,3 (BN 4 không vào dù labevent_id nhỏ nhất). 6 dòng sớm nhất + 2 id nhỏ nhất còn lại: 12, 13
    assert chosen_ids(out) == [10, 11, 12, 13, 20, 21, 30, 31]
    assert dict(zip(out["labevent_id"], out["buoc"])) == {"10": 3, "11": 3, "12": 4, "13": 4,
                                                          "20": 3, "21": 3, "30": 3, "31": 3}


def test_core_pair_different_values_pulls_its_patient_in():
    # Cặp cùng giờ khác giá trị thuộc bệnh nhân 4 -> bệnh nhân 4 vào thay cho bệnh nhân 3.
    rows = (days(1, 3, "50971", 10) + days(2, 3, "50971", 20) + days(3, 3, "50971", 30)
            + [("40", "4", "50971", "2100-02-01 08:00:00", "3.3"), ("41", "4", "50971", "2100-02-01 08:00:00", "3.4"),
               ("42", "4", "50971", "2100-03-01 08:00:00", "4.0"), ("43", "4", "50971", "2100-03-02 08:00:00", "4.1")])
    out = select_core_40(core_pool(rows), ["50971"])
    assert {"40", "41"} <= set(out["labevent_id"])
    assert set(out["subject_id"]) == {"1", "2", "4"}
    assert len(out) == 8
    assert set(out.loc[out["labevent_id"].isin(["40", "41"]), "buoc"]) == {1}


def test_core_pair_same_value_ignores_pairs_with_different_values():
    rows = (days(1, 4, "50912", 10, "0.5") + days(2, 3, "50912", 20, "0.5") + days(3, 3, "50912", 30, "0.5")
            + [("5", "1", "50912", "2100-05-01 08:00:00", "0.4"), ("6", "1", "50912", "2100-05-01 08:00:00", "0.9"),   # khác giá trị
               ("50", "1", "50912", "2100-06-01 08:00:00", "0.7"), ("51", "1", "50912", "2100-06-01 08:00:00", "0.7")])  # cùng giá trị
    out = select_core_40(core_pool(rows), ["50912"])
    got = set(out["labevent_id"])
    assert {"50", "51"} <= got and not {"5", "6"} & got


def test_core_zero_and_negative_rows_come_first():
    base = days(1, 3, "50802", 10) + days(2, 3, "50802", 20) + days(3, 3, "50802", 30)
    special = [("80", "5", "50802", "2100-03-01 08:00:00", "1"), ("81", "5", "50802", "2100-03-02 08:00:00", "2"),
               ("90", "5", "50802", "2100-04-01 08:00:00", "0"), ("91", "5", "50802", "2100-04-02 08:00:00", "-2"),
               ("92", "5", "50802", "2100-04-03 08:00:00", "-3")]
    out = select_core_40(core_pool(base + special), ["50802"])
    got = set(out["labevent_id"])
    assert {"90", "91"} <= got and "92" not in got     # chỉ lấy dòng 0 và dòng âm đầu tiên
    assert set(out.loc[out["labevent_id"].isin(["90", "91"]), "buoc"]) == {1}
    assert set(out["subject_id"]) == {"5", "1", "2"}
    assert len(out) == 8


def test_core_zero_range_and_uncommon_value_for_protein():
    # Bệnh nhân 1 chỉ có 1 dòng; dòng cận 0-0 thuộc bệnh nhân 4 (không phải 3 bệnh nhân nhỏ nhất).
    rows = ([("1", "1", "51492", "2100-01-01 08:00:00", "30")] + days(2, 4, "51492", 20, "30")
            + days(3, 3, "51492", 30, "30")
            + [("40", "4", "51492", "2100-02-01 08:00:00", "30", "0", "0"), ("41", "4", "51492", "2100-02-02 08:00:00", "30"),
               ("7", "2", "51492", "2100-09-01 08:00:00", "100")])
    out = select_core_40(core_pool(rows), ["51492"])
    got = set(out["labevent_id"])
    assert {"40", "7"} <= got                       # cận 0-0 và giá trị khác 30 (phổ biến nhất)
    assert set(out["subject_id"]) == {"1", "2", "4"}  # bệnh nhân 3 bị loại, bệnh nhân 4 vào
    assert len(out) == 8


def test_core_tie_on_charttime_uses_numeric_labevent_id():
    rows = ([("20", "1", "51222", "2100-01-01 08:00:00", "1"), ("9", "1", "51222", "2100-01-01 08:00:00", "2")]
            + days(1, 6, "51222", 100, start_day=2) + days(2, 3, "51222", 200) + days(3, 3, "51222", 300))
    out = select_core_40(core_pool(rows), ["51222"])
    assert {"9", "20"} <= set(out["labevent_id"])  # cả hai là 2 sớm nhất của bệnh nhân 1


def test_core_deterministic_and_input_order_independent():
    rows = (days(1, 5, "50971", 10) + days(2, 3, "50971", 20) + days(3, 3, "50971", 30)
            + days(1, 5, "51222", 110) + days(2, 3, "51222", 120) + days(3, 3, "51222", 130))
    pool = core_pool(rows)
    first = select_core_40(pool, ["50971", "51222"])
    pd.testing.assert_frame_equal(first, select_core_40(pool.sample(frac=1, random_state=5), ["50971", "51222"]))
    pd.testing.assert_frame_equal(first, select_core_40(pool.iloc[::-1], ["50971", "51222"]))
    assert len(first) == 16


@pytest.mark.parametrize("rows,match", [
    (days(1, 5, "51222", 10) + days(2, 5, "51222", 20), "chỉ có 2 bệnh nhân"),
    (days(1, 2, "51222", 10) + days(2, 1, "51222", 20) + days(3, 1, "51222", 30), "chỉ còn"),
    ([], "pool không có dòng nào"),
])
def test_core_errors(rows, match):
    with pytest.raises(ValueError, match=match):
        select_core_40(core_pool(rows), ["51222"])


def test_core_rejects_duplicate_id_and_non_numeric_value():
    rows = days(1, 5, "51222", 10) + days(2, 3, "51222", 20) + days(3, 3, "51222", 30)
    with pytest.raises(ValueError, match="trùng"):
        select_core_40(core_pool(rows + [rows[0]]), ["51222"])
    bad = [tuple(r[:4]) + ("abc",) for r in rows[:1]] + rows[1:]
    with pytest.raises(ValueError, match="không phải số"):
        select_core_40(core_pool(bad), ["51222"])


def test_core_itemids_constant():
    assert CORE_ITEMIDS == ("50971", "50912", "51222", "50802", "51492")
