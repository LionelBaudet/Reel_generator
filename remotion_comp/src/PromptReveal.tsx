/**
 * Composant Remotion principal — PromptReveal
 * Orchestre les 3 segments : Hook → Prompt Reveal → CTA
 *
 * Palette de couleurs @ownyourtime.ai:
 *   Midnight  #09091A  — fond principal
 *   Deep Ink  #1E1E32  — fond secondaire
 *   Gold      #E8B84B  — accent
 *   Ivory     #F2F0EA  — texte principal
 *   Muted     #52527A  — texte secondaire
 */
import React from "react";
import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Easing,
} from "remotion";
import { HookSlide } from "./HookSlide";
import { CTASlide } from "./CTASlide";

// ── Types ──────────────────────────────────────────────────────────────────

export interface PromptRevealProps {
  hookText: string;
  hookHighlight: string;
  hookDuration: number;
  promptTitle: string;
  promptText: string;
  outputText: string;
  promptDuration: number;
  ctaHeadline: string;
  ctaSubtext: string;
  ctaHandle: string;
  ctaDuration: number;
}

export const defaultPromptRevealProps: PromptRevealProps = {
  hookText: "Stop writing emails from scratch.",
  hookHighlight: "emails from scratch",
  hookDuration: 3,
  promptTitle: "Professional Client Email",
  promptText:
    "Write a professional email to [name]\nabout [topic]. Tone: direct.\nMax 5 lines. One clear CTA.",
  outputText:
    "Hi Sarah,\nFollowing up on the project timeline.\nDelivery moves to March 15th due to QA.\nDoes that work for you?\nBest, [Your name]",
  promptDuration: 12,
  ctaHeadline: "Save THIS.",
  ctaSubtext: "10 free prompts → link in bio 🎁",
  ctaHandle: "@ownyourtime.ai",
  ctaDuration: 3,
};

// ── Segment : Prompt Reveal ────────────────────────────────────────────────

interface PromptRevealSegmentProps {
  promptTitle: string;
  promptText: string;
  outputText: string;
  durationInFrames: number;
}

const PromptRevealSegment: React.FC<PromptRevealSegmentProps> = ({
  promptTitle,
  promptText,
  outputText,
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const promptLines = promptText.split("\n");
  const outputLines = outputText.split("\n");
  const totalPromptChars = promptText.length;

  // Animation de frappe du prompt (55% de la durée)
  const promptPhaseEnd = durationInFrames * 0.55;
  const promptProgress = Math.min(1, frame / promptPhaseEnd);
  const charsVisible = Math.floor(
    interpolate(promptProgress, [0, 1], [0, totalPromptChars], {
      easing: Easing.inOut(Easing.ease),
    })
  );

  // Apparition des lignes de l'output (à partir de 35%)
  const outputPhaseStart = durationInFrames * 0.35;
  const outputPhaseEnd = durationInFrames * 0.90;
  const outputLinesVisible =
    frame < outputPhaseStart
      ? 0
      : Math.min(
          outputLines.length,
          Math.floor(
            interpolate(
              frame,
              [outputPhaseStart, outputPhaseEnd],
              [0, outputLines.length],
              { extrapolateRight: "clamp", easing: Easing.out(Easing.ease) }
            )
          )
        );

  // Curseur clignotant (1.5 Hz)
  const cursorVisible = Math.floor(frame / (fps / 3)) % 2 === 0;

  // Entrée du segment avec slide depuis le bas
  const slideIn = spring({
    fps,
    frame,
    config: { damping: 20, stiffness: 120, mass: 1 },
    durationInFrames: 20,
  });
  const translateY = interpolate(slideIn, [0, 1], [80, 0]);

  return (
    <AbsoluteFill
      style={{
        background: "linear-gradient(180deg, #1E1E32 0%, #09091A 100%)",
        fontFamily: "'JetBrains Mono', 'Consolas', monospace",
        transform: `translateY(${translateY}px)`,
      }}
    >
      {/* Layout en deux colonnes */}
      <div
        style={{
          display: "flex",
          flexDirection: "row",
          gap: 20,
          padding: "30px 30px",
          marginTop: "auto",
          marginBottom: "auto",
          position: "absolute",
          top: "50%",
          transform: `translateY(calc(-50% + ${translateY}px))`,
          width: "100%",
          boxSizing: "border-box",
        }}
      >
        {/* Panneau gauche : LE PROMPT */}
        <div
          style={{
            flex: 1,
            background: "#14142A",
            border: "2px solid #2D2D4B",
            borderRadius: 16,
            padding: "20px 20px",
            minHeight: 700,
          }}
        >
          {/* Étiquette */}
          <div
            style={{
              color: "#E8B84B",
              fontSize: 26,
              marginBottom: 10,
              letterSpacing: "0.05em",
            }}
          >
            THE PROMPT
          </div>

          {/* Titre */}
          <div
            style={{
              color: "#52527A",
              fontSize: 24,
              marginBottom: 16,
            }}
          >
            {promptTitle}
          </div>

          {/* Séparateur */}
          <div
            style={{
              height: 1,
              background: "#2D2D4B",
              marginBottom: 16,
            }}
          />

          {/* Texte du prompt avec animation de frappe */}
          <div
            style={{
              color: "#F2F0EA",
              fontSize: 28,
              lineHeight: 1.6,
              whiteSpace: "pre-wrap",
            }}
          >
            {promptText.slice(0, charsVisible)}
            {/* Curseur clignotant */}
            {charsVisible < totalPromptChars || cursorVisible ? (
              <span
                style={{
                  color: "#E8B84B",
                  animation: "none",
                  opacity: cursorVisible ? 1 : 0,
                }}
              >
                ▋
              </span>
            ) : null}
          </div>
        </div>

        {/* Panneau droit : OUTPUT */}
        <div
          style={{
            flex: 1,
            background: "#0C0C18",
            border: "2px solid #28503C",
            borderRadius: 16,
            padding: "20px 20px",
            minHeight: 700,
          }}
        >
          {/* En-tête style terminal */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 10,
            }}
          >
            <span style={{ color: "#50FA7B", fontSize: 26 }}>OUTPUT</span>
            <div style={{ display: "flex", gap: 8 }}>
              {["#FF5F56", "#FFBD2E", "#27C93F"].map((color, i) => (
                <div
                  key={i}
                  style={{
                    width: 12,
                    height: 12,
                    borderRadius: "50%",
                    background: color,
                  }}
                />
              ))}
            </div>
          </div>

          {/* Séparateur */}
          <div
            style={{
              height: 1,
              background: "#1E3A2C",
              marginBottom: 16,
            }}
          />

          {/* Lignes de l'output */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}
          >
            {outputLines.slice(0, outputLinesVisible).map((line, i) => (
              <div
                key={i}
                style={{
                  color: "#50FA7B",
                  fontSize: 28,
                  lineHeight: 1.5,
                  opacity: i < outputLinesVisible - 1 ? 1 : 0.9,
                }}
              >
                {line}
              </div>
            ))}
            {/* Curseur terminal */}
            {outputLinesVisible > 0 &&
              outputLinesVisible < outputLines.length &&
              cursorVisible && (
                <div style={{ color: "#50FA7B", fontSize: 28 }}>█</div>
              )}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ── Composant Principal ────────────────────────────────────────────────────

export const PromptReveal: React.FC<PromptRevealProps> = (props) => {
  const { fps } = useVideoConfig();

  const hookFrames = Math.round(props.hookDuration * fps);
  const promptFrames = Math.round(props.promptDuration * fps);
  const ctaFrames = Math.round(props.ctaDuration * fps);

  return (
    <AbsoluteFill style={{ background: "#09091A" }}>
      {/* Segment 1 : Hook */}
      <Sequence from={0} durationInFrames={hookFrames}>
        <HookSlide
          text={props.hookText}
          highlight={props.hookHighlight}
          durationInFrames={hookFrames}
        />
      </Sequence>

      {/* Segment 2 : Prompt Reveal */}
      <Sequence from={hookFrames} durationInFrames={promptFrames}>
        <PromptRevealSegment
          promptTitle={props.promptTitle}
          promptText={props.promptText}
          outputText={props.outputText}
          durationInFrames={promptFrames}
        />
      </Sequence>

      {/* Segment 3 : CTA */}
      <Sequence from={hookFrames + promptFrames} durationInFrames={ctaFrames}>
        <CTASlide
          headline={props.ctaHeadline}
          subtext={props.ctaSubtext}
          handle={props.ctaHandle}
          durationInFrames={ctaFrames}
        />
      </Sequence>
    </AbsoluteFill>
  );
};
