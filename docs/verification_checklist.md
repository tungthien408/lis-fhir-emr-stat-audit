# Checklist trước khi dùng notebook để viết báo cáo khoa học

Danh sách này cụ thể hóa yêu cầu thực nghiệm của DOCX, không chứng minh hệ thống đã đạt.

- [ ] Xác nhận bộ dữ liệu đúng **MIMIC-IV Clinical Database Demo 2.2**, bản quyền, URL tải, ngày tải và SHA-256.
- [ ] Thống kê `patients`, `labevents`, `d_labitems` theo số dòng/unique/missing/duplicate/lỗi kiểu. Không âm thầm làm mất record khi join.
- [x] Chốt 3–5 itemid dựa trên dữ liệu THẬT; chốt lý do loại bản ghi, manifest, số bệnh nhân và số kết quả sau khi khảo sát. (xem notebook 04, 05)
- [ ] Chốt `expected_*`, bộ trường so A, field_path, quy tắc N/A và version oracle **trước** khi xem output prototype.
- [ ] Kiểm expected và actual ở ba chặng nguồn–FHIR, FHIR–đích, nguồn–đích; trường thiếu phải xuất thành phép so sai.
- [ ] Chạy các fixture cố tình sai bệnh nhân, đổi unit, mất cận, sai giá trị, bản ghi trùng để chứng minh evaluator phát hiện lỗi.
- [ ] Lưu evidence **riêng run_id** (theo Mục 14.3): `run_manifest.json`, `environment.json`, `source.jsonl`, `fhir.jsonl`, `target.jsonl`, `lis_outbox.jsonl`, `lis_dispatch_attempts.csv`, `events.jsonl`, `attempts.csv`, `validation/`, `comparisons.csv`, `metrics.csv`, `issues.csv`, `recovery_events.jsonl`.
- [ ] E6: 3 lượt trên cùng manifest; reset ba schema trước mỗi lượt; tách 5 warmup; đo tuần tự không trộn lỗi chủ động.
- [ ] Báo `n_success`, `n_fail`, `n_timeout`; FAIL/TIMEOUT **không tính như latency 0**; `INVALID_RUN` chỉ khi điều kiện chạy không đúng và có chứng cứ.
- [ ] Tính M9 từ Publish commit tới lần đọc đúng đầu tiên; không dùng `charttime/storetime` lịch sử hoặc HTTP ACK làm kết thúc.
- [ ] Tính p95 đúng **nearest-rank** và báo đủ min/median/mean/max **theo từng lượt**.
- [ ] M8 có ghi số đầu vào không sinh Observation; M12 tách trường hợp hết retry; M13 không tính thiếu bằng chứng là PASS.
- [ ] Không tuyên bố nhanh hơn kiến trúc khác hoặc hoạt động an toàn tại bệnh viện nếu chưa có bằng chứng phù hợp.

## Mẫu quyết định kết quả

- **SUPPORTED_IN_TESTBED:** đầy đủ bằng chứng, quy tắc đã khóa đạt trong tập và cấu hình đã thử.
- **NOT_MET:** phát hiện sai yêu cầu hoặc ca thử FAIL sau khi kiểm tra đầy đủ.
- **INSUFFICIENT_EVIDENCE:** thiếu dữ liệu đối chiếu, mốc đo, hoặc không xác lập được oracle độc lập.

Dùng các kết luận này với từng `requirement_id` và `case_id`, không chỉ với một phần trăm tổng hợp.
