#!/usr/bin/env python3
"""Собрать русский справочник по карточкам шотов из вендоренных файлов.

Читает references/cards/<категория>/*.md и вытаскивает из YAML-шапки апстрима
суть-в-одну-строку и поля «когда применять / длительность / энергия». Ключи
шапки китайские — переименовывать их нельзя, по ним парсится первоисточник;
исходный текст этих полей кладётся в JSON под суффиксом _zh. Результат:
  * references/cards-index.md  — таблица: имя, категория, что делает, когда
    применять, длительность, энергия (русские подписи колонок)
  * references/cards-index.json — то же машиночитаемо, для CI-сверки

Переводить апстримные тексты целиком — сознательно НЕ делаем: это
спецификации с числами, машинный перевод их портит. Русский слой — индекс
и глоссарий терминов, а не перевод.

Запуск: python3 scripts/build_index.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "references" / "cards"
OUT_MD = ROOT / "references" / "cards-index.md"
OUT_JSON = ROOT / "references" / "cards-index.json"

# Русские подписи для категорий (ключи — апстримные имена каталогов)
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

# Ключи frontmatter апстрима — китайские, и переименовывать их нельзя: именно
# по этим строкам парсится шапка вендоренных карточек (см. _zh-поля в JSON).
# Смысл ключей по порядку: суть-в-одну-строку, когда применять, длительность,
# энергия, метки.


def parse_frontmatter(text: str) -> dict[str, str]:
    """YAML-шапка апстрима: строки «ключ: значение» между --- ---."""
    m = re.search(r"^---\n(.*?)\n---", text, re.S | re.M)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        out[k.strip()] = v.strip()
    return out


def main() -> int:
    if not CARDS.exists():
        print("ОШИБКА: нет references/cards — сначала scripts/vendor_cards.py", file=sys.stderr)
        return 1

    rows = []
    for path in sorted(CARDS.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        category = path.parent.name
        name = fm.get("name") or path.stem
        rows.append(
            {
                "name": name,
                "category": category,
                "category_ru": CATEGORY_RU.get(category, category),
                # Ключи frontmatter — как в апстриме (китайские): их парсим,
                # переименовывать нельзя. В JSON кладём их под суффиксом _zh:
                # это исходный текст, и он намеренно НЕ переводится (числа и
                # параметры машинному переводу не доверяем). Русский слой — _ru.
                "essence_zh": fm.get("一句话", ""),
                "when_zh": fm.get("适用", ""),
                "duration_zh": fm.get("时长", ""),
                "energy_zh": fm.get("能量", ""),
                "tags_zh": fm.get("标签", ""),
                "path": str(path.relative_to(ROOT)),
            }
        )

    rows.sort(key=lambda r: (r["category"], r["name"]))

    by_cat: dict[str, int] = {}
    for r in rows:
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + 1

    lines = [
        "# Индекс карточек шотов (русский слой)",
        "",
        "Это НЕ перевод апстримных карточек — это навигационный индекс по ним.",
        "Полные тексты с числами и параметрами лежат в `references/cards/<категория>/`",
        "как есть, на языке оригинала: числа в спецификациях важнее гладкости",
        "русской фразы. Русские формулировки ниже — про то, ЧТО карточка делает",
        "и КОГДА её брать.",
        "",
        f"Всего карточек: **{len(rows)}**",
        "",
        "| Категория | Что это | Карточек |",
        "|---|---|---|",
    ]
    for cat in sorted(by_cat):
        lines.append(f"| `{cat}` | {CATEGORY_RU.get(cat, cat)} | {by_cat[cat]} |")

    lines += ["", "---", ""]
    for cat in sorted(by_cat):
        lines.append(f"## {cat} — {CATEGORY_RU.get(cat, cat)}")
        lines.append("")
        lines.append("| Карточка | Суть | Когда брать | Длительность | Энергия |")
        lines.append("|---|---|---|---|---|")
        for r in rows:
            if r["category"] != cat:
                continue
            cells = [
                f"`{r['name']}`",
                r.get("essence_ru") or r.get("essence_zh") or "—",
                r.get("when_ru") or r.get("when_zh") or "—",
                r.get("duration_ru") or r.get("duration_zh") or "—",
                r.get("energy_ru") or r.get("energy_zh") or "—",
            ]
            lines.append("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
        lines.append("")

    lines += [
        "---",
        "",
        "## Глоссарий терминов карточек",
        "",
        "| Оригинал | Русский эквивалент |",
        "|---|---|",
        "| hold | удержание, пауза без движения в кадре |",
        "| easing / ease-in / ease-out | кривая ускорения; ease-in — разгон, ease-out — торможение |",
        "| crash zoom | резкий наезд камеры (1–2 кадра разгона) |",
        "| 2.5D | плоский слой, двигаемый в псевдообъёме |",
        "| slot | позиция-слот, из которой элемент влетает |",
        "| transform-origin | точка-якорь трансформации (как правило — по центру/по базовой линии) |",
        "| overshoot | перелёт с возвратом (упругость) |",
        "| stagger | каскад: элементы входят по очереди с задержкой |",
        "| riser | нарастание (звуковой/энергетический подъём перед пиком) |",
        "| beat / beat grid | бит; сетка битов — равномерные узлы для склеек |",
        "| SFX | звуковой эффект (не музыка) |",
        "| BGM | фоновая музыка |",
        "",
        "Источник терминов: апстрим video-shotcraft (Apache-2.0).",
        "Индекс сгенерирован автоматически — правки вносите в `scripts/build_index.py`.",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    OUT_JSON.write_text(
        json.dumps(
            {
                "total": len(rows),
                "by_category": by_cat,
                "category_ru": CATEGORY_RU,
                "cards": rows,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"карточек: {len(rows)}  по категориям: {dict(sorted(by_cat.items()))}")
    print(f"написано: {OUT_MD.relative_to(ROOT)}, {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
