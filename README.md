# 🎙️ SlideCast

> **Frugal, zero-dependency slide-by-slide presentation recording studio with live waveform, punch-in audio repair, synchronized teleprompter, and 1-click 1080p MP4 video rendering.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.8+](https://img.shields.io/badge/Python-3.8+-green.svg)](https://www.python.org/)
[![Zero Dependencies](https://img.shields.io/badge/Dependencies-Zero%20pip%20packages-brightgreen.svg)](#requirements)

---

## ✨ Features

- 📂 **Multi-Project Management:** Create and organize multiple presentations with their own slide sets, speaker notes, and audio takes.
- 📄 **1-Click PDF Slide Import:** Upload any PDF presentation. Slides are automatically extracted as crisp 1080p slide images.
- 📊 **Real-time Live Audio Waveform:** Visual amplitude envelope drawn live as you speak, showing pauses, breaks, and speech bursts.
- 🔴 **Sample-Accurate Punch-In Audio Repair:** Stumbled on a word at `00:14.2`? Click on the waveform, preview, and resume recording from that exact spot without re-recording the whole slide.
- ✏️ **Synchronized Editable Teleprompter:** Live speech notes side-by-side with your slides, automatically saved to Markdown (`notes.md`).
- 🎬 **1-Click 1080p Video Generation:** Stitches your slide images and audio into a professional 1080p MP4 video with high-quality audio and zero sync drift.
- 🪶 **Frugal & Standalone:** Pure Python standard library backend (`http.server`) + Vanilla JavaScript frontend. No heavy frameworks, no `npm install`, no external `pip` dependencies.

---

## 🚀 Quick Start

### 1. Requirements
- **Python 3.8+** (standard library only)
- **`ffmpeg`** & **`pdftoppm`** (standard on Linux/macOS):
  ```bash
  # Ubuntu / Debian
  sudo apt install ffmpeg poppler-utils

  # macOS
  brew install ffmpeg poppler
  ```

### 2. Launch SlideCast
```bash
git clone https://github.com/bonben/slidecast.git
cd slidecast
python3 slidecast.py
```
Open **[http://localhost:8080](http://localhost:8080)** in your browser (Chrome, Firefox, Edge, Safari).

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| <kbd>Space</kbd> | Start Recording / Pause / Resume |
| <kbd>Enter</kbd> | Finish & Save Slide Audio |
| <kbd>P</kbd> | Pause / Resume Recording or Toggle Audio Playback |
| <kbd>←</kbd> / <kbd>→</kbd> | Previous / Next Slide |

---

## 📁 Project Structure

```text
slidecast/
├── slidecast.py          # Standalone server & video compiler
├── web/
│   └── index.html        # Web studio interface
├── projects/
│   └── my_presentation/
│       ├── metadata.json # Project metadata
│       ├── slides.pdf    # Source PDF slides
│       ├── slide_images/ # Extracted 1080p slide PNGs
│       ├── recordings/   # Recorded 48kHz WAV audio files
│       ├── notes.md      # Synchronized speaker notes
│       └── presentation_complete.mp4 # Rendered video
├── README.md
└── LICENSE
```

---

## 🛠️ How It Works

1. **Slide Ingestion:** `pdftoppm` renders PDF pages into high-definition raster images.
2. **Audio Streaming & Punch-In:** Audio is captured at 48kHz PCM directly via Web Audio API. When punch-in is triggered at offset $T$, the buffer is sliced at $T$ and newly recorded PCM frames are seamlessly appended.
3. **HTTP 206 Partial Streaming:** Audio playback uses byte-range streaming for instantaneous scrubbing across takes.
4. **FFmpeg Video Encoding:** Slide images are looped and coupled with their respective audio takes, then concatenated in stream-copy mode for fast, lossless 1080p video rendering.

---

## 📜 License

MIT License — Copyright (c) 2026 Mathieu Léonardon.
