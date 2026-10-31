import React from "react";
import {AbsoluteFill, Audio, interpolate, staticFile, useVideoConfig} from "remotion";
import {FactVideo, FactProps} from "./FactVideo";

export type MusicProps = FactProps & {
  music: string; // mis. "job/musik.mp3"; kosong = tanpa musik
  musicVolume: number; // 0-1, relatif terhadap suara narasi
};

// Membungkus FactVideo + musik latar (fade in 1 detik, fade out 1,5 detik)
export const FactVideoMusic: React.FC<MusicProps> = ({music, musicVolume, ...p}) => {
  const {durationInFrames, fps} = useVideoConfig();
  return (
    <AbsoluteFill>
      <FactVideo {...p} />
      {music ? (
        <Audio
          src={staticFile(music)}
          volume={(f) =>
            interpolate(
              f,
              [0, fps, durationInFrames - fps * 1.5, durationInFrames],
              [0, musicVolume, musicVolume, 0],
              {extrapolateLeft: "clamp", extrapolateRight: "clamp"},
            )
          }
        />
      ) : null}
    </AbsoluteFill>
  );
};
