#!/usr/bin/env python3
"""Собрать русский индекс, подставив переводы из батчей субагентов.

Читает references/cards-index.json (сгенерирован build_index.py) и
дополняет его русскими полями из references/translations/*.json (каталог
можно переопределить через --translations).

Строгая проверка полноты: если хоть одна карточка без перевода или имя
карточки в переводе не совпало с исходным — скрипт падает с ошибкой, а не
пишет частичный индекс. Частичный индекс хуже отсутствующего: он выглядит
готовым.

Запуск: python3 scripts/apply_translations.py [--translations DIR]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "references" / "cards-index.json"
CARDS = ROOT / "references" / "cards"
OUT_MD = ROOT / "references" / "cards-index.md"
DEFAULT_TRANSLATIONS = ROOT / "references" / "translations"

CATEGORY_RU = {
    "camera": "камера и движение в пространстве",
    "data": "данные: графики, числа, счётчики",
    "effects": "эффекты и фактуры",
    "interaction": "интерфейс: ввод, выбор, курсор",
    "opening": "открытие/первый кадр",
    "outro": "финал и логотип",
    "rhythm": "ритм и монтажные склейки",
    "transition": "переходы между сценами",
    "typography": "типографика",
    "ui-entrance": "появление элементов интерфейса",
}


def load_translations(directory: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    files = sorted(directory.glob("batch*.ru.json"))
    if not files:
        raise SystemExit(f"нет файлов batch*.ru.json в {directory}")
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        cards = data.get("cards")
        if not isinstance(cards, list):
            raise SystemExit(f"{f}: нет массива cards")
        for c in cards:
            name = c.get("name")
            if not name:
                raise SystemExit(f"{f}: запись без name")
            if name in out:
                raise SystemExit(f"{f}: дубликат карточки {name}")
            for k in ("essence_ru", "when_ru", "duration_ru", "energy_ru"):
                if not c.get(k):
                    raise SystemExit(f"{f}: у {name} пустое поле {k}")
            out[name] = c
        print(f"  {f.name}: {len(cards)} записей")
    return out


def render(index: dict, tr: dict[str, dict]) -> str:
    cards = index["cards"]
    by_cat: dict[str, list[dict]] = {}
    for c in cards:
        c.update(
            {
                "essence_ru": tr[c["name"]]["essence_ru"],
                "when_ru": tr[c["name"]]["when_ru"],
                "duration_ru": tr[c["name"]]["duration_ru"],
                "energy_ru": tr[c["name"]]["energy_ru"],
            }
        )
        by_cat.setdefault(c["category"], []).append(c)

    lines = [
        "# Индекс карточек шотов",
        "",
        f"Всего карточек: **{len(cards)}**. Полные тексты карточек (спецификации с",
        "числами, кадрами и параметрами) лежат в `references/cards/<категория>/`",
        "как есть, на языке оригинала: числа в спецификациях важнее гладкости",
        "фразы, а машинный перевод их портит. Здесь — русский навигационный слой:",
        "что карточка делает и когда её брать.",
        "",
        "Индекс генерируется: `python3 scripts/build_index.py && python3 scripts/apply_translations.py`.",
        "Правки вносить в исходные карточки/скрипты, а не в этот файл.",
        "",
        "| Категория | Что это | Карточек |",
        "|---|---|---|",
    ]
    for cat in sorted(by_cat):
        lines.append(f"| `{cat}` | {CATEGORY_RU.get(cat, cat)} | {len(by_cat[cat])} |")

    lines += ["", "---", ""]
    for cat in sorted(by_cat):
        lines.append(f"## {cat} — {CATEGORY_RU.get(cat, cat)}")
        lines.append("")
        lines.append("| Карточка | Суть | Когда брать | Длительность | Энергия |")
        lines.append("|---|---|---|---|---|")
        for c in sorted(by_cat[cat], key=lambda x: x["name"]):
            cells = [
                f"`{c['name']}`",
                c["essence_ru"],
                c["when_ru"],
                c["duration_ru"],
                c["energy_ru"],
            ]
            lines.append("| " + " | ".join(x.replace("|", "\\|") for x in cells) + " |")
        lines.append("")

    lines += [
        "---",
        "",
        "## Глоссарий",
        "",
        "| Оригинал | Русский эквивалент |",
        "|---|---|",
        "| hold | удержание: пауза без движения в кадре |",
        "| easing / ease-in / ease-out | кривая ускорения; ease-in — разгон, ease-out — торможение |",
        "| crash zoom | резкий наезд камеры (1–2 кадра разгона) |",
        "| dolly-zoom | наезд камеры с одновременным расфокусом фона (эффект «вертиго») |",
        "| 2.5D | плоский слой, двигаемый в псевдообъёме |",
        "| parallax | параллакс: слои идут с разной скоростью, создавая глубину |",
        "| slot | позиция-слот, из которой элемент влетает |",
        "| transform-origin | точка-якорь трансформации |",
        "| overshoot | перелёт с возвратом (упругость) |",
        "| stagger | каскад: элементы входят по очереди с задержкой |",
        "| riser | нарастание — звуковой/энергетический подъём перед пиком |",
        "| beat / beat grid | бит; сетка битов — равномерные узлы для склеек |",
        "| SFX | звуковой эффект (не музыка) |",
        "| BGM | фоновая музыка |",
        "| foley |拟音: звук под конкретное видимое действие |",
        "",
        "## Источники",
        "",
        "Карточки: апстрим [video-shotcraft](https://github.com/Vincentwei1021/video-shotcraft)",
        "(Apache-2.0, © Wei Yihao), файлы вендорены без изменений. Русские поля",
        "индекса — перевод этого репозитория.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--translations",
        default=str(DEFAULT_TRANSLATIONS),
        help="каталог с batch*.ru.json (по умолчанию references/translations)",
    )
    args = ap.parse_args()

    if not INDEX.exists():
        print("ОШИБКА: нет cards-index.json — сначала scripts/build_index.py", file=sys.stderr)
        return 1

    tr = load_translations(Path(args.translations))
    index = json.loads(INDEX.read_text(encoding="utf-8"))

    names = {c["name"] for c in index["cards"]}
    missing = sorted(names - set(tr))
    extra = sorted(set(tr) - names)
    if missing:
        print(f"ОШИБКА: без перевода {len(missing)} карточек: {missing[:10]}", file=sys.stderr)
        return 1
    if extra:
        print(f"ОШИБКА: лишние имена в переводах: {extra[:10]}", file=sys.stderr)
        return 1

    # вендоренные файлы на месте?
    absent = [c["name"] for c in index["cards"] if not (ROOT / c["path"]).exists()]
    if absent:
        print(f"ОШИБКА: нет вендоренных файлов для: {absent[:10]}", file=sys.stderr)
        return 1

    for c in index["cards"]:
        c.update(
            {
                "essence_ru": tr[c["name"]]["essence_ru"],
                "when_ru": tr[c["name"]]["when_ru"],
                "duration_ru": tr[c["name"]]["duration_ru"],
                "energy_ru": tr[c["name"]]["energy_ru"],
            }
        )
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    OUT_MD.write_text(render(index, tr), encoding="utf-8")
    print(f"переведено карточек: {len(index['cards'])}")
    print(f"написано: {INDEX.relative_to(ROOT)}, {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
