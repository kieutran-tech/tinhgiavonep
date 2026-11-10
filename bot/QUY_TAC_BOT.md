# Quy tắc gửi mẫu & giá tham khảo cho bot

## 1. Chỉ gửi mẫu CÙNG NHÓM sản phẩm khách hỏi

1. Xác định nhóm từ tin nhắn khách theo `nhom_san_pham.json` (khớp từ khoá dài/cụ thể nhất).
2. Chỉ gửi ảnh mẫu + giá thuộc các nhóm trong `duoc_goi_y_nhom` của nhóm đó.
   - Balo: 12.3 (trẻ em/học sinh) → 6.2 (ba lô) → 5.6 (laptop).
   - Thẻ hành lý / name tag: chỉ 8.4.
   - Móc khoá: chỉ 7.5.
3. **Bỏ** đoạn "Ngoài ra bên em còn làm móc khóa kim loại, nhựa…" nếu không cùng nhóm khách hỏi.
4. Không khớp nhóm nào → hỏi lại khách tên sản phẩm. **Không đoán sang nhóm khác.**
5. Khách chỉ gửi ảnh: ưu tiên chữ khách viết kèm ("name tag" → 8.4). Thẻ chữ nhật có ô cửa sổ
   ghi thông tin + quai/dây gắn vali là **thẻ hành lý (8.4)**, không phải móc khoá.

## 2. Khách hỏi balo

Gửi ngay 2–3 mẫu từ `balo.json → co_gia` cùng nhóm (khách nói học sinh/trẻ em → nhóm 12.3)
kèm giá tham khảo, rồi mới xin tên + SĐT. Mẫu tin:

> Dạ bên em có sẵn balo học sinh in logo theo yêu cầu. Giá THAM KHẢO (chưa VAT, chưa phí VC):
> 1. Balo trẻ em hàng sẵn kho (đã gồm in logo 1 màu 1 vị trí) — khoảng 134.000đ/chiếc
> 2. Balo trẻ em vải bố 30x35cm, in 1 màu 1 vị trí — 95.000đ – 100.000đ/chiếc tuỳ số lượng
> 3. Balo mẫu giáo 32x22cm — 88.000đ – 95.000đ/chiếc tuỳ số lượng
> (Ảnh mẫu em gửi ngay bên dưới.) Anh/chị cho em xin số lượng + tên, SĐT để nhân viên báo giá chính xác ạ.

## 3. Cập nhật dữ liệu

`python3 scripts/build_bot_data.py` (sinh lại sau khi sửa `price_data.json`),
`python3 scripts/build_bot_data.py --test` (kiểm tra phân loại các câu mẫu).
`balo.json → chua_co_gia`: 18 mẫu balo hàng sẵn (mã 510, 513, 2201, 2202, 6112, 6120, 6130,
balo mặt gấu, laptop 9080/9005-2/902…) **chưa có giá** trong dữ liệu — cần bổ sung giá vào `price_data.json`.
