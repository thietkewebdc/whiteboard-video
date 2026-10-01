#!/usr/bin/env python3
"""Hoàn thiện video dọc 9:16: render các cảnh → ghép → khắc phụ đề (.ass đúng PlayRes) → ghép giọng.

Dùng:  python finish_vertical.py <thư-mục-dự-án> <tên-video> [--jobs 2]
Cần trong thư mục dự án: plan.json, <ảnh>.png + <ảnh>.annotation.json, input.srt, narration.m4a
Kết quả: <tên-video>-final-sub-voice.mp4
"""
import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
PY = sys.executable
HAND = SKILL / "assets" / "drawing-hand.png"
DEFAULT_BRAND = SKILL / "assets" / "brand" / "blue-sea-overlay.png"

ASS_HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,52,&H00303030,&H00303030,&H20D7EBF5,&H20D7EBF5,-1,0,0,0,100,100,0,0,3,16,0,2,70,70,330,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def ts(ms: int) -> str:
    cs = ms // 10
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def srt_to_ass(srt: Path, out: Path):
    lines = [ASS_HEAD]
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("name")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--brand", help="PNG 1080x1920 trong suốt để phủ lên video (mặc định assets/brand/blue-sea-overlay.png)")
    ap.add_argument("--no-brand", action="store_true", help="không phủ lớp thương hiệu")
    a = ap.parse_args()
    proj = Path(a.project)
    plan = json.loads((proj / "plan.json").read_text(encoding="utf-8"))
    images = [s["image"] for s in plan["scenes"]]

    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        clips = list(ex.map(lambda im: render_scene(proj, im), images))

    final = proj / f"{a.name}-final.mp4"
    subprocess.run([PY, str(SKILL / "scripts/merge_scenes.py"), "--inputs", *map(str, clips),
                    "--output", str(final)], check=True, capture_output=True)
    ass = proj / "input.ass"
    srt_to_ass(proj / "input.srt", ass)
    sub = proj / f"{a.name}-final-sub.mp4"
    local = proj / "overlay.png"   # lớp thương hiệu riêng của video (có tiêu đề) được ưu tiên
    brand = None if a.no_brand else Path(a.brand) if a.brand else (local if local.exists() else DEFAULT_BRAND)
    if brand and brand.exists():
        # phủ lớp thương hiệu (logo đầu video, thanh thông tin cuối video) rồi mới khắc phụ đề lên trên
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(final), "-i", str(brand),
               "-filter_complex", f"[0:v][1:v]overlay=0:0[b];[b]subtitles={ass}[out]", "-map", "[out]"]
    else:
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(final), "-vf", f"subtitles={ass}"]
    subprocess.run(cmd + ["-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                          str(sub)], check=True)
    voiced = proj / f"{a.name}-final-sub-voice.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(sub), "-i", str(proj / "narration.m4a"),
                    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", "-movflags", "+faststart", str(voiced)], check=True)
    print(f"OUTPUT={voiced}")


if __name__ == "__main__":
    main()
