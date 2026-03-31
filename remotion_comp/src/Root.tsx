// Composition racine Remotion — définit les paramètres de rendu
import React from "react";
import { Composition } from "remotion";
import { PromptReveal, defaultPromptRevealProps } from "./PromptReveal";

// Dimensions verticales 1080×1920 (Instagram Reels)
const CANVAS_WIDTH = 1080;
const CANVAS_HEIGHT = 1920;
const FPS = 30;

export const Root: React.FC = () => {
  return (
    <>
      {/* Composition principale — 18 secondes par défaut */}
      <Composition
        id="PromptReveal"
        component={PromptReveal}
        durationInFrames={18 * FPS}
        fps={FPS}
        width={CANVAS_WIDTH}
        height={CANVAS_HEIGHT}
        defaultProps={defaultPromptRevealProps}
      />
    </>
  );
};
