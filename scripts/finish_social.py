#!/usr/bin/env python3
"""Hoàn thiện video dọc 9:16 theo chuẩn mạng xã hội (TikTok / Reels / YouTube Shorts).

Làm gì: render các cảnh (nếu chưa có) → đặt hình vẽ vào cửa sổ an toàn → ghép → phủ lớp thương hiệu
(logo, hook, dải dịch vụ) → phụ đề .ass màu nổi → ghép giọng → làm ảnh bìa → xuất gói đăng bài.
Tên file xuất = slug không dấu của tiêu đề hook, ví dụ: wordpress-vua-va-lo-hong-nghiem-trong.mp4

Cần trong thư mục dự án: plan.json, <ảnh>.png + <ảnh>.annotation.json, input.srt, narration.m4a, meta.json
meta.json: {"brand": "dc", "hook": "WordPress vừa vá lỗ hổng [NGHIÊM TRỌNG]!", "date": "2/10"}
  - [chữ] trong hook được nhấn bằng ô màu.

Dùng:  python finish_social.py <thư-mục-dự-án> [--export-dir DIR] [--jobs 2] [--preview 14] [--sub-style box|yellow]
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import social_layout as sl  # noqa: E402
from finish_vertical import render_scene  # noqa: E402

PY = sys.executable
DEFAULT_EXPORT = Path.home() / "Documents" / "code" / "video-xuat"


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"lenh loi: {' '.join(map(str, cmd))[:200]}\n{r.stderr[-800:]}")
    return r


def paper_color(clip: Path, tmp: Path):
    """Lấy màu giấy thật từ khung đầu của cảnh để các mép hoà liền nhau."""
    from PIL import Image
    png = tmp / "_bg.png"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(clip), "-frames:v", "1", str(png)])
    im = Image.open(png).convert("RGB")
    pts = [(6, 6), (1070, 6), (6, 1900), (1070, 1900), (6, 960), (1070, 960)]
    px = sorted(im.getpixel(p) for p in pts)
    return px[len(px) // 2]


def srt_to_ass(srt: Path, out: Path, sub: dict):
    def ts(ms):
        cs = ms // 10
        return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"
    lines = [sl.ass_header(sub)]
    for block in re.split(r"\n\s*\n", srt.read_text(encoding="utf-8-sig").strip()):
        p = block.strip().splitlines()
        if len(p) < 3:
            continue
        m = re.match(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", p[1])
        if not m:
            continue
        g = list(map(int, m.groups()))
        s = ((g[0] * 60 + g[1]) * 60 + g[2]) * 1000 + g[3]
        e = ((g[4] * 60 + g[5]) * 60 + g[6]) * 1000 + g[7]
        text = "\\N".join(p[2:]).replace("{", "(").replace("}", ")")
        lines.append(f"Dialogue: 0,{ts(s)},{ts(e)},Default,,0,0,0,,{text}\n")
    out.write_text("".join(lines), encoding="utf-8")


def youtube_block(hook_plain: str, post_text: str) -> str:
    cap = ""
    m = re.search(r"##\s*TIKTOK[^\n]*\n(.*?)(?=\n##\s|\Z)", post_text, re.S)
    if m:
        cap = "\n".join(l for l in m.group(1).strip().splitlines() if not l.strip().startswith("(Nhớ bật"))
    title = (hook_plain if len(hook_plain) <= 90 else hook_plain[:90].rsplit(" ", 1)[0]) + " #Shorts"
    return f"\n\n---\n\n## YOUTUBE SHORTS\nTiêu đề: {title}\n\nMô tả:\n{cap}\n#Shorts\n\n" \
           "Ảnh bìa: tải file -thumbnail.jpg lên YouTube Studio (máy tính), mục Shorts > Thumbnail.\n"


def export_package(proj: Path, meta: dict, final: Path, thumb: Path, export_dir: Path, slug: str):
    export_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(final, export_dir / f"{slug}.mp4")
    shutil.copy2(thumb, export_dir / f"{slug}-thumbnail.jpg")
    post = ""
    for name in ("bai-dang-3-kenh.md", "bai-dang.md"):
        if (proj / name).exists():
            post = (proj / name).read_text(encoding="utf-8")
            break
    head = [f"# {sl.strip_markup(meta['hook'])}", "",
            f"- Video: `{slug}.mp4`", f"- Ảnh bìa: `{slug}-thumbnail.jpg`"]
    if meta.get("date"):
        head.append(f"- Gợi ý ngày đăng: {meta['date']}")
    body = "\n".join(head) + "\n\n---\n\n" + post + youtube_block(sl.strip_markup(meta["hook"]), post)
    (export_dir / f"{slug}-noi-dung-dang.md").write_text(body, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--export-dir", default=None)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--preview", type=int, default=0, help="chỉ xuất N giây đầu để xem thử, không đóng gói")
    ap.add_argument("--reuse", action="store_true", help="dùng lại clip cửa sổ đã có (xem thử nhanh)")
    ap.add_argument("--sub-style", choices=["box", "yellow", "yellowbox"], default=None)
    a = ap.parse_args()

    proj = Path(a.project)
    meta = json.loads((proj / "meta.json").read_text(encoding="utf-8"))
    brand = sl.load_brand(meta["brand"])
    hook = meta["hook"]
    plan = json.loads((proj / "plan.json").read_text(encoding="utf-8"))
    images = [s["image"] for s in plan["scenes"]]
    slug = meta.get("slug") or sl.slugify(sl.strip_markup(hook))

    # 1) render các cảnh nếu chưa có
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        clips = list(ex.map(lambda im: render_scene(proj, im), images))

    tmp = proj / "_social"
    tmp.mkdir(exist_ok=True)
    bg = paper_color(clips[0], tmp)
    bg_hex = "%02X%02X%02X" % bg

    # 2) đặt từng cảnh vào cửa sổ an toàn (mỗi cảnh một mức thu phóng riêng)
    win_clips = []
    for im, clip in zip(images, clips):
        stem = Path(im).stem
        y0, ch, s = sl.window_params(proj / f"{stem}.annotation.json")
        out = tmp / f"{stem}-win.mp4"
        if a.reuse and out.exists():
            win_clips.append(out)
            continue
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(clip), "-vf", sl.window_filter(y0, ch, s, bg_hex),
             "-c:v", "libx264", "-crf", "16", "-preset", "fast", "-pix_fmt", "yuv420p", "-an", str(out)])
        win_clips.append(out)
        print(f"  cua so {stem}: ti le {s:.2f}", flush=True)

    merged = tmp / "merged-win.mp4"
    if not (a.reuse and merged.exists()):
        run([PY, str(HERE / "merge_scenes.py"), "--inputs", *map(str, win_clips), "--output", str(merged)])

    # 3) lớp thương hiệu + phụ đề
    overlay = tmp / "overlay.png"
    sl.draw_overlay(brand, hook, bg, overlay)
    sub = dict(brand.get("sub", {"text": [255, 255, 255], "box": brand["band"], "alpha": 38}))
    style = a.sub_style or meta.get("sub_style") or "yellowbox"
    if style == "yellow":
        sub.update({"text": [255, 224, 0], "box": [10, 10, 10], "alpha": 0x20})
    elif style == "yellowbox":
        sub.update({"text": [255, 224, 0], "box": brand["band"], "alpha": 0x26})
    ass = tmp / "input.ass"
    srt_to_ass(proj / "input.srt", ass, sub)

    # 4) ghép hình + lớp phủ + phụ đề + giọng trong một lượt
    name = slug
    final = proj / f"{name}.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(merged), "-i", str(overlay), "-i", str(proj / "narration.m4a"),
           "-filter_complex",
           f"[0:v]pad=1080:1920:0:{sl.WIN_Y}:color=0x{bg_hex}[b];[b][1:v]overlay=0:0:format=auto[c];[c]subtitles={ass}[out]",
           "-map", "[out]", "-map", "2:a:0", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart"]
    if a.preview:
        final = tmp / f"preview-{style}.mp4"
        cmd += ["-t", str(a.preview)]
    run(cmd + [str(final)])
    if a.preview:
        print(f"PREVIEW={final}")
        return

    # 5) ảnh bìa + gói đăng bài
    first_stem = Path(images[0]).stem
    thumb = proj / f"{name}-thumbnail.jpg"
    sl.make_thumbnail(brand, hook, bg, proj / images[0], proj / f"{first_stem}.annotation.json", thumb)
    export_dir = Path(a.export_dir) if a.export_dir else DEFAULT_EXPORT / brand.get("export_folder", meta["brand"])
    export_package(proj, meta, final, thumb, export_dir, slug)
    print(f"OUTPUT={export_dir / (slug + '.mp4')}")


if __name__ == "__main__":
    main()
