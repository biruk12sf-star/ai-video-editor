---
title: Autonomous AI Video Director
emoji: 🎬
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# 🎬 Autonomous AI Video Director PRO v2.5

Zero-human video editing powered by **Google Gemini 3.6 Multimodal Vision** and **ElevenLabs Voice AI**.

## 🚀 Features
- **Multimodal Video Understanding**: Gemini 3.6 Flash analyzes raw video frame-by-frame to extract timed story beats, character expressions, and plot twists.
- **Storytelling Narration**: High-energy voiceover synthesized via ElevenLabs (Adam).
- **Pro VFX Compositing**: FFmpeg and MoviePy multi-track rendering with 9:16 vertical crop, glowing neon synchronized captions, and background audio ducking.
- **YouTube Shorts Upload Kit**: Automatically writes viral titles, descriptions, hashtags, and engagement pinned comments.

## 🔑 Environment Variables Required
In your Hugging Face Space **Settings > Variables and secrets > New secret**:
- `GEMINI_API_KEY`: Your Google Gemini API Key
- `ELEVENLABS_API_KEY`: Your ElevenLabs API Key

## 🛠️ Local Development
```bash
pip install -r requirements.txt
python server.py
```
Open [http://localhost:8000](http://localhost:8000) in your browser.
