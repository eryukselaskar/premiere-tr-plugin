// hostscript.jsx — Premiere Pro ExtendScript API
// Tüm timeline ve sequence işlemleri burada çalışır

// ─── Yardımcı fonksiyonlar ───────────────────────────────────────────────────

function log(msg) {
  $.writeln("[TR-Subtitle] " + msg);
}

// ─── Caption / Altyazı Ekleme ────────────────────────────────────────────────

function addCaptionsToTimeline(captionsJson) {
  try {
    var captions = JSON.parse(captionsJson);
    if (!captions.length) return JSON.stringify({ error: "Altyazı listesi boş." });

    var seq = app.project.activeSequence;
    if (!seq) return JSON.stringify({ error: "Aktif sequence yok." });

    var srtContent = "";
    for (var i = 0; i < captions.length; i++) {
      var cap = captions[i];
      srtContent += (i + 1) + "\n";
      srtContent += formatSRTTime(cap.start) + " --> " + formatSRTTime(cap.end) + "\n";
      srtContent += cap.text + "\n\n";
    }

    var fname   = "tr_subs_" + (new Date().getTime()) + ".srt";
    var srtPath = Folder.temp.fsName + "\\" + fname;
    var f = new File(srtPath);
    f.open("w");
    f.encoding = "UTF-8";
    f.write(srtContent);
    f.close();

    var ok = app.project.importFiles([srtPath], true, app.project.rootItem, false);
    if (!ok) return JSON.stringify({ error: "Import başarısız.", srtPath: srtPath });

    var captionItem = null;
    var root = app.project.rootItem;
    for (var k = 0; k < root.children.numItems; k++) {
      if (root.children[k].name === fname) { captionItem = root.children[k]; break; }
    }

    if (!captionItem) {
      return JSON.stringify({
        success: true, added: captions.length,
        note: "SRT projeye eklendi — Project Panel'den sequence'e sürükleyin.",
        srtPath: srtPath
      });
    }

    var trackIdx = seq.videoTracks.numTracks - 1;
    seq.videoTracks[trackIdx].insertClip(captionItem, 0);

    return JSON.stringify({ success: true, added: captions.length });
  } catch(e) {
    return JSON.stringify({ error: e.message });
  }
}

// ─── Auto-Cut: Sessizlik Tespiti ─────────────────────────────────────────────

function secondsToQETimecode(seconds, timebase) {
  var fps = Math.round(254016000000 / parseFloat(timebase));
  var totalFrames = Math.round(seconds * fps);
  var h = Math.floor(totalFrames / (fps * 3600));
  var m = Math.floor((totalFrames % (fps * 3600)) / (fps * 60));
  var s = Math.floor((totalFrames % (fps * 60)) / fps);
  var f = totalFrames % fps;
  return pad(h) + ':' + pad(m) + ':' + pad(s) + ':' + pad(f);
}

// rangesJson: [ {start, end, duration}, ... ] — server tarafından hesaplanmış
function applySilenceCuts(rangesJson) {
  try {
    app.enableQE();
    var seq   = app.project.activeSequence;
    var qeSeq = qe.project.getActiveSequence();
    if (!seq || !qeSeq) return JSON.stringify({ error: "Aktif sequence yok." });

    var ranges = JSON.parse(rangesJson);
    if (!ranges.length) return JSON.stringify({ success: true, cutsApplied: 0 });

    var TICKS = 254016000000;
    var cutCount = 0;

    // Sondan başa işle — ripple önceki timecode'ları kaydırmaz
    for (var j = ranges.length - 1; j >= 0; j--) {
      var r       = ranges[j];
      var startTc = secondsToQETimecode(r.start, seq.timebase);
      var endTc   = secondsToQETimecode(r.end,   seq.timebase);

      qeSeq.razor(startTc);
      qeSeq.razor(endTc);

      var rStartTicks = Math.round(r.start * TICKS);
      var rEndTicks   = Math.round(r.end   * TICKS);

      // Video track'ler — ripple + linked items
      for (var v = 0; v < seq.videoTracks.numTracks; v++) {
        var vt = seq.videoTracks[v];
        for (var vc = vt.clips.numItems - 1; vc >= 0; vc--) {
          var vclip = vt.clips[vc];
          var cs = parseInt(vclip.start.ticks);
          var ce = parseInt(vclip.end.ticks);
          if (cs >= rStartTicks - TICKS * 0.1 && ce <= rEndTicks + TICKS * 0.1) {
            vclip.remove(true, true);
          }
        }
      }

      // Unlinked audio track'ler
      for (var a = 0; a < seq.audioTracks.numTracks; a++) {
        var at = seq.audioTracks[a];
        for (var ac = at.clips.numItems - 1; ac >= 0; ac--) {
          var aclip = at.clips[ac];
          var as2 = parseInt(aclip.start.ticks);
          var ae  = parseInt(aclip.end.ticks);
          if (as2 >= rStartTicks - TICKS * 0.1 && ae <= rEndTicks + TICKS * 0.1) {
            aclip.remove(true, false);
          }
        }
      }

      cutCount++;
    }

    return JSON.stringify({ success: true, cutsApplied: cutCount });
  } catch(e) {
    return JSON.stringify({ error: e.message });
  }
}

// ─── Sequence Yedeği ─────────────────────────────────────────────────────────

function backupSequence() {
  try {
    var seq = app.project.activeSequence;
    if (!seq) return JSON.stringify({ error: "Aktif sequence yok." });

    var ts   = new Date();
    var name = seq.name + " [Yedek " + pad(ts.getHours()) + ":" + pad(ts.getMinutes()) + ":" + pad(ts.getSeconds()) + "]";

    var dup  = seq.clone();
    dup.name = name;
    return JSON.stringify({ success: true, name: name });
  } catch(e) {
    return JSON.stringify({
      error: "Otomatik yedekleme desteklenmiyor.",
      hint:  "Project Panel'de sequence'e sağ tıklayıp 'Duplicate' seçin."
    });
  }
}

// ─── Sekansı SRT olarak dışa aktar ──────────────────────────────────────────

function exportSRT(captionsJson, outputPath) {
  try {
    var captions = JSON.parse(captionsJson);
    var srtContent = "";
    
    for (var i = 0; i < captions.length; i++) {
      var cap = captions[i];
      srtContent += (i + 1) + "\n";
      srtContent += formatSRTTime(cap.start) + " --> " + formatSRTTime(cap.end) + "\n";
      srtContent += cap.text + "\n\n";
    }

    var srtFile = new File(outputPath || (Folder.desktop.fsName + "/transcript.srt"));
    srtFile.open("w");
    srtFile.encoding = "UTF-8";
    srtFile.write(srtContent);
    srtFile.close();

    return JSON.stringify({ success: true, path: srtFile.fsName });
  } catch (e) {
    return JSON.stringify({ error: e.message });
  }
}

// ─── Timeline audio export (mevcut hali Whisper'a göndermek için) ────────────

function exportTimelineAudio() {
  try {
    var seq = app.project.activeSequence;
    if (!seq) return JSON.stringify({ error: "Aktif sequence yok." });

    var presetPath = findAudioPreset();
    if (!presetPath) {
      return JSON.stringify({ error: "Audio preset bulunamadı.", fallback: true });
    }

    // Preset adına göre uzantı belirle
    var ext  = ".wav";
    var plow = presetPath.toLowerCase();
    if (plow.indexOf("aac") !== -1) ext = ".m4a";
    else if (plow.indexOf("mp3") !== -1) ext = ".mp3";

    // Yolu backslash ile oluştur — karışık ayraç Python'da sorun çıkarır
    var outPath = Folder.temp.fsName.replace(/\//g, "\\") + "\\tr_tl_" + (new Date().getTime()) + ext;
    var outFile = new File(outPath);

    // exportAsMediaDirect asenkron çalışabilir — dönüş değeri güvenilir değil
    seq.exportAsMediaDirect(outPath, presetPath, 0);

    // Dosya oluşana dek bekle (maks 120s, 2s aralıkla)
    var waited = 0;
    while (!outFile.exists && waited < 120000) {
      $.sleep(2000);
      waited += 2000;
    }

    if (outFile.exists) return JSON.stringify({ success: true, path: outPath });
    return JSON.stringify({ error: "Export zaman aşımı (" + (waited/1000) + "s).", fallback: true });

  } catch(e) {
    return JSON.stringify({ error: e.message, fallback: true });
  }
}

function findAudioPreset() {
  var years = ["2026", "2025", "2024", "2023", "2022"];
  var knownSubs = [
    "\\MediaIO\\systempresets\\58444341_4d584641\\AAC Audio.epr",
    "\\MediaIO\\systempresets\\57415645_0000\\Waveform Audio.epr",
    "\\MediaIO\\systempresets\\4d504541_4d504541\\MP3.epr"
  ];

  // Önce bilinen preset yollarını dene
  for (var i = 0; i < years.length; i++) {
    var base = "C:\\Program Files\\Adobe\\Adobe Premiere Pro " + years[i];
    for (var j = 0; j < knownSubs.length; j++) {
      var f = new File(base + knownSubs[j]);
      if (f.exists) return f.fsName;
    }
  }

  // Bulunamazsa systempresets klasörünü tara
  for (var yi = 0; yi < years.length; yi++) {
    var presetsDir = new Folder(
      "C:\\Program Files\\Adobe\\Adobe Premiere Pro " + years[yi] + "\\MediaIO\\systempresets"
    );
    if (!presetsDir.exists) continue;
    var subs = presetsDir.getFiles();
    for (var si = 0; si < subs.length; si++) {
      if (!(subs[si] instanceof Folder)) continue;
      var eprs = subs[si].getFiles("*.epr");
      for (var ei = 0; ei < eprs.length; ei++) {
        var name = eprs[ei].name.toLowerCase();
        if (name.indexOf("audio") !== -1 || name.indexOf("aac") !== -1 || name.indexOf("wav") !== -1) {
          return eprs[ei].fsName;
        }
      }
    }
  }

  return null;
}

// ─── Timeline'dan medya yolu al ─────────────────────────────────────────────

function getFirstClipPath() {
  try {
    var seq = app.project.activeSequence;
    if (!seq) return JSON.stringify({ error: "Aktif sequence yok." });

    // Önce video track'lere bak
    for (var v = 0; v < seq.videoTracks.numTracks; v++) {
      var vtrack = seq.videoTracks[v];
      for (var vc = 0; vc < vtrack.clips.numItems; vc++) {
        var vclip = vtrack.clips[vc];
        if (vclip.projectItem) {
          var vpath = vclip.projectItem.getMediaPath();
          if (vpath) return JSON.stringify({ path: vpath, name: vclip.name });
        }
      }
    }

    // Sonra audio track'lere bak
    for (var a = 0; a < seq.audioTracks.numTracks; a++) {
      var atrack = seq.audioTracks[a];
      for (var ac = 0; ac < atrack.clips.numItems; ac++) {
        var aclip = atrack.clips[ac];
        if (aclip.projectItem) {
          var apath = aclip.projectItem.getMediaPath();
          if (apath) return JSON.stringify({ path: apath, name: aclip.name });
        }
      }
    }

    return JSON.stringify({ error: "Timeline'da medya bulunamadı. Bir klip ekle veya 'Harici Dosya' seçeneğini kullan." });
  } catch (e) {
    return JSON.stringify({ error: e.message });
  }
}

// ─── Sequence bilgisi al ─────────────────────────────────────────────────────

function getSequenceInfo() {
  try {
    var seq = app.project.activeSequence;
    if (!seq) return JSON.stringify({ error: "Aktif sequence yok." });

    var inPoint = seq.getInPoint ? seq.getInPoint() : 0;
    var outPoint = seq.getOutPoint ? seq.getOutPoint() : seq.end;

    return JSON.stringify({
      name: seq.name,
      duration: ticksToSeconds(seq.end, seq.timebase),
      frameRate: seq.timebase,
      videoTracks: seq.videoTracks.numTracks,
      audioTracks: seq.audioTracks.numTracks,
      inPoint: ticksToSeconds(inPoint, seq.timebase),
      outPoint: ticksToSeconds(outPoint, seq.timebase),
      projectPath: app.project.path
    });
  } catch (e) {
    return JSON.stringify({ error: e.message });
  }
}

// ─── Yardımcı: Zaman dönüşümleri ────────────────────────────────────────────

function secondsToTicks(seconds, timebase) {
  // Premiere tick = 1/254016000000 saniye
  var TICKS_PER_SECOND = 254016000000;
  return Math.round(seconds * TICKS_PER_SECOND);
}

function ticksToSeconds(ticks, timebase) {
  var TICKS_PER_SECOND = 254016000000;
  return ticks / TICKS_PER_SECOND;
}

function formatSRTTime(seconds) {
  var h = Math.floor(seconds / 3600);
  var m = Math.floor((seconds % 3600) / 60);
  var s = Math.floor(seconds % 60);
  var ms = Math.round((seconds % 1) * 1000);
  return pad(h) + ":" + pad(m) + ":" + pad(s) + "," + pad(ms, 3);
}

function pad(n, len) {
  var str = String(n);
  while (str.length < (len || 2)) str = "0" + str;
  return str;
}
