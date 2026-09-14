#!/usr/bin/env python3
"""Генерация BGM с точно известным темпом — для проверки бит-сетки.

Смысл: на синтетике истина известна до миллисекунды, поэтому по ней можно
ЧЕСТНО измерить, попадает ли сетка в удар. На реальном треке такой опоры нет —
там приходится верить бит-трекеру, а он, как выяснилось, систематически
опаздывает. Поэтому демо-ролик собирается на треке, где истина задана кодом:
120 BPM, клики ровно на k·0.5 с, бас на каждый четвёртый бит.

Запуск:
    ~/.venvs/shotcraft/bin/python demo/make_bgm.py demo/audio/bgm.wav
"""
import sys

import numpy as np
import soundfile as sf

SR = 22050
BPM = 120.0
DUR = 20.0


def main(out_path: str, bpm: float = BPM, dur: float = DUR) -> int:
    period = 60.0 / bpm
    n = int(SR * dur)
    y = np.zeros(n, dtype="float64")

    k = int(period * SR)
    env = np.exp(-np.linspace(0, 9, k))
    tick = np.sin(2 * np.pi * 1000 * np.arange(k) / SR) * env * 0.25

    beats = 0
    for i, start in enumerate(np.arange(0.0, dur - period, period)):
        s = int(round(start * SR))
        e = min(n, s + k)
        y[s:e] += tick[: e - s]
        beats += 1
        if i % 4 == 0:  # бас на каждый четвёртый бит — «сильный удар»
            kb = int(period * 1.4 * SR)
            eb = np.exp(-np.linspace(0, 7, kb))
            bass = np.sin(2 * np.pi * 55 * np.arange(kb) / SR) * eb * 0.5
            e2 = min(n, s + kb)
            y[s:e2] += bass[: e2 - s]

    y = y / max(np.abs(y).max(), 1e-9) * 0.85
    sf.write(out_path, y.astype("float32"), SR)
    print(f"BGM: {bpm:.1f} BPM, {dur:.0f} с, битов {beats} -> {out_path}")
    print(f"истина: клики ровно на k·{period:.6f} с (проверять сетку по ней)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("использование: make_bgm.py <выходной .wav>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
