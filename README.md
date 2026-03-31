# Reels Generator — @ownyourtime.ai

Générateur automatique de Reels Instagram pour la marque **@ownyourtime.ai** — "building in public" autour de l'IA productive.

Génère des vidéos verticales 1080×1920px (15–30s) directement depuis un fichier YAML, sans édition manuelle.

---

## Aperçu du template "Prompt Reveal"

| Segment | Durée | Description |
|---------|-------|-------------|
| **Hook** | 0–3s | Texte accrocheur mot par mot + soulignement doré |
| **Prompt Reveal** | 3–15s | Animation de frappe du prompt + output style terminal |
| **CTA** | 15–18s | Fond or, texte pulsant, appel à l'action |

---

## Installation

### Prérequis

- Python 3.9+ ([télécharger](https://www.python.org/downloads/))
- FFmpeg ([macOS](https://formulae.brew.sh/formula/ffmpeg) / [Windows](https://www.gyan.dev/ffmpeg/builds/))
- Node.js LTS (optionnel, pour Remotion) ([télécharger](https://nodejs.org/))

---

### Installation automatique (macOS / Windows Git Bash)

```bash
# Cloner ou télécharger le projet, puis:
cd reels_generator

# Lancer le script d'installation (installe tout automatiquement)
bash setup.sh
```

Le script installe :
- L'environnement virtuel Python
- Toutes les dépendances Python (`moviepy`, `pillow`, etc.)
- FFmpeg via Homebrew (macOS uniquement)
- Les dépendances Remotion (si Node.js est présent)
- Les polices Plus Jakarta Sans & JetBrains Mono
- Génère des aperçus de test pour vérifier l'installation

---

### Installation manuelle — macOS

```bash
# 1. Installer FFmpeg
brew install ffmpeg

# 2. Créer l'environnement virtuel
python3 -m venv venv
source venv/bin/activate

# 3. Installer les dépendances Python
pip install -r requirements.txt

# 4. (Optionnel) Installer Node.js pour Remotion
# Téléchargez depuis https://nodejs.org/
cd remotion_comp
npm install
cd ..

# 5. Vérifier l'installation
python main.py --setup
```

---

### Installation manuelle — Windows

```powershell
# 1. Installer FFmpeg
# Option A — Winget (recommandé):
winget install ffmpeg
# Option B — Chocolatey:
choco install ffmpeg
# Option C — Manuellement: https://www.gyan.dev/ffmpeg/builds/
#   → Extraire dans C:\ffmpeg\ et ajouter C:\ffmpeg\bin au PATH

# 2. Dans Git Bash ou PowerShell:
python -m venv venv
# Git Bash:
source venv/Scripts/activate
# PowerShell:
# venv\Scripts\Activate.ps1

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. (Optionnel) Remotion
cd remotion_comp
npm install
cd ..

# 5. Vérifier
python main.py --setup
```

---

## Utilisation

### Générer un reel unique

```bash
# Activer l'environnement virtuel (si pas déjà fait)
source venv/bin/activate         # macOS / Linux
# source venv/Scripts/activate   # Windows Git Bash

# Générer le reel
python main.py --config config/reel_config.yaml --output output/reel_001.mp4
```

### Aperçu rapide (PNG uniquement, < 5 secondes)

```bash
python main.py --config config/reel_config.yaml --output output/ --preview
# Génère : output/preview_hook.png, preview_prompt.png, preview_cta.png
```

### Génération batch

```bash
# Mettre plusieurs fichiers YAML dans config/batch/
python main.py --batch config/batch/ --output output/
```

### Avec Remotion (animations avancées, requiert Node.js)

```bash
python main.py --config config/reel_config.yaml --output output/reel.mp4 --remotion
```

### Mode verbeux (logs détaillés)

```bash
python main.py --config config/reel_config.yaml --output output/reel.mp4 --verbose
```

---

## Personnaliser votre reel

Éditez `config/reel_config.yaml` :

```yaml
hook:
  text: "Votre texte accrocheur ici."
  highlight: "texte à souligner"   # Mots qui reçoivent le soulignement doré
  duration: 3                       # Durée en secondes

prompt:
  title: "Titre du prompt"
  text: |
    Votre prompt ici...
    Sur plusieurs lignes.
  output_preview: |
    Résultat simulé ici...
    Ligne par ligne.
  saves: "saves 20 min/day"        # Badge affiché en fin de segment
  duration: 12

cta:
  headline: "Save THIS."
  subtext: "10 free prompts → link in bio 🎁"
  handle: "@votre_handle"
  duration: 3

audio:
  background_music: "assets/audio/lofi_beat.mp3"   # Optionnel
  volume: 0.3                                        # 0.0 à 1.0
```

### Ajouter de la musique

Placez votre fichier MP3 dans `assets/audio/` et référencez-le dans la config :

```yaml
audio:
  background_music: "assets/audio/mon_morceau.mp3"
  volume: 0.25
```

> Si aucun fichier audio n'est trouvé, la vidéo est générée en silence.

---

## Créer des reels en batch

1. Dupliquez `config/reel_config.yaml` dans `config/batch/`
2. Renommez chaque fichier : `reel_01.yaml`, `reel_02.yaml`, etc.
3. Personnalisez chaque fichier
4. Lancez : `python main.py --batch config/batch/ --output output/`

---

## Architecture du projet

```
reels_generator/
├── main.py                    # CLI principal
├── requirements.txt           # Dépendances Python
├── setup.sh                   # Installation automatique
│
├── config/
│   ├── reel_config.yaml       # Configuration principale
│   └── batch/                 # Configs pour génération en lot
│
├── templates/
│   ├── __init__.py
│   └── prompt_reveal.py       # Template principal (Hook + Prompt + CTA)
│
├── utils/
│   ├── fonts.py               # Gestion et téléchargement des polices
│   ├── audio.py               # Gestion audio (chargement / silence)
│   └── renderer.py            # Utilitaires de rendu Pillow
│
├── remotion_comp/             # Composants React/Remotion (optionnel)
│   ├── package.json
│   ├── remotion.config.ts
│   └── src/
│       ├── index.tsx          # Point d'entrée Remotion
│       ├── Root.tsx           # Compositions Remotion
│       ├── PromptReveal.tsx   # Composant principal
│       ├── HookSlide.tsx      # Segment Hook
│       └── CTASlide.tsx       # Segment CTA
│
├── assets/
│   ├── fonts/                 # Polices téléchargées
│   ├── audio/                 # Musique de fond
│   └── logo.svg               # Logo horloge
│
└── output/                    # Vidéos générées
```

---

## Stack technique

| Outil | Rôle | Version |
|-------|------|---------|
| Python | Runtime principal | 3.9+ |
| MoviePy | Composition vidéo | ≥ 1.0.3 |
| Pillow | Rendu des frames | ≥ 10.0 |
| FFmpeg | Encodage H.264 / audio | Tout |
| PyYAML | Lecture des configs | ≥ 6.0 |
| Remotion | Animations React (optionnel) | ≥ 4.0 |

---

## Dépannage

### "FFmpeg not found"
→ Vérifiez que FFmpeg est dans votre PATH : `ffmpeg -version`

### "No module named 'moviepy'"
→ Activez votre environnement virtuel : `source venv/bin/activate` (Mac) ou `source venv/Scripts/activate` (Windows)

### Les polices semblent basiques
→ Les polices personnalisées n'ont pas pu être téléchargées. Lancez `python main.py --setup` pour réessayer, ou placez manuellement `PlusJakartaSans-Bold.ttf` et `JetBrainsMono-Regular.ttf` dans `assets/fonts/`.

### La vidéo est très lente à générer
→ Normal — le rendu frame-par-frame avec Pillow prend 2–5 minutes pour un reel de 18s. Pour un rendu plus rapide, utilisez l'option `--remotion` avec Node.js installé.

### Remotion échoue
→ Assurez-vous que `npm install` a été lancé dans `remotion_comp/`. La génération reprend automatiquement sur Python/MoviePy en cas d'échec.

---

## Spécifications de sortie

- **Format:** MP4, codec H.264, audio AAC
- **Résolution:** 1080 × 1920 px (vertical / portrait)
- **FPS:** 30
- **Durée:** 15–30 secondes (configurable)
- **Prêt pour:** Instagram Reels, TikTok, YouTube Shorts

---

## Palette de couleurs

| Nom | Hex | Usage |
|-----|-----|-------|
| Midnight | `#09091A` | Fond principal |
| Deep Ink | `#1E1E32` | Fond secondaire |
| Gold | `#E8B84B` | Accent, soulignements |
| Ivory | `#F2F0EA` | Texte principal |
| Muted | `#52527A` | Texte secondaire |

---

*Généré par Claude Code pour @ownyourtime.ai*
