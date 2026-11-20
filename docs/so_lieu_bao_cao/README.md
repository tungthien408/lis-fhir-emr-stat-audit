# Đối chiếu số liệu của báo cáo khảo sát với dữ liệu gốc

Các file ở đây do **notebook 01** (`notebooks/01_dataset_profiling.ipynb`, mục E) tạo ra khi chạy trên 4 file MIMIC-IV Demo 2.2 thật (SHA-256 đúng như báo cáo, mục 1.1). Chỉ chứa **số tổng hợp**, không có dòng dữ liệu gốc.

Phạm vi: mục 1–4, mục 6, phụ lục A và B của báo cáo *Báo cáo khảo sát dữ liệu xét nghiệm MIMIC IV* (ngày 13/10/2026). Dữ liệu gốc là chuẩn; số trong báo cáo lệch thì ghi là lệch, không sửa code cho khớp.

## Các file

| File | Nội dung |
|---|---|
| `so_lieu_bao_cao.csv` | **File chính.** Mỗi số trong báo cáo một dòng: `muc_bao_cao`, `ten_so_lieu`, `gia_tri_trong_bao_cao`, `gia_tri_tu_code`, `khop` (có/không), `noi_tinh` (notebook và hàm tính ra số đó). Cuối file có 4 dòng tổng kết phụ lục A và B. |
| `so_lieu_lech.csv` | Chỉ các dòng có `khop = không`. |
| `phu_luc_a_so_sanh.csv` | Từng ô của phụ lục A (498 loại xét nghiệm x 8 cột). |
| `phu_luc_b_so_sanh.csv` | Từng ô của phụ lục B (498 loại xét nghiệm x 10 cột). |
| `so_lieu_chi_co_trong_code.csv` | Số code tính được nhưng báo cáo không nêu. |

Số trong báo cáo được đọc từ `data/external/bao_cao_*.csv`, do `scripts/trich_so_lieu_bao_cao.py` trích từ văn bản báo cáo. Số không có dấu tách nghìn, dấu thập phân là dấu chấm.

## Kết quả lần chạy này

- Mục 1–4 và 6: **345 số** trong báo cáo, **343 khớp, 2 lệch**.
- Phụ lục A: 3.984 ô, **khớp hết**. Phụ lục B: 4.980 ô, **khớp hết**.

Hai số lệch (cần sửa **trong báo cáo**):

| Mục | Số liệu | Trong báo cáo | Số đúng (từ dữ liệu gốc) | Ghi chú |
|---|---|---|---|---|
| 2.2 | `d_labitems.label`, cột "Thiếu" | để trống | **4** | 3 ô rỗng và 1 ô chỉ có khoảng trắng; không xét nghiệm nào dùng 4 mã này |
| 2.3 | `labevents.valueuom`, cột "Thiếu" | 16.203 | **14.381** | 14.042 ô rỗng + 339 ô khoảng trắng. Con số 16.203 là 14.042 + 2.161 ô `N/A`; `N/A` là chuỗi có mặt chứ không phải ô thiếu, như mục 3.2 và 4.2 của chính báo cáo |

Mục 4.2 của báo cáo đã ghi đúng 14.381 cho `valueuom`; chỉ bảng ở mục 2.3 sai.

## Cách tính (để làm lại hoặc kiểm tra)

- **Thiếu** = ô rỗng hoặc chỉ có khoảng trắng. `N/A`, `___`, `?` là chuỗi có mặt, không phải ô thiếu.
- **So số:** số nguyên phải bằng nhau tuyệt đối; số thập phân so sau khi làm tròn số code theo đúng số chữ số thập phân báo cáo ghi (ví dụ 296,3).
- **Phân vị 95 của độ trễ (mục 4.5):** nội suy tuyến tính (mặc định của numpy); báo cáo không nêu cách tính, kết quả 296,3 phút khớp.
- **Phụ lục A:** "Mốc đo" = số cặp (`subject_id`, `charttime`) khác nhau; "Giá trị" = số chuỗi `value` không rỗng khác nhau; "Đo lặp" = số bệnh nhân có hơn một bản ghi của loại đó; đơn vị xếp theo số dòng giảm dần.
- **Phụ lục B:** "Ứng viên" dùng đúng hàm sàng lọc cơ bản của notebook 04 và 05 (`analysis_core.selection.screen_labevents`).
- **Mục 6:** 40 kết quả do hàm `select_core_40` chọn từ dữ liệu gốc (xem `docs/quy_tac_chon_mau_40.md`), rồi tính các thống kê của mục 6.1; mục 6.3 được so từng trường với CSV gốc.

## Làm lại

```bash
python scripts/trich_so_lieu_bao_cao.py <bao_cao.md>      # chỉ cần khi báo cáo thay đổi
jupyter nbconvert --execute --inplace notebooks/01_dataset_profiling.ipynb
```

## Chưa nằm trong phạm vi

Các mục 5 và 7 của báo cáo (đối chiếu MR01–MR09, kết luận) không có con số nào để tính lại, nên không đối chiếu ở đây.
