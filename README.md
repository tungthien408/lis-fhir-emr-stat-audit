# LIS – FHIR R4 – EMR | Kiểm chứng số liệu độc lập

Bộ **Python + Jupyter** để kiểm chứng số liệu và cách chọn mẫu của đồ án trao đổi kết quả xét nghiệm LIS → Middleware (FHIR R4) → EMR, dùng MIMIC-IV Clinical Database Demo 2.2.

> **Trạng thái:** notebook **01, 04, 05 đã chạy trên CSV MIMIC-IV Demo 2.2 thật**:
> - 01: tính lại mọi con số của báo cáo khảo sát (mục 1–4, mục 6, phụ lục A, B) và so với báo cáo.
> - 04: tự chọn 40 kết quả lõi từ dữ liệu gốc và so với danh sách trong báo cáo (40/40).
> - 05: chọn 1.000 kết quả cho E1 (1.000/1.000 trùng danh sách đã nạp LIS).
>
> Notebook 02–03 vẫn chạy trên dữ liệu **SYNTHETIC** (bịa để thử code, cố ý có lỗi), không phải kết quả MIMIC.
> Repo này là công cụ kiểm chứng, không phải prototype LIS/EMR; chưa có số đo của prototype.

## Bắt đầu

Cần Python **3.11** trở lên và Git. Chạy từ thư mục repo:

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest -q
python -m jupyter lab
```

Notebook 01, 04, 05 cần 4 file `patients`, `admissions`, `d_labitems`, `labevents` (`.csv.gz`) của MIMIC-IV Demo **2.2** trong `data/raw/` (thư mục này không được commit). Thiếu file thì notebook dừng và báo lỗi, không tự chuyển sang dữ liệu giả.

Chạy lại từ đầu đến cuối (ví dụ):

```bash
jupyter nbconvert --execute --inplace notebooks/01_dataset_profiling.ipynb
jupyter nbconvert --execute --inplace notebooks/04_sample_selection_audit.ipynb
jupyter nbconvert --execute --inplace notebooks/05_sample_selection_1000.ipynb   # chạy sau 04
```

## Notebook

| File | Mục đích | Dữ liệu |
|---|---|---|
| `01_dataset_profiling.ipynb` | Khảo sát dữ liệu; tính lại các số của báo cáo và ghi vào `docs/so_lieu_bao_cao/` (đặt `INPUT_MODE="real"`, mặc định) | thật |
| `02_metric_audit.ipynb` | Thử các chỉ số M1–M8, M12–M13 | synthetic |
| `03_e6_descriptive_statistics.ipynb` | Thời lượng M9–M11, mô tả E6 | synthetic |
| `04_sample_selection_audit.ipynb` | Kiểm 40 kết quả lõi với dữ liệu gốc và tự chọn lại 40 dòng theo [`docs/quy_tac_chon_mau_40.md`](docs/quy_tac_chon_mau_40.md) | thật |
| `05_sample_selection_1000.ipynb` | Chọn 1.000 kết quả cho E1 theo [`docs/quy_tac_chon_mau_1000.md`](docs/quy_tac_chon_mau_1000.md); xuất danh sách vào `reports/` | thật |

## Cấu trúc

```text
lis-fhir-emr-stat-audit/
├── .github/workflows/pytest.yml      # CI chạy pytest
├── configs/run_manifest.example.json # Mẫu metadata, không chứa số đo thật
├── data/
│   ├── raw/                          # CSV MIMIC thật – KHÔNG COMMIT
│   ├── external/                     # Số liệu trích từ báo cáo và danh sách E1 (nhỏ, commit được)
│   └── sample_synthetic/             # CSV bịa để thử hàm
├── docs/
│   ├── quy_tac_chon_mau_40.md        # Cách chọn 40 kết quả lõi
│   ├── quy_tac_chon_mau_1000.md      # Cách chọn 1.000 kết quả cho E1
│   ├── so_lieu_bao_cao/              # Đối chiếu số liệu báo cáo với dữ liệu gốc (chỉ số tổng hợp)
│   ├── metric_contract.md, verification_checklist.md
├── notebooks/                        # 01–05
├── reports/                          # Kết quả từng lần chạy – KHÔNG COMMIT
├── scripts/                          # Tạo notebook, tạo fixture, trích số liệu từ báo cáo
├── src/analysis_core/
│   ├── selection.py                  # Sàng lọc cơ bản, chọn 40 dòng lõi, chọn 1.000 kết quả
│   ├── survey.py                     # Tính lại số liệu của báo cáo (mục 1–4, 6, phụ lục)
│   └── dataset.py, metrics.py, timing.py
├── tests/
└── pyproject.toml
```

## Số liệu của báo cáo

Notebook 01 tính lại các con số của báo cáo từ dữ liệu gốc rồi so với số trong báo cáo. Kết quả nằm trong [`docs/so_lieu_bao_cao/`](docs/so_lieu_bao_cao/README.md); file chính là `so_lieu_bao_cao.csv` (cột `khop` = có/không), số lệch ở `so_lieu_lech.csv`. Dữ liệu gốc là chuẩn: số báo cáo lệch thì ghi là lệch, không sửa code cho khớp.

Khi báo cáo được sửa, xuất lại bản markdown rồi chạy:

```bash
python scripts/trich_so_lieu_bao_cao.py <bao_cao.md>     # cập nhật data/external/bao_cao_*.csv
jupyter nbconvert --execute --inplace notebooks/01_dataset_profiling.ipynb
```

## Dữ liệu thật

1. Lấy MIMIC-IV Clinical Database Demo **2.2** đúng giấy phép; không dùng mô tả schema 3.1 thay thế.
2. Đặt 4 file `.csv.gz` trong `data/raw/`. Notebook kiểm SHA-256 theo báo cáo (mục 1.1).
3. Khi có prototype, lưu chứng cứ tách theo từng `run_id` và viết adapter đọc chính các evidence đó; **không** dùng boolean do mapper tự kết luận thay cho oracle độc lập.
4. Chạy E6 sau reset và warmup riêng; lưu môi trường, commit Git, mapping_version, config và failures.

## Làm việc nhóm

Mỗi người dùng một nhánh riêng và mở pull request; trước khi merge chạy `python -m pytest -q` và rà công thức trên `docs/metric_contract.md`. Không điền mật khẩu hay token vào notebook.

## Những gì chưa xác minh

- Chưa có chứng cứ từ prototype (`source.jsonl`, `fhir.jsonl`, `target.jsonl`), nên chưa xác minh oracle độc lập, thời điểm Publish/commit/readback hay hiệu năng.
- Quy tắc chọn 40 dòng được tìm lại từ danh sách đã chốt, không tự suy ra từ báo cáo; có thể còn cách khác cho cùng kết quả (xem tài liệu quy tắc).
- Notebook 02–03 chạy trên dữ liệu bịa; không suy kết quả nghiên cứu từ đó.
- Các nhận định không phải con số của báo cáo (mục 5, 7) chưa được đối chiếu bằng code.
