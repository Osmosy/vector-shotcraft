#!/usr/bin/env python3
"""Вендоринг карточек шотов из апстрима video-shotcraft.

Что делает: скачивает файлы карточек из references/shots/<категория>/<имя>.md
апстрима и кладёт их в references/cards/<категория>/<имя>.md, НЕ меняя
апстримный текст. Сверху дописывается русский шапка-блок с провенансом
(имя, категория, источник, SHA1 апстримного файла).

Зачем шапка, а не перевод: карточка — это спецификация с числами (кадры,
эйзинги, параметры). Машинный перевод чисел «улучшает» их и ломает смысл;
русский слой живёт отдельно (references/cards-index.md и skills/).

Идемпотентность: повторный прогон не дублирует шапку (проверка по маркеру).

Запуск:
  python3 scripts/vendor_cards.py                 # все карточки
  python3 scripts/vendor_cards.py --list          # что было бы скачано
  python3 scripts/vendor_cards.py --only camera   # одна категория
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

UPSTREAM_REPO = "Vincentwei1021/video-shotcraft"
UPSTREAM_REF = "HEAD"
RAW = f"https://raw.githubusercontent.com/{UPSTREAM_REPO}/{UPSTREAM_REF}"
TREE_API = f"https://api.github.com/repos/{UPSTREAM_REPO}/git/trees/{UPSTREAM_REF}?recursive=1"
LICENSE = "Apache-2.0"
MARKER = "<!-- vendored: video-shotcraft -->"
END_MARKER = "<!-- /vendored -->"

ROOT = Path(__file__).resolve().parents[1]
CARDS_DIR = ROOT / "references" / "cards"
MANIFEST = ROOT / "references" / "cards-manifest.json"


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def upstream_cards() -> list[str]:
    tree = json.loads(fetch(TREE_API))["tree"]
    return sorted(
        t["path"]
        for t in tree
        if t["path"].startswith("references/shots/")
        and t["path"].endswith(".md")
        and not t["path"].endswith("ATTRIBUTION.md")
    )


def header(rel: str, sha1: str) -> str:
    name = Path(rel).stem
    category = rel.split("/")[2]
    return (
        f"{MARKER}\n"
        f"<!-- name: {name} | category: {category} | upstream: {rel} -->\n"
        f"<!-- source: https://github.com/{UPSTREAM_REPO}/blob/{UPSTREAM_REF}/{rel} -->\n"
        f"<!-- license: {LICENSE} (© Wei Yihao) | upstream_sha1: {sha1} -->\n"
        "\n"
        "> Ниже — оригинальный текст карточки на языке оригинала, без правок.\n"
        "> Числа и параметры в нём — источник истины; русский разбор — в\n"
        "> `references/cards-index.md` и в скилле.\n"
        f"{END_MARKER}\n\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Вендоринг карточек шотов")
    ap.add_argument("--list", action="store_true", help="только показать список")
    ap.add_argument("--only", help="только одна категория (например camera)")
    ap.add_argument("--force", action="store_true", help="перекачать существующие")
    args = ap.parse_args()

    rels = upstream_cards()
    if args.only:
        rels = [r for r in rels if r.split("/")[2] == args.only]
    if args.list:
        for r in rels:
            print(r)
        print(f"всего: {len(rels)}")
        return 0
    if not rels:
        print("ОШИБКА: апстрим не вернул ни одной карточки", file=sys.stderr)
        return 1

    manifest: dict[str, dict] = {}
    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    new = updated = skipped = 0
    for rel in rels:
        raw = fetch(f"{RAW}/{rel}")
        sha1 = hashlib.sha1(raw).hexdigest()
        dest = CARDS_DIR / "/".join(rel.split("/")[2:])
        dest.parent.mkdir(parents=True, exist_ok=True)

        prev = manifest.get(rel)
        if dest.exists() and prev and prev["sha1"] == sha1 and not args.force:
            skipped += 1
            continue

        text = raw.decode("utf-8")
        dest.write_text(header(rel, sha1) + text, encoding="utf-8")
        manifest[rel] = {
            "sha1": sha1,
            "bytes": len(raw),
            "category": rel.split("/")[2],
            "upstream": f"https://github.com/{UPSTREAM_REPO}/blob/{UPSTREAM_REF}/{rel}",
            "vendored_header": True,
        }
        if prev:
            updated += 1
        else:
            new += 1
        print(f"  + {rel}  sha1={sha1[:12]}  {len(raw)}b")

    MANIFEST.write_text(
        json.dumps(dict(sorted(manifest.items())), ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(
        f"\nвсего в апстриме: {len(rels)} | новых: {new} | обновлено: {updated} | "
        f"без изменений: {skipped}\nманифест: {MANIFEST.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
