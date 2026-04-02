#!/usr/bin/env python3
"""
Point d'entrée principal du générateur de reels Instagram.
Usage:
    python main.py --config config/reel_config.yaml --output output/reel_001.mp4
    python main.py --batch config/batch/ --output output/
    python main.py --preview --config config/reel_config.yaml
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

import yaml

# Forcer UTF-8 sur Windows pour les caractères spéciaux dans les logs
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Configuration du logging ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("reels_generator")


def load_config(config_path: str) -> dict:
    """
    Charge et valide le fichier de configuration YAML.

    Args:
        config_path: Chemin vers le fichier YAML

    Returns:
        Dictionnaire de configuration

    Raises:
        FileNotFoundError: Si le fichier n'existe pas
        ValueError: Si la configuration est invalide
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Fichier de configuration introuvable: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if config is None:
        raise ValueError("Le fichier de configuration est vide")

    # Validation des sections requises selon le template
    template_name = config.get("reel", {}).get("template", "prompt_reveal")
    if template_name in ("multi_scene", "viral_text_centric_v1"):
        required_sections = ["reel", "scenes"]
    else:
        required_sections = ["reel", "hook", "prompt", "cta"]
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Section manquante dans la config: '{section}'")

    return config


def get_template(config: dict):
    """Instancie le template correspondant à la configuration."""
    template_name = config.get("reel", {}).get("template", "prompt_reveal")

    try:
        from templates import get_template as _get_template
        template_class = _get_template(template_name)
        return template_class(config)
    except ImportError as e:
        logger.error(f"Erreur d'import du template '{template_name}': {e}")
        sys.exit(1)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)


def generate_single(config_path: str, output_path: str, use_remotion: bool = False,
                    preview_only: bool = False) -> str:
    """
    Génère un seul reel à partir d'un fichier de configuration.

    Args:
        config_path: Chemin vers la config YAML
        output_path: Chemin de sortie MP4 (ou dossier)
        use_remotion: Utiliser Remotion pour le rendu
        preview_only: Générer uniquement des frames PNG de prévisualisation

    Returns:
        Chemin vers le fichier généré
    """
    logger.info(f"Chargement de la configuration: {config_path}")
    config = load_config(config_path)

    template = get_template(config)

    if preview_only:
        # Générer des frames de prévisualisation pour chaque segment
        output_dir = Path(output_path).parent if output_path.endswith(".mp4") else Path(output_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        preview_paths = []
        template_name = config.get("reel", {}).get("template", "prompt_reveal")
        if template_name == "multi_scene":
            scenes = config.get("scenes", [])
            segments = [(s.get("type", f"scene{i}"), 0.5) for i, s in enumerate(scenes[:4])]
        else:
            segments = [("intro", 1.5), ("hook", 1.5), ("prompt", 6.0), ("cta", 1.0)]
        for segment, t in segments:
            preview_file = str(output_dir / f"preview_{segment}.png")
            template.generate_preview_frame(preview_file, segment=segment, t=t)
            preview_paths.append(preview_file)
            logger.info(f"Aperçu {segment}: {preview_file}")

        return str(output_dir)

    # Construire le chemin de sortie
    if os.path.isdir(output_path):
        config_name = Path(config_path).stem
        output_path = os.path.join(output_path, f"{config_name}.mp4")

    start_time = time.time()
    result = template.generate(output_path, use_remotion=use_remotion)
    elapsed = time.time() - start_time

    logger.info(f"✓ Reel généré en {elapsed:.1f}s → {result}")
    return result


def generate_batch(batch_dir: str, output_dir: str, use_remotion: bool = False) -> list[str]:
    """
    Génère des reels en batch depuis un dossier de fichiers de configuration.

    Args:
        batch_dir: Dossier contenant les fichiers YAML
        output_dir: Dossier de sortie pour les vidéos
        use_remotion: Utiliser Remotion pour le rendu

    Returns:
        Liste des chemins vers les fichiers générés
    """
    batch_dir = Path(batch_dir)
    yaml_files = sorted(batch_dir.glob("*.yaml")) + sorted(batch_dir.glob("*.yml"))

    if not yaml_files:
        logger.error(f"Aucun fichier YAML trouvé dans: {batch_dir}")
        return []

    logger.info(f"Mode batch: {len(yaml_files)} fichiers trouvés dans {batch_dir}")
    os.makedirs(output_dir, exist_ok=True)

    results = []
    for i, config_file in enumerate(yaml_files, 1):
        logger.info(f"[{i}/{len(yaml_files)}] Traitement de: {config_file.name}")
        try:
            output_path = os.path.join(output_dir, f"{config_file.stem}.mp4")
            result = generate_single(str(config_file), output_path, use_remotion)
            results.append(result)
        except Exception as e:
            logger.error(f"Erreur lors du traitement de {config_file.name}: {e}")
            continue

    logger.info(f"Batch terminé: {len(results)}/{len(yaml_files)} reels générés")
    return results


def setup_environment():
    """
    Vérifie et prépare l'environnement:
    - Télécharge les polices si nécessaire
    - Vérifie FFmpeg
    - Vérifie MoviePy
    """
    logger.info("Vérification de l'environnement...")

    # Vérifier FFmpeg
    import subprocess
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version_line = result.stdout.split("\n")[0]
            logger.info(f"FFmpeg trouvé: {version_line}")
        else:
            logger.warning("FFmpeg n'est pas disponible. Certaines fonctionnalités seront limitées.")
    except FileNotFoundError:
        logger.warning("FFmpeg introuvable. Installez-le depuis https://ffmpeg.org/")

    # Vérifier MoviePy
    try:
        import moviepy
        logger.info(f"MoviePy version: {moviepy.__version__}")
    except ImportError:
        logger.error("MoviePy n'est pas installé. Lancez: pip install moviepy")
        sys.exit(1)

    # Télécharger les polices
    try:
        from utils.fonts import setup_fonts
        setup_fonts()
    except Exception as e:
        logger.warning(f"Impossible de configurer les polices: {e}")


def print_banner():
    """Affiche la bannière de démarrage."""
    banner = (
        "\n"
        "=======================================================\n"
        "      REELS GENERATOR -- @ownyourtime.ai               \n"
        "   Generateur automatique de Reels Instagram           \n"
        "=======================================================\n"
    )
    # Essayer d'afficher avec les caractères spéciaux, repli sur ASCII
    try:
        fancy = (
            "\n"
            "\u2554" + "\u2550" * 55 + "\u2557\n"
            "\u2551   REELS GENERATOR \u2014 @ownyourtime.ai          \u2551\n"
            "\u2551   Generateur automatique de Reels Instagram  \u2551\n"
            "\u255a" + "\u2550" * 55 + "\u255d\n"
        )
        sys.stdout.buffer.write(fancy.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
        sys.stdout.flush()
    except (AttributeError, UnicodeEncodeError):
        print(banner)


def main():
    """Point d'entrée principal."""
    print_banner()

    parser = argparse.ArgumentParser(
        description="Générateur automatique de Reels Instagram pour @ownyourtime.ai",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  # Générer un reel unique
  python main.py --config config/reel_config.yaml --output output/reel_001.mp4

  # Générer des aperçus PNG sans vidéo
  python main.py --config config/reel_config.yaml --output output/ --preview

  # Génération batch depuis un dossier
  python main.py --batch config/batch/ --output output/

  # Utiliser Remotion pour les animations (requiert Node.js)
  python main.py --config config/reel_config.yaml --output output/reel.mp4 --remotion
        """
    )

    # Arguments mutuellement exclusifs: --config ou --batch
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--config", "-c",
        type=str,
        help="Chemin vers le fichier de configuration YAML"
    )
    mode_group.add_argument(
        "--batch", "-b",
        type=str,
        help="Dossier contenant plusieurs fichiers de configuration YAML"
    )

    parser.add_argument(
        "--output", "-o",
        type=str,
        required=True,
        help="Chemin de sortie (fichier MP4 ou dossier)"
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Générer uniquement des frames PNG de prévisualisation (rapide)"
    )
    parser.add_argument(
        "--remotion",
        action="store_true",
        help="Utiliser Remotion pour le rendu (requiert Node.js configuré)"
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Vérifier et préparer l'environnement uniquement"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Affichage détaillé des logs"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Vérifier l'environnement
    setup_environment()

    if args.setup:
        logger.info("Configuration de l'environnement terminée.")
        sys.exit(0)

    # Mode batch
    if args.batch:
        results = generate_batch(args.batch, args.output, use_remotion=args.remotion)
        if results:
            logger.info(f"\n✓ {len(results)} reel(s) générés dans: {args.output}")
        else:
            logger.error("Aucun reel généré.")
            sys.exit(1)

    # Mode fichier unique
    else:
        try:
            result = generate_single(
                args.config,
                args.output,
                use_remotion=args.remotion,
                preview_only=args.preview,
            )
            if args.preview:
                logger.info(f"\n✓ Aperçus générés dans: {result}")
            else:
                logger.info(f"\n✓ Reel généré: {result}")
        except FileNotFoundError as e:
            logger.error(str(e))
            sys.exit(1)
        except Exception as e:
            logger.error(f"Erreur inattendue: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()
