import React from "react";
import {Composition} from "remotion";
import {FactVideo, defaultProps, FPS} from "./FactVideo";

export const Root: React.FC = () => {
  return (
    <Composition
      id="FactVideo"
      component={FactVideo}
      width={1080}
      height={1920}
      fps={FPS}
      durationInFrames={FPS * 20}
      defaultProps={defaultProps}
      calculateMetadata={({props}) => ({
        durationInFrames: Math.max(FPS * 3, Math.round(props.durationSec * FPS)),
      })}
    />
  );
};
