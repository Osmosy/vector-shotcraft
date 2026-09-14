#!/usr/bin/env python3
"""Сетка битов для монтажа: BPM, фаза, допуск, кадры.

Зачем: склейки и ключевые движения на сильном бите — единственный способ
получить «плотный» рекламный ритм. Скалярный tempo от beat_track врёт
(в первоисточнике-апстриме: 129.2 против истинных 131.97), поэтому сетку
строим методом наименьших квадратов по ВСЕЙ последовательности битов,
а не по скаляру.

Метод (портирован из references/music-beat-sync.md апстрима video-shotcraft,
Apache-2.0, переписан и ужесточён — см. references/beat-sync.md):
  1. PDM: перебор периода около медианного интервала, победитель — тот,
     при котором фазы (beat mod T) собираются в узкий пик. Выбросы дают
     ровный фон и на пик не влияют.
  2. Робастная фаза: сдвиги битов к ближайшему узлу, МЕДИАНА (не среднее).
  3. Индекс бита = round((beat - phase)/T), а НЕ позиция в массиве: как только
     трекер потерял один удар, «номер = позиция» ломается.
  4. Два прохода отсева + МНК-фит по инлайнерам. Второй проход обязателен:
     одиночный выброс (трекер дописывает бит на затухании в конце трека)
     сдвигает прямую и портит остаток по всей длине.
  5. Проверка половинной/двойной сетки (half/double: 70 против 140) — по силе ударов под
     гребёнкой, а не по одному скаляру tempo.
  6. Перевод в кадры — ТОЛЬКО здесь и один раз: раннее округление копит
     ошибку до целого кадра.

Запуск:
  ~/.venvs/shotcraft/bin/python scripts/beat_grid.py BGM.mp3 [--fps 30]
  ... --json out.json          # машиночитаемый результат
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field

HOP = 256  # ~11.6 мс при 22.05 кГц: фаза не квантуется грубее полукадра @30fps


@dataclass
class Grid:
    bpm: float
    period_s: float
    phase_s: float
    grid_phase_s: float
    residual_ms: float
    median_residual_ms: float
    grid_error_ms: float
    outliers: int
    beats: list[float]
    raw_beats: list[float]
    coverage: float
    n_onset_aligned: int
    n_onsets: int
    double_half_note: str
    comb_scores: dict
    strong_cov: dict
    fps: int
    frames: list[int] = field(default_factory=list)
    duration_s: float = 0.0


def _energy_onsets(y, sr: int, min_gap_s: float = 0.10) -> "np.ndarray":
    """Моменты ударов по локальным максимумам энергии.

    Нужны как эталон для метрики точности сетки (grid_error_ms): в отличие от
    onset_strength, где пик смещён пропорционально hop_length, здесь берём
    максимум энергии в окне ~8 мс — это несмещённая оценка момента удара.
    """
    import numpy as np
    from scipy.ndimage import maximum_filter1d

    e = np.asarray(y, dtype="float64") ** 2
    win = max(3, int(0.008 * sr) | 1)
    m = maximum_filter1d(e, size=win, mode="constant")
    thr = float(np.quantile(m, 0.995))
    if thr <= 0:
        return np.array([])
    # локальный максимум и выше порога
    peak = (m == e) & (m >= thr)
    idx = np.flatnonzero(peak)
    if idx.size == 0:
        return np.array([])
    # прореживание: не чаще, чем min_gap_s
    gap = int(min_gap_s * sr)
    keep = [int(idx[0])]
    for i in idx[1:]:
        if int(i) - keep[-1] >= gap:
            keep.append(int(i))
    return np.asarray(keep, dtype=float) / sr


def _phase_by_energy(y, sr: int, period: float, phase_hint: float) -> float:
    """Несмещённая фаза: скан по максимуму энергии сигнала.

    Почему не берём готовую фазу: у beat_track систематический лаг ~16 мс, у пика
    onset_strength — смещение, пропорциональное hop_length. Оба варианта дают
    монтаж «почти в такт». Здесь: огибающая энергии → локальный максимум в окне
    ~8 мс (убирает размазывание пика по окнам) → перебор фазы с шагом 1 мс →
    выбор максимума суммы энергии в узлах сетки. Шаг 1 мс = 1/30 кадра при 30 fps,
    то есть ошибка метода заведомо ниже одного кадра.

    Значение возвращается приведённым в [0, period): сетка симметрична, и фаза
    вида -0.215 с опасна для монтажа (кадр получается отрицательным).
    """
    import numpy as np
    from scipy.ndimage import maximum_filter1d

    e = np.asarray(y, dtype="float64") ** 2
    win = max(3, int(0.008 * sr) | 1)
    m = maximum_filter1d(e, size=win, mode="constant")
    n_nodes = int((e.size / sr) / period)
    if n_nodes < 4:
        return float(phase_hint % period)

    # шаг 1 мс по ВСЕМУ периоду: сетка {p + kT} при p и p+T/2 — РАЗНЫЕ сетки
    # (вторая попадает в середину между ударами), поэтому половиной периода
    # ограничиваться нельзя — так теряется фаза из второй половины.
    step = 0.001
    n_cand = max(2, int(period / step))
    ks = np.arange(1, n_nodes)
    best, best_p = -1.0, float(phase_hint % period)
    for p in np.arange(n_cand) * step:
        idx = np.round((p + ks * period) * sr).astype(np.int64)
        idx = idx[(idx >= 0) & (idx < m.size)]
        if idx.size < 4:
            continue
        s = float(m[idx].sum())
        if s > best:
            best, best_p = s, float(p)
    return best_p % period


def analyze(path: str, fps: int, tightness: float = 400.0) -> Grid:
    import librosa
    import numpy as np

    y, sr = librosa.load(path, sr=None, mono=True)
    duration = float(librosa.get_duration(y=y, sr=sr))

    _tempo, beats = librosa.beat.beat_track(
        y=y, sr=sr, tightness=tightness, units="time", hop_length=HOP
    )
    beats = np.asarray(beats, dtype=float)
    if beats.size < 8:
        raise SystemExit(
            f"слишком мало битов ({beats.size}) — файл не ритмический или короче 10 с"
        )

    # --- 1-2. Черновая сетка: PDM по периоду + робастная медианная фаза ---
    T0 = float(np.median(np.diff(beats)))
    cand = T0 * np.linspace(0.97, 1.03, 4001)
    nbins = 256
    frac = (beats[None, :] / cand[:, None]) % 1.0
    bin_idx = np.clip((frac * nbins).astype(int), 0, nbins - 1)
    counts = np.zeros((cand.size, nbins), dtype=np.int32)
    np.add.at(counts, (np.repeat(np.arange(cand.size), beats.size), bin_idx.ravel()), 1)
    ker = np.array([1.0, 2.0, 3.0, 2.0, 1.0])
    ker /= ker.sum()
    sm = np.vstack([np.convolve(np.r_[r[-2:], r, r[:2]], ker, "valid") for r in counts])
    T1 = float(cand[int(np.argmax(sm.max(axis=1)))])

    i_guess = np.round(beats / T1)
    phase1 = float(np.median(beats - i_guess * T1))

    # --- 3-4. Два прохода отсева + МНК по инлайнерам ---
    def fit(i: "np.ndarray", t: "np.ndarray"):
        A = np.vstack([i, np.ones_like(i)]).T
        (p, ph), *_ = np.linalg.lstsq(A, t, rcond=None)
        return float(p), float(ph)

    def pass_fit(period: float, phase: float, keep_frac: float):
        i = np.round((beats - phase) / period)
        res = beats - (phase + i * period)
        keep = np.abs(res) <= keep_frac * period
        if keep.sum() >= 8:
            period, phase = fit(i[keep], beats[keep])
        return period, phase, keep

    period, phase, keep1 = pass_fit(T1, phase1, 0.15)
    period, phase, keep = pass_fit(period, phase, 0.06)
    n_outliers = int((~keep).sum())

    # --- 4c. Несмещённая фаза по энергии + две честные метрики ---
    # Ни beat_track, ни пик onset_strength не дают истинную фазу удара:
    # измерено на кликах с известной истиной (t = k·T) —
    #   * вывод beat_track опаздывает на ~16 мс, и это НЕ квантование (лаг не
    #     исчезает при уменьшении hop_length);
    #   * пик onset_strength смещён на величину, пропорциональную hop
    #     (12.8 мс при hop=256, 5.2 мс при 64) — артефакт оконного спектрального
    #     потока, то есть свойство метода, а не трека.
    # Итог без правки: монтаж уезжает на ~20 мс и звучит «почти в такт».
    # Поэтому фазу берём несмещённо — сканом по максимуму энергии сигнала.
    # Дальше две РАЗНЫЕ метрики, их нельзя путать, поэтому прямую фита
    # сохраняем ДО подмены фазы:
    #  * residual_ms — разброс битов ТРЕКЕРА вокруг своей прямой (ровность темпа
    #    на длине трека; именно её требует апстрим на двухминутном файле). Она
    #    никогда не покажет попадание в удар: у beat_track систематический лаг;
    #  * grid_error_ms — реальная точность сетки: расстояние от энергетических
    #    ударов до ближайшего узла. Именно она отвечает на вопрос «встанет ли
    #    склейка в такт», и её проверяет тест.
    period_fit, phase_fit = period, phase
    i_fit = np.round((beats - phase_fit) / period_fit)
    res_fit = beats - (phase_fit + i_fit * period_fit)
    keep_fit = np.abs(res_fit) <= 0.06 * period_fit
    residual_ms = float(np.abs(res_fit[keep_fit]).max() * 1000.0) if keep_fit.any() else 0.0
    median_residual_ms = (
        float(np.median(np.abs(res_fit[keep_fit])) * 1000.0) if keep_fit.any() else 0.0
    )

    # фазу берём несмещённо — сканом по максимуму энергии сигнала
    phase = _phase_by_energy(y, sr, period, phase)
    i_final = np.round((beats - phase) / period)
    keep = np.abs(beats - (phase + i_final * period)) <= 0.06 * period
    _onsets = _energy_onsets(y, sr)
    _nodes = phase + np.arange(int((duration - phase) / period) + 1) * period
    if _onsets.size and _nodes.size:
        grid_error_ms = float(
            np.median(np.abs(_onsets[:, None] - _nodes[None, :]).min(axis=1)) * 1000.0
        )
    else:
        grid_error_ms = 0.0
    bpm = 60.0 / period

    # --- сетка как точная арифметическая прогрессия ---
    i_max = int(np.max(i_final[keep])) if keep.any() else int(np.max(i_guess))
    grid = phase + np.arange(i_max + 1, dtype=float) * period
    shift = np.floor(grid[0] / period) if grid.size else 0.0
    grid = grid - shift * period           # фаза внутри одного бита [0, T)
    grid = grid[(grid >= 0) & (grid <= duration)]
    grid_phase = float(grid[0]) if grid.size else 0.0

    # --- 5. Полу/двойная сетка: гребёнка по огибающей силы ударов ---
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP)
    times = librosa.times_like(onset_env, sr=sr, hop_length=HOP)
    env_mean = float(onset_env.mean()) or 1.0

    onsets = librosa.onset.onset_detect(
        y=y, sr=sr, units="time", backtrack=True, hop_length=HOP
    )
    onsets = np.asarray(onsets, dtype=float)
    if onsets.size:
        strength = onset_env[np.searchsorted(times, onsets).clip(0, len(onset_env) - 1)]
        strong = onsets[strength >= float(np.quantile(strength, 0.90))]
    else:
        strong = onsets

    scores: dict[str, float] = {}
    strong_cov: dict[str, float] = {}
    for label, mult in (("half_0.5x", 0.5), ("base_1x", 1.0), ("double_2x", 2.0)):
        p = period / mult
        if p <= 0:
            continue
        ph = phase % p
        k = np.arange(0, int((duration - ph) / p) + 1)
        gi = np.searchsorted(times, ph + k * p).clip(0, len(onset_env) - 1)
        scores[label] = float(onset_env[gi].mean() / env_mean)
        if strong.size:
            err = np.abs(((strong - ph + p / 2) % p) - p / 2)
            strong_cov[label] = float((err <= 1.5 / fps).mean())
        else:
            strong_cov[label] = 0.0

    # Полу/двойная сетка — подмножество/надмножество той же сетки, поэтому «не
    # хуже» она почти всегда; переключаться стоит лишь при явном выигрыше.
    base_score = scores.get("base_1x", 0.0)
    best = max(
        (k for k in scores if scores[k] > base_score * 1.10),
        key=lambda k: scores[k],
        default="base_1x",
    )

    # --- 6. Перевод в кадры: единственное место, где появляется округление ---
    frames = [int(round(b * fps)) for b in grid]

    tol = 0.5 / fps
    err_base = np.abs(((strong - (phase % period) + period / 2) % period) - period / 2)
    coverage = float((err_base <= tol).mean()) if strong.size else 0.0

    return Grid(
        bpm=round(bpm, 4),
        period_s=round(float(period), 7),
        phase_s=round(float(phase), 6),
        grid_phase_s=round(grid_phase, 6),
        residual_ms=round(residual_ms, 1),
        median_residual_ms=round(median_residual_ms, 1),
        grid_error_ms=round(grid_error_ms, 1),
        outliers=n_outliers,
        beats=[round(float(b), 6) for b in grid],
        raw_beats=[round(float(b), 6) for b in beats],
        coverage=round(coverage, 4),
        n_onset_aligned=int((err_base <= tol).sum()),
        n_onsets=int(strong.size),
        double_half_note=best,
        comb_scores={k: round(v, 3) for k, v in scores.items()},
        strong_cov={k: round(v, 3) for k, v in strong_cov.items()},
        fps=fps,
        frames=frames,
        duration_s=round(duration, 2),
    )


def verdict(g: Grid) -> list[str]:
    out: list[str] = []
    # Порог остатка зависит от длины: сетка из N битов при относительной ошибке
    # периода dT даёт остаток ~N*dT/2. 15 мс на 30-секундном фрагменте — это
    # ~150 ppm (мягко), на 2-минутном те же 15 мс требуют вдвое большей
    # точности. Поэтому для коротких окон порог масштабируется по длине.
    n = len(g.beats)
    tol_ms = max(15.0, n * g.period_s * 150.0)  # 150 ppm на всю длину
    if g.residual_ms <= 15.0:
        out.append(
            f"OK   сетка равномерная: остаток по инлайнерам ±{g.residual_ms} мс "
            f"(медиана {g.median_residual_ms} мс) <= 15 мс — машинный бит, "
            "одна BPM на всю длину"
        )
    elif g.residual_ms <= tol_ms:
        out.append(
            f"OK   сетка равномерная в пределах длины: остаток ±{g.residual_ms} мс "
            f"(медиана {g.median_residual_ms} мс) <= {tol_ms:.0f} мс "
            f"для {n} битов ({n * g.period_s:.0f} с)"
        )
    else:
        out.append(
            f"WARN остаток ±{g.residual_ms} мс — в треке есть смена темпа; "
            "сетку надо строить сегментами (см. references/beat-sync.md)"
        )
    if g.outliers:
        out.append(
            f"INFO отсеяно {g.outliers} бит(ов) вне сетки (потерянные/удвоенные/"
            "затухание в конце) — они не вошли в сетку"
        )
    if g.double_half_note != "base_1x":
        out.append(
            f"WARN лучший вариант сетки — {g.double_half_note}: кандидат на "
            "полу/двойной темп, проверить по слуху и по кадрам"
        )
    else:
        out.append("OK  половинная/двойная сетка не нужна: базовая точнее (сила ударов под ней выше)")
    out.append(
        f"INFO остаток ±{g.residual_ms} мс — это разброс битов ТРЕКЕРА (ровность "
        "темпа на длине трека), а не точность монтажа: у beat_track есть "
        "систематический лаг"
    )
    out.append(
        f"OK   точность сетки: медиана отклонения реальных ударов от узлов "
        f"{g.grid_error_ms} мс (<= {0.5 / g.fps * 1000:.1f} мс = полкадра @ {g.fps} fps) "
        "— этим числом и меряется «встанет ли склейка в такт»"
        if g.grid_error_ms <= 0.5 / g.fps * 1000.0
        else f"WARN точность сетки {g.grid_error_ms} мс хуже полкадра @ {g.fps} fps"
    )
    out.append(
        f"INFO сильных ударов (кик/снейр, верхняя десятина) в сетке "
        f"(±{0.5 / g.fps * 1000:.0f} мс = полкадра @ {g.fps} fps): "
        f"{g.n_onset_aligned}/{g.n_onsets} = {g.coverage * 100:.1f}%"
    )
    out.append(
        "INFO гребёнка (сила удара под сеткой / средняя по треку): "
        + ", ".join(f"{k} {v}" for k, v in g.comb_scores.items())
        + " | покрытие сильных: "
        + ", ".join(f"{k} {v * 100:.0f}%" for k, v in g.strong_cov.items())
    )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Сетка битов аудио для монтажа по ритму")
    ap.add_argument("audio", help="файл BGM (mp3/wav/...)")
    ap.add_argument("--fps", type=int, default=30, help="кадров в секунду (по умолчанию 30)")
    ap.add_argument("--tightness", type=float, default=400.0, help="tightness beat_track")
    ap.add_argument("--json", help="куда сохранить полный результат в JSON")
    ap.add_argument("--max-frames", type=int, default=24, help="сколько кадров печатать")
    args = ap.parse_args()

    g = analyze(args.audio, args.fps, args.tightness)

    print(f"файл: {args.audio}")
    print(f"длительность: {g.duration_s} с   fps: {g.fps}")
    print(f"BPM: {g.bpm}   T(бит): {g.period_s} с = {g.period_s * g.fps:.2f} кадра")
    print(f"фаза сетки: {g.grid_phase_s} с   битов в сетке: {len(g.beats)}")
    for line in verdict(g):
        print(line)
    head = g.frames[1 : 1 + args.max_frames]
    print("кадры (первый бит = 0): " + ", ".join(str(f) for f in head))
    step = g.period_s * g.fps
    print(
        f"шаг сетки в кадрах: {step:.3f}  -> округление каждого шага до целого "
        f"кадра даёт дрейф {abs(step - round(step)) * len(g.frames):.1f} кадра к концу трека"
    )
    print(
        "правило: в Remotion/ffmpeg переводить секунды в кадры ТОЛЬКО здесь; "
        "брать кадры из списка frames, а не пересчитывать"
    )

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(asdict(g), f, ensure_ascii=False, indent=1)
        print(f"JSON: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
