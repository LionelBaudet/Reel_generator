"""
Template "viral_text_centric_v1" — optimisé pour un rendu rapide.

Stratégie perf :
  • Rendu Python à 540×960 (4× moins de pixels → 4× plus rapide)
  • B-roll pré-assombri (overlay appliqué une seule fois au chargement)
  • Texte pré-rendu en numpy float32 (une seule fois par scène)
  • Blend par frame = opérations numpy légères uniquement
  • FFmpeg upscale lanczos 1080×1920 en sortie
  • FPS 24, preset veryfast
"""

import logging
import math
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from utils.fonts import font_cache
from utils.renderer import CANVAS_W, CANVAS_H, ease_out, wrap_text, get_text_dimensions
from utils.validation import validate_config

logger = logging.getLogger(__name__)

FPS            = 24
BROLL_LOAD_FPS = 12     # B-roll chargé à 12fps → boucle + lente, assez pour ambiance
FFMPEG_PRESET  = "veryfast"

# Résolution de rendu Python (upscalé par FFmpeg)
RENDER_W = 540
RENDER_H = 960

# Durées d'animation
ANIM_T = {
    "fade_in":   0.7,
    "slide_up":  0.65,
    "pop":       0.45,
    "fade_out":  0.6,
    "impact_in": 0.28,   # scale 1.3→1.0 + alpha 0→1 en 0.28s (scroll-stopper)
}
SLIDE_PX  = 40   # demi-résolution (80px équivalents à 1080p)
POP_START = 0.68

BG_COLOR   = (9, 9, 26)
TEXT_COLOR = (242, 240, 234)
GOLD_COLOR = (232, 184, 75)

# Tailles police pour RENDER_H=960 (équivalent × 2 après upscale FFmpeg)
FONT_SIZE_MAP  = {"xl": 46, "lg": 36, "md": 28, "sm": 22}
HOOK_FONT_SIZE = 54   # xl spécial hook — plus grand, plus percutant


# ── Font size ─────────────────────────────────────────────────────────────────
def _font_size(font_size_str: str, text: str, emphasis: bool,
               is_hook: bool = False) -> int:
    if is_hook and (font_size_str == "xl" or not font_size_str):
        return HOOK_FONT_SIZE
    if font_size_str in FONT_SIZE_MAP:
        s = FONT_SIZE_MAP[font_size_str]
    else:
        c = len(text)
        s = 44 if c <= 15 else 36 if c <= 30 else 28 if c <= 50 else 22
    if emphasis and s < 44:
        s = min(s + 6, 48)
    return s


# ── Chargement B-roll + pré-assombrissement ───────────────────────────────────
def _load_frames(path: str, overlay_opacity: float) -> list[np.ndarray]:
    """
    Charge les frames B-roll à RENDER_W×RENDER_H et applique l'overlay une fois.
    Les frames retournées sont uint8 RGB (déjà assombries).
    """
    try:
        from PIL import Image as _PIL
        if not hasattr(_PIL, "ANTIALIAS"):
            _PIL.ANTIALIAS = _PIL.LANCZOS
        from moviepy.editor import VideoFileClip
        clip = VideoFileClip(path).resize((RENDER_W, RENDER_H))
        dark = 1.0 - overlay_opacity
        frames = []
        for f in clip.iter_frames(fps=BROLL_LOAD_FPS):
            frames.append((np.array(f).astype(np.float32) * dark).astype(np.uint8))
        clip.close()
        logger.info(
            f"B-roll : {Path(path).name} — {len(frames)} frames "
            f"@ {BROLL_LOAD_FPS}fps · {RENDER_W}×{RENDER_H} pré-assombri"
        )
        return frames
    except Exception as e:
        logger.warning(f"Erreur B-roll {path}: {e}")
        return []


# ── Renderer d'une scène ──────────────────────────────────────────────────────
class SceneRenderer:
    """
    Rendu frame-par-frame à RENDER_W×RENDER_H.
    B-roll déjà assombri → blend texte uniquement par frame.
    Texte pré-rendu en RGBA float32 normalisé (0-1).
    """

    def __init__(self, scene_cfg: dict, broll_frames: list[np.ndarray]):
        self.text     = scene_cfg.get("text", "")
        self.keyword  = scene_cfg.get("keyword_highlight", "")
        self.emphasis = bool(scene_cfg.get("emphasis", False))
        self.duration = float(scene_cfg.get("duration", 2.8))
        self.broll    = broll_frames
        self.is_hook  = (scene_cfg.get("type") == "hook")

        # Animation : hook utilise impact_in par défaut
        default_anim  = "impact_in" if self.is_hook else "fade_in"
        self.anim     = scene_cfg.get("text_animation",
                         scene_cfg.get("animation", default_anim))

        self.fs    = _font_size(
            scene_cfg.get("font_size", ""), self.text, self.emphasis, self.is_hook
        )
        self._font = font_cache.get(self.fs, "bold")

        # Texte pré-rendu (float32 normalisé 0-1, shape H×W×4)
        self._pre: np.ndarray | None = None
        if self.anim != "typing":
            self._prerender()

    # ── Pré-rendu texte ───────────────────────────────────────────────────────
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

    def _draw_line(self, draw: ImageDraw.ImageDraw,
                   line: str, y: int, alpha: int = 255):
        # Ombre : plus forte pour le hook (4px, alpha 65%) vs standard (2px, 45%)
        if self.is_hook:
            shadow_off = 4
            shadow_a   = max(0, min(255, int(alpha * 0.65)))
        else:
            shadow_off = 2
            shadow_a   = max(0, min(255, int(alpha * 0.45)))

        tw, _ = get_text_dimensions(line, self._font, draw)
        x = (RENDER_W - tw) // 2

        def px(c): return (*c[:3], alpha)

        kw_idx = line.lower().find(self.keyword.lower()) if self.keyword else -1
        if kw_idx != -1:
            before     = line[:kw_idx]
            kw_actual  = line[kw_idx: kw_idx + len(self.keyword)]
            after      = line[kw_idx + len(self.keyword):]
            cx = x
            for part, color in [
                (before, TEXT_COLOR), (kw_actual, GOLD_COLOR), (after, TEXT_COLOR)
            ]:
                if not part:
                    continue
                draw.text((cx + shadow_off, y + shadow_off), part,
                          font=self._font, fill=(0, 0, 0, shadow_a))
                draw.text((cx, y), part, font=self._font, fill=px(color))
                pw, _ = get_text_dimensions(part, self._font, draw)
                cx += pw
        else:
            draw.text((x + shadow_off, y + shadow_off), line,
                      font=self._font, fill=(0, 0, 0, shadow_a))
            draw.text((x, y), line, font=self._font, fill=px(TEXT_COLOR))

    def _draw_keyword_underline(self, draw: ImageDraw.ImageDraw,
                                 lines: list, cy: int, lh: int):
        """Trait doré sous le keyword sur la ligne qui le contient (hook only)."""
        for li, line in enumerate(lines):
            if self.keyword in line:
                before, _, _ = line.partition(self.keyword)
                tw_before, _ = get_text_dimensions(before, self._font, draw)
                tw_kw, th_kw = get_text_dimensions(self.keyword, self._font, draw)
                x0 = (RENDER_W - get_text_dimensions(line, self._font, draw)[0]) // 2
                kx0 = x0 + tw_before
                kx1 = kx0 + tw_kw
                y_line = cy + li * lh + th_kw + 3
                draw.rectangle([kx0, y_line, kx1, y_line + 3],
                               fill=(*GOLD_COLOR, 255))
                break

    # ── B-roll frame ──────────────────────────────────────────────────────────
    def _bg(self, t: float) -> np.ndarray:
        if not self.broll:
            arr = np.zeros((RENDER_H, RENDER_W, 3), dtype=np.uint8)
            arr[:] = BG_COLOR
            return arr
        return self.broll[int(t * BROLL_LOAD_FPS) % len(self.broll)]

    # ── Alpha blend léger (texte sur fond pré-assombri) ───────────────────────
    def _blend(self, frame: np.ndarray, anim_alpha: float,
               y_off: int = 0) -> np.ndarray:
        if anim_alpha <= 0.001 or self._pre is None:
            return frame

        txt = self._pre

        if y_off != 0:
            shifted = np.roll(txt, y_off, axis=0)
            if y_off > 0:
                shifted[:y_off] = 0
            txt = shifted

        txt_a   = txt[:, :, 3:4] * anim_alpha
        txt_rgb = txt[:, :, :3] * 255.0
        out = frame.astype(np.float32) * (1.0 - txt_a) + txt_rgb * txt_a
        return np.clip(out, 0, 255).astype(np.uint8)

    def _blend_scaled(self, frame: np.ndarray, scale: float,
                      alpha: float) -> np.ndarray:
        """
        Blend texte mis à l'échelle (scale > 1 = zoom in → crop centre).
        Utilisé pour impact_in (~6 premières frames).
        """
        pil = Image.fromarray((self._pre * 255).astype(np.uint8), "RGBA")
        nw  = int(RENDER_W * scale)
        nh  = int(RENDER_H * scale)
        scaled = pil.resize((nw, nh), Image.BILINEAR)
        # Crop centre pour ramener à (RENDER_W, RENDER_H)
        left = (nw - RENDER_W) // 2
        top  = (nh - RENDER_H) // 2
        cropped = scaled.crop((left, top, left + RENDER_W, top + RENDER_H))
        tmp   = np.array(cropped, dtype=np.float32) / 255.0
        txt_a = tmp[:, :, 3:4] * alpha
        out   = frame.astype(np.float32) * (1.0 - txt_a) + tmp[:, :, :3] * 255.0 * txt_a
        return np.clip(out, 0, 255).astype(np.uint8)

    # ── make_frame ────────────────────────────────────────────────────────────
    def make_frame(self, t: float) -> np.ndarray:
        progress = min(1.0, t / max(self.duration, 0.001))
        frame    = self._bg(t)

        if self.anim == "typing":
            # Typing finishes at 80 % of scene duration — last 20 % holds the
            # complete text so the final word is always visible before cut.
            typing_progress = min(1.0, t / max(self.duration * 0.80, 0.001))
            return self._make_frame_typing(frame, typing_progress)

        if self._pre is None:
            return frame

        anim  = self.anim
        alpha = 1.0
        y_off = 0

        if anim == "impact_in":
            dur   = ANIM_T["impact_in"]
            p_sc  = ease_out(min(1.0, t / dur))
            p_al  = ease_out(min(1.0, t / (dur * 0.55)))
            scale = 1.3 - p_sc * 0.3   # 1.3 → 1.0
            alpha = p_al
            if scale > 1.005:
                return self._blend_scaled(frame, scale, alpha)
            return self._blend(frame, alpha, 0)

        elif anim == "fade_in":
            alpha = ease_out(min(1.0, t / ANIM_T["fade_in"]))

        elif anim in ("slide_up", "slide_in", "slide"):
            p     = ease_out(min(1.0, t / ANIM_T["slide_up"]))
            y_off = int((1.0 - p) * SLIDE_PX)
            alpha = ease_out(min(1.0, t / (ANIM_T["slide_up"] * 0.55)))

        elif anim == "pop":
            p     = ease_out(min(1.0, t / ANIM_T["pop"]))
            alpha = p
            scale = POP_START + p * (1.0 - POP_START)
            if scale < 0.97:
                pil  = Image.fromarray(
                    (self._pre * 255).astype(np.uint8), "RGBA"
                )
                nw, nh = int(RENDER_W * scale), int(RENDER_H * scale)
                c = Image.new("RGBA", (RENDER_W, RENDER_H), (0, 0, 0, 0))
                c.paste(pil.resize((nw, nh), Image.BILINEAR),
                        ((RENDER_W - nw) // 2, (RENDER_H - nh) // 2))
                tmp   = np.array(c, dtype=np.float32) / 255.0
                txt_a = tmp[:, :, 3:4] * alpha
                out   = frame.astype(np.float32) * (1.0 - txt_a) + tmp[:, :, :3] * 255.0 * txt_a
                return np.clip(out, 0, 255).astype(np.uint8)

        elif anim == "fade_out":
            start = max(0.0, self.duration - ANIM_T["fade_out"])
            alpha = (1.0 - max(0.0, t - start) / ANIM_T["fade_out"]) if t > start else 1.0

        return self._blend(frame, alpha, y_off)

    def _make_frame_typing(self, frame: np.ndarray, progress: float) -> np.ndarray:
        """Typing : rendu PIL, chemin plus lent mais nécessaire."""
        img   = Image.fromarray(frame, "RGB").convert("RGBA")
        layer = Image.new("RGBA", (RENDER_W, RENDER_H), (0, 0, 0, 0))
        draw  = ImageDraw.Draw(layer)
        lines = wrap_text(self.text, self._font, RENDER_W - 60)
        lh    = self.fs + 9
        cy    = (RENDER_H - len(lines) * lh) // 2
        total = sum(len(l) for l in lines)
        vis, shown = max(1, int(progress * total)), 0

        for li, line in enumerate(lines):
            take  = min(max(0, vis - shown), len(line))
            shown += len(line)
            if take <= 0:
                break
            self._draw_line(draw, line[:take], cy + li * lh, 255)

        img.alpha_composite(layer)
        return np.array(img.convert("RGB"))


# ── Gold Outro ────────────────────────────────────────────────────────────────
OUTRO_FADE_IN = 0.55   # durée du fade-in (s)

class GoldOutroRenderer:
    """
    Page finale dorée : fond sombre, ligne or, handle @compte en or, "Follow" en blanc.
    Pré-rendu une seule fois en numpy, fade-in doux.
    """

    def __init__(self, scene_cfg: dict):
        self.duration = float(scene_cfg.get("duration", 3.0))
        self.handle   = scene_cfg.get("handle", "@ownyourtime.ai")
        self.follow_text = scene_cfg.get("follow_text", "Follow pour plus")
        self._frame: np.ndarray | None = None
        self._prerender()

    def _prerender(self):
        img  = Image.new("RGBA", (RENDER_W, RENDER_H), (*BG_COLOR, 255))
        draw = ImageDraw.Draw(img)

        font_handle = font_cache.get(44, "bold")
        font_follow = font_cache.get(26, "regular")
        font_tag    = font_cache.get(20, "regular")

        cx = RENDER_W // 2
        cy = int(RENDER_H * 0.44)   # légèrement au-dessus du centre

        # ── Ligne dorée ────────────────────────────────────────────────────
        bar_w, bar_h = 180, 3
        bar_x0 = cx - bar_w // 2
        draw.rectangle([bar_x0, cy - 60, bar_x0 + bar_w, cy - 60 + bar_h],
                       fill=GOLD_COLOR)

        # ── "@ownyourtime.ai" en or ────────────────────────────────────────
        tw_h, th_h = get_text_dimensions(self.handle, font_handle, draw)
        # Ombre
        sx = cx - tw_h // 2
        draw.text((sx + 3, cy - 30 + 3), self.handle,
                  font=font_handle, fill=(0, 0, 0, 180))
        draw.text((sx, cy - 30), self.handle,
                  font=font_handle, fill=GOLD_COLOR)

        # ── "Follow pour plus" en blanc ────────────────────────────────────
        tw_f, _ = get_text_dimensions(self.follow_text, font_follow, draw)
        draw.text((cx - tw_f // 2, cy - 60 - 44),
                  self.follow_text, font=font_follow,
                  fill=(*TEXT_COLOR, 200))

        # ── Tagline sous le handle ─────────────────────────────────────────
        tag = "IA · Productivite · Revenue"
        tw_t, _ = get_text_dimensions(tag, font_tag, draw)
        draw.text((cx - tw_t // 2, cy - 30 + th_h + 16),
                  tag, font=font_tag,
                  fill=(*GOLD_COLOR[:3], 140))

        # ── Ligne dorée basse ──────────────────────────────────────────────
        draw.rectangle([bar_x0, cy - 30 + th_h + 52,
                        bar_x0 + bar_w, cy - 30 + th_h + 52 + bar_h],
                       fill=GOLD_COLOR)

        self._frame = np.array(img.convert("RGB"))

    def make_frame(self, t: float) -> np.ndarray:
        alpha = ease_out(min(1.0, t / OUTRO_FADE_IN))
        if alpha >= 0.999:
            return self._frame
        black = np.zeros_like(self._frame)
        out   = black.astype(np.float32) * (1.0 - alpha) + self._frame.astype(np.float32) * alpha
        return np.clip(out, 0, 255).astype(np.uint8)


# ── Template principal ────────────────────────────────────────────────────────
class ViralTextCentricTemplate:
    """viral_text_centric_v1 : rendu 540×960, upscale FFmpeg 1080×1920."""

    def __init__(self, config: dict):
        self.config, issues = validate_config(config)
        for msg in issues:
            logger.info(f"[auto-fix] {msg}")

        self.fps        = FPS
        self.scenes_cfg = self.config.get("scenes", [])
        self.audio_cfg  = self.config.get("audio", {})
        self.bg_cfg     = self.config.get("background", {})

        bg_videos = self.bg_cfg.get("videos", [])
        # Chemins valides présents dans le YAML
        self.video_paths: list[str] = [
            v["path"] for v in bg_videos
            if isinstance(v, dict) and v.get("path") and Path(v["path"]).exists()
        ]
        # Queries Pexels pour auto-download si paths vides
        self._pexels_queries: list[str] = [
            v["query"] for v in bg_videos
            if isinstance(v, dict) and v.get("query")
            and not (v.get("path") and Path(v.get("path", "x")).exists())
        ] if not self.video_paths else []

        self.overlay_opacity = float(self.bg_cfg.get("overlay_opacity", 0.55))
        self.total_duration  = float(self.config.get("total_duration", 0)) or sum(
            float(s.get("duration", 2.8)) for s in self.scenes_cfg
        )
        self._banks: list[list[np.ndarray]] = []

    def _load_broll(self):
        if self._banks:
            return

        # Auto-download Pexels si le YAML a des queries mais pas de paths valides
        if not self.video_paths and self._pexels_queries:
            try:
                from utils.pexels import get_pexels_videos
                paths = get_pexels_videos(self._pexels_queries, max_videos=3)
                if paths:
                    self.video_paths = paths
                    logger.info(f"Pexels auto-téléchargé : {len(paths)} vidéo(s)")
            except Exception as e:
                logger.warning(f"Pexels auto-download : {e}")

        # Fallback vidéo locale
        if not self.video_paths:
            fb = self.config.get("broll_video", "")
            if fb and Path(fb).exists():
                self.video_paths = [fb]
                logger.info(f"Fallback broll local : {Path(fb).name}")

        if not self.video_paths:
            logger.warning("Aucune vidéo de fond — fond sombre")
            self._banks = [[]]
            return

        for path in self.video_paths:
            frames = _load_frames(path, self.overlay_opacity)
            if frames:
                self._banks.append(frames)
        if not self._banks:
            self._banks = [[]]

    def _scene_frames(self, bank_idx: int, n: int, offset: int) -> list:
        bank = self._banks[bank_idx]
        if not bank:
            return []
        s = offset % len(bank)
        return [bank[(s + j) % len(bank)] for j in range(n + 6)]

    def generate_preview_frame(self, output_path: str,
                                segment: str = "hook", t: float = 0.5):
        self._load_broll()
        sc = next(
            (s for s in self.scenes_cfg if s.get("type") == segment),
            self.scenes_cfg[0] if self.scenes_cfg else {},
        )
        if sc.get("type") == "gold_outro":
            renderer = GoldOutroRenderer(sc)
        else:
            renderer = SceneRenderer(sc, self._banks[0])
        frame    = renderer.make_frame(t)
        img = Image.fromarray(frame).resize((CANVAS_W, CANVAS_H), Image.LANCZOS)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        img.save(output_path)
        logger.info(f"Preview {segment} → {output_path}")

    def _build_synced_audio(self, scene_vo_paths: list[str], total_duration: float):
        """
        Builds a CompositeAudioClip where each scene voiceover is placed at
        the correct time offset, mixed under the background music.
        Returns the composite clip or None on failure.
        """
        from moviepy.editor import AudioFileClip, CompositeAudioClip
        try:
            from moviepy.audio.AudioClip import concatenate_audioclips
        except ImportError:
            concatenate_audioclips = None

        vo_clips = []
        t_cursor = 0.0
        for path in scene_vo_paths:
            if path and Path(path).exists():
                try:
                    c = AudioFileClip(path).set_start(t_cursor)
                    vo_clips.append(c)
                    t_cursor += c.duration + 0.35   # 350 ms buffer between scenes
                except Exception as e:
                    logger.warning(f"Scène audio ignorée ({path}): {e}")
                    t_cursor += 2.8  # fallback advance
            else:
                t_cursor += 2.8

        # Background music
        bg_path  = self.audio_cfg.get("background_music", "")
        bg_vol   = float(self.audio_cfg.get("volume", 0.28))
        bg_clips = []
        if bg_path and Path(bg_path).exists():
            try:
                bg = AudioFileClip(bg_path).volumex(bg_vol)
                if concatenate_audioclips and bg.duration < total_duration:
                    repeats = int(total_duration / bg.duration) + 1
                    bg = concatenate_audioclips([bg] * repeats)
                bg = bg.subclip(0, total_duration)
                bg_clips = [bg]
            except Exception as e:
                logger.warning(f"Musique de fond ignorée : {e}")

        all_clips = bg_clips + vo_clips
        if not all_clips:
            return None
        return CompositeAudioClip(all_clips)

    def generate(self, output_path: str, use_remotion: bool = False) -> str:
        from moviepy.editor import VideoClip, AudioFileClip, concatenate_videoclips

        self._load_broll()
        n_banks  = len([b for b in self._banks if b])
        n_scenes = len(self.scenes_cfg)

        # Sync mode: one audio file per scene drives scene duration.
        # gold_outro is excluded from the count (it has no voiceover).
        scene_vo_paths: list[str] = self.audio_cfg.get("scene_voiceovers", [])
        _n_voiced = sum(1 for sc in self.scenes_cfg if sc.get("type") != "gold_outro")
        sync_mode = bool(scene_vo_paths) and len(scene_vo_paths) >= _n_voiced

        # Attribution par blocs : video 1 → scènes 0..k, video 2 → scènes k+1..2k…
        block_size = max(1, math.ceil(n_scenes / n_banks)) if n_banks > 0 else n_scenes

        logger.info(
            f"ViralTextCentric : {n_scenes} scènes · "
            f"{'SYNC' if sync_mode else 'fixed'} audio · "
            f"{n_banks} vidéo(s) · "
            f"{self.fps}fps · rendu {RENDER_W}×{RENDER_H} → upscale {CANVAS_W}×{CANVAS_H}"
        )

        clips = []
        # Offset par banque : chaque vidéo repart de 0 quand le bloc commence
        bank_offsets = [0] * max(n_banks, 1)

        for i, sc in enumerate(self.scenes_cfg):
            # In sync mode, scene duration = audio clip duration + 350 ms buffer
            if sync_mode and i < len(scene_vo_paths):
                vo_path = scene_vo_paths[i]
                if vo_path and Path(vo_path).exists():
                    try:
                        _probe = AudioFileClip(vo_path)
                        dur = round(_probe.duration + 0.35, 3)
                        _probe.close()
                    except Exception:
                        dur = float(sc.get("duration", 2.8))
                else:
                    dur = float(sc.get("duration", 2.8))
            else:
                dur = float(sc.get("duration", 2.8))

            n_frames = int(dur * self.fps)

            # Attribution bloc : video 1 pour scènes 0..k, video 2 pour k+1..2k…
            bank_idx = min(i // block_size, n_banks - 1) if n_banks > 0 else 0

            if sc.get("type") == "gold_outro":
                renderer = GoldOutroRenderer(sc)
            else:
                frames = self._scene_frames(bank_idx, n_frames, bank_offsets[bank_idx])
                bank_offsets[bank_idx] += n_frames
                # Pass the actual computed duration (sync mode may differ from YAML)
                sc_runtime = {**sc, "duration": dur}
                renderer = SceneRenderer(sc_runtime, frames)

            def make_frame(t, r=renderer): return r.make_frame(t)

            clip = VideoClip(make_frame, duration=dur).set_fps(self.fps)
            clips.append(clip)

            logger.info(
                f"  Scène {i+1}/{n_scenes} [{sc.get('type','')}] "
                f"bank={bank_idx} · {dur:.2f}s · "
                f"{sc.get('text_animation', sc.get('animation', 'fade_in'))}"
                + (" [sync]" if sync_mode else "")
            )

        final = concatenate_videoclips(clips, method="compose")

        try:
            if sync_mode:
                audio_clip = self._build_synced_audio(scene_vo_paths, final.duration)
            else:
                from utils.audio import get_audio_clip
                audio_clip = get_audio_clip(self.audio_cfg, final.duration)
            if audio_clip is not None:
                final = final.set_audio(audio_clip)
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
