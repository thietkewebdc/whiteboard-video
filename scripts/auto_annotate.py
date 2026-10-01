#!/usr/bin/env python3
"""Tự tạo annotation cho video dọc 9:16 từ ảnh xếp theo các dải ngang (band) và input.srt.

Dùng khi mỗi ảnh có vài nhóm đối tượng xếp từ trên xuống dưới, cách nhau bằng khoảng trống:
  - Pad ảnh về 1080x1920 nền kem (nếu chưa đúng cỡ).
  - Phát hiện các dải ngang chứa nét vẽ, mỗi dải thành một vùng (region) theo thứ tự trên → dưới.
  - Gắn mốc thời gian từ input.srt cho từng vùng và ghi <ảnh>.annotation.json.
  - Xuất ảnh kiểm tra (check montage) để xem nhanh.

plan.json (đặt trong thư mục dự án):
{
  "scenes": [
    {"image": "scene-01-x.png", "cues": [1, 6],
     "bands": [ {"label": "...", "role": "...", "cues": [1, 3]},
                {"label": "...", "role": "...", "cues": [4, 6]} ]}
  ]
}
cues = chỉ số câu (bắt đầu từ 1) trong input.srt, đóng hai đầu.
Thứ tự trong "bands" là thứ tự VẼ (theo lời đọc). Thêm "band": N (0 = dải trên cùng) vào một mục
nếu thứ tự vẽ khác thứ tự trên → dưới của ảnh.

Dùng:  python auto_annotate.py <thư-mục-dự-án>
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

CREAM = (245, 235, 215)
W, H = 1080, 1920
GAP_MERGE = 90      # khe dọc nhỏ hơn mức này coi là cùng một dải
PAD = 14            # đệm quanh vùng
MIN_ROW_INK = 4     # số pixel nét tối thiểu để một hàng tính là có nét


def parse_srt(path: Path):
    cues = []
    for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8-sig").strip()):
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        m = re.match(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", lines[1])
        if not m:
            continue
        g = list(map(int, m.groups()))
        s = ((g[0] * 60 + g[1]) * 60 + g[2]) * 1000 + g[3]
        e = ((g[4] * 60 + g[5]) * 60 + g[6]) * 1000 + g[7]
        cues.append({"index": int(lines[0]), "start": s, "end": e, "text": " ".join(lines[2:]).strip()})
    return cues


def pad_to_canvas(path: Path) -> Image.Image:
    im = Image.open(path).convert("RGB")
    if im.size != (W, H):
        canvas = Image.new("RGB", (W, H), CREAM)
        canvas.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
        canvas.save(path)
        im = canvas
    return im


def detect_bands(im: Image.Image, expected: int):
    """Thử ngưỡng gộp khe từ lớn đến nhỏ cho tới khi số dải khớp kế hoạch."""
    boxes = []
    for gap in (GAP_MERGE, 60, 40, 25):
        boxes = _detect_bands(im, expected, gap)
        if len(boxes) == expected:
            return boxes
    return boxes


def _detect_bands(im: Image.Image, expected: int, gap_merge: int):
    arr = np.asarray(im).astype(np.int16)
    bg = np.median(arr.reshape(-1, 3), axis=0)
    dist = np.sqrt(((arr - bg) ** 2).sum(axis=2))
    mask = dist > 50
    rows = mask.sum(axis=1) >= MIN_ROW_INK
    segs, start = [], None
    for y, v in enumerate(rows):
        if v and start is None:
            start = y
        if not v and start is not None:
            segs.append([start, y - 1])
            start = None
    if start is not None:
        segs.append([start, len(rows) - 1])
    # gộp khe nhỏ
    merged = []
    for s in segs:
        if merged and s[0] - merged[-1][1] < gap_merge:
            merged[-1][1] = s[1]
        else:
            merged.append(s)
    # bỏ dải quá mỏng (nhiễu)
    merged = [s for s in merged if s[1] - s[0] > 25]
    # nếu thừa dải thì gộp khe nhỏ nhất cho tới khi đủ
    while len(merged) > expected:
        gaps = [merged[i + 1][0] - merged[i][1] for i in range(len(merged) - 1)]
        i = int(np.argmin(gaps))
        merged[i][1] = merged[i + 1][1]
        del merged[i + 1]
    boxes = []
    for y0, y1 in merged:
        cols = np.where(mask[y0:y1 + 1].sum(axis=0) >= 2)[0]
        if len(cols) == 0:
            continue
        boxes.append((int(cols.min()), int(y0), int(cols.max()), int(y1)))
    return boxes


def narration_ms(proj: Path, last_end: int) -> int:
    m4a = proj / "narration.m4a"
    if m4a.exists():
        try:
            out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                           "-of", "default=nw=1:nk=1", str(m4a)], text=True)
            return int(float(out.strip()) * 1000)
        except Exception:
            pass
    return last_end + 600


def main(proj_dir: str) -> int:
    proj = Path(proj_dir)
    plan = json.loads((proj / "plan.json").read_text(encoding="utf-8"))
    cues = {c["index"]: c for c in parse_srt(proj / "input.srt")}
    scenes = plan["scenes"]
    total_ms = narration_ms(proj, max(c["end"] for c in cues.values()))
    problems = 0
    thumbs = []

    for si, sc in enumerate(scenes):
        img_path = proj / sc["image"]
        im = pad_to_canvas(img_path)
        bands = sc["bands"]
        boxes = detect_bands(im, len(bands))
        if len(boxes) != len(bands):
            print(f"[!] {sc['image']}: phát hiện {len(boxes)} dải, kế hoạch cần {len(bands)} — kiểm tra ảnh.")
            problems += 1
            continue
        s_start = cues[sc["cues"][0]]["start"]
        s_end = cues[scenes[si + 1]["cues"][0]]["start"] if si + 1 < len(scenes) else total_ms
        scene_ms = s_end - s_start

        starts = []
        for b in bands:
            starts.append(max(500, cues[b["cues"][0]]["start"] - s_start))
        elements = []
        for bi, b in enumerate(bands):
            # "band" (tuỳ chọn) = vị trí dải từ trên xuống (0 là trên cùng); mặc định theo thứ tự khai báo
            x0, y0, x1, y1 = boxes[b.get("band", bi)]
            x0, y0 = max(0, x0 - PAD), max(0, y0 - PAD)
            x1, y1 = min(W - 1, x1 + PAD), min(H - 1, y1 + PAD)
            st = starts[bi]
            end = (starts[bi + 1] - 250) if bi + 1 < len(bands) else (cues[b["cues"][1]]["end"] - s_start)
            end = max(end, st + 1800)
            sub = " ".join(cues[i]["text"] for i in range(b["cues"][0], b["cues"][1] + 1))
            cx = (x0 + x1) // 2
            elements.append({
                "id": f"band-{bi + 1}", "label": b["label"], "sequence": bi + 1,
                "narrativeRole": b["role"], "type": "object", "subtitle": sub,
                "region": {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0},
                "reveal": {"direction": "top_to_bottom", "startMs": st, "durationMs": end - st,
                           "maskPaddingPx": 0, "protectedRegions": []},
                "handPath": {"start": [cx, y0], "end": [cx, y1], "easing": "easeInOut"},
            })
        ann = {"sceneId": f"scene-{si + 1:02d}", "canvas": {"width": W, "height": H},
               "storyBasis": sc.get("story", ""), "sceneDurationMs": scene_ms, "elements": elements}
        (proj / (Path(sc["image"]).stem + ".annotation.json")).write_text(
            json.dumps(ann, ensure_ascii=False, indent=2), encoding="utf-8")

        # ảnh kiểm tra nhỏ
        chk = im.copy()
        d = ImageDraw.Draw(chk)
        colors = [(38, 103, 255), (255, 105, 92), (41, 167, 102), (181, 100, 255)]
        for e in elements:
            r = e["region"]
            c = colors[(e["sequence"] - 1) % 4]
            d.rectangle([r["x"], r["y"], r["x"] + r["width"], r["y"] + r["height"]], outline=c, width=8)
            d.ellipse([r["x"] + 6, r["y"] + 6, r["x"] + 70, r["y"] + 70], fill=c)
            d.text((r["x"] + 30, r["y"] + 28), str(e["sequence"]), fill="white")
        thumbs.append(chk.resize((W // 4, H // 4)))
        print(f"[ok] {sc['image']}: {len(elements)} vùng, cảnh {scene_ms / 1000:.1f}s")

    if thumbs:
        sheet = Image.new("RGB", (len(thumbs) * (W // 4 + 10) + 10, H // 4 + 20), (255, 255, 255))
        for i, t in enumerate(thumbs):
            sheet.paste(t, (10 + i * (W // 4 + 10), 10))
        sheet.save(proj / "_check.png")
        print(f"[ok] ảnh kiểm tra: {proj / '_check.png'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
