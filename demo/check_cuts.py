"""Проверка готового ролика: стоят ли склейки на узлах сетки битов.

По средней яркости судить нельзя: перед склейкой идёт намеренное затухание
(4 кадра), и максимум перепада яркости приходится на НАЧАЛО затухания, а не
на склейку. Поэтому считаем структурное различие соседних кадров по всем
пикселям: затухание даёт ровный небольшой прирост, а склейка — один резкий
пик. Пик и есть момент склейки; сверяем его с кадрами из out/grid.json.
"""
import json
import subprocess
import sys

import numpy as np

mp4 = sys.argv[1] if len(sys.argv) > 1 else "out/demo.mp4"
grid = json.load(open("out/grid.json"))
grid_frames = grid["frames"]
fps = grid["fps"]
W, H = 160, 90

raw = subprocess.run(
    ["ffmpeg", "-v", "error", "-i", mp4, "-vf", f"scale={W}:{H}",
     "-f", "rawvideo", "-pix_fmt", "gray", "-"],
    capture_output=True,
).stdout
n = len(raw) // (W * H)
frm = np.frombuffer(raw[: n * W * H], dtype=np.uint8).reshape(n, H, W).astype(np.float32)
print(f"кадров в ролике: {n}   сетка: {len(grid_frames)} битов @ {fps} fps")

diff = np.abs(np.diff(frm, axis=0)).mean(axis=(1, 2))
med = float(np.median(diff))
p99 = float(np.percentile(diff, 99))
# Порог калиброван по данным: склейки дают 6.9–73.9, весь остальной монтаж
# (панорама камеры, появление текста) — не больше 0.9. Порог берём с запасом
# от двух опор: фона и 99-го процентиля. Абсолютную константу тут брать нельзя —
# на другом ролике масштаб движения другой.
thr = max(med * 30.0, p99 * 3.0)
peaks = [i + 1 for i in range(len(diff)) if diff[i] >= thr]
cuts = []
for p in peaks:
    if not cuts or p - cuts[-1] > 4:
        cuts.append(p)
print(f"фон движения: {med:.2f}, порог склейки: {thr:.2f}")
print(f"найдено склеек: {len(cuts)} -> кадры {cuts}")

expected_bits = [0, 6, 10, 16, 22, 27]
expected = [grid_frames[b] for b in expected_bits]
print(f"ожидаемые склейки (биты {expected_bits}): кадры {expected}")

ok = 0
for e in expected[1:]:  # кадр 0 — начало ролика, склейки там нет по определению
    near = [c for c in cuts if abs(c - e) <= 2]
    if near:
        ok += 1
        print(f"  OK   склейка на бите: кадр {e} (найден на {near[0]}, "
              f"расхождение {near[0] - e} кадра)")
    else:
        print(f"  MISS ожидалась склейка на кадре {e} — не найдена")

print()
if not cuts:
    print("ПРОВАЛ: смен шота не найдено — ролик не смонтирован или однотонный")
    sys.exit(1)

dist = [min(abs(c - f) for f in grid_frames) for c in cuts]
worst_frames = max(dist)
print("расстояние склеек до ближайшего узла сетки, кадры:",
      [round(x, 2) for x in dist])
print(f"худшее расхождение: {worst_frames:.2f} кадра "
      f"= {worst_frames / fps * 1000:.0f} мс")
print(f"склеек совпало с расписанием: {ok}/{len(expected) - 1}")

fail = worst_frames > 1.0 or ok != len(expected) - 1
if not fail:
    print("ВЫВОД: все склейки стоят на узлах сетки (расхождение < 1 кадра)")
    sys.exit(0)
print("ВЫВОД: монтаж разошёлся с сеткой — проверить расписание шотов")
sys.exit(1)
