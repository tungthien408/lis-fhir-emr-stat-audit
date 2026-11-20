# Quy tắc chọn 40 kết quả lõi

Tài liệu này ghi lại **cách chọn 40 kết quả lõi** (mục 6.3 của báo cáo khảo sát) từ MIMIC-IV Demo 2.2.
Hàm `select_core_40` trong `src/analysis_core/selection.py` làm đúng theo các bước bên dưới; notebook `04_sample_selection_audit.ipynb` chạy hàm này trên dữ liệu gốc rồi so với danh sách trong báo cáo.

> **Đọc trước:** danh sách 40 dòng đã chốt và đã nạp vào LIS từ trước. Quy tắc dưới đây được **tìm lại từ danh sách đó**, không phải quy tắc có sẵn rồi mới chọn ra danh sách.
> Chạy quy tắc trên dữ liệu gốc cho đúng 40/40 dòng. Tuy vậy, dữ liệu không chứng minh được đây là cách duy nhất cho ra danh sách này.

## 1. Vì sao cần tài liệu này

Mục 6.2 của báo cáo mô tả cách chọn bằng lời: sàng lọc, sắp theo `labevent_id` tăng dần, ưu tiên một số dòng đặc biệt, rồi bổ sung cho đủ 8 dòng mỗi loại.
Làm đúng chữ như vậy **không ra được danh sách đã chốt**. Chỉ riêng việc lấy 8 `labevent_id` nhỏ nhất của mỗi loại đã chỉ khớp **20/40** dòng. Chẳng hạn:

- Potassium (50971): bỏ mã 154 nhưng lại lấy 174 và 190.
- Protein nước tiểu (51492): bỏ bệnh nhân 10002495 và mã 28157.
- Mỗi loại đều chỉ dùng 3 bệnh nhân, và các bệnh nhân này không phải lúc nào cũng là 3 người có `subject_id` nhỏ nhất.

Notebook 04 trước đây chỉ chép danh sách từ báo cáo rồi kiểm xem có khớp dữ liệu không, nên không tự chọn lại được.

## 2. Yêu cầu đã có sẵn từ báo cáo

- 5 loại xét nghiệm: 50971 Potassium, 50912 Creatinine, 51222 Hemoglobin, 50802 Base Excess, 51492 Protein (nước tiểu).
- Mỗi loại **8 kết quả**, thuộc **3 bệnh nhân**; toàn tập 40 kết quả.
- Dòng phải đạt sàng lọc cơ bản (mục 4.6 của báo cáo) và thuộc loại chỉ có một đơn vị đo.
- Không dùng ngẫu nhiên: chạy lại luôn ra cùng một danh sách.

## 3. Các bước chọn

Dữ liệu đầu vào: các dòng **đạt sàng lọc cơ bản** của 5 loại trên (cùng bộ sàng lọc với notebook 04 và 05; 9.574 dòng). Mỗi loại làm riêng:

**Bước 1 – Lấy dòng ưu tiên.** Mục 6.2 của báo cáo ưu tiên vài kiểu dòng đặc biệt. Mỗi kiểu lấy dòng có `labevent_id` **nhỏ nhất** thỏa điều kiện, tính trên toàn bộ dòng của loại đó:

| Loại | Dòng ưu tiên | Kết quả |
|---|---|---|
| 50971 Potassium | cặp cùng bệnh nhân, cùng giờ, **khác** giá trị | 174, 190 |
| 50912 Creatinine | cặp cùng bệnh nhân, cùng giờ, **cùng** giá trị | 171, 184 |
| 51222 Hemoglobin | không có | – |
| 50802 Base Excess | dòng có giá trị 0 và dòng có giá trị âm | 28240, 28277 |
| 51492 Protein | dòng có cận tham chiếu 0–0 và dòng có giá trị khác giá trị phổ biến nhất của loại này (30 mg/dL) | 39724, 28267 |

Nhờ các dòng này mẫu có đủ các trường hợp đặc biệt: hai kết quả gần giống nhau, số 0, số âm, cận 0–0.

**Bước 2 – Chọn 3 bệnh nhân.** Lấy bệnh nhân của các dòng ưu tiên trước, rồi thêm bệnh nhân có `subject_id` nhỏ nhất (trong số dòng của loại đó) cho đủ 3 người.

**Bước 3 – Mỗi bệnh nhân lấy 2 kết quả sớm nhất.** Xếp theo `charttime`; trùng thời gian thì `labevent_id` nhỏ hơn (so sánh dạng số). Dòng đã lấy ở bước 1 không lấy lại.

**Bước 4 – Bổ sung cho đủ 8.** Nếu chưa đủ 8 dòng, lấy tiếp các dòng còn lại của 3 bệnh nhân đó, theo `labevent_id` tăng dần, cho đến đủ.

Quy tắc chung (bước 2–4) giải thích 32 trong 40 dòng; 8 dòng còn lại là dòng ưu tiên ở bước 1.

## 4. Chỗ cần nói rõ (ngoại lệ và phần suy ngược)

1. **Bệnh nhân của Protein.** Ba bệnh nhân nhỏ nhất có Protein là 10000032, 10002428 và 10002495, nhưng danh sách lại dùng 10002930. Lý do: chỉ bệnh nhân 10002930 mới có dòng cận 0–0 (mã 39724) trong nhóm bệnh nhân nhỏ, và dòng này là dòng ưu tiên. Bước 2 cho dòng ưu tiên kéo bệnh nhân của nó vào trước, nên 10002930 vào thay cho 10002495. Mã 28157 bị bỏ vì bước 4 lấy `labevent_id` nhỏ nhất còn lại trong 3 bệnh nhân, và 27720 nhỏ hơn 28157.
2. **Bước 4 có hai cách đều ra 40/40.** Hoặc dồn vào bệnh nhân nhỏ nhất, hoặc lấy `labevent_id` nhỏ nhất còn lại. Dữ liệu không phân biệt được. Tài liệu chọn cách thứ hai vì khớp câu "sắp theo `labevent_id` tăng dần" trong báo cáo. Chỉ 4 dòng đi qua bước 4 (Hemoglobin 134 và 196, Base Excess 27534, Protein 27720).
3. **Giá trị "phổ biến nhất" của Protein** là 30 mg/dL (104 trong 173 dòng đạt), do code tính ra; không ghi cứng số 30.
4. **Đây là cách mô tả lại danh sách đã chốt.** Quy tắc, thứ tự ưu tiên và các điều kiện ưu tiên được chọn để khớp danh sách; có thể có cách khác cũng cho đúng 40 dòng này.
5. Quy tắc không dựa vào ngẫu nhiên, không dựa vào hadm_id, `priority` hay `flag`.

## 5. Kết quả kỳ vọng (dùng để kiểm tra notebook 04)

Số dòng và số bệnh nhân của từng loại, trong nhóm đạt sàng lọc cơ bản:

| itemid | Xét nghiệm | Số dòng đạt | Số bệnh nhân đạt |
|---|---|---|---|
| 50971 | Potassium | 2.766 | 100 |
| 50912 | Creatinine | 2.963 | 100 |
| 51222 | Hemoglobin | 2.783 | 100 |
| 50802 | Base Excess | 889 | 77 |
| 51492 | Protein (nước tiểu) | 173 | 53 |

Kết quả chọn:

| itemid | 3 bệnh nhân (số dòng) | Bước 1: ưu tiên | Bước 3: 2 sớm nhất mỗi người | Bước 4: bổ sung |
|---|---|---|---|---|
| 50971 | 10000032 (4), 10001217 (2), 10001725 (2) | 174, 190 | 33, 106, 8978, 9033, 12639, 12650 | – |
| 50912 | 10000032 (4), 10001217 (2), 10001725 (2) | 171, 184 | 19, 102, 8972, 9029, 12645, 12674 | – |
| 51222 | 10000032 (4), 10001217 (2), 10001725 (2) | – | 64, 79, 8949, 9014, 12659, 12685 | 134, 196 |
| 50802 | 10002428 (5), 10002495 (2), 10002930 (1) | 28240, 28277 | 27477, 27496, 32485, 32546, 38784 | 27534 |
| 51492 | 10000032 (1), 10002428 (4), 10002930 (3) | 28267, 39724 | 118, 27097, 27632, 38768, 38910 | 27720 |

| Kiểm tra | Giá trị đúng |
|---|---|
| Tổng số dòng / số `labevent_id` khác nhau | 40 / 40 |
| Số dòng mỗi loại | 8 |
| Số dòng theo bước | bước 1: 8 · bước 3: 28 · bước 4: 4 |
| Khớp danh sách mục 6.3 của báo cáo | 40/40 |
| Cách chạy: thứ tự dòng đầu vào | không ảnh hưởng kết quả |

Bước 3 cho 28 dòng: 6 dòng mỗi loại ở 3 loại đầu; chỉ 5 dòng ở Base Excess (bệnh nhân 10002930 chỉ có 1 dòng) và ở Protein (bệnh nhân 10000032 chỉ có 1 dòng).

## 6. Giới hạn cần nói rõ khi viết báo cáo

- Đây là chọn mẫu **có chủ đích** để thử các trường hợp đặc biệt, không phải mẫu ngẫu nhiên và không đại diện cho toàn bộ MIMIC-IV.
- Mục 6.2 của báo cáo chưa mô tả đủ để tự suy ra 40 dòng. Nếu sửa báo cáo, nên dẫn tới tài liệu này hoặc ghi lại bốn bước ở trên.
- Nếu muốn đổi cách chọn (ví dụ chọn bệnh nhân khác), phải làm lại cả danh sách đã nạp LIS và tập 1.000 kết quả, vì 40 dòng lõi nằm trong tập đó.
