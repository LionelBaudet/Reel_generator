"""
Segment vidéo d'accroche — intègre une vidéo stock au début du reel.

Fonctionnement:
  - Charge une vidéo source (MP4, MOV…) fournie par l'utilisateur
  - La recadre automatiquement en portrait 1080×1920 (crop centré)
  - Applique un gradient sombre + vignettage + fade in/out
  - Affiche un texte d'accroche optionnel en bas de l'image
  - Si aucune vidéo n'est disponible, génère un segment animé de remplacement
"""

import logging
import math
import os
import subprocess
import tempfile
import numpy as np
from PIL import Image, ImageDraw

# Patch de compatibilité : Pillow 10+ a supprimé Image.ANTIALIAS (remplacé par LANCZOS)
# MoviePy 1.0.3 utilise encore l'ancien nom — on le restaure ici.
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

from utils.fonts import font_cache
from utils.renderer import (
    COLORS, CANVAS_W, CANVAS_H,
    ease_out, draw_rounded_rect, get_text_dimensions, wrap_text,
)

logger = logging.getLogger(__name__)


class IntroVideoRenderer:
    """
    Intègre une vidéo stock en début de reel.
    Si la vidéo est absente, génère un segment animé de remplacement
    (fond sombre avec texte animé).
    """

    def __init__(self, intro_config: dict):
        self.video_path = intro_config.get("video", "")
        self.duration   = float(intro_config.get("duration", 3.0))
        self.text       = intro_config.get("text", "")
        self.subtext    = intro_config.get("subtext", "")
        self.fade_in    = float(intro_config.get("fade_in", 0.4))
        self.fade_out   = float(intro_config.get("fade_out", 0.5))
        self.overlay    = float(intro_config.get("overlay_opacity", 0.50))
        self.start_at   = float(intro_config.get("start_at", 0.0))

    # ── API publique ───────────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Retourne True si le fichier vidéo source existe."""
        return bool(self.video_path) and os.path.exists(self.video_path)

    def get_clip(self):
        """
        Prépare et retourne un clip MoviePy prêt à concaténer.

        Returns:
            VideoClip MoviePy (vidéo stock traitée ou animation de remplacement)
        """
        if self.is_available():
            return self._clip_from_video()
        else:
            logger.warning(
                f"Vidéo d'accroche introuvable: '{self.video_path}' — "
                "génération d'une animation de remplacement"
            )
            return self._clip_fallback()

    # ── Pipeline vidéo stock ──────────────────────────────────────────────

    def _clip_from_video(self):
        """Charge, recadre, et décore la vidéo stock."""
        try:
            from moviepy.editor import VideoFileClip
        except ImportError:
            from moviepy import VideoFileClip

        logger.info(f"Chargement de la vidéo d'accroche: {self.video_path}")
        raw = VideoFileClip(self.video_path, audio=False)

        # Couper à partir de start_at
        if self.start_at > 0:
            raw = raw.subclip(self.start_at)

        # Limiter à la durée configurée
        duration = min(self.duration, raw.duration)
        raw = raw.subclip(0, duration)

        # Recadrer en portrait 9:16
        raw = self._resize_to_portrait(raw)

        # Appliquer les effets visuels frame par frame
        processed = raw.fl(self._apply_effects)

        return processed

    def _resize_to_portrait(self, clip):
        """
        Redimensionne et recadre en 1080×1920 (couverture centrée).
        Compatible avec les sources 16:9, 4:3, 1:1, etc.
        """
        src_w, src_h = clip.size
        # Calculer l'échelle minimale pour couvrir le canvas entier
        scale = max(CANVAS_W / src_w, CANVAS_H / src_h)
        new_w = int(src_w * scale)
        new_h = int(src_h * scale)

        clip = clip.resize((new_w, new_h))

        # Recadrer au centre
        x1 = (new_w - CANVAS_W) // 2
        y1 = (new_h - CANVAS_H) // 2
        clip = clip.crop(x1=x1, y1=y1, x2=x1 + CANVAS_W, y2=y1 + CANVAS_H)

        return clip

    def _apply_effects(self, get_frame, t: float) -> np.ndarray:
        """
        Applique sur chaque frame:
          1. Gradient sombre en bas (lisibilité du texte)
          2. Vignettage sur les bords
          3. Fade in / fade out
          4. Texte d'accroche + sous-texte
          5. Bande de marque en bas
        """
        frame = get_frame(t)
        img = Image.fromarray(frame.astype(np.uint8)).convert("RGBA")

        # ── 1. Gradient sombre en bas ──────────────────────────────────
        grad = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
        grad_draw = ImageDraw.Draw(grad)
        grad_height = int(CANVAS_H * 0.60)
        grad_start  = CANVAS_H - grad_height

        for y in range(grad_height):
            ratio = y / grad_height
            alpha = int(self.overlay * 255 * (ratio ** 1.2))
            grad_draw.line(
                [(0, grad_start + y), (CANVAS_W, grad_start + y)],
                fill=(5, 5, 20, alpha),
            )

        # Gradient léger en haut (vignette)
        for y in range(int(CANVAS_H * 0.15)):
            alpha = int(80 * (1 - y / (CANVAS_H * 0.15)))
            grad_draw.line([(0, y), (CANVAS_W, y)], fill=(0, 0, 0, alpha))

        # ── 2. Vignettage sur les bords latéraux ──────────────────────
        vign_w = 80
        for x in range(vign_w):
            alpha = int(100 * (1 - x / vign_w) ** 2)
            grad_draw.line([(x, 0), (x, CANVAS_H)], fill=(0, 0, 0, alpha))
            grad_draw.line([(CANVAS_W - x, 0), (CANVAS_W - x, CANVAS_H)], fill=(0, 0, 0, alpha))

        img = Image.alpha_composite(img, grad)

        # ── 3. Texte d'accroche + sous-texte ──────────────────────────
        draw = ImageDraw.Draw(img)

        if self.text or self.subtext:
            self._draw_intro_text(draw, t)

        # ── 4. Bande @ownyourtime.ai (coin bas gauche) ─────────────────
        self._draw_brand_badge(draw, t)

        # ── 5. Fade in / Fade out ──────────────────────────────────────
        img = self._apply_fades(img, t)

        return np.array(img.convert("RGB"))

    def _draw_intro_text(self, draw: ImageDraw.ImageDraw, t: float):
        """Dessine le texte d'accroche animé en bas de l'image."""
        font_main = font_cache.get(68, "bold")
        font_sub  = font_cache.get(36, "regular")

        # Apparition progressive (après le fade_in)
        text_start = self.fade_in + 0.15
        text_prog  = ease_out(min(1.0, max(0.0, (t - text_start) / 0.35)))

        if text_prog <= 0:
            return

        alpha  = int(text_prog * 255)
        slide  = int((1 - text_prog) * 50)   # Glisse vers le haut à l'entrée
        margin = 60

        # ── Texte principal ────────────────────────────────────────────
        if self.text:
            lines = wrap_text(self.text, font_main, CANVAS_W - margin * 2)
            line_h = 84
            y_base = CANVAS_H - 260 - len(lines) * line_h + slide

            for i, line in enumerate(lines):
                w, h = get_text_dimensions(line, font_main, draw)
                draw.text(
                    (margin, y_base + i * line_h),
                    line,
                    font=font_main,
                    fill=(*COLORS["ivory"], alpha),
                )

            # Trait doré à gauche du texte
            bar_h = len(lines) * line_h - 10
            bar_h_visible = int(bar_h * text_prog)
            draw.rectangle(
                [margin - 12, y_base + 4, margin - 6, y_base + 4 + bar_h_visible],
                fill=(*COLORS["gold"], alpha),
            )

        # ── Sous-texte ─────────────────────────────────────────────────
        if self.subtext and t > text_start + 0.3:
            sub_prog = ease_out(min(1.0, (t - text_start - 0.3) / 0.35))
            sub_alpha = int(sub_prog * 200)
            sub_slide = int((1 - sub_prog) * 30)

            sw, sh = get_text_dimensions(self.subtext, font_sub, draw)
            draw.text(
                (margin, CANVAS_H - 160 + sub_slide),
                self.subtext,
                font=font_sub,
                fill=(*COLORS["gold"], sub_alpha),
            )

    def _draw_brand_badge(self, draw: ImageDraw.ImageDraw, t: float):
        """Affiche le handle @ownyourtime.ai en bas à droite."""
        font_brand = font_cache.get(26, "mono")
        brand = "@ownyourtime.ai"

        badge_prog = ease_out(min(1.0, max(0.0, (t - self.fade_in) / 0.4)))
        if badge_prog <= 0:
            return

        alpha = int(badge_prog * 180)
        bw, bh = get_text_dimensions(brand, font_brand, draw)
        draw.text(
            (CANVAS_W - bw - 40, CANVAS_H - 60),
            brand,
            font=font_brand,
            fill=(*COLORS["muted"], alpha),
        )

    def _apply_fades(self, img: Image.Image, t: float) -> Image.Image:
        """Applique le fondu en entrée et en sortie."""
        # Fade in
        if t < self.fade_in:
            alpha = int((1 - t / self.fade_in) * 255)
            black = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, alpha))
            img = Image.alpha_composite(img, black)

        # Fade out
        elif t > self.duration - self.fade_out:
            progress = (t - (self.duration - self.fade_out)) / self.fade_out
            alpha = int(min(1.0, progress) * 255)
            black = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, alpha))
            img = Image.alpha_composite(img, black)

        return img

    # ── Segment de remplacement (sans vidéo) ──────────────────────────────

    def _clip_fallback(self):
        """
        Génère une animation de remplacement si aucune vidéo n'est disponible.
        Fond sombre avec animation de texte et d'icône clavier.
        """
        try:
            from moviepy.editor import VideoClip
        except ImportError:
            from moviepy import VideoClip

        logger.info("Génération du segment d'accroche de remplacement (sans vidéo)")

        def make_fallback_frame(t: float) -> np.ndarray:
            img = Image.new("RGB", (CANVAS_W, CANVAS_H), COLORS["midnight"])
            draw = ImageDraw.Draw(img)

            # Fond avec dégradé subtil
            for y in range(CANVAS_H):
                ratio = y / CANVAS_H
                r = int(COLORS["midnight"][0] * (1 - ratio * 0.3) + COLORS["deep_ink"][0] * ratio * 0.3)
                g = int(COLORS["midnight"][1] * (1 - ratio * 0.3) + COLORS["deep_ink"][1] * ratio * 0.3)
                b = int(COLORS["midnight"][2] * (1 - ratio * 0.3) + COLORS["deep_ink"][2] * ratio * 0.3)
                draw.line([(0, y), (CANVAS_W, y)], fill=(r, g, b))

            # Animation d'un écran d'ordinateur stylisé
            self._draw_laptop_illustration(draw, t)

            # Texte d'accroche
            if self.text or self.subtext:
                self._draw_intro_text(draw, t)

            self._draw_brand_badge(draw, t)

            # Fade in/out
            img_rgba = img.convert("RGBA")
            img_rgba = self._apply_fades(img_rgba, t)
            return np.array(img_rgba.convert("RGB"))

        return VideoClip(make_fallback_frame, duration=self.duration)

    def _draw_laptop_illustration(self, draw: ImageDraw.ImageDraw, t: float):
        """
        Dessine une illustration minimaliste d'écran d'ordinateur
        avec un curseur qui clignote et du texte qui s'écrit.
        """
        font_code = font_cache.get(28, "mono")
        font_label = font_cache.get(22, "mono")

        # ── Écran / fenêtre de terminal ────────────────────────────────
        screen_w, screen_h = 800, 480
        screen_x = (CANVAS_W - screen_w) // 2
        screen_y = int(CANVAS_H * 0.18)

        # Entrée progressive de l'écran
        enter_prog = ease_out(min(1.0, t / 0.6))
        screen_y_offset = int((1 - enter_prog) * 80)
        screen_y -= screen_y_offset

        # Fond de l'écran
        draw_rounded_rect(
            draw,
            (screen_x, screen_y, screen_x + screen_w, screen_y + screen_h),
            radius=16,
            fill=(14, 14, 28),
            outline=COLORS["card_border"],
            outline_width=2,
        )

        # Barre de titre du terminal
        title_h = 44
        draw_rounded_rect(
            draw,
            (screen_x, screen_y, screen_x + screen_w, screen_y + title_h),
            radius=16,
            fill=(22, 22, 42),
            outline=None,
        )
        # Points macOS
        for i, color in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
            cx = screen_x + 22 + i * 22
            cy = screen_y + 22
            draw.ellipse([(cx - 7, cy - 7), (cx + 7, cy + 7)], fill=color)

        # Titre de la fenêtre
        title = "ChatGPT  —  New conversation"
        draw.text(
            (screen_x + screen_w // 2 - 120, screen_y + 13),
            title,
            font=font_label,
            fill=COLORS["muted"],
        )

        # ── Contenu de l'écran : texte qui s'écrit ─────────────────────
        content_x = screen_x + 30
        content_y = screen_y + title_h + 20
        content_max_w = screen_w - 60

        sample_lines = [
            "Write a professional email to Sarah",
            "about the project delay. Tone: direct.",
            "Max 5 lines. One clear CTA.",
        ]
        total_chars = sum(len(l) for l in sample_lines) + len(sample_lines)

        # Texte visible en fonction du temps
        type_duration = self.duration * 0.65
        chars_visible = int(min(1.0, t / type_duration) * total_chars)

        chars_drawn = 0
        line_h = 44
        for i, line in enumerate(sample_lines):
            if chars_drawn >= chars_visible:
                break
            chars_to_show = min(len(line), chars_visible - chars_drawn)
            draw.text(
                (content_x, content_y + i * line_h),
                line[:chars_to_show],
                font=font_code,
                fill=COLORS["ivory"],
            )
            chars_drawn += len(line) + 1

        # Curseur clignotant (1.5 Hz)
        cursor_on = int(t * 3) % 2 == 0
        if cursor_on and chars_drawn <= total_chars:
            # Position du curseur après le dernier caractère visible
            last_line_idx = min(len(sample_lines) - 1, chars_drawn // (total_chars // len(sample_lines) + 1))
            last_line = sample_lines[min(last_line_idx, len(sample_lines)-1)]
            chars_in_last = min(len(last_line), chars_visible - sum(len(l)+1 for l in sample_lines[:last_line_idx]))
            chars_in_last = max(0, chars_in_last)
            cursor_text = last_line[:chars_in_last]
            cw, _ = get_text_dimensions(cursor_text, font_code, draw)
            draw.text(
                (content_x + cw, content_y + last_line_idx * line_h),
                "▋",
                font=font_code,
                fill=COLORS["gold"],
            )
