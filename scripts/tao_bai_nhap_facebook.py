#!/usr/bin/env python3
"""Tạo lô bài nháp Facebook cho fanpage EPVINA từ dữ liệu trong repo.

Đọc price_data.json + image_manifest.json + image_chunk_N.json, chọn sản phẩm
có dữ liệu "✓ Chuẩn" và có ảnh, rồi xuất bài nháp (caption + ảnh + overlay +
giờ đăng) vào drafts/<năm>-W<tuần>/ để NGƯỜI DUYỆT trước khi đăng.

Không gọi API nào, không đăng gì lên Facebook.

Cách dùng (chạy ở thư mục gốc repo):
    python3 scripts/tao_bai_nhap_facebook.py                 # 5 bài cho tuần tới
    python3 scripts/tao_bai_nhap_facebook.py --so-bai 3
    python3 scripts/tao_bai_nhap_facebook.py --tuan 2026-W46
    python3 scripts/tao_bai_nhap_facebook.py --mien-nam      # dùng hotline TP.HCM

Quy tắc nội dung theo skill "Viết bài fanpage EPVINA":
  - Hook có con số ở dòng đầu, >= 2 con số thật, 1 CTA + 1 bộ hotline, 3–5 hashtag.
  - KHÔNG nêu số tiền (giá trong price_data.json chưa đối chiếu bảng giá bán lẻ
    hiện hành), không nêu giá nhập/giá vốn/nhà cung cấp, không dùng từ cấm,
    không viết "sản xuất tại xưởng Epvina".
"""
import argparse
import base64
import datetime as dt
import hashlib
import json
import re
import sys
import unicodedata
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "drafts"
USED_LOG = DRAFTS / "da_dung.json"

NAM_THANH_LAP = 2013
HOTLINE_HN = "024.3767.8915 – 0903.296.006"
HOTLINE_HCM = "028.3862.8188 – 0936.316.006"
SL_TOI_THIEU = 20
HASHTAG_CO_DINH = ["#Epvina", "#quatangdoanhnghiep"]

# Ngày đăng trong tuần (0 = thứ Hai) và giờ đăng mặc định.
# Đây là giá trị mặc định của script, KHÔNG lấy từ file nền 02 — chỉnh lại
# theo khung giờ chuẩn trong file 02 nếu khác.
LICH_DANG = [(0, "11:30"), (1, "20:00"), (2, "11:30"), (3, "20:00"), (4, "11:30"),
             (5, "09:00"), (6, "20:00")]

TU_CAM = ["đẳng cấp", "sang chảnh", "siêu hot", "uy tín số 1", "chất lượng hàng đầu",
          "rẻ nhất thị trường", "cực kỳ", "vô cùng", "tuyệt vời",
          "sản xuất tại xưởng", "100% sản xuất", "made in vietnam",
          "tự sản xuất", "15 năm"]

HOOKS = [
    "📌 {ten} in logo – nhận đơn từ {sl} sản phẩm.",
    "{sl} sản phẩm trở lên là Epvina nhận in logo {ten_thuong}.",
    "Cần {ten_thuong} in logo cho sự kiện? Đơn từ {sl} sản phẩm.",
    "Từ {sl} sản phẩm, {ten_thuong} in logo riêng cho doanh nghiệp anh/chị.",
]
BOI_CANH = [
    "Quà tặng sự kiện cần đúng ngân sách và kịp ngày giao.\nEpvina báo giá theo từng mức số lượng để anh/chị chủ động dự toán.",
    "Phòng hành chính – nhân sự thường cần chốt quà nhanh mà vẫn đúng logo, đúng màu.\nEpvina gửi bản in thử để anh/chị duyệt trước.",
    "Một món quà có logo được dùng hằng ngày giúp thương hiệu ở lại lâu với khách hàng và nhân viên.\nEpvina tư vấn mẫu theo dịp tặng và ngân sách.",
]
CTA = "👉 Inbox Epvina số lượng, ngân sách và ngày cần nhận để được báo giá."


def bo_dau(s):
    s = s.replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def ten_nhom(nhom):
    """'1.4 cốc sứ' -> 'cốc sứ'"""
    return re.sub(r"^[\d.\s]+", "", nhom or "").strip()


def hashtag_nhom(nhom):
    t = re.sub(r"[^a-z0-9]", "", bo_dau(ten_nhom(nhom).split("-")[0].split(",")[0]).lower())
    return f"#{t}inlogo" if t else None


def tach_quy_cach(sp):
    """Tách mô tả sản phẩm thành tên + các dòng quy cách.

    Bỏ các dòng nói về kỹ thuật in / giá / in ấn để tránh nêu kỹ thuật
    ngoài danh sách tại xưởng — người duyệt bổ sung nếu cần."""
    sp = sp.replace("\\*", "x").replace("*", "x")
    parts = [p.strip(" .;") for p in re.split(r"\s+-\s+|\n", sp) if p.strip(" .;")]
    ten = parts[0] if parts else sp
    # tên ngắn cho hook: cắt ở dấu ":" / "," / "(" và giới hạn 7 từ
    ten = re.split(r"[:,(]", ten)[0].strip()
    ten = " ".join(ten.split()[:7])
    quy_cach = []
    for p in parts[1:]:
        low = p.lower()
        if re.search(r"\bin\b|in ấn|khắc|giá|logo|tệ|ncc|vat", low):
            continue
        quy_cach.append(p[0].upper() + p[1:])
    return ten, quy_cach[:2]


def chon_bac_gia(rows):
    rows = [r for r in rows if r.get("chuan") and r.get("giaban") and r.get("sl")]
    rows.sort(key=lambda r: r["sl"])
    return rows


def tuan_toi(today):
    d = today + dt.timedelta(days=7 - today.weekday())  # thứ Hai tuần sau
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def thu_hai_cua_tuan(tuan):
    y, w = tuan.split("-W")
    return dt.date.fromisocalendar(int(y), int(w), 1)


def nap_du_lieu():
    data = json.loads((ROOT / "price_data.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "image_manifest.json").read_text(encoding="utf-8"))
    anh = {(m["nhom"], m["sp"]): m for m in manifest if m.get("chunk") is not None}
    nhom_sp = OrderedDict()
    for r in data:
        nhom_sp.setdefault((r["nhom"], r["sp"]), []).append(r)
    ung_vien = []
    for (nhom, sp), rows in nhom_sp.items():
        bac = chon_bac_gia(rows)
        # bỏ sản phẩm có SL tối thiểu quá nhỏ (đơn lẻ, không hợp bài quà tặng số lượng)
        if bac and bac[0]["sl"] >= SL_TOI_THIEU and (nhom, sp) in anh:
            ung_vien.append({"nhom": nhom, "sp": sp, "bac": bac, "anh": anh[(nhom, sp)]})
    return ung_vien


def khoa_sp(u):
    return hashlib.sha1(f"{u['nhom']}||{u['sp']}".encode("utf-8")).hexdigest()[:12]


def chon_san_pham(ung_vien, so_bai, tuan, da_dung):
    """Mỗi bài một nhóm khác nhau, bỏ qua sản phẩm đã đăng; thứ tự cố định theo tuần."""
    def thu_tu(u):
        return hashlib.sha1(f"{tuan}|{khoa_sp(u)}".encode()).hexdigest()
    chua_dung = sorted((u for u in ung_vien if khoa_sp(u) not in da_dung), key=thu_tu)
    if len(chua_dung) < so_bai:  # đã dùng hết -> quay vòng lại từ đầu
        chua_dung = sorted(ung_vien, key=thu_tu)
    chon, nhom_da_chon = [], set()
    for u in chua_dung:
        if u["nhom"] not in nhom_da_chon:
            chon.append(u)
            nhom_da_chon.add(u["nhom"])
        if len(chon) == so_bai:
            break
    return chon


def viet_bai(u, stt, mien_nam):
    ten, quy_cach = tach_quy_cach(u["sp"])
    sl_min = u["bac"][0]["sl"]
    so_bac = len({r["sl"] for r in u["bac"]})
    sl_txt = f"{sl_min:,}".replace(",", ".")
    # chỉ hạ chữ đầu khi không phải chữ viết tắt/viết hoa toàn bộ (vd "BÓNG BAY")
    ten_thuong = ten[0].lower() + ten[1:] if ten[1:2].islower() else ten
    nam = dt.date.today().year - NAM_THANH_LAP

    hook = HOOKS[stt % len(HOOKS)].format(ten=ten, ten_thuong=ten_thuong, sl=sl_txt)
    boi_canh = BOI_CANH[stt % len(BOI_CANH)]
    gach = [f"✅ {q}" for q in quy_cach[:1]]
    if so_bac > 1:
        gach.append(f"✅ {so_bac} mức giá theo số lượng, bắt đầu từ {sl_txt} sản phẩm")
    else:
        gach.append(f"✅ Số lượng tối thiểu {sl_txt} sản phẩm")
    gach.append("✅ In logo tại xưởng Hà Nội, in thử duyệt màu trước khi chạy hàng loạt")
    gach.append(f"✅ Epvina kiểm hàng và đóng gói trước khi giao – {nam} năm làm quà tặng doanh nghiệp")
    gach = gach[:4]
    hotline = HOTLINE_HCM if mien_nam else HOTLINE_HN
    tags = HASHTAG_CO_DINH + [t for t in [hashtag_nhom(u["nhom"]), "#quatangsukien"] if t]
    tags = list(dict.fromkeys(tags))[:5]

    caption = "\n".join([
        hook, "", boi_canh, "", *gach, "",
        CTA, f"☎️ Hotline: {hotline}", "", " ".join(tags),
    ])
    overlay = f"{ten_nhom(u['nhom']).capitalize()} – từ {sl_txt} sp"
    if len(overlay.split()) > 6:
        overlay = f"In logo từ {sl_txt} sp"
    return ten, caption, overlay, sl_min, so_bac


def kiem_tra(caption):
    loi = []
    low = caption.lower()
    for tu in TU_CAM:
        if tu in low:
            loi.append(f"có từ cấm: “{tu}”")
    if not re.search(r"\d", caption.splitlines()[0]):
        loi.append("dòng đầu không có con số")
    if re.search(r"\d[\d.]*\s*(đ|vnđ|vnd|k|tệ|đồng)(?!\w)", low):
        loi.append("có số tiền – phải đối chiếu bảng giá bán lẻ trước khi đăng")
    so_tag = len(re.findall(r"#\w+", caption))
    if not 3 <= so_tag <= 5:
        loi.append(f"{so_tag} hashtag (cần 3–5)")
    so_tu = len(re.sub(r"#\w+", "", caption).split())
    if not 80 <= so_tu <= 150:
        loi.append(f"{so_tu} từ (bài sản phẩm nên 80–150 từ)")
    if caption.count("Hotline") != 1:
        loi.append("phải có đúng 1 bộ hotline")
    return so_tu, loi


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--so-bai", type=int, default=5, help="số bài trong lô (mặc định 5, tối đa 7)")
    ap.add_argument("--tuan", help="tuần ISO, vd 2026-W46 (mặc định: tuần tới)")
    ap.add_argument("--mien-nam", action="store_true", help="dùng hotline TP.HCM thay cho Hà Nội")
    ap.add_argument("--khong-ghi-log", action="store_true", help="không đánh dấu sản phẩm là đã dùng")
    args = ap.parse_args()
    so_bai = max(1, min(args.so_bai, len(LICH_DANG)))
    tuan = args.tuan or tuan_toi(dt.date.today())
    thu_hai = thu_hai_cua_tuan(tuan)

    da_dung = json.loads(USED_LOG.read_text(encoding="utf-8")) if USED_LOG.exists() else {}
    ung_vien = nap_du_lieu()
    chon = chon_san_pham(ung_vien, so_bai, tuan, da_dung)
    if not chon:
        sys.exit("Không tìm thấy sản phẩm nào có giá chuẩn + ảnh.")

    out = DRAFTS / tuan
    (out / "anh").mkdir(parents=True, exist_ok=True)
    chunks = {}
    bai_list = []
    # rải đều các bài trong tuần
    idx_lich = [round(i * (len(LICH_DANG) - 1) / max(so_bai - 1, 1)) for i in range(so_bai)] if so_bai > 1 else [0]

    for i, u in enumerate(chon):
        ten, caption, overlay, sl_min, so_bac = viet_bai(u, i, args.mien_nam)
        so_tu, loi = kiem_tra(caption)
        c = u["anh"]["chunk"]
        if c not in chunks:
            chunks[c] = json.loads((ROOT / f"image_chunk_{c}.json").read_text(encoding="utf-8"))
        ext = Path(u["anh"]["file"]).suffix.lower() or ".jpg"
        ten_anh = f"bai{i + 1:02d}{ext}"
        (out / "anh" / ten_anh).write_bytes(base64.b64decode(chunks[c][u["anh"]["file"]]))
        thu, gio = LICH_DANG[idx_lich[i]]
        ngay = thu_hai + dt.timedelta(days=thu)
        bai_list.append({
            "stt": i + 1,
            "trang_thai": "cho_duyet",  # người duyệt đổi thành "da_duyet" khi đồng ý đăng
            "nhom": u["nhom"],
            "san_pham": u["sp"],
            "ma_sp": khoa_sp(u),
            "so_luong_toi_thieu": sl_min,
            "so_muc_gia": so_bac,
            "caption": caption,
            "overlay": overlay,
            "anh": f"anh/{ten_anh}",
            "gio_dang": f"{ngay.isoformat()}T{gio}:00+07:00",
            "so_tu": so_tu,
            "canh_bao": loi,
        })
        da_dung[khoa_sp(u)] = tuan

    (out / "posts.json").write_text(json.dumps(bai_list, ensure_ascii=False, indent=2), encoding="utf-8")

    thu_vn = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ nhật"]
    md = [f"# Bài nháp Facebook EPVINA – tuần {tuan}", "",
          f"Tạo lúc {dt.datetime.now():%d/%m/%Y %H:%M} bằng `scripts/tao_bai_nhap_facebook.py`. "
          "**Tất cả bài đang ở trạng thái chờ duyệt — chưa đăng gì.**", "",
          "Trước khi đăng, người duyệt kiểm tra:",
          "- Thông số sản phẩm đúng với hàng hiện có; số lượng tối thiểu còn đúng.",
          "- Bài không nêu số tiền (giá trong dữ liệu chưa đối chiếu bảng giá bán lẻ hiện hành).",
          "- Mỗi bài mới có 1 ảnh sản phẩm từ dữ liệu báo giá — nên bổ sung 2–4 ảnh thật theo bộ 5 ảnh chuẩn (file nền 02).",
          "- Giờ đăng là mặc định của script; chỉnh theo khung giờ trong file nền 02 nếu khác.",
          "- Duyệt xong: sửa `trang_thai` trong `posts.json` thành `da_duyet`.", ""]
    for b in bai_list:
        ngay = dt.date.fromisoformat(b["gio_dang"][:10])
        md += [f"## Bài {b['stt']} – {b['nhom']}", "",
               f"- **Sản phẩm:** {b['san_pham']}",
               f"- **Giờ đăng đề xuất:** {thu_vn[ngay.weekday()]} {ngay:%d/%m/%Y}, {b['gio_dang'][11:16]}",
               f"- **Overlay ảnh bìa:** {b['overlay']}",
               f"- **Ảnh:** `{b['anh']}`", "",
               f"![{b['nhom']}]({b['anh']})", "",
               "**Caption:**", "", "```text", b["caption"], "```", ""]
        if b["canh_bao"]:
            md += ["> ⚠️ Cần sửa: " + "; ".join(b["canh_bao"]), ""]
    (out / "bai-nhap.md").write_text("\n".join(md), encoding="utf-8")

    if not args.khong_ghi_log:
        USED_LOG.write_text(json.dumps(da_dung, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Đã tạo {len(bai_list)} bài nháp tuần {tuan} trong {out.relative_to(ROOT)}/")
    for b in bai_list:
        tt = "OK" if not b["canh_bao"] else "CẦN SỬA: " + "; ".join(b["canh_bao"])
        print(f"  Bài {b['stt']}: {b['nhom']} | {b['gio_dang'][:16]} | {b['so_tu']} từ | {tt}")


if __name__ == "__main__":
    main()
