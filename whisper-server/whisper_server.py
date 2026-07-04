"""
whisper_server.py — Yerel Türkçe Transcript Sunucusu
RTX 5070 GPU (CUDA) ile faster-whisper kullanır

Kurulum:
  pip install faster-whisper flask flask-cors
  
Çalıştırma:
  python whisper_server.py

Endpoint: http://localhost:5123
"""

import os
import sys
import json
import tempfile
import subprocess
from pathlib import Path

# Windows'ta ctranslate2'nin CUDA DLL'lerini (cublas64_12.dll vb.) bulabilmesi için site-packages/nvidia yollarını DLL arama yoluna ekle
if sys.platform == "win32":
    dll_paths = []
    for path in sys.path:
        if "site-packages" in path.lower():
            nvidia_dir = os.path.join(path, "nvidia")
            if os.path.exists(nvidia_dir):
                for root, dirs, files in os.walk(nvidia_dir):
                    if any(f.lower().endswith(".dll") for f in files):
                        try:
                            os.add_dll_directory(root)
                            dll_paths.append(root)
                            print(f"[Whisper DLL] Kaydedildi (add_dll_directory): {root}")
                        except Exception as e:
                            print(f"[Whisper DLL] Hata ({root}): {e}")
    if dll_paths:
        os.environ["PATH"] = ";".join(dll_paths) + ";" + os.environ.get("PATH", "")
        print("[Whisper DLL] System PATH güncellendi.")

from flask import Flask, request, jsonify
from flask_cors import CORS

# faster-whisper import
try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    print("[UYARI] faster-whisper kurulu değil. pip install faster-whisper")

# pydub import (ses analizi için)
try:
    from pydub import AudioSegment
    from pydub.silence import detect_silence as pydub_detect_silence
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    print("[UYARI] pydub kurulu değil. pip install pydub")

app = Flask(__name__)
CORS(app)  # CEP panel'den erişim için gerekli

# ─── Model ayarları ───────────────────────────────────────────────────────────
# RTX 5070 12GB VRAM ile "large-v3" rahatlıkla çalışır
# Türkçe için "large-v3" en iyi sonucu verir

MODEL_SIZE  = os.environ.get("WHISPER_MODEL", "large-v3")
DEVICE      = "cuda"       # RTX 5070 kullan
COMPUTE     = "float16"    # VRAM tasarrufu için float16
BEAM_SIZE   = 5

model = None

def load_model():
    global model
    if not WHISPER_AVAILABLE:
        return False
    if model is None:
        print(f"[Whisper] Model yükleniyor: {MODEL_SIZE} ({DEVICE}/{COMPUTE})...")
        try:
            model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE)
            print(f"[Whisper] Model hazır: {MODEL_SIZE}")
        except Exception as e:
            print(f"[Whisper] GPU yükleme hatası, CPU'ya geçiliyor: {e}")
            model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    return True


# ─── Endpointler ─────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "model": MODEL_SIZE,
        "device": DEVICE,
        "whisper_available": WHISPER_AVAILABLE,
        "model_loaded": model is not None
    })


@app.route("/transcribe", methods=["POST"])
def transcribe():
    """
    Ses dosyasını Türkçe olarak transkripte eder.
    
    Body: multipart/form-data
      - audio: ses dosyası (WAV, MP3, AAC, MP4)
      - word_timestamps: "true"/"false" (varsayılan: true)
      - response_format: "json"/"srt"/"vtt" (varsayılan: json)
    """
    if not load_model():
        return jsonify({"error": "faster-whisper kurulu değil."}), 500

    if "audio" not in request.files:
        return jsonify({"error": "Ses dosyası eksik. 'audio' field gerekli."}), 400

    audio_file = request.files["audio"]
    word_timestamps = request.form.get("word_timestamps", "true").lower() == "true"
    response_format = request.form.get("response_format", "json")
    vad_filter = request.form.get("vad_filter", "true").lower() == "true"

    # Geçici dosyaya kaydet
    suffix = Path(audio_file.filename).suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = tmp.name
        audio_file.save(tmp_path)

    try:
        print(f"[Whisper] Transkript başlıyor: {audio_file.filename}")

        segments, info = model.transcribe(
            tmp_path,
            language="tr",              # Türkçe zorla
            beam_size=BEAM_SIZE,
            word_timestamps=word_timestamps,
            vad_filter=vad_filter,      # Sessizlikleri otomatik atla (auto-cut için önemli)
            vad_parameters=dict(
                min_silence_duration_ms=300,   # 300ms sessizlik = yeni segment
                threshold=0.4
            )
        )

        # Segmentleri işle
        result_segments = []
        all_words = []

        for seg in segments:
            segment_data = {
                "start": round(seg.start, 3),
                "end":   round(seg.end,   3),
                "text":  seg.text.strip()
            }

            if word_timestamps and seg.words:
                words = []
                for w in seg.words:
                    word_data = {
                        "word":  w.word.strip(),
                        "start": round(w.start, 3),
                        "end":   round(w.end,   3),
                        "prob":  round(w.probability, 3)
                    }
                    words.append(word_data)
                    all_words.append(word_data)
                segment_data["words"] = words

            result_segments.append(segment_data)

        # Sessizlik analizi (auto-cut için)
        silence_ranges = detect_silence_ranges(all_words, threshold=0.35)

        if response_format == "srt":
            return segments_to_srt(result_segments), 200, {
                "Content-Type": "text/plain; charset=utf-8"
            }

        return jsonify({
            "language": "tr",
            "duration": round(info.duration, 2),
            "segments": result_segments,
            "words": all_words if word_timestamps else [],
            "silence_ranges": silence_ranges,
            "model": MODEL_SIZE
        })

    except Exception as e:
        print(f"[Whisper] Hata: {e}")
        return jsonify({"error": str(e)}), 500

    finally:
        os.unlink(tmp_path)


@app.route("/transcribe/path", methods=["GET", "POST"])
def transcribe_path():
    """
    Disk üzerindeki dosya yoluyla çalışır (büyük dosyalar için)
    ve transkripti gerçek zamanlı (stream) olarak ndjson formatında döner.
    """
    if not load_model():
        return jsonify({"error": "faster-whisper kurulu değil."}), 500

    if request.method == "POST":
        data = request.json or {}
    else:
        data = request.args or {}

    file_path = data.get("path")

    if not file_path or not os.path.exists(file_path):
        return jsonify({"error": f"Dosya bulunamadı: {file_path}"}), 400

    word_timestamps = str(data.get("word_timestamps", "true")).lower() == "true"
    vad_filter      = str(data.get("vad_filter", "true")).lower() == "true"
    max_line_chars  = int(data.get("max_line_chars", 42))

    try:
        segments, info = model.transcribe(
            file_path,
            language="tr",
            beam_size=BEAM_SIZE,
            word_timestamps=word_timestamps,
            vad_filter=vad_filter,
            vad_parameters=dict(min_silence_duration_ms=300, threshold=0.4)
        )

        def generate():
            # İlk başta genel sekans bilgisini gönder
            yield json.dumps({
                "type": "info",
                "language": "tr",
                "duration": round(info.duration, 2)
            }) + "\n"

            all_words = []
            
            for seg in segments:
                text = seg.text.strip()
                if not text:
                    continue

                seg_words = []
                if word_timestamps and seg.words:
                    seg_words = [
                        {"word": w.word.strip(), "start": round(w.start, 3),
                         "end": round(w.end, 3), "prob": round(w.probability, 3)}
                        for w in seg.words
                    ]
                    all_words.extend(seg_words)

                # Segment uzunsa böl, değilse doğrudan gönder
                if len(text) > max_line_chars:
                    chunks = split_long_segment(seg.start, seg.end, text, max_line_chars)
                    for chunk in chunks:
                        yield json.dumps({
                            "type": "segment",
                            "segment": chunk
                        }) + "\n"
                else:
                    seg_data = {"start": round(seg.start, 3), "end": round(seg.end, 3), "text": text}
                    if seg_words:
                        seg_data["words"] = seg_words
                    yield json.dumps({
                        "type": "segment",
                        "segment": seg_data
                    }) + "\n"

            # En son sessizlik analizini tamamlayıp bitir
            silence_ranges = detect_silence_ranges(all_words)
            yield json.dumps({
                "type": "done",
                "silence_ranges": silence_ranges,
                "words": all_words if word_timestamps else []
            }) + "\n"

        return app.response_class(generate(), mimetype="application/x-ndjson")

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Yardımcı ─────────────────────────────────────────────────────────────────

def detect_silence_ranges(words, threshold=0.35):
    """Kelimeler arasındaki sessizlik aralıklarını tespit et."""
    ranges = []
    for i in range(len(words) - 1):
        gap = words[i + 1]["start"] - words[i]["end"]
        if gap > threshold:
            ranges.append({
                "start": round(words[i]["end"] + 0.03, 3),
                "end":   round(words[i + 1]["start"] - 0.03, 3),
                "duration": round(gap, 3)
            })
    return ranges


def segments_to_srt(segments):
    """Segmentleri SRT formatına çevir."""
    lines = []
    for i, seg in enumerate(segments):
        lines.append(str(i + 1))
        lines.append(f"{fmt_time(seg['start'])} --> {fmt_time(seg['end'])}")
        lines.append(seg["text"])
        lines.append("")
    return "\n".join(lines)


def fmt_time(seconds):
    h  = int(seconds // 3600)
    m  = int((seconds % 3600) // 60)
    s  = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ─── Ses analizi: dB tabanlı sessizlik tespiti ───────────────────────────────

@app.route("/detect-silence", methods=["POST"])
def detect_silence_endpoint():
    """
    Ses dosyasında dB tabanlı sessizlik tespiti yapar.

    Body: JSON
      - path: dosya yolu
      - silence_thresh: dBFS eşiği (örn. -35), bu değerin altı sessizlik sayılır
      - min_silence_len: minimum sessizlik süresi (ms), default 300
      - min_segment_len: minimum konuşma segmenti (ms), default 200
      - padding: kesim başı/sonu buffer (ms), default 50
    """
    if not PYDUB_AVAILABLE:
        return jsonify({"error": "pydub kurulu değil. pip install pydub"}), 500

    data       = request.json or {}
    file_path  = data.get("path")
    thresh     = float(data.get("silence_thresh", -35))
    min_sil_ms = int(data.get("min_silence_len", 300))
    min_seg_ms = int(data.get("min_segment_len", 200))
    padding_ms = int(data.get("padding", 50))

    if not file_path or not os.path.exists(file_path):
        return jsonify({"error": f"Dosya bulunamadı: {file_path}"}), 400

    try:
        audio    = AudioSegment.from_file(file_path)
        dur_sec  = len(audio) / 1000.0
        silences = pydub_detect_silence(audio, min_silence_len=min_sil_ms, silence_thresh=thresh)

        ranges = []
        for start_ms, end_ms in silences:
            s = (start_ms + padding_ms) / 1000.0
            e = (end_ms   - padding_ms) / 1000.0
            if e > s:
                ranges.append({
                    "start":    round(s, 3),
                    "end":      round(e, 3),
                    "duration": round((end_ms - start_ms) / 1000.0, 3)
                })

        # min_segment_len: ardışık iki kesim arası konuşma çok kısaysa birleştir
        if min_seg_ms > 0 and len(ranges) > 1:
            merged = [ranges[0]]
            for r in ranges[1:]:
                gap_ms = (r["start"] - merged[-1]["end"]) * 1000
                if gap_ms < min_seg_ms:
                    merged[-1]["end"]      = r["end"]
                    merged[-1]["duration"] = round(merged[-1]["end"] - merged[-1]["start"], 3)
                else:
                    merged.append(r)
            ranges = merged

        return jsonify({
            "silence_ranges":   ranges,
            "total_duration":   round(dur_sec, 2),
            "count":            len(ranges),
            "pydub_available":  True
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─── Yardımcı: uzun segmenti max_chars'a göre böl ────────────────────────────

def split_long_segment(start, end, text, max_chars):
    words = text.split()
    if not words:
        return []

    lines, cur, cur_len = [], [], 0
    for w in words:
        need = len(w) + (1 if cur else 0)
        if cur and cur_len + need > max_chars:
            lines.append(" ".join(cur))
            cur, cur_len = [w], len(w)
        else:
            cur.append(w)
            cur_len += need
    if cur:
        lines.append(" ".join(cur))

    total_chars = sum(len(l) for l in lines) or 1
    total_dur   = end - start
    result, t   = [], start
    for line in lines:
        dur = total_dur * len(line) / total_chars
        result.append({"start": round(t, 3), "end": round(t + dur, 3), "text": line})
        t += dur
    return result


# ─── Yardımcı: kesimler uygulanmış audio oluştur ─────────────────────────────

def build_cut_audio(file_path, cuts_sec):
    """Orijinal dosyadan sessizlik bölgelerini çıkar, kesilmiş audio döndür."""
    audio    = AudioSegment.from_file(file_path)
    segments = []
    prev_ms  = 0

    for cut in sorted(cuts_sec, key=lambda x: x["start"]):
        cut_s = int(cut["start"] * 1000)
        cut_e = int(cut["end"]   * 1000)
        if cut_s > prev_ms:
            segments.append(audio[prev_ms:cut_s])
        prev_ms = cut_e

    if prev_ms < len(audio):
        segments.append(audio[prev_ms:])

    if not segments:
        return audio
    result = segments[0]
    for s in segments[1:]:
        result = result + s
    return result


# ─── Transcript: kesim uygulanmış audio + satır bölme ────────────────────────

@app.route("/transcribe/cut", methods=["POST"])
def transcribe_cut():
    """
    Timeline'ın mevcut halini (kesimler uygulanmış) transcribe eder.
    Timestamp'ler kesilmiş audio'ya göredir → doğrudan timeline ile eşleşir.

    Body: JSON
      - path: orijinal dosya yolu
      - cuts: [{start, end}, ...]  uygulanan sessizlik kesim aralıkları
      - word_timestamps: bool (default true)
      - max_line_chars: int   maksimum karakter/satır (default 42)
    """
    if not load_model():
        return jsonify({"error": "Whisper model yüklenemedi"}), 500

    data            = request.json or {}
    file_path       = data.get("path")
    cuts            = data.get("cuts", [])
    word_timestamps = data.get("word_timestamps", True)
    max_line_chars  = int(data.get("max_line_chars", 42))

    if not file_path or not os.path.exists(file_path):
        return jsonify({"error": f"Dosya bulunamadı: {file_path}"}), 400

    tmp_path = None
    try:
        # Kesimler varsa ve pydub mevcutsa kesilmiş audio oluştur
        if cuts and PYDUB_AVAILABLE:
            cut_audio = build_cut_audio(file_path, cuts)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name
            cut_audio.export(tmp_path, format="wav")
            transcript_path = tmp_path
        else:
            transcript_path = file_path

        segments_gen, info = model.transcribe(
            transcript_path,
            language="tr",
            beam_size=BEAM_SIZE,
            word_timestamps=word_timestamps,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=300, threshold=0.4)
        )

        result_segments, all_words = [], []

        for seg in segments_gen:
            text = seg.text.strip()
            if not text:
                continue

            # Kelime timestamp'lerini hazırla
            seg_words = []
            if word_timestamps and seg.words:
                seg_words = [
                    {"word": w.word.strip(), "start": round(w.start, 3),
                     "end": round(w.end, 3), "prob": round(w.probability, 3)}
                    for w in seg.words
                ]
                all_words.extend(seg_words)

            # Uzun segmentleri böl
            if len(text) > max_line_chars:
                for chunk in split_long_segment(seg.start, seg.end, text, max_line_chars):
                    result_segments.append(chunk)
            else:
                seg_data = {"start": round(seg.start, 3), "end": round(seg.end, 3), "text": text}
                if seg_words:
                    seg_data["words"] = seg_words
                result_segments.append(seg_data)

        return jsonify({
            "language": "tr",
            "duration": round(info.duration, 2),
            "segments": result_segments,
            "words":    all_words,
            "model":    MODEL_SIZE,
            "cut_applied": bool(cuts and PYDUB_AVAILABLE)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ─── Başlat ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print(" TR Altyazı — Whisper Server")
    print(f" Model: {MODEL_SIZE} | Device: {DEVICE}")
    print(" http://localhost:5123")
    print("=" * 50)

    # Model önceden yükle (arka planda yükle ki Flask sunucu hemen başlasın ve panel timeout vermesin)
    import threading
    model_loader = threading.Thread(target=load_model, daemon=True)
    model_loader.start()

    app.run(host="127.0.0.1", port=5123, debug=False)
