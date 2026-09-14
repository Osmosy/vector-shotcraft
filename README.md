<div align="center">

<img src="assets/vector-logo.png" alt="Vector Shotcraft" width="200"/>

# Vector Shotcraft

[![Architecture: live](https://img.shields.io/badge/Architecture-live_diagram-4f8ff7.svg)](https://osmosy.github.io/vector-shotcraft/docs/vector-shotcraft.architecture.html)

**Библиотека кинематографичных приёмов для продуктовых роликов — 157 карточек шотов в 10 категориях, монтаж по сетке битов, категорийный словарь звука**

[![Hermes Agent](https://img.shields.io/badge/Hermes-Agent-blue.svg)](https://github.com/NousResearch/hermes-agent)
[![Ecosystem: Vector](https://img.shields.io/badge/Ecosystem-Vector-blue.svg)](https://osmosy.github.io/)
[![Shot cards: 157](https://img.shields.io/badge/Shot%20cards-157-green.svg)](#приёмы)
[![Categories: 10](https://img.shields.io/badge/Categories-10-blueviolet.svg)](#приёмы)
[![SFX categories: 16](https://img.shields.io/badge/SFX%20categories-16-orange.svg)](references/sfx-catalog.md)
[![Source: Apache-2.0](https://img.shields.io/badge/Upstream-Apache--2.0-lightgrey.svg)](NOTICE.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Документация:** [Установка](INSTALL.md) · [Архитектура (live)](https://osmosy.github.io/vector-shotcraft/docs/vector-shotcraft.architecture.html) · [Индекс приёмов](references/cards-index.md) · [Бит-синк](references/beat-sync.md) · [Звук](references/sfx-catalog.md)

</div>

---

Библиотека приёмов для роликов о продуктах: накопленные числа, кривые ускорения
и подводные камни, а не «идеи для видео». Не готовый конвейер и не набор
компонентов: приёмы описывают, **что** делать и **с какими параметрами**,
реализация пишется под свой стек.

Второй и третий слои — то, что обычно отсутствует рядом с каталогами приёмов
и что мы разобрали сами: **монтаж по сетке битов** с рабочим инструментом и
тестами и **категорийный словарь звукового дизайна**.

## Три слоя

| Слой | Что | Где живёт |
|------|-----|-----------|
| **Приёмы** | Что и с какими числами делать | `references/cards/` + русский индекс |
| **Ритм** | Куда ставить склейки и удары | `scripts/beat_grid.py` + `references/beat-sync.md` |
| **Звук** | Что звучит под каждое действие | `references/sfx-catalog.md` (16 категорий) |

## Приёмы

157 карточек в 10 функциональных категориях. Каждая — спецификация с кадрами,
длительностями, кривыми ускорения и разделом подводных камней.

| Категория | Что это | Карточек |
|---|---|---|
| `ui-entrance` | появление элементов интерфейса | 28 |
| `typography` | типографика | 26 |
| `transition` | переходы между сценами | 19 |
| `effects` | эффекты и фактуры | 17 |
| `interaction` | интерфейс: ввод, выбор, курсор | 15 |
| `data` | данные: графики, числа, счётчики | 13 |
| `opening` | открытие и первый кадр | 11 |
| `rhythm` | ритм и монтажные склейки | 11 |
| `camera` | камера и движение в пространстве | 10 |
| `outro` | финал и логотип | 7 |

Порядок работы с библиотекой: **открытие** (один приём из `opening/`) → **тело**
(`ui-entrance/`, `interaction/`, `data/`, `camera/`) → **стыки** (`rhythm/`,
`transition/`) → **финал** (`outro/`). Тяжёлые приёмы (crash zoom, dolly-zoom,
взрыв-схема, пикирование) — не больше 1–2 раз на ролик.

## Монтаж по битам

Музыка первична: сначала сетка, потом раскадровка. Инструмент считает BPM, фазу,
допуск и готовый список кадров.

```bash
~/.venvs/shotcraft/bin/python scripts/beat_grid.py bgm.mp3 --fps 30 --json grid.json
```

```
BPM: 129.9978   T(бит): 0.4615462 с = 13.85 кадра
OK   сетка равномерная: остаток по инлайнерам ±8.0 мс (медиана 2.1 мс) <= 15 мс
OK   半/双倍 не нужен: базовая сетка точнее половинной и двойной
INFO сильных ударов в сетке (±17 мс = полкадра @ 30 fps): 12/61 = 19.7%
кадры (первый бит = 0): 21, 35, 49, 63, 77, 90, 104, ...
```

Метод устойчив к мусору в данных: скалярный tempo врёт на проценты, а бит-трекер
теряет и удваивает удары. Поэтому период ищется методом PDM по фазовому пику,
фаза — медианой сдвигов, номер бита — арифметикой, а не позицией в массиве,
затем два прохода отсева выбросов и МНК по инлайнерам. Кадры считаются **один
раз и в самом конце**: округление каждого шага до целого кадра даёт дрейф до
38 кадров к концу двухминутного трека. Подробно — [references/beat-sync.md](references/beat-sync.md).

## Звук по категориям

16 категорий, порядок жёсткий: **сначала категория по действию в кадре, потом
тембр**. Движение камеры — `transition/`, приземление — `impact/`, свет —
`light/` (каталога `sparkle/` не существует, хотя слово из словаря именно
такое), печать — `text/`. Аудиофайлы не включены: это лицензируемые активы, а
у 6 файлов апстрима источник не установлен. Словарь говорит, что искать и где.

Порядок работ: сначала картинка → потом BGM → потом точечные звуки по тактам
сетки → в конце версия без BGM (для площадок, где музыка не допускается).

## Как это работает

```
Апстрим video-shotcraft (Apache-2.0)
        │  vendor_cards.py: копия байт-в-байт + шапка провенанса + SHA1
        ▼
references/cards/ (157, оригинальный текст)
        │  build_index.py + apply_translations.py
        ▼
references/cards-index.md (русский индекс: что делает, когда брать)
        │                                    BGM ──► beat_grid.py ──► grid.json (кадры)
        ▼                                                            │
Раскадровка: приёмы + параметры в кадрах ◄──────────────────────────┘
        │
        ▼
Монтаж и рендер (свой стек) + звук по категориям из sfx-catalog.md
```

Живая диаграмма: [docs/vector-shotcraft.architecture.html](docs/vector-shotcraft.architecture.html)
(5 стадий, guided views, dark/light, экспорт PNG/SVG).

## Быстрый старт

```bash
git clone https://github.com/Osmosy/vector-shotcraft.git
cd vector-shotcraft

# Приёмы — это markdown, работает сразу
less references/cards-index.md
less references/cards/camera/crash-zoom-punch.md

# Для сетки битов — окружение
uv venv ~/.venvs/shotcraft
uv pip install --python ~/.venvs/shotcraft/bin/python librosa soundfile numpy scipy
~/.venvs/shotcraft/bin/python scripts/beat_grid.py bgm.mp3 --fps 30 --json grid.json

# Проверить сам инструмент на синтетике с известным темпом
~/.venvs/shotcraft/bin/python tests/test_beat_grid.py
```

Ни Node, ни Remotion для использования репозитория не нужны — они понадобятся
только если вы будете рендерить в Remotion в своём проекте. Пошаговое пояснение
для внешнего пользователя: [INSTALL.md](INSTALL.md).

Проверки перед коммитом (то же гоняет CI):

```bash
python3 scripts/validate.py                        # провенанс, индекс, ссылки, числа
python3 tests/test_beat_grid.py                    # сетка на известном темпе
```

## Структура репозитория

```
vector-shotcraft/
├── README.md
├── INSTALL.md                      ← как поставить и использовать (для внешнего пользователя)
├── NOTICE.md · LICENSE             ← атрибуция апстрима + MIT
├── agent-description.md            ← краткое описание для агентов
├── assets/                         ← логотипы
├── docs/
│   ├── index.html                  ← страница проекта (GitHub Pages)
│   ├── vector-shotcraft.architecture.json   ← спецификация диаграммы
│   └── vector-shotcraft.architecture.html   ← живая диаграмма (archify)
├── references/
│   ├── cards/                      ← 157 карточек, 10 категорий, оригинальный текст
│   │   ├── camera/  data/  effects/  interaction/  opening/
│   │   └── outro/  rhythm/  transition/  typography/  ui-entrance/
│   ├── cards-index.md              ← русский индекс (суть, когда брать, длительность)
│   ├── cards-index.json            ← то же машиночитаемо
│   ├── cards-manifest.json         ← SHA1 и источники всех карточек
│   ├── translations/               ← исходники русских полей индекса
│   ├── beat-sync.md                ← методика монтажа по сетке битов
│   └── sfx-catalog.md              ← 16 категорий звука
├── scripts/
│   ├── beat_grid.py                ← сетка битов: BPM, фаза, кадры, вердикт
│   ├── vendor_cards.py             ← вендоринг карточек из апстрима
│   ├── build_index.py              ← сборка индекса из карточек
│   ├── apply_translations.py       ← подстановка русских полей
│   └── validate.py                 ← валидатор репозитория
├── tests/test_beat_grid.py         ← проверка сетки на известном темпе
├── skills/vector-shotcraft/        ← навык для агента
├── THIRD_PARTY_LICENSES/           ← текст лицензии апстрима
└── .github/workflows/validate.yml  ← CI: валидация + пересборка индекса + тест
```

## Ключевые решения и грабли

- **Числа важнее гладкости перевода.** Карточки лежат на языке оригинала:
  машинный перевод «улучшает» кадры и соотношения и ломает спецификацию.
  Русский слой — отдельный индекс; апстримный текст защищён сверкой SHA1,
  подмена одного байта делает CI красным.
- **Переводы лежат в репозитории, а не в /tmp.** Иначе индекс невоспроизводим:
  первый CI-прогон упал именно на этом — шаг пересборки стирал русские поля.
- **Сетку битов нельзя строить по скаляру tempo** и нельзя пересчитывать кадры
  вручную на каждом шаге (дрейф до 38 кадров на две минуты).
- **Устойчивость к выбросам — не оптимизация, а необходимость.** Один
  «фантомный» бит на затухании без второго прохода отсева давал 60 мс остатка
  на двухминутном треке вместо 10.
- **Аудиофайлы не переносятся.** Категории — знание, файлы — лицензии и вес.

## Экосистема Vector

| Проект | Что это |
|--------|---------|
| [Vector Work](https://github.com/Osmosy/vector-work) | Хаб экосистемы |
| [Vector Marketing](https://github.com/Osmosy/vector-marketing) | Маркетинговое AI-агентство на Hermes Agent |
| [Vector Brain](https://github.com/Osmosy/vector-brain) | Локальная база знаний: гибридный поиск по markdown |
| [Vector Prediction](https://github.com/Osmosy/vector-prediction) | Гибридный прогнозный пайплайн |

## Источник и лицензии

Приёмы вендорены из [Vincentwei1021/video-shotcraft](https://github.com/Vincentwei1021/video-shotcraft)
(Apache-2.0, © Wei Yihao) — 157 карточек байт-в-байт, сверху шапка провенанса.
Методика бит-синка и словарь звука — наша переработка материалов оттуда же.

Приёмы разобраны с чужих опубликованных промо-роликов (Notion, Figma, Slack,
Framer, Raycast, Perplexity, ClickUp, Bear, Pitch, Miro, Superhuman, Loom и работ
отдельных моушн-дизайнеров): взято ремесло — тайминги, эластика, компоновка, —
реализации переписаны с нуля, брендовых элементов нет. Практический вывод для
коммерческого использования — в [NOTICE.md](NOTICE.md).

Remotion, на который ориентирован апстрим, имеет собственную лицензию: физлицам
и малым командам бесплатно, крупным компаниям нужна платная. Приёмы переносимы
в любой стек — это тайминги и кривые, а не API.

### Журнал версий

| Дата | Что обновлено |
|------|---------------|
| 2026-09-14 | init: 157 карточек в 10 категориях (вендор video-shotcraft, Apache-2.0); русский индекс по всем 157; бит-синк `scripts/beat_grid.py` + методика + тест на синтетике; категорийный словарь звука (16 категорий); навык `skills/vector-shotcraft/`; валидатор провенанса по SHA1 и CI; живая archify-диаграмма; страница проекта на Pages |

**Лицензия:** MIT (см. [LICENSE](LICENSE)). Сторонние компоненты и их лицензии — в [NOTICE.md](NOTICE.md).
