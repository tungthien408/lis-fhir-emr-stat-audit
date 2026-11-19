"""Test chọn mẫu 1.000 kết quả, dùng bảng nhỏ tự tạo (không dùng dữ liệu MIMIC thật)."""
import pandas as pd
import pytest

from analysis_core.selection import allocate_quotas, basic_screen_reason, id_list_sha256, select_round_robin


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
    assert q == {"50971": 209, "50912": 209, "51222": 209, "50802": 200, "51492": 173}
    assert sum(q.values()) == 1000
    q["50971"] = 1  # sửa bản sao không ảnh hưởng lần gọi sau
    assert allocate_quotas()["50971"] == 209


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
