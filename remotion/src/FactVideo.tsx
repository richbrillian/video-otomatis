import React, {useMemo} from "react";
import {
  AbsoluteFill,
  Audio,
  OffthreadVideo,
  Sequence,
  continueRender,
  delayRender,
  interpolate,
  random,
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
  pill?: string; // teks label di atas hook (default "DID YOU KNOW?")
  stickman?: boolean; // tampilkan karakter stickman + ajakan follow di tengah video (default true)
  ctaAt?: number; // detik munculnya ajakan follow di tengah video (default 8)
  cta?: string; // teks kecil di bawah "FOLLOW"
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

// ---------- Latar: klip video bergantian dengan zoom pelan, atau gradasi bila tidak ada klip ----------
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

// ---------- Latar animasi hasil kode: gradasi bergerak, bola cahaya, cincin, partikel, sapuan cahaya ----------
const PALET: Record<string, [string, string]> = {
  "#FFC400": ["#1b0f3a", "#5b2a86"],
  "#00E5FF": ["#04122e", "#0b4a8f"],
  "#FF4D8D": ["#2a0a2e", "#8a1c5c"],
  "#7CFF6B": ["#06241a", "#0f6b4a"],
};

const Scene: React.FC<{accent: string; overlay?: boolean}> = ({accent, overlay}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = frame / fps;
  const [c1, c2] = PALET[accent] ?? ["#0b1d3a", "#1f4aa0"];
  const drift = 1.06 + 0.03 * Math.sin(t * 0.6);
  const sweepX = interpolate((t % 4.5) / 4.5, [0, 1], [-1400, width + 600]);
  return (
    <AbsoluteFill
      style={{
        overflow: "hidden",
        ...(overlay
          ? {mixBlendMode: "screen" as const, opacity: 0.55}
          : {background: `linear-gradient(${160 + t * 9}deg, ${c1} 0%, ${c2} 55%, ${c1} 100%)`}),
      }}
    >
      <AbsoluteFill style={{transform: `scale(${drift}) rotate(${Math.sin(t * 0.4) * 1.5}deg)`}}>
        {Array.from({length: 6}).map((_, i) => {
          const x = width * (0.5 + 0.42 * Math.sin(t * (0.32 + 0.11 * i) + i * 1.7));
          const y = height * (0.5 + 0.42 * Math.cos(t * (0.26 + 0.09 * i) + i * 2.3));
          const r = 300 + i * 55;
          const col = i % 2 === 0 ? accent : c2;
          return (
            <div
              key={`b${i}`}
              style={{
                position: "absolute",
                left: x - r,
                top: y - r,
                width: r * 2,
                height: r * 2,
                borderRadius: "50%",
                background: `radial-gradient(circle, ${col}${i % 2 === 0 ? "55" : "99"} 0%, transparent 68%)`,
              }}
            />
          );
        })}
        {[0, 1, 2].map((i) => {
          const p = (t * 0.45 + i / 3) % 1;
          const size = 220 + p * 1500;
          return (
            <div
              key={`r${i}`}
              style={{
                position: "absolute",
                left: width / 2 - size / 2,
                top: height * 0.5 - size / 2,
                width: size,
                height: size,
                borderRadius: "50%",
                border: `7px solid ${accent}`,
                opacity: (1 - p) * 0.28,
              }}
            />
          );
        })}
        {Array.from({length: 30}).map((_, i) => {
          const speed = 70 + random(`sp${i}`) * 160;
          const size = 8 + random(`sz${i}`) * 26;
          const x = random(`px${i}`) * width + Math.sin(t * 0.9 + i) * 34;
          const y = height + 60 - ((t * speed + random(`py${i}`) * height) % (height + 120));
          const col = i % 3 === 0 ? accent : "#ffffff";
          return (
            <div
              key={`p${i}`}
              style={{
                position: "absolute",
                left: x,
                top: y,
                width: size,
                height: size,
                borderRadius: i % 4 === 0 ? 4 : "50%",
                background: col,
                opacity: 0.14 + random(`op${i}`) * 0.4,
                transform: `rotate(${t * 60 * (i % 2 ? 1 : -1)}deg)`,
              }}
            />
          );
        })}
      </AbsoluteFill>
      <div
        style={{
          position: "absolute",
          top: -200,
          left: sweepX,
          width: 260,
          height: height + 400,
          transform: "rotate(18deg)",
          background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.10), transparent)",
        }}
      />
    </AbsoluteFill>
  );
};

const Background: React.FC<{clips: string[]; accent: string}> = ({clips, accent}) => {
  const {durationInFrames} = useVideoConfig();
  const seg = Math.ceil(durationInFrames / Math.max(1, clips.length));
  const [c1] = PALET[accent] ?? ["#0b1d3a", "#1f4aa0"];
  // Tanpa klip: animasi penuh. Dengan klip: footage jadi dasar, animasi kode digabung di atasnya.
  if (clips.length === 0) return <Scene accent={accent} />;
  return (
    <AbsoluteFill style={{backgroundColor: "#000"}}>
      <Scene accent={accent} />
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
      <AbsoluteFill style={{background: c1, opacity: 0.22}} />
      <Scene accent={accent} overlay />
    </AbsoluteFill>
  );
};

// ---------- Hook besar di awal: pill "DID YOU KNOW?", kata muncul satu-satu, kata terakhir disorot ----------
const HookBig: React.FC<{text: string; end: number; accent: string; pill?: string}> = ({text, end, accent, pill: pillText}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const endF = Math.round(end * fps);
  const fade = interpolate(frame, [endF - 8, endF], [1, 0], clampBoth);
  const lift = interpolate(frame, [endF - 8, endF], [0, -40], clampBoth);
  const words = text.split(" ").filter(Boolean);
  const size = text.length > 70 ? 82 : text.length > 42 ? 98 : 116;
  const pill = spring({frame, fps, config: {damping: 16, stiffness: 300, mass: 0.5}});
  const barW = interpolate(
    spring({frame: frame - 3 - words.length, fps, config: {damping: 16, stiffness: 200}}),
    [0, 1],
    [0, 360],
  );
  const hiFrom = Math.max(0, words.length - 2); // dua kata terakhir disorot
  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        padding: "0 56px 150px 56px",
        opacity: fade,
        transform: `translateY(${lift}px)`,
      }}
    >
      <div
        style={{
          fontFamily,
          fontWeight: 800,
          fontSize: 44,
          letterSpacing: 6,
          color: "#111",
          background: accent,
          padding: "12px 38px",
          borderRadius: 999,
          marginBottom: 46,
          transform: `scale(${interpolate(pill, [0, 1], [0.4, 1])}) rotate(-3deg)`,
          boxShadow: "0 10px 0 rgba(0,0,0,0.55)",
        }}
      >
        {pillText ?? "DID YOU KNOW?"}
      </div>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          columnGap: 26,
          rowGap: 4,
          fontFamily,
          fontWeight: 800,
          fontSize: size,
          lineHeight: 1.12,
          textAlign: "center",
          textTransform: "uppercase",
        }}
      >
        {words.map((w, i) => {
          const sp = spring({
            frame: frame - i,
            fps,
            config: {damping: 14, stiffness: 300, mass: 0.5},
          });
          return (
            <span
              key={i}
              style={{
                display: "inline-block",
                color: i >= hiFrom ? accent : "#fff",
                WebkitTextStroke: "16px #000",
                paintOrder: "stroke fill",
                opacity: interpolate(sp, [0, 1], [0, 1]),
                transform: `translateY(${interpolate(sp, [0, 1], [60, 0])}px) scale(${interpolate(sp, [0, 1], [0.6, 1])})`,
                textShadow: "0 14px 36px rgba(0,0,0,0.5)",
              }}
            >
              {w}
            </span>
          );
        })}
      </div>
      <div style={{marginTop: 44, width: barW, height: 20, borderRadius: 10, background: accent, boxShadow: "0 8px 0 rgba(0,0,0,0.55)"}} />
    </AbsoluteFill>
  );
};

// ---------- Judul kecil di atas setelah hook selesai (kartu dengan garis aksen) ----------
const HookTop: React.FC<{text: string; start: number; accent: string}> = ({text, start, accent}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = Math.round(start * fps);
  const o = interpolate(frame, [s, s + 10], [0, 1], clampBoth);
  const y = interpolate(frame, [s, s + 10], [-24, 0], clampBoth);
  return (
    <div
      style={{
        position: "absolute",
        top: 200,
        left: 56,
        right: 56,
        opacity: o,
        transform: `translateY(${y}px)`,
        display: "flex",
        background: "rgba(0,0,0,0.62)",
        borderRadius: 28,
        overflow: "hidden",
      }}
    >
      <div style={{width: 16, background: accent, flexShrink: 0}} />
      <div
        style={{
          padding: "22px 30px",
          fontFamily,
          fontWeight: 700,
          fontSize: 46,
          lineHeight: 1.22,
          color: "#fff",
        }}
      >
        {text}
      </div>
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
              marginRight: 36,
              color: i === active ? accent : "#fff",
              WebkitTextStroke: "14px #000",
              paintOrder: "stroke fill",
              transform: i === active ? "scale(1.14) rotate(-2deg)" : "none",
            }}
          >
            {w.t.replace(/[.,!?]+$/, "")}
          </span>
        ))}
      </div>
    </div>
  );
};

// ---------- Stickman: bereaksi kaget saat hook, bergaya santai, menunjuk ajakan follow, lompat senang ----------
const dir = (deg: number): [number, number] => [Math.sin((deg * Math.PI) / 180), Math.cos((deg * Math.PI) / 180)];
const limb = (x: number, y: number, a: number, b: number, l1 = 78, l2 = 72) => {
  const [dx, dy] = dir(a);
  const ex = x + dx * l1;
  const ey = y + dy * l1;
  const [fx, fy] = dir(b);
  return `${x},${y} ${ex},${ey} ${ex + fx * l2},${ey + fy * l2}`;
};

const Line: React.FC<{pts: string}> = ({pts}) => (
  <>
    <polyline points={pts} fill="none" stroke="#000" strokeWidth={30} strokeLinecap="round" strokeLinejoin="round" />
    <polyline points={pts} fill="none" stroke="#fff" strokeWidth={16} strokeLinecap="round" strokeLinejoin="round" />
  </>
);

const Stickman: React.FC<{accent: string; hookEnd: number; ctaAt: number; durationSec: number}> = ({
  accent,
  hookEnd,
  ctaAt,
  durationSec,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const shocked = t < hookEnd + 0.3;
  const ending = t >= durationSec - 2.6;
  const cta = (t >= ctaAt && t < ctaAt + 3.6) || ending;
  const sw = Math.sin(t * 4);
  const jump = cta ? -Math.abs(Math.sin(t * 7)) * 30 : 0;
  const bob = shocked ? Math.sin(t * 22) * 4 : Math.sin(t * 5) * 5;
  const enter = spring({frame, fps, config: {damping: 12, stiffness: 140}});
  const gesture = !shocked && !cta && t % 4.5 > 3.3;

  let aL: number, bL: number, aR: number, bR: number;
  if (shocked) {
    aL = -150 + sw * 12;
    bL = -168 + sw * 10;
    aR = 150 - sw * 12;
    bR = 168 - sw * 10;
  } else if (cta) {
    aL = -98 + sw * 4;
    bL = -98;
    aR = 140 + Math.sin(t * 9) * 22;
    bR = 160 + Math.sin(t * 9 + 1) * 22;
  } else if (gesture) {
    aL = -25 + sw * 10;
    bL = -10 + sw * 15;
    aR = 125;
    bR = 165 + Math.sin(t * 10) * 20;
  } else {
    aL = -25 + sw * 14;
    bL = -10 + sw * 20;
    aR = 25 - sw * 14;
    bR = 10 - sw * 20;
  }
  const legA = cta ? 24 : 9 + sw * 12;
  const blink = t % 3.1 < 0.12;
  const shoulder = 148;
  const hip = 262;
  const mouth = shocked ? (
    <ellipse cx={150} cy={96} rx={10} ry={14 + Math.sin(t * 22) * 2} fill="#000" />
  ) : cta ? (
    <path d="M126 86 Q150 118 174 86 Z" fill="#000" />
  ) : (
    <path d="M134 90 Q150 102 166 90" fill="none" stroke="#000" strokeWidth={6} strokeLinecap="round" />
  );
  return (
    <div
      style={{
        position: "absolute",
        right: 30,
        bottom: 24,
        width: 330,
        height: 462,
        transform: `translateY(${interpolate(enter, [0, 1], [260, 0])}px)`,
      }}
    >
      <svg viewBox="0 0 300 420" width="330" height="462">
        <ellipse cx={150} cy={412} rx={70 + jump * 0.6} ry={9} fill="#000" opacity={0.35} />
        <g transform={`translate(0 ${bob + jump})`}>
          <Line pts={limb(150, hip, -legA, -legA * 0.3, 92, 86)} />
          <Line pts={limb(150, hip, legA, legA * 0.3, 92, 86)} />
          <Line pts={`150,118 150,${hip}`} />
          <Line pts={limb(150, shoulder, aL, bL)} />
          <Line pts={limb(150, shoulder, aR, bR)} />
          <g transform={`rotate(${Math.sin(t * 3) * 4} 150 110)`}>
            <circle cx={150} cy={70} r={46} fill="#fff" stroke="#000" strokeWidth={8} />
            <path d="M106 56 Q150 24 194 56" fill="none" stroke={accent} strokeWidth={14} strokeLinecap="round" />
            {shocked ? (
              <>
                <line x1={124} y1={46} x2={142} y2={52} stroke="#000" strokeWidth={5} strokeLinecap="round" />
                <line x1={176} y1={46} x2={158} y2={52} stroke="#000" strokeWidth={5} strokeLinecap="round" />
              </>
            ) : null}
            <ellipse cx={134} cy={70} rx={6} ry={blink ? 1.5 : shocked ? 9 : 7} fill="#000" />
            <ellipse cx={166} cy={70} rx={6} ry={blink ? 1.5 : shocked ? 9 : 7} fill="#000" />
            {mouth}
          </g>
          {shocked ? (
            <text
              x={232}
              y={52 + Math.sin(t * 14) * 4}
              fontFamily={fontFamily}
              fontWeight={800}
              fontSize={84}
              fill={accent}
              stroke="#000"
              strokeWidth={10}
              paintOrder="stroke"
            >
              !
            </text>
          ) : null}
        </g>
      </svg>
    </div>
  );
};

// ---------- Ajakan follow: muncul di tengah video dan lagi di akhir ----------
const FollowCta: React.FC<{accent: string; ctaAt: number; durationSec: number; text: string}> = ({
  accent,
  ctaAt,
  durationSec,
  text,
}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const win = [
    [ctaAt, ctaAt + 3.6],
    [durationSec - 2.6, durationSec],
  ].find(([a, b]) => t >= a && t < b);
  if (!win) return null;
  const sp = spring({frame: Math.round((t - win[0]) * fps), fps, config: {damping: 11, stiffness: 200, mass: 0.6}});
  const out = interpolate(t, [win[1] - 0.25, win[1]], [1, 0], clampBoth);
  const pulse = 1 + Math.sin(t * 9) * 0.03;
  return (
    <div
      style={{
        position: "absolute",
        left: 40,
        bottom: 210,
        opacity: out,
        transform: `scale(${interpolate(sp, [0, 1], [0.3, 1]) * pulse}) rotate(-3deg)`,
        transformOrigin: "left bottom",
        fontFamily,
        textAlign: "center",
      }}
    >
      <div
        style={{
          fontWeight: 800,
          fontSize: 84,
          color: "#111",
          background: accent,
          padding: "10px 44px",
          borderRadius: 36,
          boxShadow: "0 10px 0 rgba(0,0,0,0.6)",
          letterSpacing: 3,
        }}
      >
        FOLLOW
      </div>
      <div
        style={{
          marginTop: 16,
          fontWeight: 700,
          fontSize: 34,
          color: "#fff",
          background: "rgba(0,0,0,0.72)",
          padding: "8px 24px",
          borderRadius: 24,
        }}
      >
        {text}
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

export const FactVideo: React.FC<FactProps & {children?: React.ReactNode}> = (p) => {
  const hookEnd = Math.max(p.hookEnd, 1.8);
  const captionWords = p.words.slice(p.hookWordCount);
  return (
    <AbsoluteFill style={{backgroundColor: "#000"}}>
      <Background clips={p.clips} accent={p.accent} />
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(to bottom, rgba(0,0,0,0.6) 0%, rgba(0,0,0,0.12) 35%, rgba(0,0,0,0.12) 55%, rgba(0,0,0,0.72) 100%)",
        }}
      />
      {p.audio ? <Audio src={staticFile(p.audio)} /> : null}
      {p.children}
      <Captions words={captionWords} accent={p.accent} />
      {p.stickman !== false ? (
        <>
          <FollowCta
            accent={p.accent}
            ctaAt={p.ctaAt ?? 8}
            durationSec={p.durationSec}
            text={p.cta ?? "for 1 new fact every day"}
          />
          <Stickman accent={p.accent} hookEnd={hookEnd} ctaAt={p.ctaAt ?? 8} durationSec={p.durationSec} />
        </>
      ) : null}
      <HookTop text={p.hook} start={hookEnd - 0.1} accent={p.accent} />
      <Sequence from={0} durationInFrames={Math.round((hookEnd + 0.1) * FPS)} layout="none">
        <HookBig text={p.hook} end={hookEnd} accent={p.accent} pill={p.pill} />
      </Sequence>
      <Badge label={p.label} accent={p.accent} />
      <Progress accent={p.accent} />
    </AbsoluteFill>
  );
};
