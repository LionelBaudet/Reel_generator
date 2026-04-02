"""
Template "Multi Scene" — rendu text-centric, pré-rendu numpy, FPS 24.
Backward-compatible avec les anciens YAMLs (champ animation ou text_animation).
"""

import logging
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from utils.fonts import font_cache
from utils.renderer import CANVAS_W, CANVAS_H, ease_out, wrap_text, get_text_dimensions

logger = logging.getLogger(__name__)

FPS            = 24
BROLL_LOAD_FPS = 12
FFMPEG_PRESET  = "veryfast"

RENDER_W = 540
RENDER_H = 960

ANIM_T = {"fade_in": 0.7, "slide_in": 0.65, "slide_up": 0.65,
           "pop": 0.45, "fade_out": 0.6}
SLIDE_PX  = 40
POP_START = 0.68

BG_COLOR   = (9, 9, 26)
TEXT_COLOR = (242, 240, 234)
GOLD_COLOR = (232, 184, 75)


def _font_size(text: str, emphasis: bool = False) -> int:
    c = len(text)
    s = 44 if c <= 15 else 36 if c <= 30 else 28 if c <= 50 else 22
    if emphasis:
        s = min(s + 6, 48)
    return s


def _load_frames(path: str, overlay_opacity: float = 0.55) -> list[np.ndarray]:
    try:
        from PIL import Image as _PIL
        if not hasattr(_PIL, "ANTIALIAS"):
            _PIL.ANTIALIAS = _PIL.LANCZOS
        from moviepy.editor import VideoFileClip
        dark = 1.0 - overlay_opacity
        clip = VideoFileClip(path).resize((RENDER_W, RENDER_H))
        frames = [
            (np.array(f).astype(np.float32) * dark).astype(np.uint8)
            for f in clip.iter_frames(fps=BROLL_LOAD_FPS)
        ]
        clip.close()
        logger.info(f"B-roll chargé : {len(frames)} frames @ {BROLL_LOAD_FPS}fps · {RENDER_W}×{RENDER_H}")
        return frames
    except Exception as e:
        logger.warning(f"Erreur B-roll {path}: {e}")
        return []


class SceneRenderer:
    def __init__(self, scene_cfg: dict, broll_frames: list):
        self.text     = scene_cfg.get("text", "")
        self.keyword  = scene_cfg.get("keyword_highlight", "")
        self.emphasis = bool(scene_cfg.get("emphasis", False))
        self.duration = float(scene_cfg.get("duration", 2.8))
        self.broll    = broll_frames
        self.anim     = scene_cfg.get("text_animation",
                         scene_cfg.get("animation", "fade_in"))
        self.fs       = _font_size(self.text, self.emphasis)
        self._font    = font_cache.get(self.fs, "bold")

        self._pre: np.ndarray | None = None
        if self.anim != "typing":
            self._prerender()

    def _draw_line(self, draw: ImageDraw.ImageDraw, line: str, y: int, alpha: int = 255):
        sa = max(0, min(255, int(alpha * 0.45)))
        tw, _ = get_text_dimensions(line, self._font, draw)
        x = (RENDER_W - tw) // 2
        def px(c): return (*c[:3], alpha)
        if self.keyword and self.keyword in line:
            before, _, after = line.partition(self.keyword)
            cx = x
            for part, color in [
                (before, TEXT_COLOR), (self.keyword, GOLD_COLOR), (after, TEXT_COLOR)
            ]:
                if not part: continue
                draw.text((cx+2, y+2), part, font=self._font, fill=(0, 0, 0, sa))
                draw.text((cx, y),     part, font=self._font, fill=px(color))
                pw, _ = get_text_dimensions(part, self._font, draw)
                cx += pw
        else:
            draw.text((x+2, y+2), line, font=self._font, fill=(0, 0, 0, sa))
            draw.text((x, y),     line, font=self._font, fill=px(TEXT_COLOR))

    def _prerender(self):
        layer = Image.new("RGBA", (RENDER_W, RENDER_H), (0, 0, 0, 0))
        draw  = ImageDraw.Draw(layer)
        lines = wrap_text(self.text, self._font, RENDER_W - 60)
        lh    = self.fs + 9
        cy    = (RENDER_H - len(lines) * lh) // 2
        for li, line in enumerate(lines):
            self._draw_line(draw, line, cy + li * lh, 255)
        arr = np.array(layer, dtype=np.float32)
        arr /= 255.0
        self._pre = arr

    def _bg(self, t: float) -> np.ndarray:
        if not self.broll:
            arr = np.zeros((RENDER_H, RENDER_W, 3), dtype=np.uint8)
            arr[:] = BG_COLOR
            return arr
        return self.broll[int(t * BROLL_LOAD_FPS) % len(self.broll)]

    def _blend(self, frame: np.ndarray, alpha: float, y_off: int = 0) -> np.ndarray:
        if alpha <= 0.001 or self._pre is None:
            return frame
        txt = self._pre
        if y_off != 0:
            shifted = np.roll(txt, y_off, axis=0)
            if y_off > 0: shifted[:y_off] = 0
            txt = shifted
        txt_a = txt[:, :, 3:4] * alpha
        out = frame.astype(np.float32) * (1.0 - txt_a) + txt[:, :, :3] * 255.0 * txt_a
        return np.clip(out, 0, 255).astype(np.uint8)

    def make_frame(self, t: float) -> np.ndarray:
        progress = min(1.0, t / max(self.duration, 0.001))
        frame    = self._bg(t)

        if self.anim == "typing":
            img   = Image.fromarray(frame, "RGB").convert("RGBA")
            lines = wrap_text(self.text, self._font, RENDER_W - 60)
            lh    = self.fs + 9
            cy    = (RENDER_H - len(lines) * lh) // 2
            layer = Image.new("RGBA", (RENDER_W, RENDER_H), (0, 0, 0, 0))
            td    = ImageDraw.Draw(layer)
            total = sum(len(l) for l in lines)
            vis, shown = max(1, int(progress * total)), 0
            for li, line in enumerate(lines):
                take  = min(max(0, vis - shown), len(line))
                shown += len(line)
                if take <= 0: break
                self._draw_line(td, line[:take], cy + li * lh, 255)
            img.alpha_composite(layer)
            return np.array(img.convert("RGB"))

        if self._pre is None:
            return frame

        a = self.anim
        alpha, y_off = 1.0, 0

        if a == "fade_in":
            alpha = ease_out(min(1.0, t / ANIM_T["fade_in"]))
        elif a in ("slide_in", "slide_up", "slide"):
            p     = ease_out(min(1.0, t / ANIM_T["slide_in"]))
            y_off = int((1.0 - p) * SLIDE_PX)
            alpha = ease_out(min(1.0, t / (ANIM_T["slide_in"] * 0.55)))
        elif a == "pop":
            p     = ease_out(min(1.0, t / ANIM_T["pop"]))
            alpha = p
            sc    = POP_START + p * (1.0 - POP_START)
            if sc < 0.97:
                pil = Image.fromarray((self._pre * 255).astype(np.uint8), "RGBA")
                nw, nh = int(RENDER_W * sc), int(RENDER_H * sc)
                c = Image.new("RGBA", (RENDER_W, RENDER_H), (0, 0, 0, 0))
                c.paste(pil.resize((nw, nh), Image.BILINEAR),
                        ((RENDER_W - nw) // 2, (RENDER_H - nh) // 2))
                tmp = np.array(c, dtype=np.float32) / 255.0
                txt_a = tmp[:, :, 3:4] * alpha
                out   = frame.astype(np.float32) * (1.0 - txt_a) + tmp[:, :, :3] * 255.0 * txt_a
                return np.clip(out, 0, 255).astype(np.uint8)
        elif a == "fade_out":
            start = max(0.0, self.duration - ANIM_T["fade_out"])
            alpha = (1.0 - max(0.0, t - start) / ANIM_T["fade_out"]) if t > start else 1.0

        return self._blend(frame, alpha, y_off)


class MultiSceneTemplate:
    def __init__(self, config: dict):
        self.config         = config
        self.fps            = FPS
        self.scenes_cfg     = config.get("scenes", [])
        self.broll_path     = config.get("broll_video", "")
        self.audio_cfg      = config.get("audio", {})
        self.overlay_opacity = float(
            config.get("background", {}).get("overlay_opacity",
            config.get("scenes", [{}])[0].get("overlay_opacity", 0.55)
            if config.get("scenes") else 0.55)
        )
        self.total_duration = sum(
            max(2.5, float(s.get("duration", 2.5))) for s in self.scenes_cfg
        )
        self._frames: list[np.ndarray] = []

    def _load_broll(self):
        if self._frames:
            return
        if not self.broll_path or not Path(self.broll_path).exists():
            logger.warning(f"B-roll introuvable : {self.broll_path}")
            return
        self._frames = _load_frames(self.broll_path, self.overlay_opacity)

    def _scene_frames(self, offset: int, n: int) -> list:
        if not self._frames:
            return []
        s = offset % len(self._frames)
        return [self._frames[(s + j) % len(self._frames)] for j in range(n + 6)]

    def generate_preview_frame(self, output_path: str,
                                segment: str = "hook", t: float = 0.5):
        self._load_broll()
        sc = next(
            (s for s in self.scenes_cfg if s.get("type") == segment),
            self.scenes_cfg[0] if self.scenes_cfg else {},
        )
        renderer = SceneRenderer(sc, self._frames)
        img = Image.fromarray(renderer.make_frame(t)).resize(
            (CANVAS_W, CANVAS_H), Image.LANCZOS
        )
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        img.save(output_path)
        logger.info(f"Preview {segment} → {output_path}")

    def generate(self, output_path: str, use_remotion: bool = False) -> str:
        from moviepy.editor import VideoClip, AudioFileClip, concatenate_videoclips

        self._load_broll()
        logger.info(f"MultiScene : {len(self.scenes_cfg)} scènes · {self.total_duration:.1f}s")

        clips, offset = [], 0
        for i, sc in enumerate(self.scenes_cfg):
            dur      = max(2.5, float(sc.get("duration", 2.5)))
            n_frames = int(dur * self.fps)
            frames   = self._scene_frames(offset, n_frames)
            offset  += n_frames
            renderer = SceneRenderer(sc, frames)
            def make_frame(t, r=renderer): return r.make_frame(t)
            clips.append(VideoClip(make_frame, duration=dur).set_fps(self.fps))
            logger.info(
                f"  Scène {i+1}/{len(self.scenes_cfg)} : "
                f"{sc.get('type','')} · {dur}s · "
                f"{sc.get('text_animation', sc.get('animation','fade_in'))}"
            )

        final = concatenate_videoclips(clips, method="compose")

        apath  = self.audio_cfg.get("background_music", "")
        volume = float(self.audio_cfg.get("volume", 0.28))
        if apath and Path(apath).exists():
            try:
                music = AudioFileClip(apath).volumex(volume)
                if music.duration > final.duration:
                    music = music.subclip(0, final.duration)
                final = final.set_audio(music)
            except Exception as e:
                logger.warning(f"Audio ignoré : {e}")

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        final.write_videofile(
            output_path,
            fps=self.fps,
            codec="libx264",
            audio_codec="aac",
            preset=FFMPEG_PRESET,
            ffmpeg_params=[
                "-crf", "20",
                "-vf", f"scale={CANVAS_W}:{CANVAS_H}:flags=lanczos",
            ],
            logger=None,
        )
        return output_path
