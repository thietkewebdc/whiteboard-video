#!/usr/bin/env python3
"""Tạo ảnh bằng OpenAI Images API (gpt-image-*), lưu PNG cục bộ.

Đọc OPENAI_API_KEY từ biến môi trường hoặc file .env ở thư mục gốc skill.
Không in key ra ngoài.

Ví dụ:
  python scripts/gen_openai_image.py --prompt "..." --out scene.png \
      --model gpt-image-2 --size 1536x1024 --quality medium
"""
import argparse
import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

API_URL = "https://api.openai.com/v1/images/generations"


def load_key() -> str:
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key.strip()
    # tìm .env đi lên từ thư mục script
    here = Path(__file__).resolve().parent.parent
    for base in [here, Path.cwd()]:
        env = base / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("OPENAI_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    print("[loi] Khong tim thay OPENAI_API_KEY (bien moi truong hoac .env).", file=sys.stderr)
    sys.exit(2)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="gpt-image-2")
    ap.add_argument("--size", default="1536x1024", help="1536x1024 | 1024x1024 | 1024x1536 | auto")
    ap.add_argument("--quality", default="medium", help="low | medium | high | auto")
    args = ap.parse_args()

    key = load_key()
    payload = {
        "model": args.model,
        "prompt": args.prompt,
        "size": args.size,
        "quality": args.quality,
        "n": 1,
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        print(f"[loi] HTTP {e.code}: {body[:500]}", file=sys.stderr)
        sys.exit(1)

    item = data["data"][0]
    b64 = item.get("b64_json")
    if not b64:
        print("[loi] Khong co b64_json trong phan hoi.", file=sys.stderr)
        sys.exit(1)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(b64))
    usage = data.get("usage", {})
    print(f"OUTPUT={out}")
    print(f"SIZE={args.size} MODEL={args.model} QUALITY={args.quality}")
    if usage:
        print(f"USAGE={json.dumps(usage)}")


if __name__ == "__main__":
    main()
