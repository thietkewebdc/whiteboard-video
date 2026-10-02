#!/usr/bin/env python3
"""Hoàn thiện video NGANG 16:9 (YouTube): render cảnh → ghép → phụ đề vàng trên nền đậm → ghép giọng → ảnh bìa 1280x720.

Dự án cần: plan.json, scene-XX.png + .annotation.json (auto_annotate với "layout": "landscape"),
input.srt, narration.m4a, meta.json {"hook": "...[TỪ KHÓA]..."}.
Đầu ra (mặc định ~/Documents/code/video-xuat/lich-su/): <slug>.mp4, <slug>-thumbnail.jpg.

Dùng: python finish_landscape.py <thư-mục-dự-án> [--export-dir DIR] [--jobs 2] [--accent R,G,B] [--tag "LỊCH SỬ THẾ GIỚI"]
"""
import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import social_layout as sl  # noqa: E402

SKILL = Path(__file__).resolve().parent.parent
PY = str(SKILL / ".venv/bin/python")
HAND = SKILL / "assets/drawing-hand.png"
CREAM = (245, 235, 215)


def render_scene(proj: Path, image: str) -> Path:
    stem = Path(image).stem
    out = proj / f"{stem}-whiteboard.mp4"
    if out.exists():
        print(f"  (bỏ qua, đã có) {out.name}", flush=True)
        return out
    cmd = [PY, str(SKILL / "scripts/render_stream_whiteboard.py"), str(proj / image),
           str(proj / f"{stem}.annotation.json"), str(out), str(HAND), "--cap-long-edge", "1920"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError(f"render lỗi {image}:\n{r.stderr[-800:]}")
    print(f"  render xong {out.name}", flush=True)
    return out


def _ts(ms: int) -> str:
    cs = ms // 10
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def srt_to_ass(srt: Path, out: Path):
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 0\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
            "MarginL, MarginR, MarginV, Encoding\n"
            "Style: Default,Arial,54,&H0000E5FF,&H0000E5FF,&H00221E1E,&H00000000,-1,0,0,0,100,100,0,0,3,10,0,2,160,160,56,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    lines = []
    for block in re.split(r"\n\s*\n", srt.read_text(encoding="utf-8-sig").strip()):
        p = block.strip().splitlines()
        m = re.match(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", p[1]) if len(p) >= 3 else None
        if not m:
            continue
        g = list(map(int, m.groups()))
        s = ((g[0] * 60 + g[1]) * 60 + g[2]) * 1000 + g[3]
        e = ((g[4] * 60 + g[5]) * 60 + g[6]) * 1000 + g[7]
        lines.append(f"Dialogue: 0,{_ts(s)},{_ts(e)},Default,,0,0,0,,{' '.join(p[2:]).strip()}")
    out.write_text(head + "\n".join(lines) + "\n", encoding="utf-8")


def _normalize_paper(im: Image.Image) -> Image.Image:
    arr = np.asarray(im.convert("RGB")).astype(np.float32)
    bg = np.median(arr.reshape(-1, 3), axis=0)
    arr = np.clip(arr * (np.array(CREAM, dtype=np.float32) / bg), 0, 255)
    return Image.fromarray(arr.astype(np.uint8))


def make_thumbnail(proj: Path, plan: dict, hook: str, accent, tag: str, out_jpg: Path):
    W, H = 1280, 720
    img = proj / plan["scenes"][0]["image"]
    ann = json.loads((proj / (img.stem + ".annotation.json")).read_text(encoding="utf-8"))
    r = ann["elements"][-1]["region"]          # đối tượng chính thường là nhân vật ở cột cuối của cảnh mở đầu
    pad = 24
    im = Image.open(img).convert("RGB")
    crop = im.crop((r["x"] + 40, max(0, r["y"] - pad),
                    min(im.width, r["x"] + r["width"] + pad), min(im.height, r["y"] + r["height"] + pad)))
    crop = _normalize_paper(crop)
    scale = min(560 / crop.width, 620 / crop.height)
    crop = crop.resize((int(crop.width * scale), int(crop.height * scale)), Image.LANCZOS)
    canvas = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, W, 14], fill=accent)
    d.rectangle([0, H - 14, W, H], fill=accent)
    canvas.paste(crop, (W - crop.width - 50, (H - crop.height) // 2))
    f = sl.font(sl.FONT_BOLD, 34)
    tw = d.textlength(tag, font=f)
    d.rounded_rectangle([60, 56, 60 + tw + 40, 56 + 62], radius=10, fill=accent)
    d.text((80, 64), tag, font=f, fill=(255, 255, 255))
    sl.draw_hook(d, hook, (60, 150, W - crop.width - 110, H - 60), accent, max_size=112, min_size=60, max_lines=4,
                 cx=None)
    canvas.save(out_jpg, quality=92)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--export-dir", default=str(Path.home() / "Documents/code/video-xuat/lich-su"))
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--accent", default="196,24,24")
    ap.add_argument("--tag", default="LỊCH SỬ THẾ GIỚI")
    ap.add_argument("--thumb-only", action="store_true")
    ap.add_argument("--music", help="file nhạc nền (mp3/wav); tự hạ nhỏ khi có giọng (sidechain) và nhỏ dần ở cuối")
    ap.add_argument("--music-gain", type=float, default=0.55, help="độ lớn nhạc so với bản gốc (mặc định 0.55)")
    a = ap.parse_args()
    proj = Path(a.project).resolve()
    plan = json.loads((proj / "plan.json").read_text(encoding="utf-8"))
    meta = json.loads((proj / "meta.json").read_text(encoding="utf-8"))
    hook = meta["hook"]
    slug = sl.slugify(sl.strip_markup(hook))
    accent = tuple(int(x) for x in a.accent.split(","))
    export = Path(a.export_dir)
    export.mkdir(parents=True, exist_ok=True)

    thumb = export / f"{slug}-thumbnail.jpg"
    make_thumbnail(proj, plan, hook, accent, a.tag, thumb)
    print(f"THUMB={thumb}", flush=True)
    if a.thumb_only:
        return

    images = [s["image"] for s in plan["scenes"]]
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        clips = list(ex.map(lambda im: render_scene(proj, im), images))
    final = proj / "final.mp4"
    subprocess.run([PY, str(SKILL / "scripts/merge_scenes.py"), "--inputs", *map(str, clips), "--output", str(final)],
                   check=True, capture_output=True)
    ass = proj / "input.ass"
    srt_to_ass(proj / "input.srt", ass)
    out = export / f"{slug}.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(final), "-i", str(proj / "narration.m4a")]
    if a.music:
        cmd += ["-i", str(Path(a.music).resolve())]
        fc = (f"[1:a]asplit=2[v][vsc];[2:a]volume={a.music_gain}[m];"
              "[m][vsc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=450[md];"
              "[v][md]amix=inputs=2:duration=first:normalize=0,afade=t=out:st=%s:d=3[aout]")
        dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                             "default=nw=1:nk=1", str(proj / "narration.m4a")], text=True))
        cmd += ["-filter_complex", fc % max(0, dur - 3), "-map", "0:v:0", "-map", "[aout]"]
    else:
        cmd += ["-map", "0:v:0", "-map", "1:a:0"]
    subprocess.run(cmd + ["-vf", f"subtitles={ass.name}", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
                          "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)],
                   check=True, cwd=str(proj))
    print(f"OUTPUT={out}")


if __name__ == "__main__":
    main()
