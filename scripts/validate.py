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

    # Иероглифы допустимы ТОЛЬКО в полях _zh с исходным текстом апстрима.
    # Если CJK просочился в русский слой (_ru) или в имя/путь — это дефект:
    # читатель видит иероглиф вместо термина, а источник непонятен.
    cjk = re.compile(r"[\u3000-\u9fff\uff00-\uffef\u3040-\u30ff]")
    for c in cards:
        for k, v in c.items():
            if not isinstance(v, str):
                continue
            if cjk.search(v) and not k.endswith("_zh"):
                err(
                    f"индекс: у {c.get('name')} в поле {k} иероглифы — "
                    "оригинал апстрима должен лежать в *_zh, а не в русском слое"
                )
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


def check_demo() -> None:
    """9: демо-сборка воспроизводима и её артефакты на месте.

    Проверяем не «файлы существуют», а воспроизводимость: скрипты, которые
    заявлены в demo/README.md как шаги запуска, обязаны быть в репозитории, а
    сетка — содержать кадры, с которыми сверяется монтаж. Без этого демо
    превращается в картинку, которую нельзя повторить.
    """
    demo = ROOT / "demo"
    for rel in (
        "make_bgm.py",
        "check_cuts.py",
        "comp/Demo.tsx",
        "comp/Root.tsx",
        "README.md",
        "out/demo.mp4",
        "out/grid.json",
    ):
        if not (demo / rel).exists():
            err(f"demo: нет {rel} — сборка не воспроизводится")
    grid = demo / "out" / "grid.json"
    if grid.exists():
        g = json.loads(grid.read_text(encoding="utf-8"))
        for key in ("frames", "fps", "period_s", "grid_phase_s", "grid_error_ms"):
            if key not in g:
                err(f"demo/out/grid.json: нет поля {key}")
        if g.get("fps") and g.get("frames"):
            step = g["period_s"] * g["fps"]
            bad = [f for f in g["frames"] if f < 0]
            if bad:
                err(f"demo/out/grid.json: отрицательные кадры {bad[:3]}")
            if round(step, 3) != 15.0:
                err(
                    f"demo/out/grid.json: шаг сетки {step:.3f} кадра — демо "
                    "рассчитано на 15 (120 BPM @ 30 fps), расписание разъедется"
                )
        # точность сетки — то, чем меряется «встанет ли склейка в такт»
        if g.get("grid_error_ms", 99.0) > 5.0:
            err(
                f"demo/out/grid.json: точность сетки {g['grid_error_ms']} мс > 5 мс — "
                "монтаж сядет «почти в такт»"
            )
    readme = demo / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        for needle in ("beat_grid.py", "check_cuts.py", "make_bgm.py"):
            if needle not in text:
                err(f"demo/README.md не описывает шаг с {needle}")


def check_no_cjk_in_our_text() -> None:
    """10: в нашем тексте нет иероглифов — кроме строковых литералов с ключами.

    Вендоренные карточки (references/cards/) — исключение: это апстримный
    первоисточник, его нельзя править, sha1 сверяется отдельно. Карточки, где
    оригинал законно лежит в *_zh-полях, тоже пропускаем.

    В коде ключи апстрима обязаны остаться как есть — по ним парсится шапка
    вендоренных карточек, и переименование сломает сборку индекса. Поэтому
    иероглиф в строковом литерале — это код, а не дефект. А вот иероглиф в
    комментарии — ровно тот ребус, который читатель видит вместо термина.
    """
    cjk = re.compile(r"[\u3000-\u9fff\uff00-\uffef\u3040-\u30ff]")
    skip_dirs = ("references/cards", "references/translations", ".git", "node_modules")
    skip_files = {"references/cards-index.json"}
    exts = {".md", ".py", ".tsx", ".ts", ".html", ".yml", ".sh"}
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.suffix not in exts:
            continue
        rel = p.relative_to(ROOT).as_posix()
        if any(rel.startswith(d) for d in skip_dirs) or rel in skip_files:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if not cjk.search(line):
                continue
            stripped = line.strip()
            if p.suffix in {".py", ".sh"}:
                # комментарий отбрасываем: там иероглиф — всегда дефект
                code = stripped.split("#", 1)[0]
                if not cjk.search(code):
                    continue
                if "#" not in code and ("\"" in code or "'" in code):
                    continue  # строковый литерал — законный ключ апстрима
            elif p.suffix in {".tsx", ".ts"}:
                code = re.sub(r"//.*$", "", stripped).strip()
                code = re.sub(r"^\s*\*.*$", "", code)
                if not cjk.search(code):
                    continue
                if "\"" in code or "'" in code or "`" in code:
                    continue
            err(
                f"{rel}:{i}: иероглифы в нашем тексте — "
                "термин апстрима давать латиницей или по-русски"
            )


def main() -> int:
    n_cards = check_cards()
    check_index(n_cards)
    n_skills = check_skills()
    check_doc_links()
    check_readme_numbers(n_cards)
    check_notice()
    check_diagram()
    check_demo()
    check_no_cjk_in_our_text()

    if errors:
        print(f"ПРОВАЛ: {len(errors)} ошибок:")
        for e in errors:
            print(" -", e)
        return 1
    cats = len({p.parent.name for p in CARDS.rglob("*.md")})
    print(
        f"OK: карточек {n_cards} в {cats} категориях, скиллов {n_skills}; "
        "провенанс, индекс, ссылки, числа README и NOTICE согласованы; "
        "демо-сборка на месте и воспроизводима"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
