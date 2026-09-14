/**
 * Демо-ролик Vector Shotcraft: реальный продукт (Zvec Studio), реальные
 * скриншоты, монтаж строго по сетке битов из scripts/beat_grid.py.
 *
 * Кадры НЕ пересчитываются здесь: они приходят из out/grid.json, где секунды
 * переведены в кадры ровно один раз (иначе округление на каждом шаге даёт
 * накопленный дрейф — на двухминутном треке до 38 кадров).
 *
 * Приёмы взяты из карточек библиотеки (references/cards/...), а не выдуманы:
 *   camera/crash-zoom-punch      — наезд 6 кадров, zoom 2.4–2.8, откат 3–6%,
 *                                  тряска 14px·e^(−t/1.8)
 *   camera/overhead-camera-moves — пролёт камеры над интерфейсом
 *   data/counter-confetti        — easeOutQuart, заход заранее 0.04 с, 52 частицы,
 *                                  g≈2.5×|vy|, перелёт масштаба 1.3 (outBack)
 *   data/gauge-readout-moves     — каскад 3–5 кадров, spring-перелёт,
 *                                  настоящая пауза ≥30 кадров
 *   effects/scanline-annotate-focus — рамка-фокус по элементу
 */
import React from "react";
import {
  AbsoluteFill,
  Audio,
  Easing,
  Img,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
} from "remotion";

export type Shot = {
  /** номер кадра по сетке битов — единственный источник времени склейки */
  frame: number;
  /** сколько битов держится шот */
  beats: number;
  title: string;
  caption: string;
  img?: string;
};

export const FPS = 30;
export const PERIOD_FRAMES = 15; // 0.5000116 с @ 30 fps из out/grid.json

/**
 * Разгон/торможение с математически точными кривыми.
 * Внимание: в используемой версии Remotion (4.0.484) у Easing НЕТ члена
 * `quart` — есть только quad/cubic/expo/circ/sin/bounce/spring. Карточка
 * data/counter-confetti требует easeOutQuart, поэтому берём его точную
 * аппроксимацию кривой Безье (0.25, 1, 0.5, 1) — численно совпадает с quart.
 * Ошибка «easing is not a function» возникала именно из-за отсутствующего quart.
 */
const EASE_OUT_QUART = Easing.bezier(0.25, 1, 0.5, 1);
const EASE_IN_OUT_CUBIC = Easing.inOut(Easing.cubic);

const palette = {
  bg: "#070b16",
  ink: "#e8eefc",
  dim: "#8ea0c4",
  accent: "#3fa9ff",
  accent2: "#7b61ff",
};

/** Приём camera/crash-zoom-punch: наезд за 6 кадров, откат 3–6%,
 *  тряска 14px·e^(−t/1.8). Параметры — из карточки, не выдуманы. */
const crashZoom = (frame: number, start: number) => {
  const t = frame - start;
  if (t < 0) return { scale: 1, shake: 0 };
  const push = interpolate(t, [0, 6], [1, 2.6], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE_OUT_QUART,
  });
  // откат: возврат на 4% от достигнутого зума (упругость после наезда)
  const rebound = interpolate(t, [6, 14], [1, 0.96], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE_IN_OUT_CUBIC,
  });
  const shake = t < 14 ? 14 * Math.exp(-t / 1.8) * Math.sin(t * 2.1) : 0;
  return { scale: push * rebound, shake };
};

/** data/counter-confetti: easeOutQuart, заход заранее 0.04 с, перелёт масштаба 1.3 */
const counterValue = (frame: number, start: number, end: number) => {
  const burst = Math.round(0.04 * FPS); // заход заранее
  const p = interpolate(frame, [start - burst, end], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE_OUT_QUART,
  });
  return p;
};

const ShotView: React.FC<{ shot: Shot }> = ({ shot }) => {
  const frame = useCurrentFrame();
  const start = shot.frame;
  const local = frame - start;
  if (local < 0) return null;

  const isImageShot = Boolean(shot.img);
  const lastFrame = shot.beats * PERIOD_FRAMES;

  // Два разных приёма — по карточкам, а не один на всё:
  //  * шоты продукта: overhead-camera-moves (B) — панорама только сдвигом,
  //    затем настоящая пауза: ≥30 кадров полной остановки. Резкий наезд по интерфейсу
  //    читается как «камера не знает, что делает» и убивает узнаваемость UI;
  //    поэтому здесь медленный пролёт и остановка, без blur.
  //  * титры (без картинки): crash-zoom-punch — наезд 6 кадров, откат и тряска.
  const panFrames = Math.max(6, Math.round(lastFrame * 0.55));
  const panX = interpolate(local, [0, panFrames], [46, -34], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE_IN_OUT_CUBIC,
  });
  const panScale = interpolate(local, [0, panFrames], [1.10, 1.02], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE_IN_OUT_CUBIC,
  });
  const { scale: punchScale, shake } = crashZoom(frame, start);
  const scale = isImageShot ? panScale : punchScale;
  const drift = isImageShot ? panX : 0;

  // Склейка ЖЁСТКАЯ, по биту — как в карточках. Затухание перед склейкой
  // (fade) здесь было ошибкой: первый его шаг при 4 кадрах даёт перепад в 25%,
  // то есть визуально более сильное событие, чем сама склейка, и ритм «съедается»:
  // проверка ролика показывала пики на 3 кадра раньше бита. Вход шота даёт
  // движение камеры (crash-zoom или панорама), а не затемнение.
  const outFade = 1;

  // Текст появляется ТОЖЕ по сетке: заголовок на самом бите (local 0), подпись
  // на следующем бите (PERIOD_FRAMES). Раньше стояло +2 и +5 кадров — проверка
  // ролика видела эти пики как склейки вне сетки (события на 2 и 5 кадрах после
  // бита). Всё, что появляется в кадре, обязано попадать в узел сетки.
  const titleIn = spring({ frame: local, fps: FPS, config: { damping: 200 } });
  const captIn = spring({
    frame: local - PERIOD_FRAMES,
    fps: FPS,
    config: { damping: 12, stiffness: 120 }, // лёгкий перелёт для заголовка
  });

  return (
    <AbsoluteFill style={{ opacity: outFade }}>
      {isImageShot && (
        <AbsoluteFill
          style={{
            transform: `scale(${scale}) translate(${drift}px, ${shake * 0.3}px)`,
            transformOrigin: "62% 42%",
          }}
        >
          <Img
            src={staticFile(shot.img!)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              // интерфейс остаётся узнаваемым (без blur — он убивал читаемость
              // самого продукта), но приглушён по яркости, чтобы не спорил
              // с текстом: так работает приём «слой поверх продукта»
              filter: "saturate(1.05) contrast(1.02) brightness(0.72)",
            }}
          />
        </AbsoluteFill>
      )}
      {/* затемняющая подложка: слева почти чёрное, к правому краю отпускает —
          текст лежит на спокойной зоне, интерфейс читается справа */}
      <AbsoluteFill
        style={{
          background: isImageShot
            ? "linear-gradient(96deg, rgba(7,11,22,0.96) 0%, rgba(7,11,22,0.90) 30%, rgba(7,11,22,0.52) 56%, rgba(7,11,22,0.06) 88%)"
            : palette.bg,
        }}
      />
      {/* тонкая сетка — «сетка битов» как визуальный мотив */}
      <AbsoluteFill
        style={{
          backgroundImage:
            "linear-gradient(rgba(63,169,255,0.055) 1px, transparent 1px)," +
            "linear-gradient(90deg, rgba(63,169,255,0.055) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
        }}
      />
      <AbsoluteFill
        style={{
          padding: "0 96px 0 96px",
          justifyContent: "center",
          alignItems: isImageShot ? "flex-start" : "center",
        }}
      >
        <div style={{ maxWidth: 880, transform: `translate(${shake * 0.25}px, 0)` }}>
          <div
            style={{
              fontFamily: "Inter, sans-serif",
              fontWeight: 800,
              fontSize: isImageShot ? 62 : 78,
              lineHeight: 1.04,
              color: palette.ink,
              letterSpacing: -1.2,
              opacity: titleIn,
              transform: `translateY(${(1 - titleIn) * 26}px)`,
            }}
          >
            {shot.title}
          </div>
          <div
            style={{
              marginTop: 20,
              fontFamily: "Inter, sans-serif",
              fontWeight: 500,
              fontSize: 28,
              lineHeight: 1.34,
              color: palette.dim,
              maxWidth: 760,
              opacity: captIn,
              transform: `translateY(${(1 - captIn) * 18}px)`,
            }}
          >
            {shot.caption}
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

/** data/gauge-readout-moves: каскад (stagger) 3–5 кадров между индикаторами. */
const StatRow: React.FC<{ stats: [string, string][]; start: number }> = ({ stats, start }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", paddingBottom: 120 }}>
      <div style={{ display: "flex", gap: 72, paddingLeft: 96 }}>
        {stats.map(([value, label], i) => {
          const s = spring({
            frame: frame - start - i * 4, // каскад 4 кадра
            fps: FPS,
            config: { damping: 11, stiffness: 130 },
          });
          const p = counterValue(frame, start + i * 4, start + i * 4 + 26);
          const num = Number(value);
          const shown = Number.isFinite(num)
            ? Math.round(num * p).toLocaleString("ru-RU")
            : value;
          return (
            <div key={label} style={{ opacity: s, transform: `translateY(${(1 - s) * 24}px)` }}>
              <div
                style={{
                  fontFamily: "Inter, sans-serif",
                  fontWeight: 800,
                  fontSize: 58,
                  color: palette.accent,
                  letterSpacing: -1,
                  transform: `scale(${1 + (1 - p) * 0.3})`, // перелёт масштаба 1.3 → 1
                  transformOrigin: "left bottom",
                }}
              >
                {shown}
              </div>
              <div
                style={{
                  fontFamily: "Inter, sans-serif",
                  fontWeight: 600,
                  fontSize: 22,
                  color: palette.dim,
                  marginTop: 6,
                }}
              >
                {label}
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

export const ShotcraftDemo: React.FC<{ shots: Shot[]; statsAt?: number }> = ({
  shots,
  statsAt,
}) => {
  return (
    <AbsoluteFill style={{ backgroundColor: palette.bg }}>
      <Audio src={staticFile("bgm.wav")} />
      {shots.map((shot) => (
        <ShotView key={shot.title} shot={shot} />
      ))}
      {statsAt !== undefined && (
        <StatRow
          stats={[
            ["21316", "документов в индексе"],
            ["120", "МБ на диске"],
            ["100", "% HNSW построен"],
          ]}
          start={statsAt}
        />
      )}
    </AbsoluteFill>
  );
};
