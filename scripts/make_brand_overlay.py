#!/usr/bin/env python3
"""Tạo lớp thương hiệu 1080x1920 (PNG trong suốt) để phủ lên video dọc 9:16.

- Thanh đầu video: nền kem sáng + logo ở giữa + đường viền xanh.
- Thanh cuối video: nền xanh thương hiệu + hotline, website, email, dịch vụ.
Phần giữa trong suốt nên không che hình vẽ.

Dùng:
  python make_brand_overlay.py --logo assets/brand/logo-main.png --out assets/brand/blue-sea-overlay.png \
      --hotline "0900 000 000" --website "example.com" --email "info@example.com" \
      --tagline "Vận tải biển FCL · LCL · Door-to-door"
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
TOP_H = 232
FOOT_H = 232
BRAND = (0, 80, 144)          # xanh chủ đạo của logo Blue Sea
BRAND_LIGHT = (96, 170, 224)
CHIP_TEXT = (222, 238, 250)
TOP_BG = (255, 251, 243)
FONT_BOLD = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf",
             "C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
FONT_REG = ["/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
            "C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


def font(cands, size):
    for p in cands:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def centered(draw, text, y, fnt, fill):
    w = draw.textlength(text, font=fnt)
    draw.text(((W - w) / 2, y), text, font=fnt, fill=fill)


def wrap_text(d, text, fnt, max_w):
    """Ngắt dòng theo từ cho vừa chiều rộng max_w."""
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if d.textlength(trial, font=fnt) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_title_and_chips(d, title, services, top):
    """Tiêu đề video (1 dòng nếu vừa, không thì 2 dòng) + hàng nhãn dịch vụ nhỏ bên dưới."""
    max_w = W - 120
    size = 64
    while size > 50 and d.textlength(title, font=font(FONT_BOLD, size)) > max_w:
        size -= 2
    fnt = font(FONT_BOLD, size)
    if d.textlength(title, font=fnt) <= max_w:
        lines = [title]
    else:
        size = 54
        fnt = font(FONT_BOLD, size)
        lines = wrap_text(d, title, fnt, max_w)[:2]
    line_h = int(size * 1.18)
    y = top + 26
    for ln in lines:
        centered(d, ln, y, fnt, (255, 255, 255))
        y += line_h
    if not services:
        return
    # thu nhỏ chữ nhãn cho tới khi cả hàng vừa trong khung (chừa lề 60px mỗi bên)
    fsize, pad_x, chip_h, gap = 28, 18, 46, 12
    while True:
        chip_font = font(FONT_REG, fsize)
        widths = [int(d.textlength(s, font=chip_font)) + 2 * pad_x for s in services]
        total = sum(widths) + gap * (len(services) - 1)
        if total <= W - 120 or fsize <= 20:
            break
        fsize -= 1
        pad_x = max(10, round(fsize * 0.62))
        chip_h = round(fsize * 1.65)
    x = (W - total) / 2
    y_chip = max(y + 12, top + FOOT_H - chip_h - 24)
    for s, w in zip(services, widths):
        d.rounded_rectangle([x, y_chip, x + w, y_chip + chip_h], radius=chip_h // 2,
                            outline=BRAND_LIGHT + (255,), width=2)
        tw = d.textlength(s, font=chip_font)
        d.text((x + (w - tw) / 2, y_chip + (chip_h - fsize) / 2 - 3), s, font=chip_font, fill=CHIP_TEXT)
        x += w + gap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", default="", help="tiêu đề video hiện ở thanh dưới (thay cho hotline/website/email)")
    ap.add_argument("--services", default="", help="các dịch vụ chính, cách nhau bằng dấu phẩy")
    ap.add_argument("--brand-color", default="0,80,144", help="màu nền thanh dưới R,G,B (mặc định xanh Blue Sea)")
    ap.add_argument("--accent-color", default="96,170,224", help="màu viền nhãn và vạch nhấn R,G,B")
    ap.add_argument("--chip-text-color", default="222,238,250", help="màu chữ trong nhãn dịch vụ R,G,B")
    ap.add_argument("--logo", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--hotline", default="")
    ap.add_argument("--website", default="")
    ap.add_argument("--email", default="")
    ap.add_argument("--tagline", default="")
    ap.add_argument("--logo-height", type=int, default=132)
    a = ap.parse_args()
    global BRAND, BRAND_LIGHT, CHIP_TEXT
    BRAND = tuple(int(x) for x in a.brand_color.split(","))
    BRAND_LIGHT = tuple(int(x) for x in a.accent_color.split(","))
    CHIP_TEXT = tuple(int(x) for x in a.chip_text_color.split(","))

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # --- thanh đầu ---
    d.rectangle([0, 0, W, TOP_H], fill=TOP_BG + (255,))
    d.rectangle([0, TOP_H - 8, W, TOP_H], fill=BRAND + (255,))
    logo = Image.open(a.logo).convert("RGBA")
    lh = a.logo_height
    lw = round(logo.width * lh / logo.height)
    logo = logo.resize((lw, lh), Image.LANCZOS)
    img.alpha_composite(logo, ((W - lw) // 2, 84))

    # --- thanh cuối ---
    top = H - FOOT_H
    d.rectangle([0, top, W, H], fill=BRAND + (255,))
    d.rectangle([0, top, W, top + 6], fill=BRAND_LIGHT + (255,))
    y = top + 30
    if a.title:
        draw_title_and_chips(d, a.title, [s.strip() for s in a.services.split(",") if s.strip()], top)
    if a.hotline and not a.title:
        centered(d, f"HOTLINE  {a.hotline}", y, font(FONT_BOLD, 72), (255, 255, 255))
        y += 94
    info = "   |   ".join(x for x in (a.website, a.email) if x)
    if info and not a.title:
        centered(d, info, y, font(FONT_REG, 40), (222, 238, 250))
        y += 54
    if a.tagline and not a.title:
        centered(d, a.tagline, y, font(FONT_REG, 34), (170, 205, 235))

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(f"OUTPUT={out}")


if __name__ == "__main__":
    main()
