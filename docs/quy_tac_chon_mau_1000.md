# Quy tắc chọn tập 1.000 kết quả cho thực nghiệm E1

Tài liệu này ghi lại **quyết định chọn mẫu**: 1.000 kết quả xét nghiệm dùng cho E1 được lấy ra từ MIMIC-IV Demo 2.2 như thế nào, và vì sao lại chọn như vậy.
Notebook `05_sample_selection_1000.ipynb` làm đúng theo các bước bên dưới và tự kiểm tra kết quả.

## 1. Yêu cầu đã có sẵn từ kế hoạch thực nghiệm

- 1.000 kết quả, thuộc **100 bệnh nhân** (toàn bộ bệnh nhân của bộ demo) và **5 loại xét nghiệm**.
- Phải chứa đủ **40 kết quả lõi** đã chốt ở chương 2 (danh sách trong `reports/sample_selection_manifest_expected.csv`).
- Ai chạy lại cũng phải ra **đúng cùng một danh sách**.

## 2. Các bước chọn

**Bước 1 – Sàng lọc cơ bản.** Dùng đúng bộ điều kiện của notebook 04 (giá trị là số thuần, khớp `valuenum`, có đơn vị, `charttime` hợp lệ, cận tham chiếu hợp lệ, không có ghi chú…). Kết quả: 82.289 dòng đạt.

**Bước 2 – Giữ 5 loại xét nghiệm của tập lõi.** Còn 9.574 dòng, mỗi loại chỉ dùng một đơn vị đo:

| itemid | Xét nghiệm | Số dòng đạt | Số bệnh nhân |
|---|---|---|---|
| 50971 | Potassium | 2.766 | 100 |
| 50912 | Creatinine | 2.963 | 100 |
| 51222 | Hemoglobin | 2.783 | 100 |
| 50802 | Base Excess | 889 | 77 |
| 51492 | Protein (nước tiểu) | 173 | 53 |

**Bước 3 – Chia số lượng cho từng loại (hạn mức).** Chia gần đều để loại nào cũng được thử nhiều:

| itemid | Hạn mức | Lý do |
|---|---|---|
| 51492 Protein | 173 | Chỉ có 173 dòng đạt nên lấy hết |
| 50802 Base Excess | 200 | Mức chia đều 1.000 / 5 |
| 50971, 50912, 51222 | 209 mỗi loại | Phần còn lại (1.000 − 173 − 200 = 627) chia đều cho 3 loại |

Không chia theo tỉ lệ số dòng gốc, vì làm vậy Protein chỉ còn khoảng 18 dòng, quá ít để thử loại xét nghiệm có nhiều trường hợp đặc biệt (cận 0–0, thiếu cận).

**Bước 4 – Lấy 40 kết quả lõi trước.** Mỗi loại có 8 dòng lõi; các dòng này được tính vào hạn mức của loại đó.

**Bước 5 – Lấy phần còn lại theo kiểu xoay vòng bệnh nhân.** Với từng loại, bỏ các dòng lõi ra, rồi:

1. Xếp kết quả của mỗi bệnh nhân theo thời gian (`charttime`), sớm nhất trước; trùng thời gian thì `labevent_id` nhỏ hơn trước.
2. Đánh số thứ tự trong từng bệnh nhân: kết quả sớm nhất là lượt 0, kế tiếp là lượt 1, …
3. Xếp toàn bộ theo (lượt, `subject_id`, `charttime`, `labevent_id`) – tất cả so sánh dạng số/thời gian tăng dần.
4. Lấy từ trên xuống cho đến khi đủ hạn mức.

Nói đơn giản: mỗi bệnh nhân lấy 1 kết quả sớm nhất, hết một vòng thì lấy kết quả sớm thứ hai của mỗi người, cứ thế đến khi đủ.
Cách này giúp kết quả trải đều trên các bệnh nhân, không có ai chiếm quá nhiều. Cách chọn **không dùng ngẫu nhiên**, nên chạy lại luôn ra cùng một danh sách.

## 3. Kết quả kỳ vọng (dùng để kiểm tra notebook)

| Kiểm tra | Giá trị đúng |
|---|---|
| Tổng số dòng / số `labevent_id` khác nhau | 1.000 / 1.000 |
| Số bệnh nhân | 100 |
| Số dòng lõi có trong tập | 40/40 |
| Phân bố theo itemid | 50971: 209 · 50912: 209 · 51222: 209 · 50802: 200 · 51492: 173 |
| Số bệnh nhân theo itemid | 50971: 100 · 50912: 100 · 51222: 100 · 50802: 77 · 51492: 53 |
| Số kết quả mỗi bệnh nhân | ít nhất 6, nhiều nhất 22, trung vị 9 |
| Cận tham chiếu | 657 đủ hai cận · 343 thiếu cả hai · 0 chỉ có một cận |
| Giá trị đặc biệt | 48 giá trị bằng 0 · 86 giá trị âm |
| SHA-256 danh sách ID | `812e5a8917a269e3b9bbb686ebbef0866014c060eb545a32aa05bc0709e6ae6e` |

Cách tính SHA-256 danh sách ID: xếp `labevent_id` tăng dần theo số nguyên, mỗi ID một dòng, mỗi dòng kết thúc bằng `\n` (kể cả dòng cuối), mã hóa UTF-8, rồi băm SHA-256.

## 4. Giới hạn cần nói rõ khi viết báo cáo

- Đây là **chọn mẫu có chủ đích** theo quy tắc cố định, không phải mẫu ngẫu nhiên đại diện cho toàn bộ MIMIC-IV.
- Hạn mức 173/200/209 là quyết định của nhóm để cân bằng các loại xét nghiệm; có thể chọn cách chia khác, nhưng cách này đã được cố định và kiểm tra lại được.
- Nếu đợt chạy E1 trước đây đã dùng một danh sách 1.000 dòng khác, phải đối chiếu (notebook 05, mục cuối) trước khi đưa số liệu E1 vào chương 3.
