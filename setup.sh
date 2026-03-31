#!/usr/bin/env bash
# ============================================================
# Script d'installation automatique — Reels Generator
# Compatible macOS (M1/M2/Intel) et Windows (Git Bash)
# ============================================================

set -e  # Arrêter en cas d'erreur

# ── Couleurs pour les messages ───────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'  # No Color

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERREUR]${NC} $1"; }

# ── Détection du système d'exploitation ──────────────────────
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ "$OS" == "Windows_NT" ]]; then
        echo "windows"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    else
        echo "unknown"
    fi
}

OS=$(detect_os)
log_info "Système détecté: $OS"

# ── Bannière ──────────────────────────────────────────────────
echo ""
echo -e "${BOLD}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║   INSTALLATION — Reels Generator @ownyourtime.ai  ║${NC}"
echo -e "${BOLD}╚═══════════════════════════════════════════════════╝${NC}"
echo ""

# ── 1. Vérifier Python 3.11+ ─────────────────────────────────
log_info "Vérification de Python..."
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    log_error "Python n'est pas installé!"
    echo "  → macOS:   brew install python@3.11"
    echo "  → Windows: https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
log_success "Python $PYTHON_VERSION trouvé ($PYTHON_CMD)"

if $PYTHON_CMD -c "import sys; assert sys.version_info >= (3, 9)" 2>/dev/null; then
    log_success "Version Python compatible (≥ 3.9)"
else
    log_warn "Python 3.9+ recommandé. Votre version: $PYTHON_VERSION"
fi

# ── 2. Créer l'environnement virtuel ─────────────────────────
log_info "Création de l'environnement virtuel Python..."
if [ ! -d "venv" ]; then
    $PYTHON_CMD -m venv venv
    log_success "Environnement virtuel créé dans ./venv"
else
    log_success "Environnement virtuel existant détecté"
fi

# Activer l'environnement virtuel
if [[ "$OS" == "windows" ]]; then
    VENV_ACTIVATE="venv/Scripts/activate"
else
    VENV_ACTIVATE="venv/bin/activate"
fi

if [ -f "$VENV_ACTIVATE" ]; then
    source "$VENV_ACTIVATE"
    log_success "Environnement virtuel activé"
else
    log_warn "Impossible d'activer le venv automatiquement"
fi

# ── 3. Installer les dépendances Python ──────────────────────
log_info "Installation des dépendances Python..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
log_success "Dépendances Python installées"

# ── 4. Installer FFmpeg ───────────────────────────────────────
log_info "Vérification de FFmpeg..."
if command -v ffmpeg &>/dev/null; then
    FFMPEG_VERSION=$(ffmpeg -version 2>&1 | head -1)
    log_success "FFmpeg déjà installé: $FFMPEG_VERSION"
else
    log_warn "FFmpeg non trouvé. Installation en cours..."

    if [[ "$OS" == "macos" ]]; then
        if command -v brew &>/dev/null; then
            brew install ffmpeg
            log_success "FFmpeg installé via Homebrew"
        else
            log_error "Homebrew requis pour installer FFmpeg sur macOS"
            echo "  → Installez Homebrew: https://brew.sh"
            echo "  → Puis relancez: brew install ffmpeg"
        fi

    elif [[ "$OS" == "windows" ]]; then
        log_warn "Installation automatique de FFmpeg sur Windows non supportée"
        echo ""
        echo "  Installez FFmpeg manuellement:"
        echo "  1. Téléchargez depuis https://www.gyan.dev/ffmpeg/builds/"
        echo "  2. Extrayez dans C:\\ffmpeg\\"
        echo "  3. Ajoutez C:\\ffmpeg\\bin à votre PATH"
        echo "  Ou avec Chocolatey: choco install ffmpeg"
        echo "  Ou avec Winget:     winget install ffmpeg"
        echo ""

    elif [[ "$OS" == "linux" ]]; then
        if command -v apt-get &>/dev/null; then
            sudo apt-get update -qq && sudo apt-get install -y ffmpeg
        elif command -v yum &>/dev/null; then
            sudo yum install -y ffmpeg
        fi
        log_success "FFmpeg installé"
    fi
fi

# ── 5. Vérifier Node.js (optionnel pour Remotion) ────────────
log_info "Vérification de Node.js (optionnel pour Remotion)..."
if command -v node &>/dev/null; then
    NODE_VERSION=$(node --version)
    log_success "Node.js $NODE_VERSION trouvé"

    # Installer les dépendances Remotion
    log_info "Installation des dépendances Remotion..."
    if [ -d "remotion_comp" ]; then
        cd remotion_comp
        if command -v npm &>/dev/null; then
            npm install --silent 2>/dev/null || npm install
            log_success "Dépendances Remotion installées"
        fi
        cd ..
    fi
else
    log_warn "Node.js non trouvé — Remotion désactivé (le rendu Python restera fonctionnel)"
    echo "  → Pour activer Remotion: https://nodejs.org/ (LTS recommandé)"
fi

# ── 6. Créer les dossiers requis ─────────────────────────────
log_info "Création des dossiers..."
mkdir -p output assets/fonts assets/audio config/batch
log_success "Dossiers créés"

# ── 7. Télécharger les polices ───────────────────────────────
log_info "Téléchargement des polices (Plus Jakarta Sans + JetBrains Mono)..."
$PYTHON_CMD -c "
from utils.fonts import setup_fonts
setup_fonts()
" 2>/dev/null && log_success "Polices configurées" || log_warn "Téléchargement partiel des polices (repli sur polices système)"

# ── 8. Générer des aperçus de test ───────────────────────────
log_info "Génération des frames de prévisualisation de test..."
$PYTHON_CMD main.py --config config/reel_config.yaml --output output/ --preview 2>/dev/null \
    && log_success "Aperçus générés dans output/ (preview_hook.png, preview_prompt.png, preview_cta.png)" \
    || log_warn "Aperçus non générés — vérifiez l'installation manuellement"

# ── Récapitulatif ─────────────────────────────────────────────
echo ""
echo -e "${BOLD}╔═══════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║              INSTALLATION TERMINÉE                 ║${NC}"
echo -e "${BOLD}╚═══════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Commandes disponibles:"
echo ""
echo -e "  ${GREEN}# Générer un reel${NC}"
echo "  python main.py --config config/reel_config.yaml --output output/reel_001.mp4"
echo ""
echo -e "  ${GREEN}# Aperçu rapide (PNG uniquement, sans rendu vidéo)${NC}"
echo "  python main.py --config config/reel_config.yaml --output output/ --preview"
echo ""
echo -e "  ${GREEN}# Batch depuis un dossier${NC}"
echo "  python main.py --batch config/batch/ --output output/"
echo ""
echo -e "  ${GREEN}# Avec Remotion (si Node.js est installé)${NC}"
echo "  python main.py --config config/reel_config.yaml --output output/reel.mp4 --remotion"
echo ""
echo "  Éditez ${BOLD}config/reel_config.yaml${NC} pour personnaliser votre reel."
echo ""
