# vector-shotcraft — часть экосистемы Vector

Библиотека приёмов для продуктовых роликов: 157 карточек шотов с параметрами в
10 категориях, методика монтажа по сетке битов с рабочим инструментом и тестами,
категорийный словарь звукового дизайна (16 категорий).

Содержание — не программа, а справочник и методики: markdown-карточки, два
разбора и один скрипт. Единственная исполняемая часть — `scripts/beat_grid.py`
(сетка битов под BGM).

## Связанные проекты

- Хаб экосистемы: https://github.com/Osmosy/vector-work
- База знаний с гибридным поиском: https://github.com/Osmosy/vector-brain
- Прогноз спроса: https://github.com/Osmosy/vector-prediction

## Для агентов

- Читай сначала `README.md`, для установки — `INSTALL.md`
- Приёмы — `references/cards/<категория>/<имя>.md` (оригинальный текст с числами)
- Русский индекс — `references/cards-index.md` (что делает, когда брать)
- Методики — `references/beat-sync.md`, `references/sfx-catalog.md`
- Архитектура (живая диаграмма) — `docs/vector-shotcraft.architecture.html`
- Навык — `skills/vector-shotcraft/SKILL.md`
- Перед коммитом прогоняй: `python3 scripts/validate.py` и
  `python3 tests/test_beat_grid.py` (то же выполняет CI в
  `.github/workflows/validate.yml`)
- Карточки не редактировать руками: обновление только через
  `python3 scripts/vendor_cards.py` (валидатор сверяет SHA1 тела каждой карточки
  с манифестом)

## Состав

| Что | Сколько |
|-----|---------|
| Карточки шотов | 157 (`references/cards/`) в 10 категориях |
| Русский индекс | 157 записей (`references/cards-index.md`) |
| Методики | 2 (`references/beat-sync.md`, `references/sfx-catalog.md`) |
| Категорий звука | 16 (`references/sfx-catalog.md`) |
| Скрипты | 5 (`scripts/`) |
| Тесты | 1 (`tests/test_beat_grid.py`, 4 случая на синтетике) |
| Навыки | 1 (`skills/vector-shotcraft/`) |
| Диаграмма | 1 живая (`docs/vector-shotcraft.architecture.html`) |

## Источник и лицензии

Карточки вендорены из [Vincentwei1021/video-shotcraft](https://github.com/Vincentwei1021/video-shotcraft)
(Apache-2.0, © Wei Yihao) — тексты без изменений, сверху шапка провенанса.
Методика бит-синка и словарь звука — переработка материалов оттуда же.
Полные тексты лицензий: `THIRD_PARTY_LICENSES/`, сводка: `NOTICE.md`.
Репозиторий: MIT.
