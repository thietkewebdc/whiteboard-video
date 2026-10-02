#!/usr/bin/env python3
"""Tự sáng tác nhạc nền "hào hùng" gốc (pad dàn dây + trống taiko) bằng numpy: KHÔNG dính bản quyền.

Giai điệu hợp âm Rê thứ (Dm - Bb - F - C), nhịp 72 bpm, trống vang dần theo thời gian, kết bằng một nhịp lớn.
Dùng:  python make_epic_music.py --duration 135 --out nhac.mp3 [--bpm 72] [--seed 7]
Cần numpy và ffmpeg (lọc low-pass + vang cho ấm).
"""
import argparse
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

SR = 44100
NOTE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def hz(name: str, octave: int) -> float:
    n = NOTE[name[0]] + (1 if "#" in name else 0) - (1 if "b" in name else 0)
    return 440.0 * 2 ** ((n + 12 * (octave + 1) - 69) / 12)


CHORDS = [  # (bass, [các nốt pad])
    ("D", [("D", 3), ("F", 3), ("A", 3), ("D", 4)]),
    ("Bb", [("Bb", 2), ("D", 3), ("F", 3), ("Bb", 3)]),
    ("F", [("F", 3), ("A", 3), ("C", 4), ("F", 4)]),
    ("C", [("C", 3), ("E", 3), ("G", 3), ("C", 4)]),
]


def saw(f, t, vib=None, harmonics=9):
    """Sóng răng cưa cộng hài; vib là độ lệch pha (rad) tạo rung nhẹ cho giống dàn dây."""
    out = np.zeros_like(t)
    vib = 0.0 if vib is None else vib
    for k in range(1, harmonics + 1):
        if f * k > 9000:
            break
        out += np.sin(2 * np.pi * f * k * t + k * vib) / k
    return out


def pad_note(f, dur, vibrato_phase):
    t = np.arange(int(dur * SR)) / SR
    vib = 0.012 * np.sin(2 * np.pi * 5.2 * t + vibrato_phase)
    sig = sum(saw(f * d, t, vib) for d in (0.996, 1.0, 1.004)) / 3
    att, rel = min(1.6, dur / 3), min(1.8, dur / 3)
    env = np.minimum(1, t / att) * np.minimum(1, (dur - t) / rel)
    return sig * env


def taiko(vol):
    t = np.arange(int(1.1 * SR)) / SR
    f = 42 + 70 * np.exp(-t * 22)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 4.2)
    rng = np.random.default_rng(3)
    skin = rng.standard_normal(t.size) * np.exp(-t * 38) * 0.35
    return (body + skin) * vol


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=135)
    ap.add_argument("--out", required=True)
    ap.add_argument("--bpm", type=float, default=72)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()

    n = int(a.duration * SR)
    mix = np.zeros((2, n), dtype=np.float32)
    beat = 60.0 / a.bpm
    bar = beat * 4
    chord_len = bar * 2
    rng = np.random.default_rng(a.seed)

    def add(sig, start, gain=1.0, pan=0.0):
        i = int(start * SR)
        if i >= n:
            return
        seg = sig[: n - i] * gain
        mix[0, i:i + seg.size] += seg * (1 - pan) / 2 * 1.4
        mix[1, i:i + seg.size] += seg * (1 + pan) / 2 * 1.4

    # pad: các hợp âm nối nhau, chồng nhẹ để không đứt
    k, t0 = 0, 0.0
    while t0 < a.duration:
        bass, notes = CHORDS[k % len(CHORDS)]
        dur = chord_len + 1.8
        grow = min(1.0, 0.45 + t0 / (a.duration * 0.6))
        for j, (nm, oc) in enumerate(notes):
            add(pad_note(hz(nm, oc), dur, rng.uniform(0, 6)), t0, 0.16 * grow, pan=(j - 1.5) * 0.35)
        add(pad_note(hz(bass, 2), dur, 0.0) * 0.8, t0, 0.26 * grow)
        k += 1
        t0 += chord_len

    # arpeggio nhẹ bằng nốt cao (nhấn cảm xúc), xuất hiện từ khoảng 20% thời lượng
    k, t0 = 0, a.duration * 0.2
    steps = [0, 2, 1, 3, 2, 1, 3, 2]
    while t0 < a.duration - 6:
        _, notes = CHORDS[int((t0 // chord_len)) % len(CHORDS)]
        nm, oc = notes[steps[k % len(steps)]]
        tt = np.arange(int(1.2 * SR)) / SR
        pluck = np.sin(2 * np.pi * hz(nm, oc + 1) * tt) * np.exp(-tt * 3.0)
        add(pluck, t0, 0.07, pan=rng.uniform(-0.5, 0.5))
        k += 1
        t0 += beat / 2

    # taiko: thưa lúc đầu, dày dần, nhịp lớn ở cuối
    drum_start = bar * 2
    t0, bi = drum_start, 0
    while t0 < a.duration - 4:
        prog = t0 / a.duration
        add(taiko(0.9 if bi % 4 == 0 else 0.6), t0, 0.5 * (0.5 + prog))
        if prog > 0.35:
            add(taiko(0.45), t0 + beat * 2, 0.4)
        if prog > 0.6:
            add(taiko(0.35), t0 + beat * 3, 0.35)
            add(taiko(0.35), t0 + beat * 3.5, 0.3)
        bi += 1
        t0 += bar
    add(taiko(1.0), max(0, a.duration - 3.2), 0.9)

    peak = np.abs(mix).max() or 1
    mix = (mix / peak * 0.85).astype(np.float32)
    fade_in, fade_out = int(3 * SR), int(4 * SR)
    mix[:, :fade_in] *= np.linspace(0, 1, fade_in)
    mix[:, -fade_out:] *= np.linspace(1, 0, fade_out)

    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "raw.wav"
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes((mix.T * 32767).astype(np.int16).tobytes())
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-af",
                        "lowpass=f=4200,aecho=0.8:0.85:90|160:0.35|0.25,loudnorm=I=-18:TP=-2",
                        "-b:a", "192k", a.out], check=True)
    print(f"OUTPUT={a.out}")


if __name__ == "__main__":
    main()
