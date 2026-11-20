"""Trích các con số trong báo cáo khảo sát (dạng markdown) ra CSV để notebook 01 đối chiếu với dữ liệu gốc.

Chạy:  python scripts/trich_so_lieu_bao_cao.py <duong_dan_bao_cao.md>

Đầu vào: bản markdown của báo cáo "Báo cáo khảo sát dữ liệu xét nghiệm MIMIC IV" (xuất từ Google Docs).
Đầu ra (thư mục `data/external/`, được commit):
  - bao_cao_so_lieu.csv      : muc_bao_cao, ten_so_lieu, gia_tri_trong_bao_cao   (mục 1–4 và 6)
  - bao_cao_phu_luc_a.csv    : bảng phụ lục A (498 loại xét nghiệm)
  - bao_cao_phu_luc_b.csv    : bảng phụ lục B
  - bao_cao_muc_6_3.csv      : 40 dòng của mục 6.3

Chỉ ĐỌC báo cáo, không sửa. Số được ghi lại đúng như báo cáo nói (bỏ dấu tách nghìn, dấu phẩy thập phân đổi thành dấu chấm).
Nếu báo cáo đổi cách viết đến mức mẫu câu không còn khớp, script dừng và nêu rõ mẫu nào không tìm thấy;
không tự đoán. `ten_so_lieu` phải trùng tên mà `src/analysis_core/survey.py` dùng.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "external"


def clean(s: str) -> str:
    """Bỏ ký tự thoát markdown (dấu \\), dấu ** và khoảng trắng thừa."""
    return re.sub(r"\s+", " ", s.replace("\\", "").replace("**", "")).strip()


def num(s: str) -> str:
    """'107.727' -> '107727'; '26,38%' -> '26.38'; '296,3' -> '296.3'."""
    s = s.strip().rstrip("%").strip().rstrip(".")  # bỏ dấu chấm cuối câu
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    return s


def nums_in_text(s: str) -> str:
    """Bỏ dấu tách nghìn của các số trong chuỗi (dùng cho bảng đơn vị)."""
    return re.sub(r"\d{1,3}(?:\.\d{3})+", lambda m: m.group(0).replace(".", ""), s)


class Report:
    def __init__(self, text: str):
        self.sections: list[dict] = []   # {level, title, muc, text}
        cur = None
        muc = ""
        for line in text.splitlines():
            m = re.match(r"^(#{1,4})\s+(.*)$", line)
            if m:
                level, title = len(m.group(1)), clean(m.group(2))
                mm = re.match(r"^(\d+(?: \d+)?) \D", title + " x") if title[:1].isdigit() else None
                if level <= 2:
                    muc = ".".join(mm.group(1).split()) if mm and not re.match(r"^\d{5}", title) else title
                cur = {"level": level, "title": title, "muc": muc, "lines": []}
                self.sections.append(cur)
            elif cur is not None:
                cur["lines"].append(line)
            else:
                cur = {"level": 0, "title": "", "muc": "mo_dau", "lines": [line]}
                self.sections.append(cur)
        for s in self.sections:
            s["text"] = "\n".join(s["lines"])

    def muc(self, muc: str) -> list[dict]:
        found = [s for s in self.sections if s["muc"] == muc]
        if not found:
            raise KeyError(f"Không thấy mục {muc} trong báo cáo")
        return found

    def text(self, muc: str) -> str:
        """Toàn bộ văn bản của một mục (gồm các mục con cấp 3), đã bỏ ký tự thoát."""
        return clean_multiline("\n".join(s["text"] for s in self.muc(muc)))

    def tables(self, muc: str) -> list[list[list[str]]]:
        """Các bảng của mục: mỗi bảng là danh sách dòng (không gồm dòng tiêu đề), mỗi dòng là danh sách ô."""
        out = []
        for s in self.muc(muc):
            out += parse_tables(s["text"])
        return out


def clean_multiline(s: str) -> str:
    return "\n".join(clean(x) for x in s.replace("\\", "").splitlines())


def parse_tables(text: str) -> list[list[list[str]]]:
    tables, cur = [], []
    for line in text.splitlines() + [""]:
        if line.startswith("|"):
            cur.append(line)
        elif cur:
            sep = next((i for i, r in enumerate(cur) if re.match(r"^\|\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$", r)), None)
            body = cur[sep + 1:] if sep is not None else cur
            rows = [[clean(c) for c in r.strip().strip("|").split(" | ")] for r in body]
            tables.append(rows[1:])  # dòng đầu sau dòng phân cách là tiêu đề cột (in đậm)
            cur = []
    return tables


def grab(text: str, pattern: str, what: str) -> tuple[str, ...]:
    m = re.search(pattern, text, flags=re.S)
    if not m:
        raise ValueError(f"Không tìm thấy mẫu câu cho '{what}': {pattern}")
    return m.groups()


def extract_scalars(rp: Report) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []

    def add(muc, ten, val):
        out.append((muc, ten, num(str(val)) if re.fullmatch(r"[\d.,]+%?", str(val)) else str(val)))

    # ---- Kết quả chính (phần mở đầu)
    t = clean_multiline(rp.muc("Kết quả chính")[0]["text"])
    n_res, n_pat = grab(t, r"kiểm tra ([\d.]+) kết quả của (\d+) bệnh nhân", "kết quả chính")
    add("Kết quả chính", "số kết quả đã kiểm tra", n_res)
    add("Kết quả chính", "số bệnh nhân", n_pat)

    # ---- Mục 1
    for r in rp.tables("1")[0]:
        name = r[0].replace(".csv.gz", "")
        add("1", f"{name}: số bản ghi", r[1])
        add("1", f"{name}: số cột", r[2])
    for name, h in re.findall(r"(\w+)\.csv\.gz\s+khớp bản 2\.2\s+([0-9a-f]{64})", rp.text("1.1")):
        add("1.1", f"SHA-256 {name}.csv.gz", h)

    # ---- Mục 2
    t = rp.text("2.1")
    n, k = grab(t, r"Bảng có (\d+) dòng và (\d+) subject_id khác nhau", "2.1 số dòng")
    add("2.1", "patients: số dòng", n)
    add("2.1", "patients: số subject_id khác nhau", k)
    for r in rp.tables("2.1")[0]:
        add("2.1", f"patients.{r[0]}: thiếu", r[3])
    grab(t, r"Tuổi trên 89 tại năm mốc được nguồn quy về 91", "2.1 tuổi trên 89")
    add("2.1", "patients: số bệnh nhân có anchor_age > 89 nhưng khác 91", "0")  # báo cáo khẳng định mọi tuổi > 89 đều là 91

    t = rp.text("2.2")
    a, b, c = grab(t, r"Bảng có ([\d.]+) itemid khác nhau\. Chỉ (\d+) itemid xuất hiện trong labevents; ([\d.]+) mã còn lại", "2.2 itemid")
    add("2.2", "d_labitems: số itemid khác nhau", a)
    add("2.2", "d_labitems: số itemid có trong labevents", b)
    add("2.2", "d_labitems: số itemid không có kết quả trong labevents", c)
    grab(t, r"Bốn dòng có label rỗng hoặc chỉ gồm khoảng trắng, nhưng không dòng xét nghiệm nào dùng các mã đó", "2.2 label rỗng")
    add("2.2", "d_labitems: số dòng có label rỗng hoặc chỉ khoảng trắng", "4")
    add("2.2", "số kết quả xét nghiệm dùng itemid có label rỗng", "0")
    for r in rp.tables("2.2")[0]:
        add("2.2", f"d_labitems.{r[0]}: thiếu", r[3])  # ô trống trong báo cáo được giữ là chuỗi rỗng

    t = rp.text("2.3")
    a, b = grab(t, r"gồm ([\d.]+) kết quả của (\d+) bệnh nhân", "2.3 số dòng")
    add("2.3", "labevents: số dòng", a)
    add("2.3", "labevents: số subject_id khác nhau", b)
    for r in rp.tables("2.3")[0]:
        add("2.3", f"labevents.{r[0]}: thiếu", r[3])

    t = rp.text("2.4")
    (a,) = grab(t, r"Bảng có (\d+) lượt nhập viện", "2.4 số dòng")
    add("2.4", "admissions: số dòng", a)
    grab(t, r"hadm_id là mã duy nhất của từng lượt", "2.4 hadm_id duy nhất")
    add("2.4", "admissions: số hadm_id khác nhau", a)
    for r in rp.tables("2.4")[0]:
        add("2.4", f"admissions.{r[0]}: thiếu", r[3])
    (a,) = grab(t, r"Trong language có (\d+) dòng ghi dấu \?", "2.4 language ?")
    add("2.4", "admissions.language: số dòng ghi dấu ?", a)

    # ---- Mục 3
    tb = {r[0]: r[1] for r in rp.tables("3")[0]}
    for key, label in (("labevents → patients qua subject_id", "labevents → patients"), ("labevents → d_labitems qua itemid", "labevents → d_labitems"),
                       ("admissions → patients", "admissions → patients")):
        a, b = grab(tb[key], r"([\d.]+) nối được; ([\d.]+) không nối được", key)
        add("3", f"{label}: nối được", a)
        add("3", f"{label}: không nối được", b)
    a, b = grab(tb["labevents → admissions khi hadm_id có mặt"], r"([\d.]+) nối được; ([\d.]+) mã không tìm thấy", "admissions")
    add("3", "labevents → admissions (khi có hadm_id): nối được", a)
    add("3", "labevents → admissions (khi có hadm_id): mã không tìm thấy", b)
    add("3", "hadm_id có nhưng thuộc bệnh nhân khác", tb["hadm_id có nhưng thuộc bệnh nhân khác"])
    a, b = grab(tb["hadm_id thiếu"], r"([\d.]+) dòng, tương đương ([\d,]+)%", "hadm_id thiếu")
    add("3", "hadm_id thiếu: số dòng", a)
    add("3", "hadm_id thiếu: tỷ lệ (%)", b)
    (a,) = grab(rp.text("3"), r"Nối trái với admissions giữ nguyên ([\d.]+) dòng", "nối trái")
    add("3", "nối trái labevents với admissions: số dòng", a)

    for r in rp.tables("3.1")[0]:
        name, key = r[0], r[1]
        add("3.1", f"{name}.{key}: giá trị thiếu", r[2])
        add("3.1", f"{name}.{key}: dòng lặp mã", r[3])
        add("3.1", f"{name}: dòng trùng toàn bộ", r[4])
    t = rp.text("3.1")
    (a,) = grab(t, r"có (\d+) dòng vượt quá dòng đầu trong các nhóm trùng bộ ba này", "3.1 470")
    add("3.1", "dòng vượt quá dòng đầu trong nhóm (subject_id, itemid, charttime)", a)
    (a,) = grab(t, r"Thêm value và valueuom vẫn còn (\d+) dòng vượt quá dòng đầu", "3.1 194")
    add("3.1", "dòng vượt quá dòng đầu trong nhóm (subject_id, itemid, charttime, value, valueuom)", a)
    s, ts, v = grab(t, r"171 và 184 cùng thuộc subject_id (\d+), cùng thời điểm ([\d-]+ [\d:]+), cùng giá trị ([\d.]+) mg/dL", "3.1 ví dụ")
    add("3.1", "ví dụ 171 và 184: cùng subject_id, itemid, charttime và value", "có")
    add("3.1", "ví dụ 171 và 184: subject_id", s)
    add("3.1", "ví dụ 171 và 184: charttime", ts)
    add("3.1", "ví dụ 171 và 184: value", v)
    a, b = grab(t, r"có ([\d.]+) specimen_id khác nhau, không có specimen_id nào thuộc nhiều subject_id\. Có ([\d.]+) cặp bệnh nhân và itemid", "3.1 specimen")
    add("3.1", "số specimen_id khác nhau", a)
    add("3.1", "số specimen_id thuộc nhiều subject_id", "0")
    add("3.1", "số cặp (subject_id, itemid) có nhiều kết quả", b)

    t = rp.text("3.2")
    grab(t, r"Không phát hiện số vô hạn, NaN trong các cột số, cận tham chiếu sai định dạng hoặc cận dưới lớn hơn cận trên", "3.2 số")
    add("3.2", "ô valuenum và cận không phải số hữu hạn (vô hạn, NaN, sai dạng)", "0")
    add("3.2", "dòng có cận dưới lớn hơn cận trên", "0")
    grab(t, r"Tất cả ngày giờ có mặt đều phân tích được", "3.2 ngày giờ")
    add("3.2", "ô ngày giờ có mặt nhưng không phân tích được", "0")
    grab(t, r"không có lượt nhập viện có dischtime sớm hơn admittime", "3.2 dischtime")
    add("3.2", "lượt nhập viện có dischtime sớm hơn admittime", "0")
    a, b, c = grab(t, r"valueuom có (\d+) dòng chỉ chứa một khoảng trắng\. Vì vậy, tổng số thiếu đơn vị là ([\d.]+), gồm ([\d.]+) ô rỗng", "3.2 valueuom")
    add("3.2", "valueuom: số dòng chỉ chứa khoảng trắng", a)
    add("3.2", "valueuom: tổng số thiếu đơn vị", b)
    add("3.2", "valueuom: số dòng ô rỗng", c)
    grab(t, r"Có hai nhãn danh mục chứa khoảng trắng ở đầu hoặc cuối, trong đó một nhãn là khoảng trắng hoàn toàn", "3.2 nhãn")
    add("3.2", "d_labitems.label: số nhãn có khoảng trắng ở đầu hoặc cuối", "2")
    add("3.2", "d_labitems.label: số nhãn chỉ gồm khoảng trắng", "1")

    # ---- Mục 4
    t = rp.text("4.1")
    a, b, c = grab(t, r"Có (\d+) itemid xuất hiện, thuộc (\d+) loại mẫu và (\d+) nhóm xét nghiệm\. Mỗi itemid được tra đúng một dòng danh mục", "4.1")
    add("4.1", "số itemid xuất hiện trong labevents", a)
    add("4.1", "số loại mẫu (fluid)", b)
    add("4.1", "số nhóm xét nghiệm (category)", c)
    add("4.1", "số itemid tra được đúng một dòng d_labitems", a)
    t1, t2, t3 = rp.tables("4.1")
    for r in t1:
        add("4.1", f"nhóm {r[0]}: số kết quả", r[1])
    for r in t2:
        add("4.1", f"loại mẫu {r[0]}: số kết quả", r[1])
    for rank, r in enumerate(t3, start=1):
        add("4.1", f"hạng {rank}: itemid", r[0])
        add("4.1", f"hạng {rank}: tên", r[1])
        add("4.1", f"hạng {rank}: mẫu và nhóm", r[2])
        add("4.1", f"hạng {rank}: số kết quả", r[3])
        add("4.1", f"hạng {rank}: số bệnh nhân", r[4])

    for r in rp.tables("4.2")[0]:
        add("4.2", f"{r[0]}: có dữ liệu", r[1])
        add("4.2", f"{r[0]}: thiếu", r[2])
        add("4.2", f"{r[0]}: tỷ lệ có (%)", r[3])
    t = rp.text("4.2")
    a, b = grab(t, r"có đủ hai cận ở ([\d.]+) dòng; thiếu cả hai ở ([\d.]+) dòng; không có dòng chỉ mang một cận", "4.2 cận")
    add("4.2", "khoảng tham chiếu: đủ hai cận", a)
    add("4.2", "khoảng tham chiếu: thiếu cả hai cận", b)
    add("4.2", "khoảng tham chiếu: chỉ một cận", "0")
    grab(t, r"Cũng không có cận tham chiếu đảo thứ tự", "4.2 cận đảo")
    add("4.2", "khoảng tham chiếu: cận dưới lớn hơn cận trên", "0")

    names = {"Số thuần": "số thuần", "Có dấu so sánh": "có dấu so sánh",
             "Có chữ hoặc ký hiệu, không có dấu so sánh": "có chữ hoặc ký hiệu, không có dấu so sánh", "Rỗng": "rỗng"}
    for r in rp.tables("4.3")[0]:
        add("4.3", f"value {names[r[0]]}: số dòng", r[1])
        add("4.3", f"value {names[r[0]]}: tỷ lệ (%)", r[2])
    t = rp.text("4.3")
    (a,) = grab(t, r"Tổng bốn nhóm bằng ([\d.]+)", "4.3 tổng")
    add("4.3", "tổng bốn dạng value", a)
    grab(t, r"Toàn bộ ([\d.]+) value dạng số đều có valuenum bằng nhau về số học", "4.3 valuenum bằng")
    add("4.3", "value số thuần nhưng valuenum không bằng về số học", "0")
    a, b = grab(t, r"Có ([\d.]+) dòng value không phải số thuần nhưng valuenum có số\. Riêng value = ___ xuất hiện ([\d.]+) lần", "4.3 value ___")
    add("4.3", "value không phải số thuần nhưng valuenum có số", a)
    add("4.3", "value = ___: số dòng", b)
    nm, v, vn = grab(t, r"labevent_id 172082 của (\w+) có value = (___), valuenum = (\d+) và comments chứa", "4.3 172082")
    add("4.3", "labevent 172082: value", v)
    add("4.3", "labevent 172082: valuenum", vn)
    add("4.3", "labevent 172082: tên xét nghiệm", nm)
    add("4.3", "labevent 172082: comments không rỗng", "có")
    a, b = grab(t, r"Cả ([\d.]+) dòng Glucose máu, itemid (\d+), đều có value = ___ và comments", "4.3 glucose")
    add("4.3", f"itemid {b} (Glucose máu): số dòng", a)
    add("4.3", f"itemid {b}: số dòng có value = ___", a)
    add("4.3", f"itemid {b}: số dòng có comments", a)
    n, strs = grab(t, r"Có (\d+) kết quả chứa dấu so sánh, gồm các chuỗi (.+?)\. Chẳng hạn", "4.3 dấu so sánh")
    items = [x.strip() for x in re.split(r",| và ", strs) if x.strip()]
    add("4.3", "value có dấu so sánh: các chuỗi khác nhau", " | ".join(sorted(items)))
    add("4.3", "value có dấu so sánh: số chuỗi khác nhau", str(len(items)))
    v, u = grab(t, r"labevent_id 150770 ghi (\S+) (\S+);", "4.3 150770")
    add("4.3", "labevent 150770: value", v)
    add("4.3", "labevent 150770: valueuom", u)
    a, b = grab(t, r"Trong valuenum có ([\d.]+) giá trị bằng 0 và ([\d.]+) giá trị âm", "4.3 0 và âm")
    add("4.3", "valuenum bằng 0: số dòng", a)
    add("4.3", "valuenum âm: số dòng", b)

    t = rp.text("4.4")
    (a,) = grab(t, r"Có (\d+) itemid có nhiều hơn một chuỗi đơn vị không rỗng", "4.4 nhiều đơn vị")
    add("4.4", "số itemid có nhiều hơn một chuỗi đơn vị không rỗng", a)
    for r in rp.tables("4.4")[0]:
        add("4.4", f"{r[0]}: đơn vị và số dòng", nums_in_text(r[1]))
    (a,) = grab(t, r"Có ([\d.]+) dòng ghi valueuom = N/A", "4.4 N/A")
    add("4.4", "valueuom = N/A: số dòng", a)
    grab(t, r"Trong tập ([\d.]+) dòng vượt qua sàng lọc số cơ bản không có N/A, \? hoặc ___ ở đơn vị", "4.4 sàng lọc đơn vị")
    add("4.4", "dòng đạt sàng lọc cơ bản có đơn vị N/A, ? hoặc ___", "0")
    a, b, c = grab(t, r"comments có nội dung ở ([\d.]+) dòng; ([\d.]+) dòng ghi đúng ___ và ([\d.]+) dòng có comments nhưng value rỗng", "4.4 comments")
    add("4.4", "comments có nội dung: số dòng", a)
    add("4.4", "comments đúng ___: số dòng", b)
    add("4.4", "comments có nội dung nhưng value rỗng: số dòng", c)
    grab(t, r"không có dòng value dạng số thuần nào đồng thời có comments không rỗng", "4.4 số thuần có comments")
    add("4.4", "value số thuần đồng thời có comments", "0")

    tb = {r[0]: r for r in rp.tables("4.5")[0]}
    for col in ("charttime", "storetime"):
        add("4.5", f"{col}: có dữ liệu", tb[col][1])
        lo, hi = grab(tb[col][2], r"([\d-]+ [\d:]+) đến ([\d-]+ [\d:]+)", f"4.5 {col}")
        add("4.5", f"{col}: nhỏ nhất", lo)
        add("4.5", f"{col}: lớn nhất", hi)
    t = rp.text("4.5")
    (a,) = grab(t, r"Có (\d+) dòng thiếu storetime", "4.5 thiếu storetime")
    add("4.5", "storetime: thiếu", a)
    a, b, c = grab(t, r"Trong ([\d.]+) dòng có đủ hai mốc, (\d+) dòng có hai mốc bằng nhau, ([\d.]+) dòng có storetime sau charttime, không có dòng storetime trước charttime", "4.5 hai mốc")
    add("4.5", "có đủ hai mốc: số dòng", a)
    add("4.5", "hai mốc bằng nhau: số dòng", b)
    add("4.5", "storetime sau charttime: số dòng", c)
    add("4.5", "storetime trước charttime: số dòng", "0")
    a, b, c = grab(t, r"Trung vị chênh lệch là ([\d,.]+) phút, phân vị 95 là ([\d,.]+) phút và lớn nhất là ([\d,.]+) phút", "4.5 độ trễ")
    add("4.5", "độ trễ: trung vị (phút)", a)
    add("4.5", "độ trễ: phân vị 95 (phút, nội suy tuyến tính)", b)
    add("4.5", "độ trễ: lớn nhất (phút)", c)

    tb = rp.tables("4.6")
    keys = ["số thuần đủ trường cơ bản (qua sàng lọc)", "trong nhóm trên có itemid nhiều đơn vị",
            "ứng viên có itemid chỉ một đơn vị", "không đạt sàng lọc số cơ bản"]
    for k, r in zip(keys, tb[0]):
        add("4.6", k, r[1])
    keys = ["loại vì thiếu value", "loại vì value không phải số thuần (không tính dấu so sánh)",
            "loại vì value dạng số nhưng thiếu đơn vị", "loại vì giá trị có dấu so sánh"]
    for k, r in zip(keys, tb[1]):
        add("4.6", k, r[1])
    (a,) = grab(rp.text("4.6"), r"Tổng là ([\d.]+)\.", "4.6 tổng")
    add("4.6", "tổng các lý do bị loại", a)

    # ---- Mục 6.1
    for s in rp.muc("6.1"):
        if s["level"] != 3:
            continue
        item_name = s["title"]
        t = clean_multiline(s["text"])
        n, p, c = grab(t, r"Nguồn có ([\d.]+) kết quả, (\d+) bệnh nhân và ([\d.]+) ứng viên qua sàng lọc", f"6.1 {item_name}")
        fluid, cat, unit = grab(t, r"Mẫu (\w+), nhóm (\w+(?: \w+)?), đơn vị duy nhất (\S+)\.", f"6.1 {item_name} mẫu")
        chosen, cp, dv = grab(t, r"Chọn (\d+) kết quả của (\d+) bệnh nhân, với (\d+) giá trị dạng chuỗi valuenum khác nhau", f"6.1 {item_name} chọn")
        add("6.1", f"{item_name}: số kết quả trong nguồn", n)
        add("6.1", f"{item_name}: số bệnh nhân trong nguồn", p)
        add("6.1", f"{item_name}: số ứng viên qua sàng lọc", c)
        add("6.1", f"{item_name}: mẫu", fluid)
        add("6.1", f"{item_name}: nhóm", cat)
        add("6.1", f"{item_name}: số đơn vị duy nhất của ứng viên", "1")
        add("6.1", f"{item_name}: đơn vị", unit)
        add("6.1", f"{item_name}: số kết quả được chọn", chosen)
        add("6.1", f"{item_name}: số bệnh nhân được chọn", cp)
        add("6.1", f"{item_name}: số giá trị valuenum (chuỗi) khác nhau trong mẫu", dv)
    t = rp.text("6.1")
    a, b, c, d = grab(t, r"Toàn tập có (\d+) labevent_id duy nhất, (\d+) bệnh nhân, (\d+) kết quả đủ hai cận và (\d+) kết quả thiếu cả hai cận", "6.1 toàn tập")
    add("6.1", "toàn tập: số labevent_id khác nhau", a)
    add("6.1", "toàn tập: số bệnh nhân", b)
    add("6.1", "toàn tập: kết quả đủ hai cận", c)
    add("6.1", "toàn tập: kết quả thiếu cả hai cận", d)
    a, b = grab(t, r"có (\d+) kết quả bằng 0 và (\d+) kết quả âm", "6.1 0 và âm")
    add("6.1", "toàn tập: kết quả chỉ một cận", "0") if re.search(r"Không có kết quả chỉ một cận", t) else None
    add("6.1", "toàn tập: kết quả bằng 0", a)
    add("6.1", "toàn tập: kết quả âm", b)
    (a,) = grab(clean_multiline(rp.muc("Kết quả chính")[0]["text"]), r"thuộc (\d+) loại xét nghiệm và \d+ bệnh nhân", "kết quả chính 5 loại")
    add("6.1", "toàn tập: số loại xét nghiệm", a)

    # ---- Mục 6.2
    a, b, c = grab(rp.text("6.2"), r"Sau sàng lọc có ([\d.]+) ứng viên; (\d+) dòng đi vào mẫu và ([\d.]+) ứng viên còn lại không được chọn", "6.2")
    add("6.2", "số ứng viên sau sàng lọc", a)
    add("6.2", "số dòng vào mẫu", b)
    add("6.2", "số ứng viên không được chọn", c)

    # ---- Mục 6.3 (40 dòng) và 6.4
    rows = rows_6_3(rp)
    add("6.3", "số dòng trong danh sách 6.3", str(len(rows)))
    grab(rp.text("6.3"), r"value bằng valuenum về số học ở cả 40 dòng", "6.3 value bằng valuenum")
    add("6.3", "số dòng khớp CSV gốc ở mọi trường (kể cả số thứ tự bản ghi CSV)", str(len(rows)))  # báo cáo: danh sách là bản ghi thật
    t64 = rp.tables("6.4")[0]
    add("6.4", "số subject_id của bảng chuẩn bệnh nhân có trong patients", str(len(t64)))
    t65 = {r[0]: r for r in rp.tables("6.5")[0]}
    r = t65["E5c"]
    grab(r[1] + " " + r[2], r"150770 và 172081.*>300 hoặc kết quả nằm trong comments", "6.5 E5c")
    add("6.5", "labevent 150770: value có dấu so sánh", "có")
    add("6.5", "labevent 172081: kết quả nằm trong comments (value rỗng, comments không rỗng)", "có")
    return out


def rows_6_3(rp: Report) -> pd.DataFrame:
    """Đọc 5 bảng của mục 6.3 thành 40 dòng, giữ thứ tự trong báo cáo."""
    rows = []
    for s in rp.muc("6.3"):
        if s["level"] != 3:
            continue
        itemid = s["title"].split()[0]
        unit = grab(clean_multiline(s["text"]), r"Đơn vị giữ nguyên (\S+);", f"6.3 {itemid} đơn vị")[0]
        for r in parse_tables(s["text"])[0]:
            lo, hi = (x.strip() for x in r[4].split("/"))
            rows.append({"labevent_id": r[0], "subject_id": r[1], "itemid": itemid, "charttime": r[2], "valuenum": r[3],
                         "valueuom": unit, "ref_range_lower": "" if lo == "Trống" else lo,
                         "ref_range_upper": "" if hi == "Trống" else hi, "csv_record": r[5]})
    df = pd.DataFrame(rows)
    if len(df) != 40:
        raise ValueError(f"Mục 6.3 cần 40 dòng, đọc được {len(df)}")
    return df


def extract_appendix(rp: Report, which: str) -> pd.DataFrame:
    """which = 'A' hoặc 'B'. Trả về bảng dài một dòng một itemid."""
    start = next(i for i, s in enumerate(rp.sections) if s["title"].startswith(f"Phụ lục {which} "))
    end = next((i for i, s in enumerate(rp.sections[start + 1:], start + 1) if s["level"] == 1), len(rp.sections))
    cols_a = ["itemid", "label", "ket_qua", "benh_nhan", "moc_do", "gia_tri", "do_lap", "don_vi"]
    cols_b = ["itemid", "label", "tong", "co_value", "co_so", "co_don_vi", "hai_can", "khong_can", "ghi_chu", "ung_vien"]
    cols = cols_a if which == "A" else cols_b
    rows = []
    for s in rp.sections[start + 1:end]:
        for t in parse_tables(s["text"]):
            for r in t:
                if len(r) != len(cols):
                    raise ValueError(f"Phụ lục {which}: dòng có {len(r)} ô, cần {len(cols)}: {r}")
                row = dict(zip(cols, r))
                row["nhom"] = s["title"]
                for c in cols[2:]:
                    if c != "don_vi":
                        row[c] = num(row[c])
                row["don_vi"] = nums_in_text(row["don_vi"]) if which == "A" else ""
                rows.append(row)
    df = pd.DataFrame(rows)
    if which == "B":
        df = df.drop(columns="don_vi")
    return df[["itemid", "nhom"] + [c for c in cols if c != "itemid"] if which == "A" else ["itemid", "nhom"] + [c for c in cols if c != "itemid"]]


def main(path: str) -> None:
    text = Path(path).read_text(encoding="utf-8")
    rp = Report(text)
    OUT.mkdir(parents=True, exist_ok=True)
    scalars = pd.DataFrame(extract_scalars(rp), columns=["muc_bao_cao", "ten_so_lieu", "gia_tri_trong_bao_cao"])
    dup = scalars[scalars.duplicated(["muc_bao_cao", "ten_so_lieu"], keep=False)]
    if len(dup):
        raise ValueError(f"Có số liệu trùng khóa:\n{dup}")
    scalars.to_csv(OUT / "bao_cao_so_lieu.csv", index=False, encoding="utf-8")
    a, b = extract_appendix(rp, "A"), extract_appendix(rp, "B")
    a.to_csv(OUT / "bao_cao_phu_luc_a.csv", index=False, encoding="utf-8")
    b.to_csv(OUT / "bao_cao_phu_luc_b.csv", index=False, encoding="utf-8")
    rows_6_3(rp).to_csv(OUT / "bao_cao_muc_6_3.csv", index=False, encoding="utf-8")
    print(f"Đã ghi {len(scalars)} số liệu, phụ lục A {len(a)} dòng, phụ lục B {len(b)} dòng, mục 6.3 40 dòng vào {OUT}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
