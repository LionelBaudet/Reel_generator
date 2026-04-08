"""
generate_reel.py
Full pipeline: YAML config → ElevenLabs voiceover → FFmpeg video assembly.

Usage:
    python generate_reel.py --config config/reel_01.yaml
    python generate_reel.py --config config/reel_01.yaml --voiceover-only
    python generate_reel.py --config config/reel_01.yaml --skip-voiceover
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

from generate_voiceover import generate_voiceover

OUTPUT_DIR = Path("output")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_filename(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "_", slug)
    return slug[:60]


def _require_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        sys.exit(
            "Error: ffmpeg is not installed or not on PATH.\n"
            "Install it from https://ffmpeg.org/download.html"
        )


def _run(cmd: list[str], step: str) -> None:
    """Run an FFmpeg command, exit with a clear message on failure."""
    print(f"[ffmpeg:{step}] {' '.join(cmd[:6])}…")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ffmpeg:{step}] FAILED — stderr:\n{result.stderr[-800:]}")
        sys.exit(f"Error: FFmpeg failed at step '{step}' (code {result.returncode}).")


def _probe_duration(path: str | Path) -> float:
    """Return duration of a media file in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except ValueError:
        sys.exit(f"Error: Could not probe duration of {path}.")


# ---------------------------------------------------------------------------
# Step 1 — Concatenate video clips
# ---------------------------------------------------------------------------

def _concat_clips(clips: list[str], tmp_dir: Path) -> Path:
    """
    Concatenate one or more video clips into a single file.
    If only one clip, return it directly (no re-encode needed).
    """
    valid = [c for c in clips if Path(c).exists()]
    if not valid:
        sys.exit("Error: No valid video clips found. Check 'video.clips' in YAML.")

    if len(valid) == 1:
        print(f"[concat] Single clip — using {valid[0]} directly.")
        return Path(valid[0])

    # Write a concat list file
    concat_list = tmp_dir / "concat_list.txt"
    with concat_list.open("w") as f:
        for clip in valid:
            f.write(f"file '{Path(clip).resolve()}'\n")

    out = tmp_dir / "concat.mp4"
    _run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(out),
    ], step="concat")
    print(f"[concat] Merged {len(valid)} clips → {out}")
    return out


# ---------------------------------------------------------------------------
# Step 2 — Loop/trim video to target duration
# ---------------------------------------------------------------------------

def _loop_video_to_duration(video: Path, duration: float, tmp_dir: Path) -> Path:
    """Loop a video clip so it covers at least `duration` seconds, then trim."""
    out = tmp_dir / "video_looped.mp4"
    _run([
        "ffmpeg", "-y",
        "-stream_loop", "-1",          # infinite loop
        "-i", str(video),
        "-t", str(duration),
        "-c:v", "libx264", "-crf", "23",
        "-an",                         # drop audio from source clip
        "-preset", "fast",
        str(out),
    ], step="loop_video")
    return out


# ---------------------------------------------------------------------------
# Step 3 — Overlay slides
# ---------------------------------------------------------------------------

def _overlay_slides(
    video: Path,
    slides: list[str],
    total_duration: float,
    tmp_dir: Path,
) -> Path:
    """
    Overlay PNG slides in sequence, each shown for an equal share of the video.
    Uses FFmpeg overlay filter with enable= time windows.
    """
    valid_slides = [s for s in slides if Path(s).exists()]
    if not valid_slides:
        print("[slides] No valid slides found — skipping overlay step.")
        return video

    n          = len(valid_slides)
    per_slide  = total_duration / n

    # Build complex filter: scale each slide then overlay at its time window
    filter_parts: list[str] = []
    inputs:       list[str] = ["-i", str(video)]

    for i, slide in enumerate(valid_slides):
        inputs += ["-i", slide]

    # Chain overlays: [base][slide1] → tmp1; [tmp1][slide2] → tmp2; …
    filter_parts = []
    for i, _ in enumerate(valid_slides):
        t_start = i * per_slide
        t_end   = (i + 1) * per_slide
        in_tag  = f"[v{i}]" if i > 0 else "[0:v]"
        slide_tag = f"[{i + 1}:v]"
        out_tag  = f"[v{i + 1}]"
        scale    = f"{slide_tag}scale=iw:ih[s{i}]"
        overlay  = (
            f"{in_tag}[s{i}]overlay=0:0:"
            f"enable='between(t,{t_start:.3f},{t_end:.3f})'"
            f"{out_tag}"
        )
        filter_parts.append(scale)
        filter_parts.append(overlay)

    final_video_tag = f"[v{n}]"
    filter_str = ";".join(filter_parts)

    out = tmp_dir / "video_slides.mp4"
    _run([
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_str,
        "-map", final_video_tag,
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        "-t", str(total_duration),
        str(out),
    ], step="slides")
    return out


# ---------------------------------------------------------------------------
# Step 4 — Prepare background music (loop + fade out)
# ---------------------------------------------------------------------------

def _prepare_music(
    music_path: str,
    duration: float,
    fade_out: float,
    tmp_dir: Path,
) -> Path | None:
    """Loop background music to cover `duration`, add a fade-out tail."""
    if not music_path or not Path(music_path).exists():
        print(f"[music] File not found ({music_path}) — skipping background music.")
        return None

    tail     = duration + fade_out         # extend slightly for the fade
    fade_start = duration - fade_out       # where fade begins

    out = tmp_dir / "music_prepared.mp3"
    _run([
        "ffmpeg", "-y",
        "-stream_loop", "-1",
        "-i", music_path,
        "-t", str(tail),
        "-af", (
            f"afade=t=out:st={fade_start:.3f}:d={fade_out:.3f}"
        ),
        "-c:a", "libmp3lame", "-q:a", "4",
        str(out),
    ], step="music")
    return out


# ---------------------------------------------------------------------------
# Step 5 — Final assembly
# ---------------------------------------------------------------------------

def _assemble(
    video:            Path,
    voiceover:        Path,
    music:            Path | None,
    vo_volume:        float,
    music_volume:     float,
    output_path:      Path,
    total_duration:   float,
) -> None:
    """
    Mix video + voiceover + optional background music.
    Voiceover drives the final duration.
    """
    # Build audio filter
    if music:
        audio_filter = (
            f"[1:a]volume={vo_volume}[vo];"
            f"[2:a]volume={music_volume}[bg];"
            f"[vo][bg]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        )
        audio_inputs = ["-i", str(voiceover), "-i", str(music)]
        audio_map    = "[aout]"
    else:
        audio_filter = f"[1:a]volume={vo_volume}[aout]"
        audio_inputs = ["-i", str(voiceover)]
        audio_map    = "[aout]"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    _run([
        "ffmpeg", "-y",
        "-i", str(video),
        *audio_inputs,
        "-filter_complex", audio_filter,
        "-map", "0:v",
        "-map", audio_map,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(total_duration),
        "-movflags", "+faststart",
        str(output_path),
    ], step="assemble")

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"\n[done] Output → {output_path}  ({size_mb:.1f} MB, {total_duration:.1f}s)")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def build_reel(config: dict, voiceover_path: Path) -> Path:
    """
    Assemble the final reel from config + a pre-generated voiceover.
    Returns the output video path.
    """
    _require_ffmpeg()

    title       = config.get("title", "reel")
    video_cfg   = config.get("video", {})
    slides      = config.get("slides", [])

    clips           = video_cfg.get("clips", [])
    bg_music        = video_cfg.get("background_music", "")
    music_volume    = float(video_cfg.get("music_volume", 0.15))
    vo_volume       = float(video_cfg.get("voiceover_volume", 1.0))
    fade_duration   = float(video_cfg.get("music_fade_out", 0.5))

    output_path = Path(config.get("output", OUTPUT_DIR / f"{_safe_filename(title)}.mp4"))

    # Duration is driven by the voiceover
    total_duration = _probe_duration(voiceover_path)
    print(f"[reel] Voiceover duration: {total_duration:.2f}s — this drives video length.")

    with tempfile.TemporaryDirectory(prefix="reel_tmp_") as tmp:
        tmp_dir = Path(tmp)

        # 1. Concat source clips
        raw_video = _concat_clips(clips, tmp_dir)

        # 2. Loop video to cover voiceover duration
        looped = _loop_video_to_duration(raw_video, total_duration, tmp_dir)

        # 3. Overlay slides (optional)
        if slides:
            with_slides = _overlay_slides(looped, slides, total_duration, tmp_dir)
        else:
            with_slides = looped

        # 4. Prepare background music
        music = _prepare_music(bg_music, total_duration, fade_duration, tmp_dir)

        # 5. Final mix
        _assemble(
            video          = with_slides,
            voiceover      = voiceover_path,
            music          = music,
            vo_volume      = vo_volume,
            music_volume   = music_volume,
            output_path    = output_path,
            total_duration = total_duration,
        )

    return output_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a full Instagram Reel from a YAML config."
    )
    parser.add_argument(
        "--config", required=True,
        help="Path to the reel YAML config (e.g. config/reel_01.yaml)"
    )
    parser.add_argument(
        "--voiceover-only", action="store_true",
        help="Only generate the voiceover MP3, skip video assembly."
    )
    parser.add_argument(
        "--skip-voiceover", action="store_true",
        help="Skip API call — use an existing voiceover file if present."
    )
    parser.add_argument(
        "--voiceover-path", default=None,
        help="Explicit path to an existing voiceover MP3 (implies --skip-voiceover)."
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        sys.exit(f"Error: Config file not found — {config_path}")

    with config_path.open(encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # ── Resolve voiceover ─────────────────────────────────────────────────
    if args.voiceover_path:
        vo_path = Path(args.voiceover_path)
        if not vo_path.exists():
            sys.exit(f"Error: Voiceover file not found — {vo_path}")
        print(f"[reel] Using provided voiceover: {vo_path}")
    elif args.skip_voiceover:
        title   = config.get("title", "reel")
        vo_path = Path("assets/voiceover") / (_safe_filename(title) + ".mp3")
        if not vo_path.exists():
            sys.exit(
                f"Error: --skip-voiceover requires an existing file at {vo_path}.\n"
                f"Run without --skip-voiceover first to generate it."
            )
        print(f"[reel] Reusing existing voiceover: {vo_path}")
    else:
        vo_path = generate_voiceover(config)

    if args.voiceover_only:
        print("[reel] --voiceover-only: done.")
        return

    # ── Assemble video ────────────────────────────────────────────────────
    build_reel(config, vo_path)


if __name__ == "__main__":
    main()
