#!/usr/bin/env python3
"""Chạy BÊN TRONG .venv của VieNeu-TTS: nạp model một lần, tổng hợp hàng loạt câu ra WAV.

Đầu vào là một manifest JSON:
  { "voice": "Minh Đức", "ref_audio": null,
    "items": [ {"text": "...", "out": "/abs/cue-001-xxxx.wav"}, ... ] }
Nếu có "ref_audio" (đường dẫn clip 3-8s) thì clone giọng theo clip đó, bỏ qua "voice".
Chỉ tổng hợp những "out" chưa tồn tại (đóng vai trò cache).
"""
import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    args = ap.parse_args()

    m = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    voice = (m.get("voice") or "").strip() or None
    ref = (m.get("ref_audio") or "").strip() or None
    items = m["items"]
    todo = [it for it in items if not Path(it["out"]).exists()]
    if not todo:
        print("  VieNeu: không có câu nào cần tổng hợp")
        return 0

    from vieneu import Vieneu
    v = Vieneu()

    for i, it in enumerate(todo, 1):
        kwargs = {}
        if ref:
            kwargs["ref_audio"] = ref
        elif voice:
            kwargs["voice"] = voice
        audio = v.infer(it["text"], **kwargs)
        out = Path(it["out"])
        out.parent.mkdir(parents=True, exist_ok=True)
        v.save(audio, str(out))
        print(f"  VieNeu {i:>2}/{len(todo)} -> {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
