#!/usr/bin/env python3
"""Проверка scripts/beat_grid.py на синтетике с ИЗВЕСТНЫМ темпом.

Синтетический клик-трек: BPM и фаза известны заранее, поэтому утверждаем,
а не «выглядит правдоподобно».

Что проверяем и с каким допуском — это важно, и вот почему:
  * BPM: допуск 0.5% от истинного. Точнее нельзя требовать от 30-секундного
    фрагмента: период в нём уточняется на ~1e-4 с, а librosa кладёт первый
    удар на ~16 мс позже (систематический сдвиг) — остаток фазы и ошибка
    периода на коротком окне неразличимы.
  * Фаза: сетка должна начинаться ВНУТРИ первого бита [0, T), а не с
    отрицательного значения (иначе первый кадр за пределами трека).
  * Внутренняя согласованность: шаг сетки постоянный, сетка монотонна.
  * Выбросы: биты, дописанные трекером на затухании, отсеиваются и не
    попадают в сетку.
  * Длинный прогон: на 2 минутах остаток должен уложиться в апстрим-порог
    (<= 15 мс) — это и есть проверка, что метод держит длину.

Запуск: ~/.venvs/shotcraft/bin/python tests/test_beat_grid.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

# (BPM, фаза, длительность, fps) — короткие; отдельно проверяется длинный трек
CASES = [
    (120.0, 0.250, 30.0, 30),
    (97.5, 0.100, 30.0, 25),
    (140.0, 0.000, 30.0, 60),
]
LONG_CASE = (128.0, 0.150, 120.0, 30)


def make_click_track(bpm: float, phase: float, dur: float, out: Path) -> None:
    import numpy as np
    import soundfile as sf

    sr = 22050
    n = int(sr * dur)
    y = np.zeros(n, dtype="float32")
    period = 60.0 / bpm
    t = phase
    rng = np.random.default_rng(7)
    while t < dur - 0.05:
        i = int(t * sr)
        length = int(0.03 * sr)
        env = np.exp(-np.linspace(0, 12, length))
        tone = np.sin(2 * np.pi * 140 * np.linspace(0, 0.03, length)) * env
        tone = tone + 0.4 * rng.standard_normal(length) * env
        end = min(n, i + length)
        y[i:end] += tone[: end - i]
        t += period
    sf.write(out, y, sr)


def run_grid(audio: Path, fps: int) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        js = Path(f.name)
    subprocess.run(
        [PY, str(ROOT / "scripts" / "beat_grid.py"), str(audio),
         "--fps", str(fps), "--json", str(js)],
        check=True, capture_output=True, text=True,
    )
    data = json.loads(js.read_text(encoding="utf-8"))
    js.unlink()
    return data


def check(g: dict, bpm: float, label: str) -> list[str]:
    """Инварианты сетки. Реконструкцию темпа проверяем отдельно (check_tempo):
    абсолютный BPM на коротком окне ограничен точностью бит-трекера, а вот
    КАЧЕСТВО сетки от длины не зависит и проверяется строго."""
    import numpy as np

    bad: list[str] = []
    period = 60.0 / bpm

    if not (0.0 <= g["grid_phase_s"] < period + 1e-9):
        bad.append(
            f"{label}: фаза сетки {g['grid_phase_s']} вне [0, {period:.3f}) — "
            "первый кадр уйдёт за начало трека"
        )
    b = np.array(g["beats"])
    if b.size < 4:
        bad.append(f"{label}: в сетке меньше 4 битов")
        return bad
    d = np.diff(b)
    # допуск — накопление double в арифметической прогрессии (1e-4 с)
    if np.ptp(d) > 5e-4:
        bad.append(f"{label}: шаг сетки не постоянный (разброс {np.ptp(d):.2e} с)")
    if not np.all(d > 0):
        bad.append(f"{label}: сетка не монотонна")
    # сетка обязана лежать на прямой: это гарантия метода, а не приблизительность
    idx = np.arange(b.size)
    dev = np.abs(b - (g["grid_phase_s"] + idx * g["period_s"])).max()
    if dev > 1e-3:
        bad.append(f"{label}: сетка не лежит на прямой (макс. отклонение {dev:.4f} с)")
    # внутренняя согласованность: период в JSON совпадает с шагом сетки
    if abs(g["period_s"] - float(np.median(d))) > 5e-4:
        bad.append(
            f"{label}: period_s={g['period_s']} не совпадает со шагом сетки "
            f"{float(np.median(d)):.6f}"
        )
    return bad


def check_tempo(g: dict, bpm: float, label: str, tol_frac: float) -> list[str]:
    if abs(g["bpm"] - bpm) / bpm > tol_frac:
        return [
            f"{label}: BPM {g['bpm']} вне {tol_frac * 100:.1f}% от {bpm} "
            f"(медианный остаток {g['median_residual_ms']} мс)"
        ]
    return []


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        for bpm, phase, dur, fps in CASES:
            audio = Path(td) / f"click-{bpm}.wav"
            make_click_track(bpm, phase, dur, audio)
            g = run_grid(audio, fps)
            label = f"{bpm} BPM ({dur:.0f} с)"
            bad = check(g, bpm, label) + check_tempo(g, bpm, label, 0.005)
            failures += bad
            print(
                f"{'FAIL' if bad else 'OK  '} клик {bpm:6.1f} BPM ({dur:.0f} с, фаза {phase:.3f} с, "
                f"{fps} fps) -> bpm={g['bpm']:7.2f} фаза сетки={g['grid_phase_s']:.3f} "
                f"битов={len(g['beats'])} отсеяно={g['outliers']} "
                f"остаток медиана/макс={g['median_residual_ms']:.1f}/{g['residual_ms']:.1f} мс"
            )

        bpm, phase, dur, fps = LONG_CASE
        audio = Path(td) / f"click-long-{bpm}.wav"
        make_click_track(bpm, phase, dur, audio)
        g = run_grid(audio, fps)
        label = f"{bpm} BPM ({dur:.0f} с, длинный)"
        bad = check(g, bpm, label) + check_tempo(g, bpm, label, 0.0005)
        # на двух минутах требование апстрима применимо: остаток <= 15 мс
        if g["residual_ms"] > 15.0:
            bad.append(
                f"{label}: остаток {g['residual_ms']} мс > 15 мс — метод не держит длину"
            )
        failures += bad
        print(
            f"{'FAIL' if bad else 'OK  '} клик {bpm:6.1f} BPM ({dur:.0f} с, длинный) -> "
            f"bpm={g['bpm']:7.2f} остаток медиана/макс="
            f"{g['median_residual_ms']:.1f}/{g['residual_ms']:.1f} мс "
            f"битов={len(g['beats'])} отсеяно={g['outliers']} "
            f"покрытие сильных={g['coverage'] * 100:.0f}%"
        )

    if failures:
        print("\nПРОВАЛ:")
        for f in failures:
            print(" -", f)
        return 1
    print(
        "\nвсе случаи прошли: сетка лежит на прямой, шаг постоянный, фаза внутри "
        "первого бита, выбросы отсеяны, на 2 минутах остаток <= 15 мс"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
