"""Tạo notebooks/01_dataset_profiling.ipynb (chạy: python scripts/create_notebook_01.py)."""
from pathlib import Path
import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
cells = []


def md(text):
    cells.append(nbf.v4.new_markdown_cell(text.strip("\n")))


def code(text):
    cells.append(nbf.v4.new_code_cell(text.strip("\n")))


md("""
# 01 — Khảo sát dữ liệu MIMIC-IV Demo 2.2 và đối chiếu số liệu của báo cáo

**Không phải kết quả nghiên cứu.** Notebook làm hai việc:

1. **Khảo sát chung** (mục A–D): số dòng, giá trị thiếu, mã trùng, khóa tham chiếu, lỗi kiểu số.
2. **Đối chiếu báo cáo** (mục E, chỉ khi `INPUT_MODE = "real"`): tính lại **mọi con số** ở mục 1–4, mục 6 và phụ lục A, B của báo cáo khảo sát từ 4 file gốc, rồi so với số trong báo cáo.

Dữ liệu gốc là chuẩn. Số trong báo cáo lệch với số code tính ra thì ghi là **lệch**, không sửa code cho khớp báo cáo.
`INPUT_MODE = "synthetic"` chỉ để thử code trên dữ liệu bịa (cố tình có lỗi), không phải kết quả MIMIC.
""")

code('''
from pathlib import Path
import pandas as pd
from IPython.display import display
from analysis_core.dataset import load_csv, profile_mimic_like

ROOT = next((path for path in (Path.cwd(), *Path.cwd().parents) if (path / "pyproject.toml").exists()), None)
if ROOT is None:
    raise RuntimeError("Hãy mở notebook từ thư mục repo có pyproject.toml")
SYNTHETIC = ROOT / "data" / "sample_synthetic"
print("Repository:", ROOT)

# CHỌN NGUỒN DỮ LIỆU MỘT CÁCH TƯỜNG MINH; KHÔNG TỰ ĐỘNG CHUYỂN SANG DỮ LIỆU GIẢ.
INPUT_MODE = "real"   # "real" = CSV MIMIC-IV Demo 2.2 trong data/raw/; "synthetic" = dữ liệu bịa để thử code
REAL_FILES = {
    "patients": ROOT / "data" / "raw" / "patients.csv.gz",
    "admissions": ROOT / "data" / "raw" / "admissions.csv.gz",
    "d_labitems": ROOT / "data" / "raw" / "d_labitems.csv.gz",
    "labevents": ROOT / "data" / "raw" / "labevents.csv.gz",
}
if INPUT_MODE not in {"synthetic", "real"}:
    raise ValueError("INPUT_MODE phải là 'synthetic' hoặc 'real'")
if INPUT_MODE == "synthetic":
    print("⚠️ DỮ LIỆU SYNTHETIC — KHÔNG ĐƯỢC BÁO CÁO NHƯ KẾT QUẢ MIMIC")
    paths = {name: SYNTHETIC / f"{name}.csv" for name in ("patients", "labevents", "d_labitems")}
else:
    print("DỮ LIỆU THẬT — cần đúng phiên bản 2.2 (kiểm SHA-256 ở mục E)")
    paths = REAL_FILES

patients, labevents, d_labitems = [load_csv(paths[name]) for name in ("patients", "labevents", "d_labitems")]
print("Đã đọc:", {name: str(paths[name]) for name in ("patients", "labevents", "d_labitems")})
''')

md("""
## A. Số bản ghi, số lượng định danh

`rows` là số bản ghi trong bảng, `unique_subject_id` chỉ tính trong các bảng có cột đó.
""")
code('''
summary, missing, issues = profile_mimic_like(patients, labevents, d_labitems)
display(summary)
''')

md("""
## B. Giá trị thiếu theo từng cột

Bảng này đọc CSV theo cách mặc định của pandas, nên chỉ đếm ô rỗng. Số "thiếu" của báo cáo (ô rỗng **hoặc chỉ có khoảng trắng**) nằm ở mục E.
""")
code('''
display(missing.sort_values(["table", "missing_count"], ascending=[True, False]).reset_index(drop=True))
''')

md("""
## C. Dữ liệu trùng, khóa tham chiếu không khớp, lỗi kiểu số

Không `dropna` hay nối chỉ giữ dòng khớp một cách âm thầm. Nếu cần loại dòng, mỗi dòng bị loại phải có lý do và số lượng riêng.
""")
code('''
display(issues)
display(labevents.groupby("itemid", dropna=False).size().rename("records").reset_index().sort_values("records", ascending=False).head(15))
''')

md("""
## D. Việc cần ghi khi chạy thật

Ghi vào `run_manifest.json`: phiên bản dữ liệu, URL, giấy phép, SHA-256, lựa chọn itemid, tiêu chí loại, mã commit, số bệnh nhân và số kết quả thực. Dữ liệu synthetic ở đây cố tình có lỗi để kiểm tra chức năng phát hiện.
""")

md("""
## E. Đối chiếu số liệu của báo cáo (chỉ dữ liệu thật)

Các bước:

1. Đọc 4 file **dạng chuỗi** (giữ nguyên `N/A`, `___`, số 0) và tính SHA-256 của từng file.
2. Sàng lọc cơ bản bằng `screen_labevents` và chọn 40 dòng lõi bằng `select_core_40` (cùng hàm với notebook 04 và 05).
3. `analysis_core.survey` tính mọi con số của mục 1–4 và mục 6; phụ lục A và B tính từng ô.
4. So với số trong báo cáo, đọc từ `data/external/bao_cao_*.csv` (các file này do `scripts/trich_so_lieu_bao_cao.py` trích từ báo cáo, không sửa tay).
5. Ghi kết quả vào `docs/so_lieu_bao_cao/` — chỉ có số tổng hợp, **không có dòng dữ liệu gốc**.

Quy ước "thiếu": ô rỗng hoặc chỉ có khoảng trắng. Số thập phân của báo cáo được so sau khi làm tròn số code theo đúng số chữ số báo cáo ghi.
""")
code('''
from analysis_core import survey
from analysis_core.selection import screen_labevents

if INPUT_MODE != "real":
    print("INPUT_MODE != 'real': bỏ qua mục E (cần dữ liệu thật).")
else:
    EXTERNAL = ROOT / "data" / "external"
    OUT = ROOT / "docs" / "so_lieu_bao_cao"
    OUT.mkdir(parents=True, exist_ok=True)
    raw = {name: survey.read_raw(REAL_FILES[name]) for name in survey.TABLES}
    hashes = {name: survey.file_sha256(REAL_FILES[name]) for name in survey.TABLES}
    print({name: len(df) for name, df in raw.items()})
    screen = screen_labevents(raw["labevents"], raw["patients"], raw["d_labitems"])
    print("Qua sàng lọc cơ bản:", int((screen == "PASS").sum()))
''')

code('''
if INPUT_MODE == "real":
    report_values = pd.read_csv(EXTERNAL / "bao_cao_so_lieu.csv", dtype=str, keep_default_na=False)
    expected_6_3 = pd.read_csv(EXTERNAL / "bao_cao_muc_6_3.csv", dtype=str, keep_default_na=False)
    entries = survey.compute_survey_entries(raw, screen, hashes, expected_6_3)
    main, extra = survey.compare_with_report(entries, report_values)
    print(f"Số liệu trong báo cáo: {len(main)} | code tính được: {len(entries)} | khớp: {int((main.khop == 'có').sum())} | lệch: {int((main.khop == 'không').sum())}")
    print("Số liệu code tính ra nhưng báo cáo không nêu:", len(extra))
    assert not (main["noi_tinh"] == "chưa có hàm tính").any(), "Có số trong báo cáo mà code chưa tính"
    print("Số liệu lệch với báo cáo (mục 1–4, 6):")
    display(main[main["khop"] == "không"])
''')

md("""
### Phụ lục A và B

Mỗi ô của mỗi loại xét nghiệm (498 loại) được so riêng. Phụ lục A: số kết quả, bệnh nhân, mốc đo, giá trị, đo lặp, đơn vị. Phụ lục B: tổng, có value, có số, có đơn vị, hai cận, không cận, ghi chú, ứng viên.
""")
code('''
if INPUT_MODE == "real":
    A_COLS = ["ket_qua", "benh_nhan", "moc_do", "gia_tri", "do_lap", "don_vi"]
    B_COLS = ["tong", "co_value", "co_so", "co_don_vi", "hai_can", "khong_can", "ghi_chu", "ung_vien"]
    rep_a = pd.read_csv(EXTERNAL / "bao_cao_phu_luc_a.csv", dtype=str, keep_default_na=False)
    rep_b = pd.read_csv(EXTERNAL / "bao_cao_phu_luc_b.csv", dtype=str, keep_default_na=False)
    code_a, code_b = survey.appendix_a(raw), survey.appendix_b(raw, screen)
    cmp_a = survey.compare_appendix(code_a, rep_a, A_COLS)
    cmp_b = survey.compare_appendix(code_b, rep_b, B_COLS)
    for name, cmp_df, code_df, rep_df in (("A", cmp_a, code_a, rep_a), ("B", cmp_b, code_b, rep_b)):
        print(f"Phụ lục {name}: {len(code_df)} loại (báo cáo {len(rep_df)}) | {len(cmp_df)} ô | khớp {int((cmp_df.khop == 'có').sum())} | lệch {int((cmp_df.khop == 'không').sum())}")
        display(cmp_df[cmp_df["khop"] == "không"].head(20))
    print("Dòng chỉ có một cận (phụ lục B: báo cáo nói 0 ở mọi loại):", survey.appendix_b_one_bound(raw))
''')

md("""
### Ghi kết quả

Ghi vào `docs/so_lieu_bao_cao/` (thư mục được commit, chỉ chứa số tổng hợp):

| File | Nội dung |
|---|---|
| `so_lieu_bao_cao.csv` | Bảng chính: `muc_bao_cao, ten_so_lieu, gia_tri_trong_bao_cao, gia_tri_tu_code, khop, noi_tinh` (kèm 4 dòng tổng kết phụ lục) |
| `so_lieu_lech.csv` | Chỉ các dòng lệch |
| `phu_luc_a_so_sanh.csv`, `phu_luc_b_so_sanh.csv` | Từng ô của phụ lục A và B |
| `so_lieu_chi_co_trong_code.csv` | Số code tính được nhưng báo cáo không nêu |
""")
code('''
if INPUT_MODE == "real":
    summary_rows = []
    for name, cmp_df, code_df in (("A", cmp_a, code_a), ("B", cmp_b, code_b)):
        func = f"notebook 01 → analysis_core.survey.appendix_{name.lower()} + compare_appendix"
        summary_rows.append((f"Phụ lục {name}", "số loại xét nghiệm", str(len(rep_a if name == "A" else rep_b)), str(len(code_df)),
                             "có" if len(rep_a if name == "A" else rep_b) == len(code_df) else "không", func))
        n_ok = int((cmp_df.khop == "có").sum())
        summary_rows.append((f"Phụ lục {name}", "số ô khớp dữ liệu gốc (trên tổng số ô đối chiếu)", str(len(cmp_df)), str(n_ok),
                             "có" if n_ok == len(cmp_df) else "không", func))
    main_out = pd.concat([main, pd.DataFrame(summary_rows, columns=main.columns)], ignore_index=True)
    main_out.to_csv(OUT / "so_lieu_bao_cao.csv", index=False, encoding="utf-8-sig")
    main_out[main_out["khop"] == "không"].to_csv(OUT / "so_lieu_lech.csv", index=False, encoding="utf-8-sig")
    cmp_a.to_csv(OUT / "phu_luc_a_so_sanh.csv", index=False, encoding="utf-8-sig")
    cmp_b.to_csv(OUT / "phu_luc_b_so_sanh.csv", index=False, encoding="utf-8-sig")
    extra.to_csv(OUT / "so_lieu_chi_co_trong_code.csv", index=False, encoding="utf-8-sig")
    for f in sorted(OUT.glob("*.csv")):
        print("Đã lưu:", f.relative_to(ROOT))
    print("Tổng kết:", main_out["khop"].value_counts().to_dict())
''')

md("""
### Kết luận mục E

- Đã chứng minh: các số được liệt kê trong `so_lieu_bao_cao.csv` do code tính từ 4 file gốc có SHA-256 đúng như báo cáo (mục 1.1). Cột `khop` cho biết số trong báo cáo có đúng không.
- Số lệch (cột `khop = không`) cần sửa **ở báo cáo**, không sửa ở code. Danh sách nằm trong `so_lieu_lech.csv`.
- Chưa chứng minh: các nhận định không phải con số (ví dụ "nên chọn loại nào") và các mục 5, 7 của báo cáo.
""")

nb = nbf.v4.new_notebook()
nb.cells = cells
nb.metadata = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
               "language_info": {"name": "python"}}
nbf.write(nb, ROOT / "notebooks" / "01_dataset_profiling.ipynb")
print("Đã tạo notebooks/01_dataset_profiling.ipynb")
