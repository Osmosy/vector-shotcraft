#!/usr/bin/env python3
"""Валидатор репозитория vector-shotcraft.

Что проверяет (и падает, а не предупреждает):
  1. вендоренные карточки — их ровно столько, сколько в манифесте, и SHA1
     каждого файла совпадает с манифестом (защита от правки апстримного текста);
  2. каждая карточка имеет шапку провенанса с корректной ссылкой на источник;
  3. у каждой карточки в индексе есть все четыре русских поля;
  4. каждый скилл существует и имеет frontmatter с name/description;
  5. каждая ссылка на файл внутри markdown-документов существует;
  6. числа в README (сколько карточек, сколько категорий) совпадают с фактом;
  7. NOTICE.md перечисляет лицензию апстрима;
  8. документация упоминает живую диаграмму, и её файлы на месте.

Запуск: python3 scripts/validate.py
CI: .github/workflows/validate.yml
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "references" / "cards"
MANIFEST = ROOT / "references" / "cards-manifest.json"
INDEX = ROOT / "references" / "cards-index.json"
SKILLS = ROOT / "skills"

errors: list[str] = []


def err(msg: str) -> None:
    errors.append(msg)


def check_cards() -> int:
    """1+2: карточки вендорены, не изменены, имеют шапку провенанса."""
    if not MANIFEST.exists():
        err("нет references/cards-manifest.json — запусти scripts/vendor_cards.py")
        return 0
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = sorted(CARDS.rglob("*.md"))
    if len(files) != len(manifest):
        err(f"карточек на диске {len(files)}, в манифесте {len(manifest)}")

    end = "<!-- /vendored -->"
    for path in files:
        rel = "references/shots/" + "/".join(path.relative_to(CARDS).parts)
        entry = manifest.get(rel)
        if not entry:
            err(f"{path.relative_to(ROOT)}: нет в манифесте")
            continue
        text = path.read_text(encoding="utf-8")
        if end not in text:
            err(f"{path.relative_to(ROOT)}: нет маркера конца шапки провенанса")
            continue
        # тело карточки — всё после маркера, ровно как скачано из апстрима
        body = text.split(end, 1)[1].lstrip("\n")
        sha1 = hashlib.sha1(body.encode("utf-8")).hexdigest()
        if sha1 != entry["sha1"]:
            err(
                f"{path.relative_to(ROOT)}: апстримный текст изменён "
                f"(sha1 {sha1[:12]} != {entry['sha1'][:12]})"
            )
        if "<!-- vendored: video-shotcraft -->" not in text:
            err(f"{path.relative_to(ROOT)}: нет шапки провенанса")
        if entry["upstream"] not in text:
            err(f"{path.relative_to(ROOT)}: в шапке нет ссылки на источник")
    return len(files)


def check_index(n_cards: int) -> int:
    """3: у каждой карточки есть русские поля и вендоренный файл на месте."""
    if not INDEX.exists():
        err("нет references/cards-index.json — запусти build_index.py + apply_translations.py")
        return 0
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    cards = index.get("cards", [])
    if len(cards) != n_cards:
        err(f"в индексе {len(cards)} карточек, на диске {n_cards}")
    need = ("essence_ru", "when_ru", "duration_ru", "energy_ru")
    for c in cards:
        for k in need:
            if not c.get(k):
                err(f"индекс: у {c.get('name')} нет поля {k}")
        if not (ROOT / c["path"]).exists():
            err(f"индекс: нет файла {c['path']}")
    return len(cards)


def check_skills() -> int:
    """4: скиллы на месте и с валидным frontmatter."""
    if not SKILLS.exists():
        err("нет каталога skills/")
        return 0
    found = sorted(SKILLS.glob("*/SKILL.md"))
    if not found:
        err("в skills/ нет ни одного SKILL.md")
    for p in found:
        text = p.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---", text, re.S)
        if not m:
            err(f"{p.relative_to(ROOT)}: нет frontmatter")
            continue
        fm = m.group(1)
        if "name:" not in fm:
            err(f"{p.relative_to(ROOT)}: нет поля name")
        if "description:" not in fm:
            err(f"{p.relative_to(ROOT)}: нет поля description")
        # name должен совпадать с именем каталога
        name = re.search(r"^name:\s*(\S+)", fm, re.M)
        if name and name.group(1) != p.parent.name:
            err(
                f"{p.relative_to(ROOT)}: name={name.group(1)} != каталог {p.parent.name}"
            )
    return len(found)


def check_doc_links() -> int:
    """5: относительные ссылки на файлы в markdown-документах существуют."""
    docs = [ROOT / "README.md", ROOT / "NOTICE.md", ROOT / "INSTALL.md",
            ROOT / "agent-description.md"]
    docs += sorted((ROOT / "references").glob("*.md"))
    docs += sorted(SKILLS.glob("*/SKILL.md"))
    n = 0
    link_re = re.compile(r"\[[^\]]*\]\(([^)#]+?)\)")
    skip_prefix = ("http://", "https://", "mailto:", "#")
    for doc in docs:
        if not doc.exists():
            continue
        n += 1
        text = doc.read_text(encoding="utf-8")
        for raw in link_re.findall(text):
            target = raw.strip()
            if target.startswith(skip_prefix) or not target:
                continue
            rel = target.split("#")[0]
            if not rel:
                continue
            if not (doc.parent / rel).exists():
                err(f"{doc.relative_to(ROOT)}: ссылка ведёт в никуда: {target}")
    return n


def check_diagram() -> None:
    """8: диаграмма на месте и не разошлась со своей спецификацией.

    Правило из distribution-практики: артефакт, который ничего не проверяет,
    тихо устаревает. Поэтому проверяем не только наличие файлов, но и связь
    спецификации с отрендеренным HTML: если правили JSON, а HTML не
    перегенерировали, заголовок и идентификаторы view-режимов разойдутся —
    это и ловим. Полная проверка геометрии требует archify (см. CI).
    """
    spec = ROOT / "docs" / "vector-shotcraft.architecture.json"
    html = ROOT / "docs" / "vector-shotcraft.architecture.html"
    if not spec.exists():
        err("нет docs/vector-shotcraft.architecture.json (спецификация диаграммы)")
        return
    if not html.exists():
        err("нет docs/vector-shotcraft.architecture.html (отрендеренная диаграмма)")
        return

    data = json.loads(spec.read_text(encoding="utf-8"))
    text = html.read_text(encoding="utf-8")
    title = (data.get("meta") or {}).get("title")
    if title and title not in text:
        err(
            "docs/vector-shotcraft.architecture.html: не содержит заголовок из "
            f"спецификации («{title}») — HTML не перегенерирован после правки JSON"
        )
    for view in (data.get("meta") or {}).get("views") or []:
        label = view.get("label")
        if label and label not in text:
            err(
                f"docs/vector-shotcraft.architecture.html: нет view-режима «{label}» "
                "из спецификации — HTML устарел"
            )
    for doc in (ROOT / "README.md", ROOT / "agent-description.md"):
        if doc.exists() and "vector-shotcraft.architecture.html" not in doc.read_text(encoding="utf-8"):
            err(f"{doc.relative_to(ROOT)}: нет ссылки на живую диаграмму")
    page = ROOT / "docs" / "index.html"
    if page.exists() and "vector-shotcraft.architecture.html" not in page.read_text(encoding="utf-8"):
        err("docs/index.html: страница проекта не ссылается на диаграмму")


def check_readme_numbers(n_cards: int) -> None:
    """6: числа в README не разошлись с фактом."""
    readme = ROOT / "README.md"
    if not readme.exists():
        err("нет README.md")
        return
    text = readme.read_text(encoding="utf-8")
    if str(n_cards) not in text:
        err(f"README не упоминает фактическое число карточек ({n_cards})")
    cats = {p.parent.name for p in CARDS.rglob("*.md")}
    if str(len(cats)) not in text:
        err(f"README не упоминает фактическое число категорий ({len(cats)})")


def check_notice() -> None:
    """7: NOTICE.md и лицензия апстрима на месте."""
    notice = ROOT / "NOTICE.md"
    if not notice.exists():
        err("нет NOTICE.md")
        return
    text = notice.read_text(encoding="utf-8")
    for needle in ("video-shotcraft", "Apache-2.0"):
        if needle not in text:
            err(f"NOTICE.md не упоминает {needle}")
    lic = ROOT / "THIRD_PARTY_LICENSES"
    if not lic.exists() or not any(lic.iterdir()):
        err("нет THIRD_PARTY_LICENSES/ с текстом лицензии апстрима")


def main() -> int:
    n_cards = check_cards()
    check_index(n_cards)
    n_skills = check_skills()
    check_doc_links()
    check_readme_numbers(n_cards)
    check_notice()
    check_diagram()

    if errors:
        print(f"ПРОВАЛ: {len(errors)} ошибок:")
        for e in errors:
            print(" -", e)
        return 1
    cats = len({p.parent.name for p in CARDS.rglob("*.md")})
    print(
        f"OK: карточек {n_cards} в {cats} категориях, скиллов {n_skills}; "
        "провенанс, индекс, ссылки, числа README и NOTICE согласованы"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
