import React from "react";
import {Composition} from "remotion";
import {defaultProps, FPS} from "./FactVideo";
import {FactVideoMusic, MusicProps} from "./FactVideoMusic";

const defaultMusicProps: MusicProps = {...defaultProps, music: "", musicVolume: 0.22};

export const Root: React.FC = () => {
  return (
    <Composition
      id="FactVideo"
      component={FactVideoMusic}
      width={1080}
      height={1920}
      fps={FPS}
      durationInFrames={FPS * 20}
      defaultProps={defaultMusicProps}
      calculateMetadata={({props}) => ({
        durationInFrames: Math.max(FPS * 3, Math.round(props.durationSec * FPS)),
      })}
    />
  );
};
