"""
Utilitaires de rendu partagés pour les templates de reels.
Fonctions helper pour le dessin avec Pillow.
"""

import math
import logging
from typing import Optional
from PIL import Image, ImageDraw, ImageFilter

logger = logging.getLogger(__name__)

# ── Palette de couleurs de la marque ──────────────────────────────────────────
COLORS = {
    "midnight": (9, 9, 26),          # #09091A — fond principal
    "deep_ink": (30, 30, 50),         # #1E1E32 — fond secondaire
    "gold": (232, 184, 75),           # #E8B84B — accent
    "ivory": (242, 240, 234),         # #F2F0EA — texte principal
    "muted": (82, 82, 122),           # #52527A — texte secondaire
    "green": (80, 250, 123),          # #50FA7B — texte terminal/output
    "dark_text": (15, 15, 30),        # Texte sombre sur fond or
    "card_bg": (20, 20, 38),          # Fond des cartes
    "card_border": (45, 45, 75),      # Bordure des cartes
}

# Dimensions du canvas vertical Instagram Reels
CANVAS_W = 1080
CANVAS_H = 1920


def ease_in_out(t: float, start: float = 0.0, end: float = 1.0) -> float:
    """
    Fonction d'interpolation ease-in-out.

    Args:
        t: Progression normalisée [0, 1]
        start: Valeur de départ
        end: Valeur de fin

    Returns:
        Valeur interpolée avec accélération douce
    """
    t = max(0.0, min(1.0, t))
    # Formule cubic ease-in-out
    t_smooth = t * t * (3 - 2 * t)
    return start + (end - start) * t_smooth


def ease_out(t: float) -> float:
    """Interpolation ease-out (décélération)."""
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 2


def pulse(t: float, frequency: float = 2.0, amplitude: float = 0.05) -> float:
    """
    Génère un effet de pulsation sinusoïdale.

    Args:
        t: Temps en secondes
        frequency: Fréquence en Hz
        amplitude: Amplitude de la pulsation

    Returns:
        Facteur d'échelle [1-amplitude, 1+amplitude]
    """
    return 1.0 + amplitude * math.sin(2 * math.pi * frequency * t)


def shake_offset(t: float, duration: float = 0.4, intensity: int = 8) -> tuple[int, int]:
    """
    Calcule le décalage de tremblement pour l'animation shake.

    Args:
        t: Temps en secondes depuis le début
        duration: Durée de l'animation de tremblement
        intensity: Intensité maximale du tremblement en pixels

    Returns:
        Tuple (offset_x, offset_y) en pixels
    """
    if t > duration:
        return (0, 0)
    # Tremblement avec atténuation progressive
    decay = 1.0 - (t / duration)
    freq = 25  # Hz
    ox = int(intensity * decay * math.sin(2 * math.pi * freq * t))
    oy = int(intensity * decay * math.cos(2 * math.pi * freq * t * 0.7))
    return (ox, oy)


def draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    bbox: tuple[int, int, int, int],
    radius: int = 20,
    fill: Optional[tuple] = None,
    outline: Optional[tuple] = None,
    outline_width: int = 2,
):
    """
    Dessine un rectangle aux coins arrondis.

    Args:
        draw: Objet ImageDraw PIL
        bbox: (x1, y1, x2, y2) — coordonnées du rectangle
        radius: Rayon des coins arrondis
        fill: Couleur de remplissage (R, G, B)
        outline: Couleur du contour (R, G, B) ou None
        outline_width: Épaisseur du contour en pixels
    """
    x1, y1, x2, y2 = bbox
    draw.rounded_rectangle(bbox, radius=radius, fill=fill, outline=outline, width=outline_width)


def draw_text_with_shadow(
    draw: ImageDraw.ImageDraw,
    pos: tuple[int, int],
    text: str,
    font,
    fill: tuple,
    shadow_offset: int = 3,
    shadow_color: tuple = (0, 0, 0, 80),
):
    """
    Dessine du texte avec une ombre portée subtile.

    Args:
        draw: Objet ImageDraw PIL
        pos: Position (x, y) du texte
        text: Texte à afficher
        font: Police PIL
        fill: Couleur principale du texte
        shadow_offset: Décalage de l'ombre en pixels
        shadow_color: Couleur de l'ombre
    """
    sx, sy = pos[0] + shadow_offset, pos[1] + shadow_offset
    draw.text((sx, sy), text, font=font, fill=(0, 0, 0, 60))
    draw.text(pos, text, font=font, fill=fill)


def draw_gradient_background(img: Image.Image, color_top: tuple, color_bottom: tuple) -> Image.Image:
    """
    Dessine un fond avec dégradé vertical.

    Args:
        img: Image PIL à modifier
        color_top: Couleur en haut (R, G, B)
        color_bottom: Couleur en bas (R, G, B)

    Returns:
        Image avec dégradé appliqué
    """
    width, height = img.size
    draw = ImageDraw.Draw(img)

    for y in range(height):
        # Interpolation linéaire entre les deux couleurs
        ratio = y / height
        r = int(color_top[0] + (color_bottom[0] - color_top[0]) * ratio)
        g = int(color_top[1] + (color_bottom[1] - color_top[1]) * ratio)
        b = int(color_top[2] + (color_bottom[2] - color_top[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    return img


def wrap_text(text: str, font, max_width: int) -> list[str]:
    """
    Coupe le texte en lignes pour qu'il rentre dans max_width.

    Args:
        text: Texte à envelopper
        font: Police PIL pour mesurer les dimensions
        max_width: Largeur maximale en pixels

    Returns:
        Liste de lignes de texte
    """
    words = text.split()
    lines = []
    current_line = []

    # Créer un objet draw temporaire pour mesurer
    temp_img = Image.new('RGB', (1, 1))
    temp_draw = ImageDraw.Draw(temp_img)

    for word in words:
        test_line = ' '.join(current_line + [word])
        try:
            bbox = temp_draw.textbbox((0, 0), test_line, font=font)
            line_width = bbox[2] - bbox[0]
        except AttributeError:
            line_width = temp_draw.textlength(test_line, font=font)

        if line_width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]

    if current_line:
        lines.append(' '.join(current_line))

    return lines if lines else [text]


def get_text_dimensions(text: str, font, draw: ImageDraw.ImageDraw) -> tuple[int, int]:
    """
    Retourne les dimensions (largeur, hauteur) d'un texte avec la police donnée.
    """
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]
    except AttributeError:
        w = draw.textlength(text, font=font)
        return int(w), font.size


def draw_noise_overlay(img: Image.Image, intensity: float = 0.02) -> Image.Image:
    """
    Ajoute un léger grain de film pour un effet cinématique.

    Args:
        img: Image PIL source
        intensity: Intensité du grain [0, 1]

    Returns:
        Image avec grain ajouté
    """
    import random
    draw = ImageDraw.Draw(img)
    width, height = img.size
    n_pixels = int(width * height * intensity)

    for _ in range(n_pixels):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        brightness = random.randint(200, 255)
        alpha = random.randint(10, 40)
        draw.point((x, y), fill=(brightness, brightness, brightness))

    return img
