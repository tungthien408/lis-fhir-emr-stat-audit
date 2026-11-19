"""Recreate human-readable Jupyter notebooks from Markdown/code cells."""
from pathlib import Path
import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "notebooks"
DEST.mkdir(exist_ok=True)


def make(filename, cells):
    nb = nbf.v4.new_notebook()
    nb.cells = [nbf.v4.new_markdown_cell(body) if kind == "md" else nbf.v4.new_code_cell(body)
                for kind, body in cells]
    nb.metadata = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                   "language_info": {"name": "python", "version": "3.11"}}
    nbf.write(nb, DEST / filename)


root_cell = '''from pathlib import Path
import pandas as pd
from IPython.display import display
ROOT = next((path for path in (Path.cwd(), *Path.cwd().parents) if (path / "pyproject.toml").exists()), None)
if ROOT is None:
    raise RuntimeError("Notebook must run from this repository folder or one of its subfolders")
SYNTHETIC = ROOT / "data" / "sample_synthetic"
print("Repository:", ROOT)
'''

make("01_dataset_profiling.ipynb", [
    ("md", "# 01 — Dataset profiling (MIMIC-IV Demo 2.2)\n\n**KHÔNG PHẢI KẾT QUẢ NGHIÊN CỨU.** Theo mục **5.1–5.2**, kiểm tra số dòng, số mã bệnh nhân, khóa trùng, dữ liệu thiếu, lỗi kiểu số và khóa tham chiếu trước chọn subset.\n\nNotebook mặc định đọc dữ liệu **SYNTHETIC do nhóm tự tạo** để chứng minh pipeline hoạt động; phải chuyển rõ `INPUT_MODE` sang `real` khi có CSV thật."),
    ("code", root_cell + '''from analysis_core.dataset import load_csv, profile_mimic_like

# CHỌN NGUỒN DỮ LIỆU MỘT CÁCH TƯỜNG MINH; KHÔNG TỰ ĐỘNG FALLBACK.
INPUT_MODE = "synthetic"  # đổi thành "real" sau khi tải bộ CSV thật
REAL_FILES = {
    "patients": ROOT / "data" / "raw" / "patients.csv.gz",       # chỉnh đúng đường dẫn
    "labevents": ROOT / "data" / "raw" / "labevents.csv.gz",   # chỉnh đúng đường dẫn
    "d_labitems": ROOT / "data" / "raw" / "d_labitems.csv.gz" # chỉnh đúng đường dẫn
}
if INPUT_MODE not in {"synthetic", "real"}:
    raise ValueError("INPUT_MODE must be 'synthetic' or 'real'")
if INPUT_MODE == "synthetic":
    print("⚠️ SYNTHETIC FIXTURE ONLY — DO NOT REPORT AS MIMIC OR PROTOTYPE RESULT")
    paths = {name: SYNTHETIC / f"{name}.csv" for name in REAL_FILES}
else:
    print("REAL CSV INPUT — verify dataset license, version 2.2, hash and paths")
    paths = REAL_FILES

patients, labevents, d_labitems = [load_csv(paths[name]) for name in ("patients", "labevents", "d_labitems")]
print("Loaded:", {name: str(path) for name, path in paths.items()})
'''),
    ("md", "## A. Số bản ghi, số lượng định danh\n\n`rows` là số bản ghi trong bảng, `unique_subject_id` chỉ tính trong các bảng có cột đó; không suy `n` được nạp vào LIS từ số lượng public dataset."),
    ("code", '''summary, missing, issues = profile_mimic_like(patients, labevents, d_labitems)
display(summary)
'''),
    ("md", "## B. Missing values theo từng cột"),
    ("code", '''display(missing.sort_values(["table", "missing_count"], ascending=[True, False]).reset_index(drop=True))
'''),
    ("md", "## C. Dữ liệu trùng, khóa tham chiếu không khớp, lỗi kiểu số\n\nKhông `dropna`/`merge(inner)` âm thầm trước khi tổng kết. Nếu cần loại, mỗi bản ghi bị loại phải có lý do và số lượng riêng."),
    ("code", '''display(issues)
display(labevents.groupby("itemid", dropna=False).size().rename("records").reset_index().sort_values("records", ascending=False))
'''),
    ("md", "## D. Nhật ký kiểm chứng thủ công\n\nTrước khi thực nghiệm chính thức hãy ghi ở `run_manifest.json`: dataset version, URL, giấy phép, SHA-256, lựa chọn itemid, tiêu chí loại, mã commit, số bệnh nhân và số kết quả thực. Phần tiền xử lý phải tách **bản ghi bị loại** theo từng lý do. Tệp synthetic ở đây cố tình có lỗi để kiểm tra chức năng phát hiện."),
])

make("02_metric_audit.ipynb", [
    ("md", "# 02 — Kiểm chứng chỉ số M1–M8, M12–M13\n\n**CHỈ CHẠY VỚI FIXTURE SYNTHETIC. KHÔNG PHẢI KẾT QUẢ ĐỒ ÁN.**\n\nCác công thức nằm trong `src/analysis_core/metrics.py`; xem `docs/metric_contract.md` để biết mẫu số, oracle, hành vi N/A và giới hạn. M2 phải tách 3 chặng. M9–M11 chuyển sang Notebook 03."),
    ("code", root_cell + '''from analysis_core.metrics import (audit_summary, m2_field_accuracy, m8_fhir_validity)

def get(file):
    return pd.read_csv(SYNTHETIC / file)

cases = get("cases.csv")
comparisons = get("comparisons.csv")
targets = get("target_records.csv")
transactions = get("transactions.csv")
error_cases = get("error_cases.csv")
validations = get("fhir_validation.csv")
recovery = get("recovery_cases.csv")
requirements = get("requirements.csv")
print("⚠️ ALL INPUTS ARE SYNTHETIC, WITH INTENTIONAL FAILURES")
'''),
    ("md", "## A. Chỉ số tổng quan\n\nBộ khung tính các tỷ lệ **trên bảng đã chuẩn hóa và phải có oracle độc lập**. Nó chưa đọc được `source.jsonl/fhir.jsonl/target.jsonl` của prototype. `numerator`, `denominator`, `percentage` minh bạch; số đếm M4–M6 không có mẫu số."),
    ("code", '''report = audit_summary(cases, comparisons, targets, transactions, error_cases, validations, recovery, requirements)
display(report)
'''),
    ("md", "## B. M2: Tỷ lệ đúng ở ba chặng\n\nKhông gộp ba chặng thành một con số chung khi chưa có định nghĩa. Missing comparison trong tập A phải được ghi thành FALSE, không được xóa dòng."),
    ("code", '''display(m2_field_accuracy(comparisons))
'''),
    ("md", "## C. M8: Đếm cả kết quả hợp lệ không sinh Observation\n\nM8 có mẫu số là Observation đã sinh, vì vậy phải ghi số nguồn hợp lệ không tạo resource để tránh báo cáo lạc quan."),
    ("code", '''m8, not_generated = m8_fhir_validity(validations)
print("M8:", m8.as_dict())
print("Valid inputs without generated Observation:", not_generated)
'''),
    ("md", "## D. Đối chiếu với báo cáo thực tế (chưa thực hiện)\n\nKhi có evidence chính thức, tạo adapter có truy vết từ `run_id/case_id/exchange_id` đến `source.jsonl`, `target.jsonl`, `comparisons.csv` và trạng thái lịch sử. Chạy lại `pytest` sau khi xác định expected output độc lập. Không dùng dữ liệu synthetic để thay chỗ dữ liệu còn thiếu."),
])

make("03_e6_descriptive_statistics.ipynb", [
    ("md", "# 03 — Descriptive statistics của M9–M11 (E6, phục hồi)\n\n**⚠️ TOÀN BỘ SỐ LIỆU BÊN DƯỚI LÀ SYNTHETIC.**\n\nTheo mục **10.8** và **11.2**, E6 chạy 3 lượt, mỗi lượt 5 warmup không tính, cùng manifest kết quả. Báo từng lượt min/median/mean/p95 nearest-rank/max và số FAIL/TIMEOUT. M9 là thời gian tới **kết thúc readback đúng**, không phải `charttime` hay timestamp `stored_at` trước commit."),
    ("code", root_cell + '''import matplotlib.pyplot as plt
from analysis_core.timing import (e6_run_summary, nearest_rank, m10_mapping_durations,
                                  m11_recovery_durations, summarize, duration_ms)
e6 = pd.read_csv(SYNTHETIC / "e6_timings.csv")
recovery = pd.read_csv(SYNTHETIC / "recovery_timings.csv")
print("⚠️ SYNTHETIC — DO NOT USE FOR RESEARCH CONCLUSIONS")
'''),
    ("md", "## A. E6: M9, thống kê theo run_id\n\nM9 = T1 (kết thúc lần đọc lại đúng) − T0 (LIS commit Publish). Không gán độ trễ 0 cho timeout và không đưa warmup vào thống kê. Với `n` rất nhỏ, p95 không ổn định."),
    ("code", '''e6_report = e6_run_summary(e6)
display(e6_report)
'''),
    ("md", "## B. Kiểm tra nearest-rank so với pandas mặc định\n\nVới 10 giá trị 1,...,10: nearest-rank p95 = 10 trong khi pandas mặc định dùng nội suy, vì thế hai con số khác nhau."),
    ("code", '''example = pd.Series(range(1, 11))
print("Nearest-rank p95:", nearest_rank(example))
print("Pandas default p95:", example.quantile(0.95))
'''),
    ("md", "## C. Phân bố M9 theo lượt E6 (chỉ SUCCESS)\n\nBiểu đồ chỉ giúp nhìn hình dạng phân bố, không chứng minh ưu thế của một kiến trúc khi chưa có baseline."),
    ("code", '''plots = []
labels = []
for run_id, rows in e6.groupby("run_id", sort=True):
    rows = rows.loc[(~rows["is_warmup"]) & (rows["run_status"] == "VALID") & (rows["outcome"] == "SUCCESS")]
    plots.append(duration_ms(rows["t0_publish_committed"], rows["t1_verified_readback"]).to_numpy())
    labels.append(run_id)
fig, ax = plt.subplots(figsize=(8, 4))
ax.boxplot(plots)
ax.set_xticks(range(1, len(labels) + 1))
ax.set_xticklabels(labels)
ax.set(title="SYNTHETIC E6 end-to-end time (successes only)", ylabel="Latency (ms)", xlabel="Run")
plt.show()
'''),
    ("md", "## D. M10 — Thời gian ánh xạ dữ liệu\n\nChỉ đo mốc `mapping_started_at` đến `transformed_at`, không được xem đây là thời gian toàn luồng."),
    ("code", '''mapped = e6.loc[(e6["outcome"] == "SUCCESS") & (~e6["is_warmup"])]
print("M10 mapping durations (synthetic, ms):", summarize(m10_mapping_durations(mapped)))
'''),
    ("md", "## E. M11 — Thời gian phục hồi\n\nE4/E7/E8 cần mốc recovery rõ nghĩa theo từng kịch bản; số đo tổng từ Publish phải ghi riêng. M12 là **tỷ lệ** phục hồi và được tính trong Notebook 02."),
    ("code", '''print("M11 recovery durations (synthetic, ms):", summarize(m11_recovery_durations(recovery)))
print("Reminder: recovery point must be independently verified against recovery_events.jsonl")
'''),
])
print("Created notebooks:")
for p in sorted(DEST.glob("*.ipynb")):
    print(" -", p.name)
