/**
 * Корень композиции. Расписание берётся из out/grid.json — файла, который
 * построил scripts/beat_grid.py по реальному аудио. Здесь НЕЛЬЗЯ пересчитывать
 * секунды в кадры: единственное место такого перевода — сам инструмент.
 * Поэтому кадры склейек читаются из сетки по номеру бита.
 */
import React from "react";
import { Composition } from "remotion";
import grid from "../out/grid.json";
import { FPS, ShotcraftDemo, type Shot } from "./Demo";

const frames: number[] = grid.frames;

/** Шот начинается на бите `bit` и держится `beats` битов. */
const at = (bit: number) => {
  const f = frames[bit];
  if (f === undefined) throw new Error(`нет бита №${bit} в сетке (всего ${frames.length})`);
  return f;
};

const schedule: Shot[] = [
  {
    frame: at(0),
    beats: 6,
    title: "Монтаж по сетке битов",
    caption:
      "Склейки стоят по ударам, а не «примерно в такт». Всё расписание — из реального аудио: 120 BPM, шаг 15 кадров при 30 fps.",
  },
  {
    frame: at(6),
    beats: 4,
    title: "Точность ниже кадра",
    caption:
      "Медиана отклонения ударов от узлов сетки — 3 мс при полкадре 16.7 мс. Фаза ищется по максимуму энергии, а не по выводу бит-трекера.",
    img: "shots/raw-01-overview.png",
  },
  {
    frame: at(10),
    beats: 6,
    title: "21 316 документов в индексе",
    caption:
      "Реальная коллекция: HNSW построен на 100%, 120 МБ, 7 полей. Экран снят с живого продукта, не нарисован.",
    img: "shots/raw-02-browse.png",
  },
  {
    frame: at(16),
    beats: 6,
    title: "Запрос собирается без кода",
    caption:
      "Выбор эмбеддинга, топ-K, выходные поля и фильтр — в панели запроса. Скриншот рабочего экрана Zvec Studio.",
    img: "shots/raw-03-query.png",
  },
  {
    frame: at(22),
    beats: 5,
    title: "Слой поверх продукта",
    caption:
      "Приёмы взяты из карточек библиотеки: наезд за 6 кадров, откат 4%, затухающая тряска 14px·e^(−t/1.8).",
    img: "shots/raw-04-query-result.png",
  },
  {
    frame: at(27),
    beats: 7,
    title: "Vector Shotcraft",
    caption:
      "157 карточек приёмов · 16 категорий звука · методика монтажа по битам · бит-сетка с проверкой точности",
  },
];

const totalFrames = at(34);

export const RemotionRoot: React.FC = () => (
  <Composition
    id="ShotcraftDemo"
    component={ShotcraftDemo}
    durationInFrames={totalFrames}
    fps={FPS}
    width={1600}
    height={900}
    defaultProps={{ shots: schedule, statsAt: at(30) }}
  />
);
