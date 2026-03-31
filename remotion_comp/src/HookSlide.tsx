/**
 * Composant HookSlide — Segment 1 du reel
 * Affiche le texte accrocheur mot par mot avec soulignement doré
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

interface HookSlideProps {
  text: string;
  highlight: string;
  durationInFrames: number;
}

export const HookSlide: React.FC<HookSlideProps> = ({
  text,
  highlight,
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const words = text.split(" ");
  const highlightWords = highlight.toLowerCase().split(" ");

  // Phase des mots : 70% de la durée
  const wordsPhaseEnd = durationInFrames * 0.70;
  // Phase du soulignement : après 65%
  const underlinePhaseStart = durationInFrames * 0.65;

  // Fade-in du fond
  const bgOpacity = interpolate(frame, [0, 15], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: `rgba(9, 9, 26, ${bgOpacity})`,
        backgroundImage: `radial-gradient(ellipse at 50% 30%, rgba(232, 184, 75, 0.06) 0%, transparent 70%)`,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "60px 60px",
      }}
    >
      {/* Ligne décorative dorée en haut */}
      <div
        style={{
          position: "absolute",
          top: 80,
          left: "50%",
          transform: "translateX(-50%)",
          width: interpolate(frame, [0, 20], [0, 120], {
            extrapolateRight: "clamp",
          }),
          height: 3,
          background: "#E8B84B",
          borderRadius: 2,
        }}
      />

      {/* Texte mot par mot */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          alignItems: "center",
          gap: "0 18px",
          maxWidth: 960,
          textAlign: "center",
        }}
      >
        {words.map((word, i) => {
          // Chaque mot apparaît progressivement
          const wordStartFrame = (i / words.length) * wordsPhaseEnd;
          const wordOpacity = interpolate(
            frame,
            [wordStartFrame, wordStartFrame + 8],
            [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );
          const wordSlide = interpolate(
            frame,
            [wordStartFrame, wordStartFrame + 10],
            [30, 0],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );

          // Vérifier si ce mot fait partie de la surbrillance
          const isHighlighted = highlightWords.some((hw) =>
            word.toLowerCase().includes(hw)
          );

          // Animation du soulignement
          const underlineWidth =
            isHighlighted && frame >= underlinePhaseStart
              ? interpolate(
                  frame,
                  [underlinePhaseStart, underlinePhaseStart + 12],
                  [0, 100],
                  { extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) }
                )
              : 0;

          return (
            <div
              key={i}
              style={{
                display: "inline-block",
                opacity: wordOpacity,
                transform: `translateY(${wordSlide}px)`,
                position: "relative",
                marginBottom: 8,
              }}
            >
              <span
                style={{
                  fontFamily: "'Plus Jakarta Sans', 'Arial', sans-serif",
                  fontWeight: 800,
                  fontSize: 72,
                  color: "#F2F0EA",
                  lineHeight: 1.15,
                  letterSpacing: "-0.02em",
                }}
              >
                {word}
              </span>

              {/* Soulignement doré animé */}
              {isHighlighted && (
                <div
                  style={{
                    position: "absolute",
                    bottom: -6,
                    left: 0,
                    height: 5,
                    width: `${underlineWidth}%`,
                    background: "#E8B84B",
                    borderRadius: 3,
                    boxShadow: "0 0 12px rgba(232, 184, 75, 0.6)",
                  }}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Watermark marque en bas */}
      <div
        style={{
          position: "absolute",
          bottom: 100,
          opacity: interpolate(frame, [durationInFrames - 20, durationInFrames], [1, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          color: "#52527A",
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 28,
          letterSpacing: "0.05em",
        }}
      >
        @ownyourtime.ai
      </div>
    </AbsoluteFill>
  );
};
