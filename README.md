# LIS – FHIR R4 – EMR | Independent Statistical Audit

Bộ khung **Python + Jupyter** để kiểm chứng các thống kê trong kế hoạch thực nghiệm trao đổi kết quả xét nghiệm LIS → Middleware (FHIR R4) → EMR.

> **Trạng thái:** Notebook 04 và 05 đã chạy trên CSV MIMIC-IV Demo 2.2 thật (kiểm tập mẫu 40 kết quả và chọn tập 1.000 kết quả). Notebook 01–03 vẫn là khung chạy trên dữ liệu **SYNTHETIC — tạo hoàn toàn để thử code, cố ý chứa lỗi**, không phải dữ liệu từ MIMIC-IV. Repo này là công cụ phân tích và kiểm chứng *phương pháp*, không phải prototype LIS/EMR và chưa có kết quả đo của prototype.

## Bắt đầu sau khi giải nén

Yêu cầu cài Python **3.11** và Git.

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest -q
python -m jupyter lab
```

### macOS / Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest -q
python -m jupyter lab
```

Mở notebooks theo thứ tự. `INPUT_MODE="synthetic"` là **lựa chọn hiển thị rõ trong notebook 01**, không tự động giả làm dữ liệu thực. Muốn dùng CSV thực phải chỉnh đường dẫn và đặt `INPUT_MODE="real"`; nếu không có dữ liệu thì lỗi dừng rõ ràng.

## Notebooks

| File | Mục đích |
|---|---|
| `01_dataset_profiling.ipynb` | Thống kê số dòng, unique, missing, duplicate, khóa tham chiếu thiếu, lỗi numeric trước khi chọn MIMIC-IV Demo 2.2 |
| `02_metric_audit.ipynb` | Tính thử M1–M8 và M12–M13 trên fixture synthetic; diễn giải tử số/mẫu số và chỉ ra điều kiện FAIL |
| `03_e6_descriptive_statistics.ipynb` | Tính M9/M10/M11 (thời lượng), mô tả E6 từng lượt và nearest-rank p95, giữ riêng FAIL/TIMEOUT/warmup |
| `04_sample_selection_audit.ipynb` | Kiểm tập mẫu 40 kết quả lõi trên CSV MIMIC-IV Demo 2.2 thật (40/40 PASS; 82.289 dòng đạt sàng lọc cơ bản) |
| `05_sample_selection_1000.ipynb` | Chọn 1.000 kết quả cho E1 theo [`docs/quy_tac_chon_mau_1000.md`](docs/quy_tac_chon_mau_1000.md) và tự kiểm tra; xuất danh sách vào `reports/` |

Chi tiết **định nghĩa và nguồn mục tài liệu**: [`docs/metric_contract.md`](docs/metric_contract.md).

## Cấu trúc

```text
lis-fhir-emr-stat-audit/
├── .github/workflows/pytest.yml     # CI tự kiểm thử code
├── data/
│   ├── raw/                         # CSV MIMIC thật – KHÔNG COMMIT
│   └── sample_synthetic/            # CSV bịa để kiểm thử hàm
├── docs/{metric_contract,verification_checklist}.md  # Định nghĩa + checklist
├── notebooks/
│   ├── 01_dataset_profiling.ipynb
│   ├── 02_metric_audit.ipynb
│   └── 03_e6_descriptive_statistics.ipynb
├── reports/                          # Kết quả riêng từng lần chạy – KHÔNG COMMIT
├── scripts/generate_synthetic_fixtures.py
├── src/analysis_core/{dataset,metrics,timing}.py
├── tests/{test_dataset,test_metrics,test_timing}.py
├── configs/run_manifest.example.json # Mẫu metadata không chứa số đo thật
├── .gitignore
└── pyproject.toml
```

## Kết nối dữ liệu thật

1. Lấy bộ MIMIC-IV Clinical Database Demo **2.2** đúng giấy phép/điều kiện nguồn cung cấp. Không lấy mô tả schema 3.1 thay thế schema 2.2.
2. Ghi URL, ngày tải, hash SHA-256 và phiên bản. Đặt `patients`, `labevents`, `d_labitems` CSV hoặc CSV.GZ trong `data/raw/`; sửa chính xác ba đường dẫn ở notebook 01.
3. Kiểm tra dữ liệu MIMIC (mục 5 tài liệu), **trước** bước chọn 3–5 itemid và tập con 20–50 kết quả dự kiến. Những cỡ mẫu này là **mục tiêu**, chưa phải kết quả đã đo.
4. Khi có prototype, lưu chứng cứ tách theo từng `run_id`, theo danh sách ở mục 14.3 của DOCX. Viết adapter đọc chính các evidence đó thành bảng phân tích chuẩn; **không** dùng boolean do mapper tự kết luận thay cho oracle độc lập.
5. Chạy E6 sau reset và warmup riêng; lưu môi trường, commit Git, mapping_version, config, hạn quan sát, và failures. Chỉ so sánh với báo cáo khi các định nghĩa và tập dữ liệu giống nhau.

## Khởi tạo Git và đưa lên GitHub

Tạo repository **trống** trên GitHub tên `lis-fhir-emr-stat-audit` (đừng chọn tạo sẵn README để tránh conflict), rồi chạy từ thư mục đã giải nén:

```bash
git init -b main
git add .
git commit -m "chore: scaffold statistical audit notebooks"
git remote add origin https://github.com/<USERNAME>/lis-fhir-emr-stat-audit.git
git push -u origin main
```

Thay `<USERNAME>` bằng username hoặc tổ chức GitHub thật của nhóm. Nếu GitHub báo cần xác thực, dùng GitHub CLI hoặc cách đăng nhập được Git hỗ trợ; **không** điền mật khẩu/token vào notebook. Nên đặt repo `Private` lúc đầu để rà soát dữ liệu và tài liệu, sau mới quyết định công khai.

**Gợi ý quy trình nhóm:** bảo vệ branch `main`, mỗi người dùng một feature branch, mở pull request; trước merge chạy `pytest` và review công thức trên `docs/metric_contract.md`.

## Những gì bộ khung CHƯA xác minh

- Chưa xác minh MIMIC-IV Demo CSV thực hoặc tên xét nghiệm thực tế.
- Chưa thực hiện independent oracle trên `source.jsonl`, `fhir.jsonl`, `target.jsonl` của prototype.
- Chưa xác minh thời điểm Publish/commit/readback thực tế, cũng chưa xác minh hiệu năng.
- Không suy rằng một thống kê từ dữ liệu synthetic là kết quả nghiên cứu.

**Tiêu chí hoàn thành bước tiếp theo:** Notebook 01 dùng CSV thật; bảng manifest đã khóa; 100% test unit chạy; tài liệu mapping của mỗi cột bảng phân tích sang bằng chứng gốc được kiểm tra chéo.
