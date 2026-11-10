#!/usr/bin/env python3
"""Sinh dữ liệu cho bot tư vấn từ price_data.json + image_manifest.json.

Đầu ra (thư mục bot/):
  - nhom_san_pham.json : danh mục nhóm SP + từ khoá + "họ" sản phẩm.
                         Bot CHỈ được gửi mẫu/giá trong cùng nhóm (hoặc cùng họ)
                         với nhóm khách hỏi.
  - balo.json          : thông tin + giá tham khảo + ảnh mẫu các loại balo
                         (ưu tiên hàng sẵn kho).

Chạy:  python3 scripts/build_bot_data.py
Kiểm tra phân loại:  python3 scripts/build_bot_data.py --test
"""
import json
import re
import sys
import unicodedata
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "bot"

# ---------------------------------------------------------------------------
# Từ khoá nhận diện nhóm. Khoá = mã nhóm "x.y".
# Tên nhóm (bỏ mã số) luôn được thêm tự động làm từ khoá.
# ---------------------------------------------------------------------------
KEYWORDS = {
    "5.6": ["balo laptop", "ba lô laptop", "balo máy tính", "balo văn phòng"],
    "6.2": ["balo", "ba lô", "balô", "backpack", "balo du lịch", "balo vải",
            "balo dây rút", "túi dây rút"],
    "12.3": ["balo trẻ em", "balo học sinh", "ba lô học sinh", "balô học sinh",
             "cặp học sinh", "balo mầm non", "balo mẫu giáo", "balo cho bé",
             "balo cho học sinh",
             # "a+b": đủ các cụm trong câu (không cần liền nhau)
             "balo+học sinh", "ba lô+học sinh", "balo+trẻ em", "ba lô+trẻ em",
             "balo+mầm non", "balo+mẫu giáo", "balo+cho bé", "balo+đi học"],
    "8.4": ["thẻ hành lý", "thẻ treo hành lý", "tag hành lý", "name tag",
            "nametag", "luggage tag", "thẻ treo vali", "thẻ vali", "tag vali",
            "bag tag"],
    "7.5": ["móc khoá", "móc khóa", "móc chìa khoá", "móc chìa khóa", "keychain",
            "key chain", "móc treo chìa"],
    "8.7": ["dây đeo thẻ", "dây đeo", "lanyard", "dây strap"],
    "3.1": ["biển tên", "bảng tên", "thẻ tên"],
    "6.3": ["túi canvas", "túi vải canvas", "túi tote", "tote"],
    "6.10": ["túi du lịch", "túi trống", "túi xách du lịch"],
    "1.6": ["bình nước", "bình giữ nhiệt", "chai nước"],
    "8.2": ["mũ lưỡi trai", "nón lưỡi trai", "mũ"],
    "8.5": ["áo phông", "áo thun", "áo đồng phục"],
    "8.1": ["ô", "dù"],
    "4.2": ["bút bi"],
    "5.1": ["usb"],
}

# Họ sản phẩm: các nhóm cùng loại hàng, được phép gợi ý chéo trong họ.
# Nhóm không thuộc họ nào => chỉ gợi ý trong chính nhóm đó.
FAMILIES = {
    "balo": ["12.3", "6.2", "5.6"],
    "the_hanh_ly": ["8.4"],
    "moc_khoa": ["7.5"],
}

# Nhóm "ưu tiên" khi trùng từ khoá chung (VD: "balo" khớp cả 6.2 và 12.3).
# Từ khoá dài hơn (cụ thể hơn) luôn thắng.


def strip_accents(s):
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "D")


def norm(s):
    s = strip_accents((s or "").lower())
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " " + s.strip() + " "


def group_code(nhom):
    m = re.match(r"\s*(\d+)\s*\.\s*(\d+)", nhom or "")
    return f"{int(m.group(1))}.{int(m.group(2))}" if m else None


def group_name(nhom):
    return re.sub(r"^\s*\d+\s*\.\s*\d+\s*\.?\s*", "", nhom or "").strip()


def load():
    data = json.loads((ROOT / "price_data.json").read_text(encoding="utf-8"))
    mani = json.loads((ROOT / "image_manifest.json").read_text(encoding="utf-8"))
    return data, mani


def build_groups(data, mani):
    groups = OrderedDict()
    for x in data + mani:
        code = group_code(x["nhom"])
        if not code:
            continue
        g = groups.setdefault(code, {"ma": code, "ten": group_name(x["nhom"]),
                                     "ten_goc": set(), "so_dong_gia": 0,
                                     "so_anh": 0})
        g["ten_goc"].add(x["nhom"])
    for x in data:
        code = group_code(x["nhom"])
        if code:
            groups[code]["so_dong_gia"] += 1
    for x in mani:
        code = group_code(x["nhom"])
        if code:
            groups[code]["so_anh"] += 1

    fam_of = {c: f for f, cs in FAMILIES.items() for c in cs}
    out = []
    for code in sorted(groups, key=lambda c: tuple(map(int, c.split(".")))):
        g = groups[code]
        kws = [g["ten"].lower()] + KEYWORDS.get(code, [])
        seen, uniq = set(), []
        for k in kws:
            key = "+".join(norm(p) for p in k.split("+"))
            if key not in seen and key.strip():
                seen.add(key)
                uniq.append(k)
        fam = fam_of.get(code)
        out.append({
            "ma": code,
            "ten": g["ten"],
            "ten_goc": sorted(g["ten_goc"]),
            "tu_khoa": uniq,
            "ho": fam,
            "duoc_goi_y_nhom": FAMILIES[fam] if fam else [code],
            "so_dong_gia": g["so_dong_gia"],
            "so_anh": g["so_anh"],
        })
    return out


def classify(text, groups):
    """Trả về mã nhóm khớp từ khoá dài nhất, hoặc None nếu không khớp."""
    t = norm(text)
    best, best_len = None, 0
    for g in groups:
        for k in g["tu_khoa"]:
            parts = [norm(p) for p in k.split("+")]
            if all(p in t for p in parts):
                n = sum(len(p) for p in parts)
                if n > best_len:
                    best, best_len = g["ma"], n
    return best


def fmt_price(v):
    return f"{int(round(v)):,}".replace(",", ".") + "đ"


def build_balo(data, mani):
    codes = FAMILIES["balo"]
    items = OrderedDict()
    for x in data:
        code = group_code(x["nhom"])
        if code not in codes:
            continue
        sp = re.sub(r"\\\*", "*", x["sp"]).strip()
        key = (code, norm(sp))
        it = items.setdefault(key, {
            "nhom": code, "ten": sp, "ghi_chu": "", "san_kho": False,
            "bac_gia": {},
        })
        note = re.sub(r"\s+", " ", (x.get("ghichu") or "")).strip()
        if note and len(note) > len(it["ghi_chu"]):
            it["ghi_chu"] = note
        if "sẵn" in (note + " " + sp).lower():
            it["san_kho"] = True
        price = x.get("giatt") or x.get("giaban")
        if price and x.get("sl"):
            sl = int(x["sl"])
            # giữ giá thấp nhất cho mỗi mức SL
            if sl not in it["bac_gia"] or price < it["bac_gia"][sl]:
                it["bac_gia"][sl] = price

    imgs = {}
    for x in mani:
        code = group_code(x["nhom"])
        if code in codes:
            imgs.setdefault(code, []).append(x["file"])

    out = []
    for it in items.values():
        tiers = [{"sl": s, "gia": p} for s, p in sorted(it["bac_gia"].items())]
        prices = [t["gia"] for t in tiers]
        it2 = {
            "nhom": it["nhom"],
            "ten": it["ten"],
            "san_kho": it["san_kho"],
            "ghi_chu": it["ghi_chu"],
            "bac_gia": tiers,
            "gia_tham_khao": (
                f"{fmt_price(min(prices))} – {fmt_price(max(prices))}/chiếc tuỳ số lượng"
                if prices and min(prices) != max(prices)
                else (f"khoảng {fmt_price(prices[0])}/chiếc" if prices else None)
            ),
        }
        out.append(it2)
    # Ưu tiên: có giá trước, sẵn kho trước
    out.sort(key=lambda i: (i["gia_tham_khao"] is None, not i["san_kho"],
                            codes.index(i["nhom"])))
    return {
        "mo_ta": "Balo (12.3 trẻ em/học sinh, 6.2 ba lô, 5.6 laptop). "
                 "Giá THAM KHẢO, chưa VAT, chưa phí VC; mục có ghi chú 'hàng sẵn' "
                 "là hàng có sẵn kho, đã gồm in logo 1 màu 1 vị trí.",
        "co_gia": [i for i in out if i["gia_tham_khao"]],
        "chua_co_gia": [i for i in out if not i["gia_tham_khao"]],
        "anh_mau": imgs,
    }


TESTS = [
    ("Mình muốn đặt Balô vải cho học sinh", "12.3"),
    ("báo giá balo", "6.2"),
    ("cần ba lô đi học cho trẻ em", "12.3"),
    ("có mẫu cặp học sinh không", "12.3"),
    ("balo laptop in logo", "5.6"),
    ("Bên mình có làm name tag mẫu như này k ạ", "8.4"),
    ("thẻ hành lý da", "8.4"),
    ("móc khoá da", "7.5"),
    ("dây đeo thẻ in logo", "8.7"),
]


def main():
    data, mani = load()
    groups = build_groups(data, mani)
    if "--test" in sys.argv:
        bad = 0
        for text, want in TESTS:
            got = classify(text, groups)
            ok = got == want
            bad += not ok
            print(("OK  " if ok else "SAI ") + f"{text!r} -> {got} (cần {want})")
        sys.exit(1 if bad else 0)
    OUT.mkdir(exist_ok=True)
    (OUT / "nhom_san_pham.json").write_text(
        json.dumps({
            "quy_tac": "Chỉ gửi mẫu/giá trong 'duoc_goi_y_nhom' của nhóm khách hỏi. "
                       "Không khớp nhóm nào => hỏi lại khách, KHÔNG đoán sang nhóm khác.",
            "nhom": groups,
        }, ensure_ascii=False, indent=1),
        encoding="utf-8")
    (OUT / "balo.json").write_text(
        json.dumps(build_balo(data, mani), ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"Đã ghi {OUT/'nhom_san_pham.json'} ({len(groups)} nhóm), {OUT/'balo.json'}")


if __name__ == "__main__":
    main()
