#!/usr/bin/env python3
"""Mattone 3 — Short verticale "faceless" (script → MP4 9:16).

Genera uno short on-brand SENZA chiavi: voce AI (edge-tts) + frame testuali brand
(HTML→Chrome) montati con ffmpeg. Lo sfondo b-roll da Pexels è un upgrade OPZIONALE
(serve PEXELS_API_KEY) — vedi pexels_clip().

Uso:
  .venv/bin/python short.py                 # genera lo short d'esempio
  .venv/bin/python short.py mio.json
JSON: {"slug":"nome","lang":"it","lines":["riga 1 (hook)","riga 2", ...]}
Le 'lines' sono sia i sottotitoli a schermo (un frame per riga) sia la voce (concatenata).
"""
import os
import sys
import json
import shutil
import subprocess

import voiceover  # mattone 1

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "output")
W, H = 1080, 1920
CHROME = shutil.which("google-chrome-stable") or shutil.which("google-chrome") or shutil.which("chromium")
FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

FRAME_CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:%(W)dpx;height:%(H)dpx;overflow:hidden}
body{font-family:'Segoe UI',system-ui,sans-serif;
 background:radial-gradient(800px 700px at 50%% 30%%,rgba(203,166,92,.18),transparent),#0a0e18;
 color:#e9ebf2;display:flex;flex-direction:column;justify-content:center;align-items:center;
 text-align:center;padding:120px 90px;position:relative}
.brand{position:absolute;top:80px;left:0;right:0;display:flex;justify-content:center;align-items:center;gap:12px;font-weight:800;letter-spacing:3px;font-size:30px}
.brand i{font-style:normal;color:#cba65c;font-size:14px;letter-spacing:4px}
.brand .mk{width:42px;height:42px;border:2px solid #cba65c;border-radius:9px;display:flex;align-items:center;justify-content:center;color:#cba65c}
.cap{font-size:72px;line-height:1.22;font-weight:800;letter-spacing:-.5px}
.cap b{color:#cba65c}
.hook .cap{font-size:86px}
.cta .cap{color:#cba65c}
.disc{position:absolute;bottom:120px;left:0;right:0;color:#5a6273;font-size:26px;padding:0 90px}
""" % {"W": W, "H": H}


def _frame_html(text, kind):
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{FRAME_CSS}</style></head>
<body class="{kind}">
<div class="brand"><span class="mk">P</span>PHAI <i>TRADING</i></div>
<div class="cap">{text}</div>
<div class="disc">Il trading comporta rischi. Nessun rendimento è garantito.</div>
</body></html>"""


def _render_frame(text, kind, path):
    html = path + ".html"
    open(html, "w", encoding="utf-8").write(_frame_html(text, kind))
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    f"--window-size={W},{H}", f"--screenshot={path}", "file://" + html],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.remove(html)


def _audio_dur(path):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", path], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def pexels_clip(query, out_path):
    """OPZIONALE: scarica un b-roll verticale da Pexels (serve PEXELS_API_KEY).
    Ritorna True se ok. Senza chiave → False (si usa lo sfondo brand)."""
    key = os.getenv("PEXELS_API_KEY")
    if not key:
        return False
    import urllib.request
    import json as _json
    req = urllib.request.Request(
        f"https://api.pexels.com/videos/search?query={urllib.parse.quote(query)}&orientation=portrait&per_page=5",
        headers={"Authorization": key})
    try:
        data = _json.load(urllib.request.urlopen(req, timeout=20))
        files = data["videos"][0]["video_files"]
        link = sorted([f for f in files if f.get("width", 0) >= 1080], key=lambda f: f["width"])[0]["link"]
        urllib.request.urlretrieve(link, out_path)
        return True
    except Exception as e:
        print("  (Pexels non disponibile:", e, ")")
        return False


def make_short(slug, lines, lang="it"):
    if not (CHROME and FFMPEG and FFPROBE):
        raise SystemExit("Servono Chrome + ffmpeg + ffprobe.")
    d = os.path.join(OUT, "short_" + slug)
    os.makedirs(d, exist_ok=True)

    # 1) Voce (concatena le righe)
    vo_text = " ".join(l.replace("<b>", "").replace("</b>", "") for l in lines)
    voice = os.path.join(d, "voice.mp3")
    voiceover.speak(vo_text, voice, lang=lang)
    total = _audio_dur(voice) or (len(lines) * 2.5)

    # 2) Frame per riga, durata pesata sulla lunghezza del testo
    weights = [max(8, len(l)) for l in lines]
    sw = sum(weights)
    durs = [max(1.4, total * w / sw) for w in weights]
    # riscala per combaciare con l'audio
    k = total / sum(durs)
    durs = [x * k for x in durs]

    frames_txt = os.path.join(d, "frames.txt")
    with open(frames_txt, "w") as ft:
        for i, (line, dur) in enumerate(zip(lines, durs)):
            kind = "hook" if i == 0 else ("cta" if i == len(lines) - 1 else "mid")
            png = os.path.join(d, f"f{i:02d}.png")
            _render_frame(line, kind, png)
            ft.write(f"file '{png}'\nduration {dur:.3f}\n")
        ft.write(f"file '{png}'\n")  # ultimo frame ripetuto (quirk concat)

    # 3) Sfondo b-roll Pexels (opzionale) o solo i frame brand
    out = os.path.join(OUT, f"short_{slug}.mp4")
    bg = os.path.join(d, "broll.mp4")
    has_broll = pexels_clip(lines[0][:40], bg)

    if has_broll:
        # b-roll sotto, frame brand (con trasparenza) sopra: per semplicità qui usiamo
        # i frame brand pieni; il b-roll resta come opzione avanzata (overlay) futura.
        pass

    subprocess.run([
        FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", frames_txt, "-i", voice,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-vf", f"scale={W}:{H},fps=30",
        "-c:a", "aac", "-b:a", "128k", "-shortest", out
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"  ✓ short → {out}  ({total:.1f}s, {len(lines)} frame)")
    return out


EXAMPLE = {
    "slug": "anti-truffa",
    "lang": "it",
    "lines": [
        "I robot di trading su Instagram? Quasi tutti <b>finti</b>.",
        "Ti mostrano solo i profitti. Mai i drawdown, mai gli anni in perdita.",
        "Noi facciamo l'opposto: storico <b>reale</b>, anche quando il sistema ha perso.",
        "Un sistema che non perde mai non esiste.",
        "Guardalo dal vivo nella Demo. <b>Link in bio.</b>",
    ],
}

if __name__ == "__main__":
    data = json.load(open(sys.argv[1], encoding="utf-8")) if len(sys.argv) > 1 else EXAMPLE
    if len(sys.argv) <= 1:
        print("(nessun file: genero lo short d'esempio 'anti-truffa')")
    make_short(data["slug"], data["lines"], data.get("lang", "it"))
