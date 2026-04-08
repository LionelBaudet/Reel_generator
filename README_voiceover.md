# Reel Generator — Voiceover Pipeline

Automated Instagram Reel generator with ElevenLabs TTS voiceover and FFmpeg video assembly.

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.10+ | |
| FFmpeg | any recent | must be on `PATH` |
| ElevenLabs account | — | free tier works |

### Install Python dependencies

```bash
pip install -r requirements.txt
```

### Install FFmpeg

- **Windows**: download from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) and add to PATH  
- **macOS**: `brew install ffmpeg`  
- **Linux**: `sudo apt install ffmpeg`

---

## Setup

### 1. Create `.env`

```bash
cp .env.example .env   # or create manually
```

`.env` content:

```
ELEVENLABS_API_KEY=your_key_here
```

Get your key at [elevenlabs.io/app/speech-synthesis](https://elevenlabs.io/app/speech-synthesis) → Profile → API Key.

### 2. Create a reel config

Copy `config/reel_01.yaml` and edit it:

```yaml
title: "Stop typing emails from scratch"

voiceover:
  text: >
    Stop typing emails from scratch.
    Use this prompt instead.
    Copy it, paste it, done.
  voice_id: "EXAVITQu4vr4xnSDxMaL"   # see voice list below
  speed: 1.0
  stability: 0.5
  similarity_boost: 0.75

video:
  clips:
    - assets/video/my_clip.mp4         # b-roll video
  background_music: assets/audio/lofi_beat.wav
  music_volume: 0.15
  voiceover_volume: 1.0
  music_fade_out: 0.5

slides: []                             # optional PNG overlays

output: output/reel_01.mp4
```

### 3. Add your assets

```
assets/
├── video/      ← drop your b-roll clips here (.mp4)
├── audio/      ← background music (.mp3 or .wav)
└── voiceover/  ← auto-created, MP3s saved here
```

---

## Usage

### Full pipeline (voiceover + video)

```bash
python generate_reel.py --config config/reel_01.yaml
```

### Voiceover only (no video)

```bash
python generate_reel.py --config config/reel_01.yaml --voiceover-only
# or
python generate_voiceover.py --config config/reel_01.yaml
```

### Skip API call — reuse existing voiceover

Useful when iterating on video edits without burning API credits:

```bash
python generate_reel.py --config config/reel_01.yaml --skip-voiceover
```

### Use a custom voiceover file

```bash
python generate_reel.py --config config/reel_01.yaml --voiceover-path assets/voiceover/my_take.mp3
```

---

## YAML config reference

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `title` | string | `"reel"` | Used for output filename |
| `voiceover.text` | string | required | Script spoken by the voice |
| `voiceover.voice_id` | string | Sarah | ElevenLabs voice ID |
| `voiceover.speed` | float | `1.0` | Speech speed (0.7–1.2) |
| `voiceover.stability` | float | `0.5` | Voice consistency (0–1) |
| `voiceover.similarity_boost` | float | `0.75` | Voice fidelity (0–1) |
| `voiceover.style` | float | `0.0` | Expressiveness (0–1) |
| `voiceover.model_id` | string | `eleven_multilingual_v2` | TTS model |
| `video.clips` | list | `[]` | Source video clips (looped if too short) |
| `video.background_music` | string | `""` | Background audio file |
| `video.music_volume` | float | `0.15` | Background music level (0–1) |
| `video.voiceover_volume` | float | `1.0` | Voiceover level (0–1) |
| `video.music_fade_out` | float | `0.5` | Fade-out duration in seconds |
| `slides` | list | `[]` | PNG files overlaid in sequence |
| `output` | string | `output/{title}.mp4` | Output file path |

**Note**: final video duration = voiceover duration. Background music loops and fades out automatically.

---

## ElevenLabs voice IDs

| Voice | ID | Style |
|-------|----|-------|
| **Sarah** | `EXAVITQu4vr4xnSDxMaL` | Clear, professional — best for tutorials |
| **Adam** | `pNInz6obpgDQGcFmaJgB` | Deep, authoritative — best for bold hooks |
| **Antoni** | `ErXwobaYiN019PkySvjV` | Natural, conversational — best for storytelling |

Browse more voices at [elevenlabs.io/app/voice-library](https://elevenlabs.io/app/voice-library).

---

## Pipeline diagram

```
config/reel_01.yaml
        │
        ▼
generate_voiceover()
  └─ ElevenLabs API ──► assets/voiceover/{title}.mp3
        │
        ▼  (duration probed with ffprobe)
build_reel()
  ├─ concat video clips
  ├─ loop to voiceover duration
  ├─ overlay PNG slides (optional)
  ├─ loop + fade background music
  └─ mix all ──► output/{title}.mp4
```

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `ELEVENLABS_API_KEY is not set` | Missing `.env` | Add key to `.env` |
| `401 Unauthorized` | Wrong API key | Check key at elevenlabs.io |
| `429 rate limit` | Too many requests | Wait or upgrade plan |
| `ffmpeg is not installed` | FFmpeg not on PATH | Install FFmpeg |
| `No valid video clips found` | Missing asset files | Add clips to `assets/video/` |
| `Could not probe duration` | Corrupt audio file | Re-generate voiceover |
