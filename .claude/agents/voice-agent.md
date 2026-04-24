---
name: voice-agent
description: Converts reel scripts into high-quality voiceovers. Splits text into fragments, inserts calibrated pauses, generates audio via ElevenLabs (or gTTS fallback), and merges into a single MP3.
model: claude-haiku-4-5-20251001
---

# Voice Agent

Thin wrapper around `agents/voice_agent.py`. This agent is invoked programmatically — not via Claude text generation.

## Role
Convert the script from `output/agents/03_script.json` into `output/audio/reel_voice.mp3`.

## Voice rules
- Pauses between fragments (0.35s) and between scenes (0.4–0.8s depending on scene type)
- HOOK: 0.8s pause — let it land
- TENSION: 0.35s between each fragment — rapid fire
- PROOF: 0.6s — let the stat sink in
- RESULT: 0.8s — let the emotion land

## TTS priority
1. ElevenLabs API (`ELEVENLABS_API_KEY`) — eleven_multilingual_v2, stability 0.5, style 0.05
2. gTTS fallback (no API key required)

## Output
`output/audio/reel_voice.mp3` + duration in seconds
