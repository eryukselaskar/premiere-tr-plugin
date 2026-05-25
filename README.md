<div align="center">

# 🎙 TR Altyazı — AI Transcript & Auto-Cut for Premiere Pro

**Local AI transcription, SRT export, and silence-based auto-cut — all inside Premiere Pro. No API keys. No cloud. Completely free.**

[![License: MIT](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)
[![Premiere Pro](https://img.shields.io/badge/Premiere%20Pro-2022--2026-blue?logo=adobe-premiere-pro)](https://www.adobe.com/products/premiere.html)
[![Python](https://img.shields.io/badge/Python-3.9%2B-yellow?logo=python)](https://python.org)
[![CUDA](https://img.shields.io/badge/CUDA-GPU%20Accelerated-green?logo=nvidia)](https://developer.nvidia.com/cuda-toolkit)
[![Model](https://img.shields.io/badge/Whisper-large--v3-orange)](https://github.com/openai/whisper)

</div>

---

## ✨ What It Does

TR Altyazı is a **Premiere Pro CEP panel** that runs OpenAI Whisper locally on your GPU. Transcribe speech, generate subtitles, and remove silences — all without leaving Premiere.

| Feature | Description |
|---|---|
| 🎙 **AI Transcription** | Powered by `faster-whisper` with word-level timestamps |
| ✂ **Auto-Cut** | Detect and remove silences with 4 precision controls |
| 📄 **SRT Export** | One-click subtitle file to your desktop |
| 🎬 **Timeline Insert** | Captions directly into your Premiere sequence |
| 🔒 **100% Local** | Your footage never leaves your machine |
| 💸 **Zero Cost** | No API keys, no subscriptions, no usage limits |

> Optimized for **Turkish** with `large-v3`, but works with any language Whisper supports (English, Spanish, Japanese, Arabic, etc.)

---

## 🖥 Preview

```
┌─────────────────────────────────────┐
│  TR  Altyazı & Transcript    ● cut  │
├──────────────┬──────────────┬───────┤
│  Transcript  │   Auto-Cut   │ Ayar  │
├─────────────────────────────────────┤
│  ▶ Transkript Al          large-v3  │
│  Kaynak: [Aktif Sequence      ▼]    │
│                                     │
│  › Sequence: my_video (165s)        │
│  › Timeline audio export ediliyor  │
│  › Export tamam: tr_tl_177.wav      │
│  › Whisper'a gönderiliyor...        │
│  ████████████████░░░░  85%          │
│                                     │
│  0:02.1 → 0:05.8  Merhaba arkadaşlar│
│  0:06.0 → 0:09.2  Bugün sizinle...  │
│  0:09.5 → 0:14.1  Bu videoyu...     │
│                                     │
│  [ Timeline'a At ]                  │
│  [ Düzenle ]  [ SRT İndir ]  [ ✕ ] │
└─────────────────────────────────────┘
```

---

## ⚡ Quick Start

### Requirements

- **Adobe Premiere Pro** 2022–2026
- **Python** 3.9+
- **NVIDIA GPU** with CUDA (for GPU acceleration — CPU works too, just slower)
- **ffmpeg** in PATH (required by pydub for audio processing)

### 1. Clone & Install

```powershell
git clone https://github.com/eryukselaskar/premiere-tr-plugin.git
cd premiere-tr-plugin

# Run the installer (copies extension + sets registry keys)
Set-ExecutionPolicy Bypass -Scope Process
.\install.ps1
```

Or **manual install** — copy the repo folder to:
```
C:\Users\<YOU>\AppData\Roaming\Adobe\CEP\extensions\tr-subtitle\
```

### 2. Enable Unsigned Extensions (one-time)

```powershell
# Run in PowerShell as Administrator
reg add "HKCU\Software\Adobe\CSXS.11" /v PlayerDebugMode /t REG_DWORD /d 1 /f
reg add "HKCU\Software\Adobe\CSXS.12" /v PlayerDebugMode /t REG_DWORD /d 1 /f
reg add "HKCU\Software\Adobe\CSXS.13" /v PlayerDebugMode /t REG_DWORD /d 1 /f
```

### 3. Start the Whisper Server

```powershell
cd whisper-server
pip install -r ../requirements.txt

python whisper_server.py
# Server starts at http://127.0.0.1:5123
# large-v3 model (~3 GB) downloads on first run
```

### 4. Open in Premiere Pro

```
Window → Extensions → TR Altyazı & Transcript
```

---

## 🔧 How It Works

```
Premiere Pro Panel (HTML/JS)
        │
        ├── evalScript() ──► ExtendScript (JSX)
        │                         │
        │                    exportAsMediaDirect()
        │                    (exports current timeline audio)
        │
        └── fetch() ────────► Flask Server (Python)
                                    │
                              faster-whisper
                              (GPU transcription)
                                    │
                              word timestamps
                              silence detection
                              ◄─── segments ─────┘
```

**Why export the timeline first?** If you've already used Auto-Cut to remove silences, the source file is longer than your timeline. The panel exports the *current timeline state* as audio before transcribing, so timestamps always match what's on screen.

---

## 🎛 Auto-Cut Parameters

| Parameter | Default | Description |
|---|---|---|
| **Cutoff (dBFS)** | -50 dB | Volume threshold — below this = silence |
| **Min. Silence** | 0.5 s | Minimum silence duration to cut |
| **Min. Segment** | 0.5 s | Keep segments longer than this |
| **Padding** | 0.2 s | Buffer to keep around speech |

The panel detects silences server-side with `pydub`, then applies cuts via Premiere's QE API (razor + ripple delete).

---

## 📁 Project Structure

```
premiere-tr-plugin/
├── CSXS/
│   └── manifest.xml          ← CEP extension definition
├── HTML/
│   ├── index.html            ← Panel UI + all JavaScript
│   └── CSInterface.js        ← Adobe CEP bridge library
├── jsx/
│   └── hostscript.jsx        ← ExtendScript (Premiere timeline API)
├── whisper-server/
│   └── whisper_server.py     ← Flask + faster-whisper server
├── install.ps1               ← One-click Windows installer
├── requirements.txt
└── README.md
```

---

## 🧠 Model Performance

Tested on **RTX 5070 (12 GB VRAM)**:

| Model | VRAM | Speed | Turkish Quality |
|---|---|---|---|
| `tiny` | 1 GB | ~10x realtime | Poor |
| `base` | 1 GB | ~7x realtime | OK |
| `small` | 2 GB | ~5x realtime | Good |
| `medium` | 5 GB | ~3x realtime | Very Good |
| `large-v2` | 10 GB | ~2x realtime | Excellent |
| `large-v3` | 12 GB | ~2x realtime | **Best** ⭐ |

Change model in the **Settings** tab. CPU fallback works automatically if no GPU is detected.

---

## 🛠 Troubleshooting

<details>
<summary><b>Extension not showing in Premiere's Extensions menu</b></summary>

1. Make sure `PlayerDebugMode = 1` (DWORD, not String) for CSXS.11, CSXS.12, CSXS.13
2. Verify the folder is at: `%APPDATA%\Adobe\CEP\extensions\tr-subtitle\`
3. Fully restart Premiere Pro (not just reload)
4. Open `manifest.xml` in a browser to verify it's valid XML

</details>

<details>
<summary><b>Whisper server won't start</b></summary>

```powershell
# Check CUDA
nvidia-smi

# Reinstall with CUDA support
pip install faster-whisper --upgrade

# Run with explicit CUDA device
$env:CUDA_VISIBLE_DEVICES=0; python whisper_server.py
```

</details>

<details>
<summary><b>ffmpeg not found (pydub error)</b></summary>

```powershell
# Install via winget
winget install ffmpeg

# Or via chocolatey
choco install ffmpeg
```

Then restart the Whisper server.

</details>

<details>
<summary><b>Auto-cut misses some silences</b></summary>

Try raising the **Cutoff** threshold (e.g., -50 dB → -45 dB). Background noise can prevent pydub from detecting silence. Also reduce **Min. Silence** if short pauses are being missed.

</details>

---

## 🤝 Contributing

PRs welcome! Ideas for contribution:

- [ ] macOS support (different CEP paths)
- [ ] Multi-track Auto-Cut
- [ ] Caption styling via Essential Graphics API
- [ ] Speaker diarization
- [ ] Streaming progress from Whisper to the panel
- [ ] Batch transcription for multiple sequences

```bash
git clone https://github.com/eryukselaskar/premiere-tr-plugin.git
code premiere-tr-plugin
```

For ExtendScript debugging, use the `ExtendScript Debugger` VS Code extension.

---

## 📄 License

MIT — do whatever you want, attribution appreciated.

---

<div align="center">

**If this saved you time, a ⭐ star helps others find it.**

Made with ☕ for video editors who hate paying for transcription APIs.

</div>
