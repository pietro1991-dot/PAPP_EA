#!/usr/bin/env python3
"""Mattone 1 — Voce / speakerato (testo → MP3).

Provider:
  - "edge"  (default): edge-tts, gratis, nessuna chiave, voci IT/EN/FR/ES ottime.
            (Servizio Microsoft non ufficiale: ok per test/volumi; per uso commerciale
             intensivo valutare Piper, sotto.)
  - "piper" (commercial-safe): Piper TTS open-source self-host. Imposta PIPER_BIN e
            PIPER_MODEL (path al .onnx della voce). Gira su CPU.

Uso:
  python3 voiceover.py "Ciao, questo è PHAI." out.mp3
  python3 voiceover.py --file script.txt out.mp3 --voice it-IT-DiegoNeural
  VOICE_PROVIDER=piper PIPER_BIN=piper PIPER_MODEL=it_IT-paola-medium.onnx python3 voiceover.py "..." out.wav
"""
import os
import sys
import asyncio
import subprocess

PROVIDER = os.getenv("VOICE_PROVIDER", "edge")
# Voci edge-tts consigliate per lingua (cambia con --voice):
VOICES = {"it": "it-IT-DiegoNeural", "en": "en-US-AndrewNeural", "fr": "fr-FR-HenriNeural", "es": "es-ES-AlvaroNeural"}


async def _edge(text, out_path, voice):
    import edge_tts
    await edge_tts.Communicate(text, voice).save(out_path)


async def _edge_marks(text, out_path, voice):
    """Sintetizza e cattura i word boundary (timing per parola) da edge-tts.
    Ritorna [{'word','start','dur'}] in secondi. Niente Whisper: timing esatto."""
    import edge_tts
    marks = []
    with open(out_path, "wb") as f:
        async for ch in edge_tts.Communicate(text, voice, boundary="WordBoundary").stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                marks.append({"word": ch["text"], "start": ch["offset"] / 1e7, "dur": ch["duration"] / 1e7})
    return marks


def synth_marks(text, out_path, voice=None, lang="it"):
    """Genera l'audio E i tempi di ogni parola (solo edge-tts). Per i sottotitoli animati."""
    voice = voice or VOICES.get(lang, VOICES["it"])
    marks = asyncio.run(_edge_marks(text, out_path, voice))
    print(f"  ✓ voce+timing → {out_path}  ({len(marks)} parole, {voice})")
    return marks


def _piper(text, out_path):
    pbin = os.getenv("PIPER_BIN", "piper")
    model = os.getenv("PIPER_MODEL", "")
    if not model:
        raise SystemExit("PIPER_MODEL non impostato (path al .onnx della voce).")
    # piper legge il testo da stdin e scrive un wav
    p = subprocess.run([pbin, "--model", model, "--output_file", out_path],
                       input=text.encode("utf-8"))
    if p.returncode != 0:
        raise SystemExit("piper ha fallito.")


def speak(text, out_path, voice=None, lang="it"):
    voice = voice or VOICES.get(lang, VOICES["it"])
    if PROVIDER == "piper":
        _piper(text, out_path)
    else:
        asyncio.run(_edge(text, out_path, voice))
    print(f"  ✓ voce → {out_path}  ({PROVIDER}, {voice if PROVIDER=='edge' else 'piper'})")


def _parse_args(argv):
    text, out, voice, lang = None, None, None, "it"
    i = 0
    rest = []
    while i < len(argv):
        a = argv[i]
        if a == "--file":
            text = open(argv[i + 1], encoding="utf-8").read(); i += 2
        elif a == "--voice":
            voice = argv[i + 1]; i += 2
        elif a == "--lang":
            lang = argv[i + 1]; i += 2
        else:
            rest.append(a); i += 1
    if text is None and rest:
        text = rest.pop(0)
    if rest:
        out = rest.pop(0)
    return text, out or "voce.mp3", voice, lang


if __name__ == "__main__":
    text, out, voice, lang = _parse_args(sys.argv[1:])
    if not text:
        print(__doc__); sys.exit(1)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    speak(text, out, voice, lang)
