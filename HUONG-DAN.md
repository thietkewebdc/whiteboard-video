# Hướng dẫn: Tạo video vẽ tay (whiteboard) + giọng đọc tiếng Việt offline

Bộ đôi công cụ:

1. **whiteboard-video** — Skill cho Claude Code/Claude app: biến **một chủ đề, một kịch bản, hoặc file phụ đề `.srt`** thành video vẽ tay bảng trắng hoàn chỉnh (có giọng đọc + phụ đề). Hỗ trợ cả video dọc 9:16 cho TikTok/Reels.
   → https://github.com/thietkewebdc/whiteboard-video
2. **VieNeu-TTS** — Giọng đọc tiếng Việt chạy **offline** trên máy (miễn phí), nhiều giọng dựng sẵn, hoặc clone giọng từ clip 3–8s. (Fork từ tác giả gốc [pnnbao97/VieNeu-TTS](https://github.com/pnnbao97/VieNeu-TTS).)
   → https://github.com/thietkewebdc/VieNeu-TTS

> Hướng dẫn này viết cho **macOS**. Windows/Linux làm tương tự (đổi vài lệnh).

---

## 0. Chuẩn bị (cài 1 lần)

Cần có:

- **Claude Code** (hoặc Claude desktop app có hỗ trợ Skills) — đây là nơi "chạy" skill.
- **Python 3** (bản 3.10+). Kiểm tra: `python3 --version`
- **ffmpeg** — để dựng/ghép video. Kiểm tra: `ffmpeg -version`. Chưa có thì cài qua Homebrew: `brew install ffmpeg`
- **Google Chrome** — dùng khi cần (ví dụ xuất ảnh SVG, hoặc mở trang chỉnh vùng).
- **uv** — trình quản lý Python siêu nhanh, để chạy VieNeu-TTS:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- *(Tuỳ chọn)* **OpenAI API key** nếu muốn tạo ảnh nét vẽ bằng AI (`gpt-image`). Lấy ở https://platform.openai.com/api-keys — **lưu ý: đây là API trả phí theo dùng, KHÁC gói ChatGPT Plus** (Plus không dùng lập trình được).

---

## 1. Cài VieNeu-TTS (giọng đọc offline)

```bash
git clone https://github.com/thietkewebdc/VieNeu-TTS.git
cd VieNeu-TTS
uv sync
```

`uv sync` tạo môi trường `.venv` và cài thư viện. **Lần chạy đầu sẽ tự tải model (vài trăm MB), chờ một chút.**

**Thử giọng bằng giao diện web:**

```bash
uv run vieneu-web
```

Mở trình duyệt vào `http://127.0.0.1:7860`, gõ chữ, chọn giọng và nghe thử.

**Các giọng dựng sẵn** (v3 Turbo, 48kHz):

| Nam | Nữ |
|---|---|
| Minh Đức (Bắc, tin tức) | Trúc Ly (Bắc, tự nhiên) |
| Phạm Tuyên (Bắc, tự nhiên) | Đoan Trang (Bắc, tự nhiên) |
| Thanh Bình (Bắc, kể chuyện) | Ngọc Linh (Bắc, kể chuyện) |
| Minh Triết (Nam, tin tức) | Mai Anh (Bắc, tin tức) |
| Xuân Vĩnh / Thái Sơn (Nam) | Thục Đoan / Thùy Dung (Nam) |
| Quang Sơn (Trung) | Ngọc Trân (Trung) |

> Ghi lại **đường dẫn tuyệt đối** tới thư mục này (ví dụ `/Users/<tên-bạn>/code/VieNeu-TTS`) — lát nữa điền vào `.env` của skill (`VIENEU_ROOT`).

---

## 2. Cài Skill whiteboard-video

Clone thẳng vào thư mục skills của Claude Code:

```bash
git clone https://github.com/thietkewebdc/whiteboard-video.git ~/.claude/skills/whiteboard-video
cd ~/.claude/skills/whiteboard-video
```

**Tạo môi trường render:**

```bash
python3 scripts/prepare_env.py
```

(Tạo `.venv` và cài opencv-python, numpy, av, Pillow, edge-tts.)

**Tạo file cấu hình `.env`:**

```bash
cp .env.example .env
```

Mở `.env` và điền (tuỳ nhu cầu):

```ini
# Dùng giọng VieNeu offline
TTS_PROVIDER=vieneu
TTS_VOICE=Minh Đức
VIENEU_ROOT=/Users/<tên-bạn>/code/VieNeu-TTS

# Nếu muốn tạo ảnh bằng AI OpenAI (tuỳ chọn)
OPENAI_API_KEY=sk-...
```

> `.env` đã nằm trong `.gitignore` — **không bao giờ commit/gửi file này đi** vì chứa API key.

---

## 3. Cách dùng (trong Claude Code / Claude app)

Mở Claude Code tại thư mục bất kỳ, rồi **nói bằng tiếng Việt**, ví dụ:

- *"Làm video whiteboard về chủ đề: [chủ đề của bạn]"*
- *"Biến file SRT này thành video vẽ tay"* (đính kèm `.srt`)
- *"Từ link bài viết này làm video giới thiệu 2 phút, giọng nữ Trúc Ly"*
- *"Làm bản dọc 9:16 cho TikTok"*

Claude sẽ tự chạy quy trình, dừng lại ở các mốc để bạn duyệt (hoặc bạn bảo **"chạy full"** để làm một mạch):

```
Chủ đề → viết kịch bản → giọng đọc + phụ đề (SRT) → phân cảnh
      → tạo ảnh nét vẽ → chia vùng → render nét bút → ghép cảnh → gắn phụ đề + giọng
```

**Chọn nguồn giọng** (đặt trong `.env` hoặc nói trực tiếp):
- `vieneu` — offline, miễn phí, chất lượng cao (khuyên dùng)
- `edge` — Microsoft Edge TTS, online, miễn phí
- `vbee` — trả phí (cần key Vbee)

**Chọn nguồn ảnh:**
- OpenAI `gpt-image` — đẹp, cần `OPENAI_API_KEY` (vài cent/ảnh)
- Tự vẽ SVG line-art bằng Chrome — miễn phí, nét icon tối giản

**Video dọc 9:16 (TikTok):** tạo ảnh `1024x1536` → pad lên `1080x1920` nền kem; render thêm `--cap-long-edge 1920`.

---

## 4. Mẹo & khắc phục lỗi thường gặp

- **Lần đầu dùng VieNeu chậm** vì tải model — các lần sau nhanh (giọng từng câu được cache trong `tts-cache/`).
- **ChatGPT Plus không thay được API key** — muốn tạo ảnh bằng tài khoản OpenAI của mình thì phải tạo **API key** riêng ở platform.openai.com (trả phí theo dùng).
- **Phụ đề video dọc 9:16 bị mất/chữ quá to**: do filter `subtitles` của ffmpeg mặc định PlayRes 384×288. Phải burn phụ đề qua file `.ass` có khai báo `PlayResX: 1080 / PlayResY: 1920` (skill đã xử lý sẵn khi làm video dọc).
- **`ffmpeg: command not found`**: cài `brew install ffmpeg`.
- **VieNeu báo "Voice not found"**: gõ đúng tên giọng (có dấu), ví dụ `Minh Đức`, `Trúc Ly`.

---

## 5. Link

- Skill tạo video: https://github.com/thietkewebdc/whiteboard-video
- Giọng VieNeu-TTS: https://github.com/thietkewebdc/VieNeu-TTS
- Tác giả gốc VieNeu-TTS (Phạm Nguyễn Ngọc Bảo): https://github.com/pnnbao97/VieNeu-TTS

Chúc bạn làm video vui! 🎬
