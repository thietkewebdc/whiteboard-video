#!/usr/bin/env python3
"""Bố cục video dọc 9:16 cho TikTok / Reels / YouTube Shorts.

Khung 1080x1920. Theo các hướng dẫn vùng an toàn của TikTok (nguồn bên thứ ba, xem README):
chừa ~130px trên, ~484px dưới, ~44px trái, ~140px phải cho giao diện nền tảng (tên kênh, chú thích,
nút thích/chia sẻ). Nội dung quan trọng nằm trong khung chữ x 50..950, y 130..1436.

Bản đồ theo chiều dọc:
    0 -  230  Đầu video: logo thương hiệu (logo nằm dưới vạch 130px trên cùng)
  238 -  496  Tiêu đề HOOK to, từ khoá nhấn trong ô màu
  500 - 1500  Cửa sổ hình vẽ (đường chia ba trên y=640 rơi vào đối tượng đầu tiên,
              phụ đề nằm quanh đường chia ba dưới y=1280)
 1500 - 1920  Dải thương hiệu (vùng bị giao diện nền tảng che nên chỉ có nhãn dịch vụ trang trí)
"""
import json
import re
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
SAFE_X0, SAFE_X1 = 50, 950
CX = (SAFE_X0 + SAFE_X1) // 2            # 500: tâm khung chữ an toàn (lệch trái để tránh cột nút bên phải)
HEADER_H = 230
HOOK_Y0, HOOK_Y1 = 238, 496
WIN_Y, WIN_H = 500, 1000
BAND_Y = WIN_Y + WIN_H                    # 1500
SUB_BOTTOM = 1436                         # đáy chữ phụ đề, nằm trong vùng an toàn (dưới 484px cuối)

FONT_BOLD = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf",
             "C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
FONT_REG = ["/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
            "C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
INK = (24, 24, 24)
TOP_BAND_H = 130                          # dải trên cùng: vùng TikTok dùng cho thanh tab và tìm kiếm

SKILL = Path(__file__).resolve().parent.parent


# ---------- tiện ích văn bản ----------
def slugify(text: str, max_len: int = 70) -> str:
    """'Hàng Việt vào Mỹ: thuế 12,5%' -> 'hang-viet-vao-my-thue-12-5'."""
    t = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    if len(t) > max_len:
        t = t[:max_len].rsplit("-", 1)[0]
    return t


def strip_markup(hook: str) -> str:
    return re.sub(r"[\[\]]", "", hook).replace("_", " ")


def parse_hook(hook: str):
    """'Web có [VI PHẠM] luật?' -> token; phần trong [] được nhấn bằng ô màu."""
    toks = []
    for part in re.split(r"(\[[^\]]+\])", hook):
        if not part:
            continue
        if part.startswith("["):
            toks.append({"text": part[1:-1], "accent": True, "glue": False})
        else:
            for w in part.split():
                glue = bool(re.fullmatch(r"[!?.,:;…)%]+", w)) and bool(toks)
                toks.append({"text": w.replace("_", " "), "accent": False, "glue": glue})
    return toks


def font(cands, size):
    for p in cands:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _wrap(d, toks, fnt, max_w, pad):
    space = d.textlength(" ", font=fnt)
    lines, cur, cur_w = [], [], 0
    for t in toks:
        w = d.textlength(t["text"], font=fnt) + (2 * pad if t["accent"] else 0)
        add = w if (not cur or t["glue"]) else space + w
        if cur and cur_w + add > max_w and not t["glue"]:
            lines.append((cur, cur_w))
            cur, cur_w, add = [], 0, w
        cur.append((t, w))
        cur_w += add
    if cur:
        lines.append((cur, cur_w))
    return lines


def draw_hook(d, hook, box, accent, max_size=104, min_size=56, max_lines=3, cx=None, ink=INK):
    """Vẽ hook căn giữa trong box=(x0,y0,x1,y1): tự chọn cỡ chữ lớn nhất còn vừa."""
    x0, y0, x1, y1 = box
    cx = cx if cx is not None else (x0 + x1) // 2
    toks = parse_hook(hook)
    chosen = None
    for limit in sorted({min(3, max_lines), max_lines}):          # ưu tiên bố cục gọn tối đa 3 dòng
        for size in range(max_size, min_size - 1, -4):
            fnt = font(FONT_BOLD, size)
            pad = max(10, size // 7)
            lines = _wrap(d, toks, fnt, x1 - x0, pad)
            if len(lines) > 1:
                lo, hi = max(w for _, w in lines) * 0.5, x1 - x0
                for _i in range(14):
                    mid = (lo + hi) / 2
                    if len(_wrap(d, toks, fnt, mid, pad)) <= len(lines):
                        hi = mid
                    else:
                        lo = mid
                lines = _wrap(d, toks, fnt, hi + 1, pad)
            lh = int(size * 1.2)
            if (len(lines) <= limit and len(lines) * lh <= (y1 - y0)
                    and max(w for _, w in lines) <= (x1 - x0) + 1):
                chosen = (size, fnt, pad, lines, lh)
                break
        if chosen:
            break
    if not chosen:                                                # không vừa: dùng cỡ nhỏ nhất
        fnt = font(FONT_BOLD, min_size); size = min_size; pad = max(10, size // 7)
        lines = _wrap(d, toks, fnt, x1 - x0, pad); lh = int(size * 1.2)
        chosen = (size, fnt, pad, lines, lh)
    size, fnt, pad, lines, lh = chosen
    total = len(lines) * lh
    y = y0 + ((y1 - y0) - total) // 2
    space = d.textlength(" ", font=fnt)
    for line, lw in lines:
        x = cx - lw / 2
        for i, (t, w) in enumerate(line):
            if i and not t["glue"]:
                x += space
            if t["accent"]:
                d.rounded_rectangle([x, y + 2, x + w, y + lh - 2], radius=size // 5, fill=tuple(accent) + (255,))
                d.text((x + pad, y + (lh - size) / 2 - size * 0.08), t["text"], font=fnt, fill=(255, 255, 255, 255),
                       stroke_width=1, stroke_fill=(255, 255, 255, 255))
            else:
                d.text((x, y + (lh - size) / 2 - size * 0.08), t["text"], font=fnt, fill=tuple(ink) + (255,),
                       stroke_width=1, stroke_fill=tuple(ink) + (255,))
            x += w
        y += lh


def draw_chips(d, services, y_top, chip_line, chip_text, cx=CX, max_w=W - 140):
    if not services:
        return
    fsize, pad_x, chip_h, gap = 28, 18, 46, 12
    while True:
        chip_font = font(FONT_REG, fsize)
        widths = [int(d.textlength(s, font=chip_font)) + 2 * pad_x for s in services]
        total = sum(widths) + gap * (len(services) - 1)
        if total <= max_w or fsize <= 18:
            break
        fsize -= 1
        pad_x = max(10, round(fsize * 0.62))
        chip_h = round(fsize * 1.65)
    x = cx - total / 2
    for s, w in zip(services, widths):
        d.rounded_rectangle([x, y_top, x + w, y_top + chip_h], radius=chip_h // 2,
                            outline=tuple(chip_line) + (255,), width=2)
        tw = d.textlength(s, font=chip_font)
        d.text((x + (w - tw) / 2, y_top + (chip_h - fsize) / 2 - 3), s, font=chip_font, fill=tuple(chip_text) + (255,))
        x += w + gap


# ---------- thương hiệu ----------
def load_brand(name: str) -> dict:
    for p in (SKILL / "assets" / "brand" / "brands.json", SKILL / "assets" / "brands.example.json"):
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            if name in data:
                b = data[name]
                b["logo_path"] = str((SKILL / b["logo"]) if not Path(b["logo"]).is_absolute() else Path(b["logo"]))
                return b
    raise SystemExit(f"[loi] khong tim thay thuong hieu '{name}' trong assets/brand/brands.json")


def _logo(brand, height=None):
    logo = Image.open(brand["logo_path"]).convert("RGBA")
    lh = height or brand.get("logo_height", 78)
    lw = round(logo.width * lh / logo.height)
    return logo.resize((lw, lh), Image.LANCZOS)


# ---------- lớp phủ video ----------
def draw_overlay(brand: dict, hook: str, bg, out_png: Path):
    """PNG 1080x1920: đầu video + hook + dải thương hiệu; cửa sổ hình vẽ để trong suốt."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    band, accent = tuple(brand["band"]), tuple(brand["accent"])
    style = brand.get("header_style", "band")
    logo = _logo(brand, 84 if style == "band" else 78)
    if style == "plain":
        d.rectangle([0, 0, W, HEADER_H], fill=tuple(brand["header_bg"]) + (255,))
        d.rectangle([0, HEADER_H - 8, W, HEADER_H], fill=band + (255,))
        img.alpha_composite(logo, (CX - logo.width // 2, 136))
    elif style == "pill":
        d.rectangle([0, 0, W, HEADER_H], fill=band + (255,))
        d.rectangle([0, HEADER_H - 6, W, HEADER_H], fill=tuple(brand["chip_line"]) + (255,))
        pw, ph = logo.width + 80, logo.height + 28
        py = 120 + (HEADER_H - 6 - 120 - ph) // 2
        d.rounded_rectangle([CX - pw // 2, py, CX + pw // 2, py + ph], radius=ph // 2,
                            fill=tuple(brand["header_bg"]) + (255,))
        img.alpha_composite(logo, (CX - logo.width // 2, py + 14))
    else:  # band: dải màu thương hiệu phía trên (nơi TikTok đặt thanh tab) + dải kem chứa logo
        d.rectangle([0, 0, W, TOP_BAND_H], fill=band + (255,))
        d.rectangle([0, TOP_BAND_H, W, HEADER_H], fill=tuple(brand["header_bg"]) + (255,))
        d.rectangle([0, TOP_BAND_H, W, TOP_BAND_H + 5], fill=tuple(brand["chip_line"]) + (255,))
        d.rectangle([0, HEADER_H - 6, W, HEADER_H], fill=band + (255,))
        img.alpha_composite(logo, (CX - logo.width // 2, TOP_BAND_H + 5 + (HEADER_H - 6 - TOP_BAND_H - 5 - logo.height) // 2))
    d.rectangle([0, HEADER_H, W, WIN_Y], fill=tuple(bg) + (255,))
    draw_hook(d, hook, (SAFE_X0 + 10, HOOK_Y0, SAFE_X1 - 10, HOOK_Y1), accent, cx=CX)
    d.rectangle([0, BAND_Y, W, H], fill=band + (255,))
    d.rectangle([0, BAND_Y, W, BAND_Y + 6], fill=tuple(brand["chip_line"]) + (255,))
    draw_chips(d, brand.get("services", []), BAND_Y + 20, brand["chip_line"], brand["chip_text"])
    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)


# ---------- cửa sổ hình vẽ ----------
def window_params(ann_path: Path):
    """Từ annotation của một cảnh: (y0, ch, s) = vùng cắt trong ảnh nguồn và tỉ lệ thu nhỏ."""
    d = json.loads(Path(ann_path).read_text(encoding="utf-8"))
    regs = [e["region"] for e in d["elements"]]
    top = min(r["y"] for r in regs) - 36
    bot = max(r["y"] + r["height"] for r in regs) + 36
    span = max(bot - top, 600)
    s = min(0.90, WIN_H / span)
    ch = round(WIN_H / s)
    y0 = round(top - (ch - (bot - top)) / 2)
    y0 = max(0, min(y0, H - ch))
    return y0, ch, s


def window_filter(y0, ch, s, bg_hex):
    sw = 2 * round(1080 * s / 2)
    sh = min(WIN_H, 2 * round(ch * s / 2))
    px = max(0, (1080 - sw) // 2 + (CX - 540))
    py = (WIN_H - sh) // 2
    return (f"crop=1080:{ch}:0:{y0},scale={sw}:{sh}:flags=lanczos,"
            f"pad=1080:{WIN_H}:{px}:{py}:color=0x{bg_hex}")


# ---------- phụ đề .ass ----------
def ass_header(sub: dict) -> str:
    def bgr(c, alpha=0):
        return "&H%02X%02X%02X%02X" % (alpha, c[2], c[1], c[0])
    primary, box = sub["text"], sub["box"]
    size = sub.get("size", 54)
    outline = sub.get("outline", 14)
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{size},{bgr(primary)},{bgr(primary)},{bgr(box, sub.get('alpha', 0x26))},{bgr(box, sub.get('alpha', 0x26))},-1,0,0,0,100,100,0,0,3,{outline},0,2,{SAFE_X0 + 10},{W - SAFE_X1 + 10},{H - SUB_BOTTOM - 4},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


# ---------- ảnh bìa ----------
def make_thumbnail(brand: dict, hook: str, bg, scene_png: Path, ann_path: Path, out_jpg: Path):
    """Ảnh bìa 1080x1920 cho TikTok / YouTube Shorts: hook to + hình minh hoạ + dải thương hiệu."""
    img = Image.new("RGBA", (W, H), tuple(bg) + (255,))
    d = ImageDraw.Draw(img)
    band, accent = tuple(brand["band"]), tuple(brand["accent"])
    d.rectangle([0, 0, W, 64], fill=band + (255,))
    d.rectangle([0, 64, W, 200], fill=tuple(brand["header_bg"]) + (255,))
    d.rectangle([0, 64, W, 69], fill=tuple(brand["chip_line"]) + (255,))
    d.rectangle([0, 192, W, 200], fill=band + (255,))
    logo = _logo(brand, 84)
    img.alpha_composite(logo, ((W - logo.width) // 2, 69 + (192 - 69 - logo.height) // 2))
    # hook nằm trọn vùng giữa để không bị cắt khi lưới hồ sơ hiển thị tỉ lệ 3:4
    draw_hook(d, hook, (60, 250, W - 60, 900), accent, max_size=150, min_size=84, max_lines=4, cx=W // 2)
    # hình minh hoạ: đối tượng đầu tiên của cảnh mở đầu, hoà nền giấy vào nền bìa
    import numpy as np
    ann = json.loads(Path(ann_path).read_text(encoding="utf-8"))
    r = ann["elements"][0]["region"]
    x0, y0 = max(0, r["x"] - 24), max(0, r["y"] - 24)
    x1, y1 = min(W, r["x"] + r["width"] + 24), min(H, r["y"] + r["height"] + 24)
    art = Image.open(scene_png).convert("RGB").crop((x0, y0, x1, y1))
    arr = np.asarray(art).astype(np.float32)
    corners = np.array([arr[2, 2], arr[2, -3], arr[-3, 2], arr[-3, -3]])
    paper = np.median(corners, axis=0)
    arr = np.clip(arr / np.maximum(paper, 1), 0, 1) * np.array(bg, dtype=np.float32)
    art = Image.fromarray(arr.astype(np.uint8))
    box_w, box_h = W - 160, 640
    s = min(box_w / art.width, box_h / art.height)
    art = art.resize((round(art.width * s), round(art.height * s)), Image.LANCZOS)
    ay = 940 + (box_h - art.height) // 2
    img.paste(art, ((W - art.width) // 2, ay))
    d.rectangle([0, 1640, W, H], fill=band + (255,))
    d.rectangle([0, 1640, W, 1646], fill=tuple(brand["chip_line"]) + (255,))
    draw_chips(d, brand.get("services", []), 1690, brand["chip_line"], brand["chip_text"], cx=W // 2)
    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out_jpg, quality=92)
