"""
Template "Prompt Reveal" — le template principal pour @ownyourtime.ai
Génère un reel en 4 segments : Intro vidéo → Hook → Prompt Reveal → CTA

Structure:
  - Segment 0 (Intro, 0–3s)   : Vidéo stock (personne qui tape) + texte d'accroche
  - Segment 1 (Hook, 3–6s)    : Texte accrocheur mot par mot + soulignement or
  - Segment 2 (Prompt, 6–18s) : Carte prompt avec animation de frappe + output terminal
  - Segment 3 (CTA, 18–21s)   : Fond or, texte pulsant, appel à l'action
"""

import logging
import math
import os
import subprocess
import json
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from utils.fonts import font_cache
from utils.renderer import (
    COLORS, CANVAS_W, CANVAS_H,
    ease_in_out, ease_out, pulse, shake_offset,
    draw_rounded_rect, draw_gradient_background,
    wrap_text, get_text_dimensions, draw_text_with_shadow,
)

logger = logging.getLogger(__name__)

FPS = 30  # Images par seconde


# ─────────────────────────────────────────────────────────────────────────────
# SEGMENT 1 — HOOK
# ─────────────────────────────────────────────────────────────────────────────

class HookRenderer:
    """Génère les frames du segment Hook (texte accrocheur mot par mot)."""

    def __init__(self, hook_config: dict):
        self.text = hook_config.get("text", "")
        self.highlight = hook_config.get("highlight", "")
        self.duration = float(hook_config.get("duration", 3))
        self.words = self.text.split()

    def make_frame(self, t: float) -> np.ndarray:
        """
        Génère un frame à l'instant t (en secondes).

        Args:
            t: Temps relatif au début du segment [0, duration]

        Returns:
            Array numpy (H, W, 3) uint8
        """
        img = Image.new("RGB", (CANVAS_W, CANVAS_H), COLORS["midnight"])
        draw = ImageDraw.Draw(img)

        # ── Dégradé de fond subtil ─────────────────────────────────────────
        draw_gradient_background(img, COLORS["midnight"], COLORS["deep_ink"])
        draw = ImageDraw.Draw(img)

        # ── Paramètres de timing ──────────────────────────────────────────
        n_words = len(self.words)
        # Les mots apparaissent sur 70% de la durée
        words_phase_end = self.duration * 0.70
        # Le soulignement apparaît après les mots
        underline_phase_start = self.duration * 0.65

        # Nombre de mots visibles à cet instant
        if t <= words_phase_end:
            words_progress = t / words_phase_end if words_phase_end > 0 else 1
            n_visible = max(1, int(words_progress * n_words))
        else:
            n_visible = n_words

        # ── Polices ────────────────────────────────────────────────────────
        font_title = font_cache.get(72, "bold")
        font_label = font_cache.get(28, "mono")

        # ── Rendu des mots ─────────────────────────────────────────────────
        visible_text = " ".join(self.words[:n_visible])
        lines = wrap_text(visible_text, font_title, CANVAS_W - 120)

        # Calculer la hauteur totale du bloc de texte
        line_height = 90
        total_text_h = len(lines) * line_height
        y_start = (CANVAS_H - total_text_h) // 2 - 60

        for i, line in enumerate(lines):
            w, h = get_text_dimensions(line, font_title, draw)
            x = (CANVAS_W - w) // 2
            y = y_start + i * line_height

            # Opacité progressive pour l'apparition des mots
            if i == len(lines) - 1 and n_visible < n_words:
                # Dernière ligne en cours d'apparition — légère transparence
                alpha = int(ease_out(words_progress % (1 / max(n_words, 1)) * n_words) * 255)
                alpha = max(180, alpha)
            else:
                alpha = 255

            # Dessiner le texte en ivoire
            draw.text((x, y), line, font=font_title, fill=COLORS["ivory"])

        # ── Soulignement doré sous le texte en surbrillance ──────────────
        if self.highlight and t >= underline_phase_start:
            underline_progress = min(1.0, (t - underline_phase_start) / 0.4)
            underline_progress = ease_out(underline_progress)
            self._draw_highlight_underline(draw, font_title, lines, y_start, line_height, underline_progress)

        # ── Étiquette de marque en bas ────────────────────────────────────
        brand_alpha = min(255, int(ease_out(t / self.duration) * 200))
        brand_text = "@ownyourtime.ai"
        bw, bh = get_text_dimensions(brand_text, font_label, draw)
        draw.text(
            ((CANVAS_W - bw) // 2, CANVAS_H - 120),
            brand_text,
            font=font_label,
            fill=(*COLORS["muted"], brand_alpha)
        )

        return np.array(img)

    def _draw_highlight_underline(self, draw, font, lines, y_start, line_height, progress):
        """Dessine le soulignement doré sous les mots en surbrillance."""
        highlight_words = self.highlight.lower().split()

        for i, line in enumerate(lines):
            line_lower = line.lower()
            # Chercher si cette ligne contient des mots en surbrillance
            if any(word in line_lower for word in highlight_words):
                w, h = get_text_dimensions(line, font, draw)
                x = (CANVAS_W - w) // 2
                y = y_start + i * line_height + line_height - 5

                # Largeur animée (slide depuis la gauche)
                underline_w = int(w * progress)
                underline_thickness = 5

                draw.rectangle(
                    [x, y, x + underline_w, y + underline_thickness],
                    fill=COLORS["gold"]
                )


# ─────────────────────────────────────────────────────────────────────────────
# SEGMENT 2 — PROMPT REVEAL
# ─────────────────────────────────────────────────────────────────────────────

class PromptRevealRenderer:
    """
    Segment Prompt Reveal — interface fidèle à ChatGPT Dark Mode.

    Layout mobile vertical (1080×1920):
      ┌─────────────────────────────┐
      │  Status bar  (heure etc.)   │  55px
      │  Nav: ChatGPT  4o  ▾        │  90px
      ├─────────────────────────────┤
      │                             │
      │  [bulle utilisateur →]      │  frappe animée
      │                             │
      │  ● ChatGPT                  │
      │  Réponse qui streame...      │  mot par mot
      │                             │
      ├─────────────────────────────┤
      │  [ Message ChatGPT...  🎤 ] │  130px
      └─────────────────────────────┘

    Timing sur 12 secondes:
      0.0–0.4s  : fondu d'entrée
      0.4–4.2s  : frappe du message utilisateur
      4.2–5.4s  : animation trois points (réflexion)
      5.4–11.5s : streaming de la réponse mot par mot
      11.5–12s  : fondu de sortie vers le CTA
    """

    # ── Palette ChatGPT Dark Mode ──────────────────────────────────────
    BG          = (33, 33, 33)      # #212121
    NAV_BG      = (33, 33, 33)
    USER_BG     = (64, 64, 64)      # bulle utilisateur
    TEXT        = (236, 236, 236)   # #ececec
    TEXT_DIM    = (142, 142, 160)   # #8e8ea0
    TEAL        = (16, 163, 127)    # #10a37f — vert OpenAI
    INPUT_BG    = (47, 47, 47)      # #2f2f2f
    BORDER      = (60, 60, 60)      # séparateurs
    CODE_BG     = (39, 39, 39)      # fond code inline

    def __init__(self, prompt_config: dict):
        self.title       = prompt_config.get("title", "The Prompt")
        self.prompt_text = prompt_config.get("text", "").strip()
        self.output_text = prompt_config.get("output_preview", "").strip()
        self.saves       = prompt_config.get("saves", "")
        self.duration    = float(prompt_config.get("duration", 12))

        # Mots de la réponse pour le streaming
        # Tokenise en préservant les sauts de ligne comme tokens spéciaux
        self.output_tokens = self._tokenize_output(self.output_text)
        self.output_words  = self.output_text.split()   # pour compatibilité _words_at

        # ── Timing des phases ─────────────────────────────────────────
        self.t_fade_in    = 0.4
        self.t_type_start = 0.4
        self.t_type_end   = min(4.2, self.duration * 0.35)
        self.t_think_end  = self.t_type_end + 1.2
        self.t_stream_end = self.duration - 0.4
        self.t_fade_out   = self.duration - 0.4

    def make_frame(self, t: float) -> np.ndarray:
        """Génère un frame à l'instant t."""
        img  = Image.new("RGB", (CANVAS_W, CANVAS_H), self.BG)
        draw = ImageDraw.Draw(img)

        # ── Layout zones ───────────────────────────────────────────────
        STATUS_H = 55
        NAV_H    = 90
        INPUT_H  = 130
        CHAT_TOP = STATUS_H + NAV_H
        CHAT_BOT = CANVAS_H - INPUT_H

        # ── Rendu des composants ───────────────────────────────────────
        self._draw_status_bar(draw, STATUS_H)
        self._draw_nav_bar(draw, STATUS_H, NAV_H)
        draw.line([(0, CHAT_TOP), (CANVAS_W, CHAT_TOP)], fill=self.BORDER, width=1)
        bottom_y = self._draw_chat(draw, img, t, CHAT_TOP, CHAT_BOT)
        self._draw_input_area(draw, CHAT_BOT, INPUT_H)

        # ── Badge "saves X min/day" ───────────────────────────────────
        if self.saves and t > self.t_stream_end - 1.0:
            prog = min(1.0, (t - (self.t_stream_end - 1.0)) / 0.4)
            self._draw_saves_badge(draw, prog)

        # ── Fades entrée / sortie ─────────────────────────────────────
        img_rgba = img.convert("RGBA")
        if t < self.t_fade_in:
            alpha = int((1 - t / self.t_fade_in) * 255)
            img_rgba = Image.alpha_composite(
                img_rgba, Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, alpha))
            )
        elif t > self.t_fade_out:
            alpha = int(min(1.0, (t - self.t_fade_out) / 0.4) * 255)
            img_rgba = Image.alpha_composite(
                img_rgba, Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, alpha))
            )
        return np.array(img_rgba.convert("RGB"))

    # ─────────────────────────────────────────────────────────────────
    # Composants UI
    # ─────────────────────────────────────────────────────────────────

    def _draw_status_bar(self, draw: ImageDraw.ImageDraw, height: int):
        """Barre de statut iOS/Android (heure, batterie, signal)."""
        font = font_cache.get(26, "mono")

        # Heure au centre — "9:41" (référence Apple)
        time_str = "9:41"
        tw, th = get_text_dimensions(time_str, font, draw)
        draw.text(((CANVAS_W - tw) // 2, (height - th) // 2), time_str, font=font, fill=self.TEXT)

        # Icônes réseau (droite) — simplifiées
        rx, ry = CANVAS_W - 220, height // 2 - 8
        # WiFi — 3 arcs concentriques
        for i, r in enumerate([16, 11, 6]):
            draw.arc([(rx - r, ry), (rx + r, ry + r)], 210, 330, fill=self.TEXT, width=2)
        # Barres réseau
        bx = rx + 28
        for i in range(4):
            bar_h = 6 + i * 4
            draw.rectangle(
                [(bx + i * 10, ry + 16 - bar_h), (bx + i * 10 + 6, ry + 16)],
                fill=self.TEXT if i < 3 else self.TEXT_DIM,
            )
        # Batterie
        bx2 = bx + 56
        draw.rounded_rectangle([(bx2, ry + 1), (bx2 + 42, ry + 15)], radius=3,
                                fill=None, outline=self.TEXT, width=2)
        draw.rectangle([(bx2 + 3, ry + 4), (bx2 + 32, ry + 12)], fill=self.TEXT)
        draw.rectangle([(bx2 + 42, ry + 5), (bx2 + 46, ry + 11)], fill=self.TEXT)

    def _draw_nav_bar(self, draw: ImageDraw.ImageDraw, top: int, height: int):
        """Barre de navigation ChatGPT — titre centré + icônes latérales."""
        font_title = font_cache.get(38, "bold")
        font_model = font_cache.get(29, "regular")
        font_icon  = font_cache.get(34, "regular")

        cx = CANVAS_W // 2
        mid = top + height // 2

        # ── Titre "ChatGPT" ──────────────────────────────────────────
        tw, th = get_text_dimensions("ChatGPT", font_title, draw)
        ty = mid - th - 4
        draw.text((cx - tw // 2, ty), "ChatGPT", font=font_title, fill=self.TEXT)

        # ── Sous-label "4o  ▾" ────────────────────────────────────────
        model_str = "4o  ▾"
        mw, mh = get_text_dimensions(model_str, font_model, draw)
        draw.text((cx - mw // 2, mid + 4), model_str, font=font_model, fill=self.TEXT_DIM)

        # ── Icône gauche : crayon (nouveau chat) ──────────────────────
        px, py = 55, mid - 18
        # Corps du crayon
        draw.polygon([(px, py + 28), (px + 6, py + 36), (px + 36, py + 6),
                      (px + 30, py - 2)], fill=None, outline=self.TEXT_DIM)
        draw.line([(px, py + 28), (px + 6, py + 36)], fill=self.TEXT_DIM, width=2)
        # Pointe
        draw.polygon([(px, py + 28), (px + 3, py + 35), (px + 8, py + 32)], fill=self.TEXT_DIM)

        # ── Icône droite : sidebar / liste ────────────────────────────
        sx = CANVAS_W - 80
        sy = mid - 14
        for i in range(3):
            y_line = sy + i * 14
            draw.rounded_rectangle([(sx, y_line), (sx + 38, y_line + 4)], radius=2, fill=self.TEXT_DIM)

    def _draw_chat(self, draw: ImageDraw.ImageDraw, img: Image.Image,
                   t: float, chat_top: int, chat_bot: int) -> int:
        """
        Zone de chat principale.
        Retourne la coordonnée Y du bas du dernier élément affiché.
        """
        MARGIN   = 44
        LINE_H   = 48
        font_msg = font_cache.get(36, "regular")

        # ── Calculer les caractères visibles du prompt ─────────────────
        n_chars = self._chars_at(t)
        user_text = self.prompt_text[:n_chars]
        typing_cursor = n_chars < len(self.prompt_text) and int(t * 3) % 2 == 0

        # ── Bulle utilisateur ─────────────────────────────────────────
        user_bottom = chat_top + 60
        if user_text or typing_cursor:
            user_bottom = self._draw_user_bubble(
                draw, img, user_text, typing_cursor,
                chat_top + 60, MARGIN, font_msg, LINE_H
            )

        # ── Trois points de réflexion ─────────────────────────────────
        if self.t_type_end <= t < self.t_think_end:
            think_y = user_bottom + 50
            self._draw_thinking_dots(draw, img, t - self.t_type_end, think_y, MARGIN)

        # ── Réponse streamée ──────────────────────────────────────────
        elif t >= self.t_think_end:
            resp_y = user_bottom + 50
            n_words = self._words_at(t)
            streaming = n_words < len(self.output_words)
            cursor_on = streaming and int(t * 3) % 2 == 0
            visible = self._build_visible_text(n_words)
            self._draw_assistant_message(
                draw, img, visible, cursor_on,
                resp_y, MARGIN, font_msg, LINE_H, chat_bot
            )

        return user_bottom

    def _draw_user_bubble(self, draw, img, text, show_cursor,
                          y, margin, font, line_h) -> int:
        """Bulle de message utilisateur — droite, fond gris arrondi."""
        PAD_X, PAD_Y = 32, 22
        MAX_W = int(CANVAS_W * 0.72)

        display = text + ("|" if show_cursor else "")
        lines = wrap_text(display or " ", font, MAX_W - PAD_X * 2)

        bubble_w = max(
            (get_text_dimensions(l, font, draw)[0] for l in lines),
            default=80
        ) + PAD_X * 2
        bubble_w = min(bubble_w, MAX_W)
        bubble_h = len(lines) * line_h + PAD_Y * 2

        bx = CANVAS_W - margin - bubble_w
        by = y

        draw.rounded_rectangle(
            [bx, by, bx + bubble_w, by + bubble_h],
            radius=22, fill=self.USER_BG,
        )
        for i, line in enumerate(lines):
            draw.text(
                (bx + PAD_X, by + PAD_Y + i * line_h),
                line, font=font, fill=self.TEXT,
            )
        return by + bubble_h

    def _draw_thinking_dots(self, draw, img, elapsed, y, margin):
        """Trois points pulsants — animation de réflexion ChatGPT."""
        icon_size = 46
        self._draw_chatgpt_icon(draw, margin, y, icon_size)

        cx = margin + icon_size + 24
        for i in range(3):
            phase = (elapsed * 2.5 - i * 0.35) % 1.0
            # Amplitude sinusoïdale
            brightness = 0.45 + 0.55 * max(0, math.sin(math.pi * phase))
            r = int(self.TEXT_DIM[0] * brightness)
            g = int(self.TEXT_DIM[1] * brightness)
            b = int(self.TEXT_DIM[2] * brightness)
            dot_y = y + icon_size // 2 - 8
            # Léger rebond vertical
            bounce = int(-6 * max(0, math.sin(math.pi * phase)))
            draw.ellipse(
                [(cx + i * 30 - 9, dot_y + bounce - 9),
                 (cx + i * 30 + 9, dot_y + bounce + 9)],
                fill=(r, g, b),
            )

    def _draw_assistant_message(self, draw, img, text, show_cursor,
                                y, margin, font, line_h, max_y):
        """Message de l'assistant : icône + label + texte streamé avec auto-scroll."""
        icon_size  = 46
        font_label = font_cache.get(30, "bold")
        font_subj  = font_cache.get(36, "bold")   # Subject line en gras
        max_w      = CANVAS_W - margin * 2

        # ── Construire toutes les lignes ──────────────────────────────
        display   = text + ("|" if show_cursor else "")
        raw_lines = display.split("\n")
        all_lines = []   # list of (text, is_bold)
        for raw in raw_lines:
            is_subj = raw.strip().lower().startswith("subject:")
            wrapped = wrap_text(raw or " ", font, max_w)
            for wl in wrapped:
                all_lines.append((wl, is_subj))

        # ── Zone disponible pour le texte ─────────────────────────────
        header_h  = icon_size + 18          # icône + gap
        text_top  = y + header_h            # y absolu du début du texte
        avail_h   = max_y - text_top - 10   # hauteur disponible

        total_text_h = len(all_lines) * line_h
        # Scroll : si le contenu dépasse, décaler vers le haut pour montrer la fin
        scroll_offset = max(0, total_text_h - avail_h)

        # ── Rendu de l'en-tête (icône + label) ───────────────────────
        # Décaler l'en-tête vers le haut avec le scroll (reste ancré)
        header_y = y - min(scroll_offset, header_h - 10)
        self._draw_chatgpt_icon(draw, margin, header_y, icon_size)
        lx = margin + icon_size + 16
        ly = header_y + (icon_size - 30) // 2
        draw.text((lx, ly), "ChatGPT", font=font_label, fill=self.TEXT)

        # ── Rendu des lignes de texte ─────────────────────────────────
        text_y = text_top - scroll_offset
        for (line, is_bold) in all_lines:
            if text_y + line_h < text_top - 2:   # ligne déjà scrollée hors vue
                text_y += line_h
                continue
            if text_y > max_y - 10:              # ligne hors écran (bas)
                break
            f = font_subj if is_bold else font
            color = self.TEXT if not (line.strip() == " " or line.strip() == "") else self.BG
            draw.text((margin, text_y), line, font=f, fill=self.TEXT)
            text_y += line_h

    def _draw_chatgpt_icon(self, draw: ImageDraw.ImageDraw, x: int, y: int, size: int):
        """Icône ChatGPT : cercle sombre + étoile verte OpenAI."""
        # Fond circulaire
        draw.ellipse([(x, y), (x + size, y + size)], fill=(52, 52, 52))

        cx, cy = x + size // 2, y + size // 2
        r_outer = size // 2 - 3
        r_inner = int(r_outer * 0.42)

        # Anneau extérieur
        draw.ellipse(
            [(cx - r_outer, cy - r_outer), (cx + r_outer, cy + r_outer)],
            fill=None, outline=self.TEAL, width=2,
        )

        # Branches de l'étoile (logo OpenAI simplifié — 6 branches)
        branch = int(r_outer * 0.72)
        w_branch = max(2, size // 18)
        for angle_deg in range(0, 360, 60):
            rad = math.radians(angle_deg)
            x1 = int(cx + math.cos(rad) * r_inner)
            y1 = int(cy + math.sin(rad) * r_inner)
            x2 = int(cx + math.cos(rad) * branch)
            y2 = int(cy + math.sin(rad) * branch)
            draw.line([(x1, y1), (x2, y2)], fill=self.TEAL, width=w_branch)

    def _draw_input_area(self, draw: ImageDraw.ImageDraw, top: int, height: int):
        """Barre de saisie en bas — champ arrondi + icônes."""
        draw.line([(0, top), (CANVAS_W, top)], fill=self.BORDER, width=1)
        draw.rectangle([(0, top), (CANVAS_W, top + height)], fill=self.BG)

        margin  = 32
        field_h = 78
        field_y = top + (height - field_h) // 2 - 10

        # ── Champ de saisie ───────────────────────────────────────────
        draw.rounded_rectangle(
            [margin, field_y, CANVAS_W - margin, field_y + field_h],
            radius=39, fill=self.INPUT_BG, outline=self.BORDER, width=1,
        )

        # Icône + (gauche)
        font_icon = font_cache.get(38, "bold")
        draw.text((margin + 22, field_y + (field_h - 38) // 2), "+", font=font_icon, fill=self.TEXT_DIM)

        # Placeholder
        font_ph = font_cache.get(32, "regular")
        ph = "Message ChatGPT"
        _, ph_h = get_text_dimensions(ph, font_ph, draw)
        draw.text(
            (margin + 72, field_y + (field_h - ph_h) // 2),
            ph, font=font_ph, fill=self.TEXT_DIM,
        )

        # Icône micro (droite) — cercle + base
        mic_x = CANVAS_W - margin - 46
        mic_cy = field_y + field_h // 2
        draw.ellipse(
            [(mic_x - 24, mic_cy - 24), (mic_x + 24, mic_cy + 24)],
            fill=(80, 80, 80),
        )
        # Micro stylisé
        draw.rounded_rectangle(
            [(mic_x - 7, mic_cy - 14), (mic_x + 7, mic_cy + 4)],
            radius=6, fill=self.TEXT,
        )
        draw.arc([(mic_x - 13, mic_cy - 6), (mic_x + 13, mic_cy + 16)], 0, 180, fill=self.TEXT, width=2)
        draw.line([(mic_x, mic_cy + 16), (mic_x, mic_cy + 22)], fill=self.TEXT, width=2)

        # Disclaimer
        font_disc = font_cache.get(22, "regular")
        disc = "ChatGPT can make mistakes. Check important info."
        dw, dh = get_text_dimensions(disc, font_disc, draw)
        draw.text(
            ((CANVAS_W - dw) // 2, top + height - dh - 10),
            disc, font=font_disc, fill=(75, 75, 85),
        )

    def _draw_saves_badge(self, draw: ImageDraw.ImageDraw, progress: float):
        """Badge doré '@ownyourtime.ai saves X min/day' centré en bas."""
        font_badge = font_cache.get(28, "bold")
        badge_text = f"saves {self.saves} with ChatGPT"
        bw, bh = get_text_dimensions(badge_text, font_badge, draw)

        alpha = int(ease_out(progress) * 255)
        slide = int((1 - ease_out(progress)) * 40)
        bx = (CANVAS_W - bw) // 2
        by = CANVAS_H - 230 + slide

        draw_rounded_rect(
            draw,
            (bx - 24, by - 12, bx + bw + 24, by + bh + 12),
            radius=30, fill=COLORS["gold"],
        )
        draw.text((bx, by), badge_text, font=font_badge, fill=COLORS["dark_text"])

    @staticmethod
    def _tokenize_output(text: str) -> list:
        """
        Tokenise le texte de sortie en mots + marqueurs de saut de ligne.
        Chaque token est soit un mot (str) soit None (saut de ligne).
        """
        tokens = []
        for line in text.split("\n"):
            if tokens:                # séparateur de ligne
                tokens.append(None)
            for word in line.split():
                tokens.append(word)
        return tokens

    def _build_visible_text(self, n_words: int) -> str:
        """Reconstruit le texte visible à partir des tokens, en préservant les \\n."""
        count = 0
        result = []
        current_line = []
        for tok in self.output_tokens:
            if tok is None:            # saut de ligne
                result.append(" ".join(current_line))
                current_line = []
            else:
                current_line.append(tok)
                count += 1
                if count >= n_words:
                    break
        result.append(" ".join(current_line))
        return "\n".join(result)

    # ── Helpers de timing ─────────────────────────────────────────────

    def _chars_at(self, t: float) -> int:
        """Nombre de caractères du prompt visibles à l'instant t."""
        if t < self.t_type_start:
            return 0
        if t >= self.t_type_end:
            return len(self.prompt_text)
        prog = ease_in_out((t - self.t_type_start) / (self.t_type_end - self.t_type_start))
        return int(prog * len(self.prompt_text))

    def _words_at(self, t: float) -> int:
        """Nombre de mots de la réponse visibles à l'instant t (streaming)."""
        if t < self.t_think_end:
            return 0
        if t >= self.t_stream_end:
            return len(self.output_words)
        prog = ease_out((t - self.t_think_end) / (self.t_stream_end - self.t_think_end))
        return int(prog * len(self.output_words))


# ─────────────────────────────────────────────────────────────────────────────
# SEGMENT 3 — CTA
# ─────────────────────────────────────────────────────────────────────────────

class CTARenderer:
    """Génère les frames du segment CTA (Call to Action)."""

    def __init__(self, cta_config: dict):
        self.headline = cta_config.get("headline", "Save THIS.")
        self.subtext = cta_config.get("subtext", "")
        self.handle = cta_config.get("handle", "@ownyourtime.ai")
        self.duration = float(cta_config.get("duration", 3))

    def make_frame(self, t: float) -> np.ndarray:
        """Génère un frame à l'instant t."""
        img = Image.new("RGB", (CANVAS_W, CANVAS_H), COLORS["gold"])
        draw = ImageDraw.Draw(img)

        # ── Dégradé or chaud ──────────────────────────────────────────────
        gold_top = (240, 200, 90)
        gold_bottom = (210, 165, 55)
        draw_gradient_background(img, gold_top, gold_bottom)
        draw = ImageDraw.Draw(img)

        # ── Polices ────────────────────────────────────────────────────────
        font_headline = font_cache.get(110, "bold")
        font_subtext = font_cache.get(44, "bold")
        font_handle = font_cache.get(32, "mono")

        # ── Animation d'entrée (0–0.5s) ───────────────────────────────────
        enter_progress = min(1.0, t / 0.5)
        slide_offset = int((1 - ease_out(enter_progress)) * 120)

        # ── Effet de tremblement initial (0–0.6s) ─────────────────────────
        sx, sy = shake_offset(t, duration=0.6, intensity=10)

        # ── Effet de pulsation continu ────────────────────────────────────
        scale = pulse(t, frequency=1.8, amplitude=0.04)

        # ── Headline "Save THIS." ──────────────────────────────────────────
        headline_lines = self.headline.split("\n")
        line_h = 120
        total_h = len(headline_lines) * line_h
        center_y = CANVAS_H // 2 - 80

        for i, line in enumerate(headline_lines):
            # Créer une image temporaire pour le scaling
            temp_img = Image.new("RGBA", (CANVAS_W, 140), (0, 0, 0, 0))
            temp_draw = ImageDraw.Draw(temp_img)

            tw, th = get_text_dimensions(line, font_headline, draw)
            tx = (CANVAS_W - tw) // 2
            draw_text_with_shadow(
                temp_draw, (tx, 10), line, font_headline,
                fill=COLORS["dark_text"], shadow_offset=4, shadow_color=(0, 0, 0, 40)
            )

            # Appliquer le scale et le décalage
            new_w = int(CANVAS_W * scale)
            new_h = int(140 * scale)
            temp_img = temp_img.resize((new_w, new_h), Image.LANCZOS)

            paste_x = (CANVAS_W - new_w) // 2 + sx
            paste_y = center_y + i * line_h - slide_offset + sy + (140 - new_h) // 2
            img.paste(temp_img, (paste_x, paste_y), temp_img)

        draw = ImageDraw.Draw(img)

        # ── Texte secondaire ───────────────────────────────────────────────
        subtext_progress = min(1.0, max(0.0, (t - 0.3) / 0.4))
        if subtext_progress > 0:
            subtext_y = center_y + len(headline_lines) * line_h + 20 - slide_offset + sy
            sw, sh = get_text_dimensions(self.subtext, font_subtext, draw)
            draw.text(
                ((CANVAS_W - sw) // 2, subtext_y),
                self.subtext,
                font=font_subtext,
                fill=(*COLORS["dark_text"], int(subtext_progress * 220))
            )

        # ── Handle @ownyourtime.ai en bas ────────────────────────────────
        handle_progress = min(1.0, max(0.0, (t - 0.6) / 0.5))
        if handle_progress > 0:
            hw, hh = get_text_dimensions(self.handle, font_handle, draw)
            draw.text(
                ((CANVAS_W - hw) // 2, CANVAS_H - 130),
                self.handle,
                font=font_handle,
                fill=(*COLORS["dark_text"], int(handle_progress * 180))
            )

        return np.array(img)


# ─────────────────────────────────────────────────────────────────────────────
# TEMPLATE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

class PromptRevealTemplate:
    """
    Template principal "Prompt Reveal".
    Orchestre les 4 segments et produit la vidéo finale.

    Ordre: Intro vidéo → Hook → Prompt Reveal → CTA
    """

    def __init__(self, config: dict):
        self.config = config
        self.reel_cfg = config.get("reel", {})
        self.fps = int(self.reel_cfg.get("fps", 30))

        # Segment d'intro vidéo (optionnel)
        from utils.video_intro import IntroVideoRenderer
        intro_cfg = config.get("intro", {})
        self.intro = IntroVideoRenderer(intro_cfg) if intro_cfg else None

        # Segments animés
        self.hook   = HookRenderer(config.get("hook", {}))
        self.prompt = PromptRevealRenderer(config.get("prompt", {}))
        self.cta    = CTARenderer(config.get("cta", {}))

        # Durée totale (avec ou sans intro)
        self.intro_duration = self.intro.duration if self.intro else 0.0
        self.total_duration = (
            self.intro_duration
            + self.hook.duration
            + self.prompt.duration
            + self.cta.duration
        )

    def _make_animated_frame(self, t: float) -> np.ndarray:
        """
        Génère le frame animé (segments Hook/Prompt/CTA) à l'instant t
        relatif au début des segments animés (après l'intro).
        """
        hook_end   = self.hook.duration
        prompt_end = hook_end + self.prompt.duration

        if t < hook_end:
            return self.hook.make_frame(t)
        elif t < prompt_end:
            return self.prompt.make_frame(t - hook_end)
        else:
            return self.cta.make_frame(t - prompt_end)

    def generate(self, output_path: str, use_remotion: bool = False) -> str:
        """
        Génère la vidéo complète et l'enregistre dans output_path.

        Args:
            output_path: Chemin de sortie du fichier MP4
            use_remotion: Si True, tente d'utiliser Remotion pour les animations

        Returns:
            Chemin vers le fichier vidéo généré
        """
        intro_label = f"Intro: {self.intro_duration}s | " if self.intro_duration else ""
        logger.info(f"Génération du reel ({self.total_duration}s @ {self.fps}fps)...")
        logger.info(
            f"  {intro_label}Hook: {self.hook.duration}s | "
            f"Prompt: {self.prompt.duration}s | CTA: {self.cta.duration}s"
        )

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        if use_remotion and self._check_remotion_available():
            return self._generate_with_remotion(output_path)
        else:
            return self._generate_with_moviepy(output_path)

    def _generate_with_moviepy(self, output_path: str) -> str:
        """Génère la vidéo avec MoviePy — concatène intro + segments animés."""
        try:
            from moviepy.editor import VideoClip, concatenate_videoclips
        except ImportError:
            from moviepy import VideoClip, concatenate_videoclips

        from utils.audio import get_audio_clip

        logger.info("Rendu avec MoviePy + Pillow...")

        # ── Durée des segments animés (sans intro) ─────────────────────
        animated_duration = self.hook.duration + self.prompt.duration + self.cta.duration

        # Clip des segments animés (rendu Pillow frame par frame)
        animated_clip = VideoClip(
            make_frame=self._make_animated_frame,
            duration=animated_duration,
        )

        # ── Clip d'intro ───────────────────────────────────────────────
        clips_to_concat = []
        if self.intro:
            intro_clip = self.intro.get_clip()
            if intro_clip is not None:
                # S'assurer que l'intro est au bon FPS
                intro_clip = intro_clip.set_fps(self.fps)
                clips_to_concat.append(intro_clip)
                logger.info(
                    f"Intro: {'vidéo stock' if self.intro.is_available() else 'animation de remplacement'} "
                    f"({self.intro.duration}s)"
                )

        clips_to_concat.append(animated_clip)

        # Concaténer intro + segments animés
        if len(clips_to_concat) > 1:
            video_clip = concatenate_videoclips(clips_to_concat, method="compose")
        else:
            video_clip = clips_to_concat[0]

        # ── Audio ──────────────────────────────────────────────────────
        audio_config = self.config.get("audio", {})
        audio_clip = get_audio_clip(audio_config, self.total_duration)

        if audio_clip is not None:
            video_clip = video_clip.set_audio(audio_clip)

        # Exporter en MP4 H.264
        logger.info(f"Export vers {output_path}...")
        write_kwargs = dict(
            fps=self.fps,
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            ffmpeg_params=["-crf", "23", "-pix_fmt", "yuv420p"],
            logger="bar",
        )

        try:
            video_clip.write_videofile(output_path, **write_kwargs)
        except TypeError:
            # Ancienne API MoviePy
            write_kwargs.pop("logger", None)
            write_kwargs["verbose"] = False
            video_clip.write_videofile(output_path, **write_kwargs)

        logger.info(f"Vidéo générée : {output_path}")
        return output_path

    def _check_remotion_available(self) -> bool:
        """Vérifie si Remotion et Node.js sont disponibles."""
        try:
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                return False
            remotion_dir = Path(__file__).parent.parent / "remotion_comp"
            node_modules = remotion_dir / "node_modules" / "remotion"
            return node_modules.exists()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _generate_with_remotion(self, output_path: str) -> str:
        """
        Génère la vidéo en utilisant Remotion pour les animations avancées,
        puis MoviePy pour la composition finale avec audio.
        """
        logger.info("Rendu avec Remotion...")

        remotion_dir = Path(__file__).parent.parent / "remotion_comp"
        remotion_output = Path(output_path).with_suffix("") / "_remotion_raw.mp4"
        remotion_output.parent.mkdir(parents=True, exist_ok=True)

        # Préparer les props pour Remotion
        props = {
            "hookText": self.hook.text,
            "hookHighlight": self.hook.highlight,
            "hookDuration": self.hook.duration,
            "promptTitle": self.prompt.title,
            "promptText": self.prompt.prompt_text,
            "outputText": self.prompt.output_text,
            "promptDuration": self.prompt.duration,
            "ctaHeadline": self.cta.headline,
            "ctaSubtext": self.cta.subtext,
            "ctaHandle": self.cta.handle,
            "ctaDuration": self.cta.duration,
        }

        # Appel Remotion via subprocess
        cmd = [
            "npx", "remotion", "render",
            str(remotion_dir / "src" / "index.tsx"),
            "PromptReveal",
            str(remotion_output),
            "--props", json.dumps(props),
            "--codec", "h264",
            "--fps", str(self.fps),
        ]

        logger.info(f"Commande Remotion: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=str(remotion_dir), capture_output=True, text=True)

        if result.returncode != 0:
            logger.warning(f"Remotion a échoué: {result.stderr}")
            logger.info("Repli sur MoviePy...")
            return self._generate_with_moviepy(output_path)

        # Ajouter l'audio avec FFmpeg
        audio_config = self.config.get("audio", {})
        bg_music = audio_config.get("background_music", "")
        if bg_music and os.path.exists(bg_music):
            volume = audio_config.get("volume", 0.3)
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-i", str(remotion_output),
                "-i", bg_music,
                "-filter_complex", f"[1:a]volume={volume}[bg];[0:a][bg]amix=inputs=2:duration=first",
                "-c:v", "copy",
                "-c:a", "aac",
                output_path
            ]
            subprocess.run(ffmpeg_cmd, check=True)
        else:
            import shutil
            shutil.copy(str(remotion_output), output_path)

        logger.info(f"Vidéo Remotion générée : {output_path}")
        return output_path

    def generate_preview_frame(self, output_path: str, segment: str = "hook", t: float = 1.5):
        """
        Génère une image PNG de prévisualisation d'un frame du reel.

        Args:
            output_path: Chemin de sortie PNG
            segment: 'intro', 'hook', 'prompt' ou 'cta'
            t: Temps relatif dans le segment (en secondes)
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        if segment == "intro" and self.intro:
            # Générer un frame de l'intro (via le clip MoviePy ou le fallback)
            intro_clip = self.intro.get_clip()
            if intro_clip is not None:
                t_clamped = min(t, intro_clip.duration - 0.01)
                frame = intro_clip.get_frame(t_clamped)
            else:
                frame = self.hook.make_frame(0)
        elif segment == "hook":
            frame = self.hook.make_frame(t)
        elif segment == "prompt":
            frame = self.prompt.make_frame(t)
        elif segment == "cta":
            frame = self.cta.make_frame(t)
        else:
            frame = self._make_animated_frame(t)

        img = Image.fromarray(frame.astype(np.uint8))
        img.save(output_path, "PNG", optimize=True)
        logger.info(f"Frame de prévisualisation sauvegardé : {output_path}")
        return output_path
