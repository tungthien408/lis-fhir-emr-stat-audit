# Hợp đồng tính chỉ số — bản chuyển thành code từ kế hoạch thực nghiệm

**Nguồn chính:** `Ke_hoach_thuc_nghiem_LIS_FHIR_EMR_da_chinh_sua(1).docx`, mục **5.1–5.4**, **10.7–10.8**, **11–11.2**, **14** và **15**. Không phải tài liệu công bố kết quả. Đây là *cách hiện thực hóa để kiểm chứng*, không được thay ngầm định nghĩa trong tài liệu nguồn.

## M1–M13

| Mã | Cách tính theo kế hoạch | Tệp đầu vào dự kiến của bộ khung | Ghi chú kiểm chứng |
|---|---|---|---|
| M1 | E2E hợp lệ, đúng bệnh nhân và trường, tra cứu được trong hạn / N kết quả logic hợp lệ lên lịch | `cases.csv` | Không tăng N khi retry; HTTP 2xx không đủ |
| M2 | Số phép đối chiếu đúng / số phép so áp dụng được (A) | `comparisons.csv` | Báo ba chặng: nguồn–FHIR, FHIR–đích, nguồn–đích; thiếu trường = sai |
| M3 | Trường bắt buộc có mặt ở đích / trường bắt buộc theo nguồn | `comparisons.csv` | Có giá trị `0` = hiện diện; không có ở nguồn = không vào mẫu số |
| M4 | Đếm bản ghi tạo/cập nhật có patient_key khác oracle | `target_records.csv` | Kiểm cả ca được báo lỗi; điều kiện đạt bằng 0 |
| M5 | Tổng số bản ghi vượt 1 trên mỗi khóa nghiệp vụ phải duy nhất | `target_records.csv` | Khóa: source_system + source_result_id, tách từng run |
| M6 | Đếm giao dịch **từng** DELIVERED mà oracle không tìm đúng bản ghi **tại lúc xác nhận** | `transactions.csv` | Không chỉ xét trạng thái hiện tại |
| M7 | Ca lỗi đạt toàn bộ expected output / số ca lỗi đã chạy | `error_cases.csv` | Từ chối đúng là ca thử đạt, không phải E2E thành công |
| M8 | Observation được sinh ra và đạt các quy tắc FHIR thuộc phạm vi / Observation đã sinh từ tập hợp lệ | `fhir_validation.csv` | Báo riêng số đầu vào hợp lệ nhưng **không sinh Observation** |
| M9 | T1 − T0 (ms), T0=Publish commit tại LIS; T1=kết thúc lần đọc lại đầu tiên đúng tại EMR | `e6_timings.csv` | Bao gồm thời gian readback; **không** dùng `charttime` lịch sử |
| M10 | `transformed_at` − `mapping_started_at` | `e6_timings.csv` | Thời gian mapping, không phải E2E |
| M11 | Mốc xác nhận đúng bản ghi − mốc khôi phục component | `recovery_timings.csv` | E4/E7/E8 phục hồi; báo cả độ trễ từ Publish |
| M12 | Ca đạt E2E sau phục hồi / ca thuộc nhóm cần phục hồi trong cửa sổ | `recovery_cases.csv` | Ca hết retry (E4d/E8d) báo riêng; không âm thầm loại |
| M13 | Yêu cầu lõi có đủ bằng chứng đạt / tổng yêu cầu lõi đã khóa | `requirements.csv` | Thiếu bằng chứng không phải PASS |

**Lưu ý khoa học:** Tỷ lệ M1/M2/M3/M7/M8/M12/M13 là *ước lượng mô tả theo mẫu kiểm thử đã chọn*, không phải bằng chứng suy rộng cho bệnh viện. M4/M5/M6 là số đếm. M9–M11 là đo thời lượng (tổng hợp thống kê trên nhiều quan sát). Việc viết hàm tính KHÔNG thay thế đánh giá độc lập nguồn–đích hoặc FHIR Validator.

## Quy ước báo cáo thời gian (mục 10.8, 11.2)

- E6: **3 lượt độc lập về thực thi**, mỗi lượt **5 ca warmup** dùng khóa riêng và không tính vào thống kê.
- Sau warmup: phát tuần tự một tập hợp lệ đã khóa (cùng manifest mỗi lượt).
- Báo riêng từng lượt: `n`, `min`, `median`, `mean`, `p95 nearest-rank`, `max`, `n_success`, `n_fail`, `n_timeout`; công khai điều kiện máy và hạn quan sát.
- `p95 = sort(x)[ceil(0.95*n) - 1]`; mặc định `pandas.Series.quantile(.95)` **không tương đương** khi có nội suy.
- Timeout và FAIL **không** nhận độ trễ 0; ghi trong số đếm thất bại và nhật ký.
- Nếu gộp kết quả 3 lượt để mô tả, vẫn giữ thống kê riêng từng lượt. 3 lượt cùng dữ liệu **không** là 3 mẫu bệnh nhân độc lập.
- `INVALID_RUN` chỉ khi điều kiện chạy sai (có lý do); FAIL/TIMEOUT khi điều kiện chạy đúng thì vẫn phải được giữ.

## Giới hạn và nguy cơ cần người đánh giá rà soát

1. Dữ liệu `cases.csv` là **bảng chuẩn hóa cho audit**, không phải tên tệp bắt buộc trong DOCX. DOCX ưu tiên `source.jsonl`, `fhir.jsonl`, `target.jsonl`, `comparisons.csv`, `events.jsonl`, `attempts.csv`, `metrics.csv`, `run_manifest.json`, ... (mục 14.3). Khi có log thật phải viết adapter và kiểm tra đối chiếu đầy đủ, không tự động tin các cột boolean do hệ thống tự xuất.
2. Để tránh tự chứng minh tính đúng, **oracle phải độc lập với mapper**. Khóa định danh, nội dung được phép biến đổi và expected output phải chốt trước khi xem kết quả.
3. `comparisons.csv`: để đo M2 chính xác, phải sinh **đủ mọi phép so A** được chốt từ trước, kể cả trường bị thiếu ở đích. Nếu chỉ ghi dòng cho trường có mặt thì M2 sẽ bị thổi phồng.
4. M8 có thể cao dù mapper không sinh resource cho một số kết quả: luôn báo riêng số đầu vào không sinh resource.
5. Chưa có dữ liệu prototype thực. Mọi CSV trong `data/sample_synthetic/` đều là dữ liệu **bịa hoàn toàn để thử công thức**, cố ý chứa bất thường, tuyệt đối không đưa kết quả của chúng vào báo cáo đồ án.
6. M11 cần mốc khôi phục đúng với từng ca, đặc biệt trường hợp E8b trong DOCX có cách xác định mốc riêng. Bảng mẫu không thể chứng minh việc đánh dấu mốc đó là đúng.

## Khi có bằng chứng E2E thực tế

Tạo bước chuyển đổi (adapter) từ tệp gốc ở `evidence/<run_id>/` sang các bảng phân tích trên. Mỗi biến phát sinh phải gắn `run_id`, `case_id`, `source_system`, `source_result_id` hoặc `exchange_id`, dấu vết tệp và phương pháp suy ra. Nếu mất `events.jsonl` hay không đối chiếu được `target.jsonl`, ghi **chưa đủ bằng chứng** thay vì giả định PASS.
