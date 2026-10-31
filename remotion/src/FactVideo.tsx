import React, {useMemo} from "react";
import {
  AbsoluteFill,
  Audio,
  OffthreadVideo,
  Sequence,
  continueRender,
  delayRender,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {loadFont} from "@remotion/fonts";
import poppins700 from "@fontsource/poppins/files/poppins-latin-700-normal.woff2";
import poppins800 from "@fontsource/poppins/files/poppins-latin-800-normal.woff2";

// Font dibundel dari paket npm (tidak bergantung pada internet saat render)
const fontFamily = "Poppins";
const fontHandle = delayRender("Memuat font Poppins");
Promise.all([
  loadFont({family: fontFamily, url: poppins700, weight: "700"}),
  loadFont({family: fontFamily, url: poppins800, weight: "800"}),
])
  .then(() => continueRender(fontHandle))
  .catch((err) => {
    console.error("Gagal memuat font:", err);
    continueRender(fontHandle);
  });

export const FPS = 30;

export type Word = {t: string; s: number; e: number};

export type FactProps = {
  hook: string; // kalimat pembuka (besar di 2-3 detik pertama)
  label: string; // nama kanal, tampil di atas
  words: Word[]; // semua kata yang diucapkan (termasuk kata hook), dalam detik
  hookWordCount: number; // jumlah kata awal yang termasuk hook
  hookEnd: number; // detik saat hook selesai diucapkan
  durationSec: number;
  clips: string[]; // klip latar, mis. "job/bg0.mp4" (relatif ke folder public)
  audio: string; // mis. "job/voice.mp3"; kosong = tanpa suara
  accent: string; // warna aksen
};

export const defaultProps: FactProps = {
  hook: "Your banana is slightly radioactive.",
  label: "DAILY FACT BITES",
  words: "Your banana is slightly radioactive. Bananas hold natural potassium, and a tiny part of it is radioactive. The amount is harmless. Follow for more."
    .split(" ")
    .map((t, i) => ({t, s: i * 0.38, e: i * 0.38 + 0.34})),
  hookWordCount: 5,
  hookEnd: 5 * 0.38 + 0.1,
  durationSec: 14,
  clips: [],
  audio: "",
  accent: "#FFC400",
};

const clampBoth = {extrapolateLeft: "clamp", extrapolateRight: "clamp"} as const;

// ---------- Latar: klip bergantian dengan zoom pelan, atau gradasi bila tidak ada klip ----------
const Clip: React.FC<{src: string; len: number; flip: boolean}> = ({src, len, flip}) => {
  const frame = useCurrentFrame();
  const scale = interpolate(frame, [0, len], flip ? [1.14, 1.0] : [1.0, 1.14], clampBoth);
  return (
    <AbsoluteFill style={{overflow: "hidden"}}>
      <OffthreadVideo
        src={staticFile(src)}
        muted
        style={{width: "100%", height: "100%", objectFit: "cover", transform: `scale(${scale})`}}
      />
    </AbsoluteFill>
  );
};

const Background: React.FC<{clips: string[]}> = ({clips}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  if (clips.length === 0) {
    const angle = 160 + interpolate(frame, [0, durationInFrames], [0, 70]);
    return (
      <AbsoluteFill
        style={{background: `linear-gradient(${angle}deg, #0b1d3a 0%, #1f4aa0 50%, #0b1d3a 100%)`}}
      />
    );
  }
  const seg = Math.ceil(durationInFrames / clips.length);
  return (
    <AbsoluteFill style={{backgroundColor: "#000"}}>
      {clips.map((c, i) => {
        const from = i * seg;
        const len = Math.min(seg, durationInFrames - from);
        if (len <= 0) return null;
        return (
          <Sequence key={c} from={from} durationInFrames={len}>
            <Clip src={c} len={len} flip={i % 2 === 1} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

// ---------- Hook besar di awal ----------
const HookBig: React.FC<{text: string; end: number; accent: string}> = ({text, end, accent}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const endF = Math.round(end * fps);
  const pop = spring({frame, fps, config: {damping: 12, stiffness: 150, mass: 0.7}});
  const fade = interpolate(frame, [endF - 8, endF], [1, 0], clampBoth);
  const grow = interpolate(frame, [endF - 8, endF], [1, 1.08], clampBoth);
  const scale = interpolate(pop, [0, 1], [0.7, 1]) * grow;
  const size = text.length > 70 ? 80 : text.length > 42 ? 94 : 108;
  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        padding: "0 64px 160px 64px",
        opacity: fade,
        transform: `scale(${scale})`,
      }}
    >
      <div
        style={{
          fontFamily,
          fontWeight: 800,
          fontSize: size,
          lineHeight: 1.12,
          textAlign: "center",
          color: "#fff",
          WebkitTextStroke: "14px #000",
          paintOrder: "stroke fill",
          textShadow: "0 12px 40px rgba(0,0,0,0.55)",
        }}
      >
        {text}
      </div>
      <div style={{marginTop: 40, width: 240, height: 16, borderRadius: 8, background: accent}} />
    </AbsoluteFill>
  );
};

// ---------- Judul kecil di atas setelah hook selesai ----------
const HookTop: React.FC<{text: string; start: number}> = ({text, start}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = Math.round(start * fps);
  const o = interpolate(frame, [s, s + 10], [0, 1], clampBoth);
  const y = interpolate(frame, [s, s + 10], [-24, 0], clampBoth);
  return (
    <div
      style={{
        position: "absolute",
        top: 210,
        left: 56,
        right: 56,
        opacity: o,
        transform: `translateY(${y}px)`,
        textAlign: "center",
        fontFamily,
        fontWeight: 700,
        fontSize: 46,
        lineHeight: 1.22,
        color: "#fff",
        background: "rgba(0,0,0,0.5)",
        borderRadius: 30,
        padding: "22px 32px",
      }}
    >
      {text}
    </div>
  );
};

// ---------- Teks per kata (kata yang sedang diucapkan disorot) ----------
const makeChunks = (words: Word[]): Word[][] => {
  const chunks: Word[][] = [];
  let cur: Word[] = [];
  for (const w of words) {
    const len = [...cur, w].map((x) => x.t).join(" ").length;
    if (cur.length > 0 && (cur.length >= 3 || len > 18)) {
      chunks.push(cur);
      cur = [];
    }
    cur.push(w);
    if (/[.?!,]$/.test(w.t)) {
      chunks.push(cur);
      cur = [];
    }
  }
  if (cur.length > 0) chunks.push(cur);
  return chunks;
};

const Captions: React.FC<{words: Word[]; accent: string}> = ({words, accent}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const chunks = useMemo(() => makeChunks(words), [words]);

  let idx = -1;
  for (let i = 0; i < chunks.length; i++) {
    if (t >= chunks[i][0].s - 0.05) idx = i;
    else break;
  }
  if (idx < 0) return null;
  const chunk = chunks[idx];
  const last = chunk[chunk.length - 1];
  if (t > last.e + 0.6) return null;

  let active = 0;
  chunk.forEach((w, i) => {
    if (t >= w.s - 0.02) active = i;
  });
  const pop = spring({
    frame: frame - Math.round(chunk[0].s * fps),
    fps,
    config: {damping: 13, stiffness: 220, mass: 0.5},
  });
  const scale = interpolate(pop, [0, 1], [0.85, 1]);

  return (
    <div
      style={{
        position: "absolute",
        left: 50,
        right: 50,
        bottom: 470,
        display: "flex",
        justifyContent: "center",
        transform: `scale(${scale})`,
      }}
    >
      <div
        style={{
          maxWidth: 980,
          fontFamily,
          fontWeight: 800,
          fontSize: 92,
          lineHeight: 1.18,
          textAlign: "center",
          textTransform: "uppercase",
        }}
      >
        {chunk.map((w, i) => (
          <span
            key={`${idx}-${i}`}
            style={{
              display: "inline-block",
              marginRight: 22,
              color: i === active ? accent : "#fff",
              WebkitTextStroke: "14px #000",
              paintOrder: "stroke fill",
            }}
          >
            {w.t.replace(/[.,!?]+$/, "")}
          </span>
        ))}
      </div>
    </div>
  );
};

const Badge: React.FC<{label: string; accent: string}> = ({label, accent}) => (
  <div style={{position: "absolute", top: 96, left: 0, right: 0, display: "flex", justifyContent: "center"}}>
    <div
      style={{
        fontFamily,
        fontWeight: 800,
        fontSize: 36,
        letterSpacing: 4,
        color: "#111",
        background: accent,
        padding: "10px 30px",
        borderRadius: 999,
      }}
    >
      {label}
    </div>
  </div>
);

const Progress: React.FC<{accent: string}> = ({accent}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        bottom: 0,
        height: 14,
        width: `${(frame / durationInFrames) * 100}%`,
        background: accent,
      }}
    />
  );
};

export const FactVideo: React.FC<FactProps> = (p) => {
  const hookEnd = Math.max(p.hookEnd, 1.8);
  const captionWords = p.words.slice(p.hookWordCount);
  return (
    <AbsoluteFill style={{backgroundColor: "#000"}}>
      <Background clips={p.clips} />
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(to bottom, rgba(0,0,0,0.6) 0%, rgba(0,0,0,0.12) 35%, rgba(0,0,0,0.12) 55%, rgba(0,0,0,0.72) 100%)",
        }}
      />
      {p.audio ? <Audio src={staticFile(p.audio)} /> : null}
      <Captions words={captionWords} accent={p.accent} />
      <HookTop text={p.hook} start={hookEnd - 0.1} />
      <Sequence from={0} durationInFrames={Math.round((hookEnd + 0.1) * FPS)} layout="none">
        <HookBig text={p.hook} end={hookEnd} accent={p.accent} />
      </Sequence>
      <Badge label={p.label} accent={p.accent} />
      <Progress accent={p.accent} />
    </AbsoluteFill>
  );
};
