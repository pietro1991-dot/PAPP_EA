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

CHART_SVG = """<svg class="chart" viewBox="0 0 1080 420" preserveAspectRatio="none">
<defs><linearGradient id="ga" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#cba65c" stop-opacity=".20"/><stop offset="1" stop-color="#cba65c" stop-opacity="0"/></linearGradient></defs>
<path d="M0,350 L135,300 L270,330 L405,225 L540,260 L675,150 L810,185 L945,80 L1080,40 L1080,420 L0,420 Z" fill="url(#ga)"/>
<path d="M0,350 L135,300 L270,330 L405,225 L540,260 L675,150 L810,185 L945,80 L1080,40" fill="none" stroke="#cba65c" stroke-opacity=".5" stroke-width="3.5"/>
</svg>"""

FRAME_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@600;700;800&family=Inter:wght@400;500;600&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1920px;overflow:hidden}
body{font-family:'Inter',system-ui,sans-serif;color:#eef1f8;position:relative;
 background:
  radial-gradient(700px 560px at 50% 26%, rgba(203,166,92,.22), transparent 60%),
  radial-gradient(760px 620px at 12% 100%, rgba(46,86,160,.18), transparent 60%),
  linear-gradient(165deg,#0b1120 0%,#070b14 60%,#05080f 100%);
 display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:0 96px}
.grid{position:absolute;inset:0;background-image:
  linear-gradient(rgba(255,255,255,.03) 1px,transparent 1px),
  linear-gradient(90deg,rgba(255,255,255,.03) 1px,transparent 1px);
 background-size:72px 72px;mask-image:radial-gradient(circle at 50% 40%,#000 50%,transparent 88%)}
.chart{position:absolute;left:0;right:0;bottom:0;width:100%;height:420px}
.top{position:absolute;top:120px;left:0;right:0;display:flex;flex-direction:column;align-items:center;gap:26px}
.brand{display:flex;align-items:center;gap:14px;font-family:'Sora';font-weight:800;letter-spacing:3px;font-size:34px}
.brand i{font-style:normal;color:#cba65c;font-size:15px;letter-spacing:5px}
.brand .mk{width:52px;height:52px;border-radius:13px;display:flex;align-items:center;justify-content:center;font-size:30px;
 color:#0a0e18;background:linear-gradient(135deg,#e9c878,#cba65c);box-shadow:0 6px 22px rgba(203,166,92,.4)}
.prog{width:300px;height:7px;border-radius:7px;background:rgba(255,255,255,.10);overflow:hidden}
.prog>i{display:block;height:100%;border-radius:7px;background:linear-gradient(90deg,#f4d98c,#cba65c)}
.cap{position:relative;font-family:'Sora','Segoe UI',sans-serif;font-size:80px;line-height:1.18;font-weight:800;letter-spacing:-1px;
 background:linear-gradient(180deg,#ffffff,#cbd4e6);-webkit-background-clip:text;background-clip:text;color:transparent}
.cap b{background:linear-gradient(135deg,#f4d98c,#cba65c);-webkit-background-clip:text;background-clip:text;color:transparent}
.hook .cap{font-size:96px}
.cta-pill{position:relative;display:inline-block;font-family:'Sora';font-weight:800;font-size:62px;color:#0a0e18;
 background:linear-gradient(135deg,#f4d98c,#cba65c);padding:34px 52px;border-radius:24px;box-shadow:0 22px 60px rgba(203,166,92,.4);line-height:1.1}
.disc{position:absolute;bottom:150px;left:0;right:0;color:#566079;font-size:30px;padding:0 96px;font-weight:500}
"""


def _frame_html(text, kind, idx, total):
    pct = int(idx / max(1, total) * 100)
    cap = f'<div class="cta-pill">{text}</div>' if kind == "cta" else f'<div class="cap">{text}</div>'
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{FRAME_CSS}</style></head>
<body class="{kind}">
<div class="grid"></div>{CHART_SVG}
<div class="top"><div class="brand"><span class="mk">P</span>PHAI <i>TRADING</i></div><div class="prog"><i style="width:{pct}%"></i></div></div>
{cap}
<div class="disc">Il trading comporta rischi. Nessun rendimento è garantito.</div>
</body></html>"""


def _render_frame(text, kind, path, idx, total):
    html = path + ".html"
    open(html, "w", encoding="utf-8").write(_frame_html(text, kind, idx, total))
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                    "--virtual-time-budget=4000", f"--window-size={W},{H}", f"--screenshot={path}", "file://" + html],
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


# --- sfondo brand (senza caption: il testo è nei sottotitoli animati) ---
def _bg_html():
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{FRAME_CSS}</style></head>
<body><div class="grid"></div>{CHART_SVG}
<div class="top"><div class="brand"><span class="mk">P</span>PHAI <i>TRADING</i></div></div>
<div class="disc">Il trading comporta rischi. Nessun rendimento è garantito.</div></body></html>"""


def _render_bg(path):
    html = path + ".html"
    open(html, "w", encoding="utf-8").write(_bg_html())
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                    "--virtual-time-budget=4000", f"--window-size={W},{H}", f"--screenshot={path}", "file://" + html],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.remove(html)


# --- sottotitoli animati (ASS karaoke) dai word-timing di edge-tts ---
def _ass_t(t):
    cs = int(round(max(0, t) * 100)); h = cs // 360000; cs %= 360000
    m = cs // 6000; cs %= 6000; s = cs // 100; cs %= 100
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_esc(w):
    return w.replace("\\", "").replace("{", "").replace("}", "")


def build_ass(marks, path):
    head = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding\n"
        # PrimaryColour=oro (parola 'cantata'), SecondaryColour=bianco (prima)
        "Style: Cap,DejaVu Sans,92,&H005CA6CB,&H00FFFFFF,&H00140E08,&H64000000,-1,0,0,0,100,100,0,0,1,7,5,5,80,80,0,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    n = len(marks)

    def kdur(i):
        return (marks[i + 1]["start"] - marks[i]["start"]) if i + 1 < n else marks[i]["dur"]

    rows = []
    i = 0
    while i < n:
        chunk = []
        chars = 0
        while i < n and len(chunk) < 4 and chars < 20:
            chunk.append(i)
            chars += len(marks[i]["word"]) + 1
            brk = marks[i]["word"][-1:] in ".?!,;:"
            i += 1
            if brk:
                break
        start = marks[chunk[0]]["start"]
        end = marks[chunk[-1]]["start"] + max(0.05, kdur(chunk[-1]))
        text = "".join("{\\k%d}%s " % (max(1, round(kdur(g) * 100)), _ass_esc(marks[g]["word"])) for g in chunk).strip()
        rows.append(f"Dialogue: 0,{_ass_t(start)},{_ass_t(end)},Cap,,0,0,0,,{{\\pos(540,840)}}{text}")
    open(path, "w", encoding="utf-8").write(head + "\n".join(rows) + "\n")


def make_short(slug, lines, lang="it"):
    if not (CHROME and FFMPEG and FFPROBE):
        raise SystemExit("Servono Chrome + ffmpeg + ffprobe.")
    d = os.path.join(OUT, "short_" + slug)
    os.makedirs(d, exist_ok=True)
    vo_text = " ".join(l.replace("<b>", "").replace("</b>", "") for l in lines)
    voice = os.path.join(d, "voice.mp3")
    marks = voiceover.synth_marks(vo_text, voice, lang=lang)   # voce + timing per parola
    total = _audio_dur(voice) or (len(lines) * 2.5)
    ass = os.path.join(d, "subs.ass")
    build_ass(marks, ass)
    bg = os.path.join(d, "bg.png")
    _render_bg(bg)
    out = os.path.join(OUT, f"short_{slug}.mp4")
    subprocess.run([
        FFMPEG, "-y", "-loop", "1", "-i", bg, "-i", voice, "-t", f"{total:.2f}",
        "-vf", f"ass={ass},format=yuv420p", "-r", "30",
        "-c:v", "libx264", "-c:a", "aac", "-b:a", "128k", "-shortest", out
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"  ✓ short → {out}  ({total:.1f}s, {len(marks)} parole, sottotitoli animati)")
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
