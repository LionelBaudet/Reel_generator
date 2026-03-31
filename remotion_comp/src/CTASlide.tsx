/**
 * Composant CTASlide — Segment 3 du reel
 * Fond doré, texte pulsant "Save THIS." avec animation de tremblement
 */
import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Easing,
} from "remotion";

interface CTASlideProps {
  headline: string;
  subtext: string;
  handle: string;
  durationInFrames: number;
}

export const CTASlide: React.FC<CTASlideProps> = ({
  headline,
  subtext,
  handle,
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Animation d'entrée : slide depuis le bas + fade
  const enterSpring = spring({
    fps,
    frame,
    config: { damping: 15, stiffness: 200, mass: 0.8 },
    durationInFrames: 18,
  });
  const slideY = interpolate(enterSpring, [0, 1], [150, 0]);
  const fadeIn = interpolate(enterSpring, [0, 1], [0, 1]);

  // Tremblement initial (0–18 frames)
  const shakeIntensity = interpolate(frame, [0, 18], [10, 0], {
    extrapolateRight: "clamp",
  });
  const shakeX =
    frame < 18
      ? shakeIntensity * Math.sin(frame * 1.8) * (frame % 2 === 0 ? 1 : -1)
      : 0;
  const shakeY =
    frame < 18
      ? shakeIntensity * 0.5 * Math.cos(frame * 1.2)
      : 0;

  // Pulsation continue du texte principal (1.8 Hz)
  const pulseScale =
    1 + 0.04 * Math.sin((2 * Math.PI * 1.8 * frame) / fps);

  // Apparition du sous-texte (delay 0.3s)
  const subtextDelay = Math.round(0.3 * fps);
  const subtextOpacity = interpolate(
    frame,
    [subtextDelay, subtextDelay + 12],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Apparition du handle (delay 0.6s)
  const handleDelay = Math.round(0.6 * fps);
  const handleOpacity = interpolate(
    frame,
    [handleDelay, handleDelay + 12],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Fond dégrade doré
  const bgGradient = "linear-gradient(180deg, #F0C85A 0%, #D2A537 100%)";

  return (
    <AbsoluteFill
      style={{
        background: bgGradient,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 32,
        opacity: fadeIn,
      }}
    >
      {/* Motif de fond décoratif */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `repeating-linear-gradient(
            45deg,
            rgba(0,0,0,0.03) 0px,
            rgba(0,0,0,0.03) 1px,
            transparent 1px,
            transparent 20px
          )`,
        }}
      />

      {/* Headline principal avec tremblement + pulsation */}
      <div
        style={{
          transform: `translate(${shakeX}px, ${slideY + shakeY}px) scale(${pulseScale})`,
          textAlign: "center",
          zIndex: 1,
        }}
      >
        <span
          style={{
            fontFamily: "'Plus Jakarta Sans', 'Arial Black', sans-serif",
            fontWeight: 900,
            fontSize: 108,
            color: "#0F0F1E",
            lineHeight: 1.1,
            letterSpacing: "-0.03em",
            textShadow: "0 6px 20px rgba(0,0,0,0.15)",
            display: "block",
          }}
        >
          {headline}
        </span>
      </div>

      {/* Séparateur décoratif */}
      <div
        style={{
          width: interpolate(frame, [8, 24], [0, 200], {
            extrapolateRight: "clamp",
          }),
          height: 4,
          background: "rgba(15, 15, 30, 0.3)",
          borderRadius: 2,
          transform: `translateY(${slideY * 0.5}px)`,
        }}
      />

      {/* Sous-texte */}
      <div
        style={{
          opacity: subtextOpacity,
          transform: `translateY(${(1 - subtextOpacity) * 30}px)`,
          textAlign: "center",
          padding: "0 60px",
          zIndex: 1,
        }}
      >
        <span
          style={{
            fontFamily: "'Plus Jakarta Sans', 'Arial', sans-serif",
            fontWeight: 700,
            fontSize: 44,
            color: "#0F0F1E",
            lineHeight: 1.4,
          }}
        >
          {subtext}
        </span>
      </div>

      {/* Handle @ownyourtime.ai */}
      <div
        style={{
          position: "absolute",
          bottom: 100,
          opacity: handleOpacity,
          zIndex: 1,
        }}
      >
        <span
          style={{
            fontFamily: "'JetBrains Mono', 'Consolas', monospace",
            fontSize: 32,
            color: "rgba(15, 15, 30, 0.6)",
            letterSpacing: "0.05em",
          }}
        >
          {handle}
        </span>
      </div>
    </AbsoluteFill>
  );
};
