"""
Gestion des polices de caractères pour le générateur de reels.
Télécharge et met en cache les polices Google Fonts nécessaires.
"""

import os
import logging
import urllib.request
import zipfile
import io
from pathlib import Path
from PIL import ImageFont

logger = logging.getLogger(__name__)

# Répertoire des polices
FONTS_DIR = Path(__file__).parent.parent / "assets" / "fonts"

# URLs de téléchargement des polices depuis GitHub (releases officielles)
FONT_URLS = {
    "PlusJakartaSans-Bold": (
        "https://github.com/tokotype/PlusJakartaSans/releases/download/2.7.1/"
        "PlusJakartaSans-2.7.1.zip"
    ),
    "JetBrainsMono-Regular": (
        "https://github.com/JetBrains/JetBrainsMono/releases/download/v2.304/"
        "JetBrainsMono-2.304.zip"
    ),
}

# Polices alternatives pour les systèmes Mac et Windows
SYSTEM_FONT_FALLBACKS = {
    "bold": [
        "/System/Library/Fonts/Helvetica.ttc",           # macOS
        "/System/Library/Fonts/SFProDisplay-Bold.otf",   # macOS M1/M2
        "C:/Windows/Fonts/arialbd.ttf",                  # Windows
        "C:/Windows/Fonts/calibrib.ttf",                 # Windows
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux
    ],
    "mono": [
        "/System/Library/Fonts/Menlo.ttc",               # macOS
        "C:/Windows/Fonts/consola.ttf",                  # Windows (Consolas)
        "C:/Windows/Fonts/cour.ttf",                     # Windows (Courier)
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",   # Linux
    ],
    "regular": [
        "/System/Library/Fonts/Helvetica.ttc",           # macOS
        "C:/Windows/Fonts/arial.ttf",                    # Windows
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",       # Linux
    ],
}


def ensure_fonts_dir():
    """Crée le répertoire des polices s'il n'existe pas."""
    FONTS_DIR.mkdir(parents=True, exist_ok=True)


def download_plus_jakarta_sans():
    """Télécharge la police Plus Jakarta Sans Bold depuis le ZIP GitHub."""
    dest_path = FONTS_DIR / "PlusJakartaSans-Bold.ttf"
    if dest_path.exists():
        return dest_path

    url = FONT_URLS["PlusJakartaSans-Bold"]
    logger.info(f"Téléchargement de Plus Jakarta Sans depuis GitHub...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        response = urllib.request.urlopen(req, timeout=30)
        zip_data = response.read()
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            # Chercher le fichier Bold (variable ou static) dans l'archive
            candidates = [
                n for n in zf.namelist()
                if n.endswith(".ttf") and ("Bold" in n or "Variable" in n or "bold" in n)
            ]
            if not candidates:
                # Prendre n'importe quel TTF disponible
                candidates = [n for n in zf.namelist() if n.endswith(".ttf")]
            if candidates:
                # Préférer le fichier Bold statique
                chosen = next(
                    (c for c in candidates if "Bold" in c and "static" in c.lower()),
                    candidates[0]
                )
                with zf.open(chosen) as f:
                    dest_path.write_bytes(f.read())
                logger.info(f"Plus Jakarta Sans téléchargée avec succès ({chosen})")
                return dest_path
    except Exception as e:
        logger.warning(f"Impossible de télécharger Plus Jakarta Sans: {e}")
    return None


def download_jetbrains_mono():
    """Télécharge la police JetBrains Mono depuis l'archive ZIP."""
    dest_path = FONTS_DIR / "JetBrainsMono-Regular.ttf"
    if dest_path.exists():
        return dest_path

    url = FONT_URLS["JetBrainsMono-Regular"]
    logger.info(f"Téléchargement de JetBrains Mono depuis {url}")
    try:
        response = urllib.request.urlopen(url, timeout=30)
        zip_data = response.read()
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            # Chercher le fichier Regular dans l'archive
            for name in zf.namelist():
                if "JetBrainsMono-Regular.ttf" in name and "fonts/ttf" in name:
                    with zf.open(name) as f:
                        dest_path.write_bytes(f.read())
                    logger.info("JetBrains Mono téléchargée avec succès")
                    return dest_path
    except Exception as e:
        logger.warning(f"Impossible de télécharger JetBrains Mono: {e}")
    return None


def find_system_font(font_type: str) -> str | None:
    """Cherche une police système disponible pour le type donné."""
    for path in SYSTEM_FONT_FALLBACKS.get(font_type, []):
        if os.path.exists(path):
            return path
    return None


def load_font(size: int, style: str = "regular") -> ImageFont.FreeTypeFont:
    """
    Charge une police de caractères PIL avec repli sur polices système.

    Args:
        size: Taille de la police en pixels
        style: 'bold', 'mono', ou 'regular'

    Returns:
        ImageFont.FreeTypeFont ou ImageFont.load_default()
    """
    ensure_fonts_dir()

    # Essayer d'abord les polices personnalisées téléchargées
    custom_font_paths = {
        "bold": FONTS_DIR / "PlusJakartaSans-Bold.ttf",
        "mono": FONTS_DIR / "JetBrainsMono-Regular.ttf",
        "regular": FONTS_DIR / "PlusJakartaSans-Bold.ttf",
    }

    font_path = custom_font_paths.get(style)
    if font_path and font_path.exists():
        try:
            return ImageFont.truetype(str(font_path), size)
        except Exception as e:
            logger.warning(f"Erreur chargement police personnalisée: {e}")

    # Repli sur les polices système
    system_path = find_system_font(style)
    if system_path:
        try:
            return ImageFont.truetype(system_path, size)
        except Exception as e:
            logger.warning(f"Erreur chargement police système {system_path}: {e}")

    # Dernier recours: police PIL par défaut (très basique)
    logger.warning(f"Utilisation de la police par défaut PIL (taille {size})")
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def setup_fonts():
    """
    Tente de télécharger toutes les polices nécessaires.
    Ne plante pas si le téléchargement échoue.
    """
    ensure_fonts_dir()
    logger.info("Vérification des polices...")

    bold_path = FONTS_DIR / "PlusJakartaSans-Bold.ttf"
    if not bold_path.exists():
        download_plus_jakarta_sans()

    mono_path = FONTS_DIR / "JetBrainsMono-Regular.ttf"
    if not mono_path.exists():
        download_jetbrains_mono()

    # Vérifier l'état final
    available = []
    if bold_path.exists():
        available.append("PlusJakartaSans-Bold")
    if mono_path.exists():
        available.append("JetBrainsMono-Regular")

    if available:
        logger.info(f"Polices disponibles: {', '.join(available)}")
    else:
        logger.warning("Aucune police personnalisée disponible - utilisation des polices système")


class FontCache:
    """Cache des polices pour éviter les rechargements répétés."""

    def __init__(self):
        self._cache: dict[tuple, ImageFont.FreeTypeFont] = {}

    def get(self, size: int, style: str = "regular") -> ImageFont.FreeTypeFont:
        """Retourne la police depuis le cache ou la charge."""
        key = (size, style)
        if key not in self._cache:
            self._cache[key] = load_font(size, style)
        return self._cache[key]


# Instance globale du cache de polices
font_cache = FontCache()
