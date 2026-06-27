#!/usr/bin/env python3
"""Mattone 2 — Caroselli/grafiche on-brand PREMIUM (HTML → PNG via Chrome).

Slide IG 1080x1350 (4:5) con design curato: font moderni, sfondo a strati con
motivo chart, oro sfumato, chip, indicatori di pagina. Zero AI, testo perfetto,
nessuna chiave.

Uso:
  python3 carousels.py                      # carosello d'esempio
  python3 carousels.py mio.json
JSON: {"slug":"..","slides":[{"type":"cover|content|cta","eyebrow":"..","title":"..","body":".."}]}
"""
import os
import sys
import json
import subprocess
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "output")
W, H = 1080, 1350
CHROME = shutil.which("google-chrome-stable") or shutil.which("google-chrome") or shutil.which("chromium")

# Motivo "chart" di sfondo (linea + area), tenue, oro.
CHART_SVG = """<svg class="chart" viewBox="0 0 1080 360" preserveAspectRatio="none">
<defs><linearGradient id="ga" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#cba65c" stop-opacity=".22"/><stop offset="1" stop-color="#cba65c" stop-opacity="0"/></linearGradient></defs>
<path d="M0,300 L120,250 L240,275 L360,190 L480,215 L600,120 L720,150 L840,70 L960,95 L1080,30 L1080,360 L0,360 Z" fill="url(#ga)"/>
<path d="M0,300 L120,250 L240,275 L360,190 L480,215 L600,120 L720,150 L840,70 L960,95 L1080,30" fill="none" stroke="#cba65c" stroke-opacity=".55" stroke-width="3"/>
</svg>"""

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@600;700;800&family=Inter:wght@400;500;600&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1350px;overflow:hidden}
body{font-family:'Inter',system-ui,sans-serif;color:#eef1f8;position:relative;
 background:
  radial-gradient(640px 440px at 84% 8%, rgba(203,166,92,.20), transparent 60%),
  radial-gradient(720px 560px at 10% 100%, rgba(46,86,160,.20), transparent 60%),
  linear-gradient(160deg,#0b1120 0%,#070b14 60%,#05080f 100%);
 padding:92px 84px;display:flex;flex-direction:column}
.grid{position:absolute;inset:0;background-image:
  linear-gradient(rgba(255,255,255,.035) 1px,transparent 1px),
  linear-gradient(90deg,rgba(255,255,255,.035) 1px,transparent 1px);
 background-size:64px 64px;mask-image:radial-gradient(circle at 50% 40%,#000 55%,transparent 90%)}
.chart{position:absolute;left:0;right:0;bottom:0;width:100%;height:360px}
.glowline{position:absolute;top:0;left:84px;right:84px;height:3px;border-radius:3px;
 background:linear-gradient(90deg,transparent,#cba65c,transparent);opacity:.6}
.brand{position:relative;display:flex;align-items:center;gap:14px;font-family:'Sora';font-weight:800;letter-spacing:3px;font-size:27px}
.brand .mk{width:46px;height:46px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:26px;
 color:#0a0e18;background:linear-gradient(135deg,#e9c878,#cba65c);box-shadow:0 6px 22px rgba(203,166,92,.35)}
.brand i{font-style:normal;color:#cba65c;font-size:13px;letter-spacing:5px}
.content{position:relative;margin-top:auto;margin-bottom:auto}
.chip{display:inline-block;font-family:'Sora';font-weight:700;font-size:21px;letter-spacing:3px;text-transform:uppercase;
 color:#e9c878;padding:11px 22px;border:1.5px solid rgba(203,166,92,.45);border-radius:999px;
 background:rgba(203,166,92,.08);margin-bottom:34px}
h1{font-family:'Sora','Segoe UI',system-ui,sans-serif;font-weight:800;font-size:78px;line-height:1.08;letter-spacing:-1.5px;
 background:linear-gradient(180deg,#ffffff,#c7d0e2);-webkit-background-clip:text;background-clip:text;color:transparent}
h1 b{font-weight:800;background:linear-gradient(135deg,#f4d98c,#cba65c);-webkit-background-clip:text;background-clip:text;color:transparent}
.cover h1{font-size:96px}
.body{color:#9fb0c9;font-size:38px;line-height:1.5;margin-top:30px;font-weight:400;max-width:840px}
.body b{color:#eef1f8;font-weight:600}
.cta-pill{display:inline-flex;align-items:center;gap:16px;margin-top:38px;font-family:'Sora';font-weight:800;font-size:42px;
 color:#0a0e18;background:linear-gradient(135deg,#f4d98c,#cba65c);padding:24px 40px;border-radius:18px;
 box-shadow:0 18px 50px rgba(203,166,92,.35)}
.foot{position:relative;display:flex;align-items:center;justify-content:space-between;margin-top:auto}
.dots{display:flex;gap:10px}
.dot{width:12px;height:12px;border-radius:50%;background:#2a3450}
.dot.on{width:34px;background:linear-gradient(135deg,#f4d98c,#cba65c)}
.disc{color:#566079;font-size:21px;max-width:560px;text-align:right}
"""


def _html(slide, idx, total):
    t = slide.get("type", "content")
    eyebrow = slide.get("eyebrow", "")
    title = slide.get("title", "")
    body = slide.get("body", "")
    cls = "cover" if t == "cover" else ""
    inner = ""
    if eyebrow:
        inner += f'<div class="chip">{eyebrow}</div>'
    inner += f"<h1>{title}</h1>"
    if body and t != "cta":
        inner += f'<div class="body">{body}</div>'
    if t == "cta":
        inner += f'<div class="cta-pill">{body or "▶ Apri la Demo"}</div>'
    dots = "".join(f'<span class="dot {"on" if i==idx-1 else ""}"></span>' for i in range(total))
    disc = '<div class="disc">Il trading comporta rischi. Nessun rendimento è garantito.</div>' if t in ("cover", "cta") else f'<div class="disc">{idx}/{total}</div>'
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head>
<body class="{cls}">
<div class="grid"></div>{CHART_SVG}<div class="glowline"></div>
<div class="brand"><span class="mk">P</span>PHAI <i>TRADING</i></div>
<div class="content">{inner}</div>
<div class="foot"><div class="dots">{dots}</div>{disc}</div>
</body></html>"""


def render_carousel(slug, slides):
    if not CHROME:
        print("ERRORE: Chrome non trovato."); return
    outdir = os.path.join(OUT, slug)
    os.makedirs(outdir, exist_ok=True)
    total = len(slides)
    for i, slide in enumerate(slides, 1):
        html_path = os.path.join(outdir, f"slide_{i:02d}.html")
        png_path = os.path.join(outdir, f"slide_{i:02d}.png")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(_html(slide, i, total))
        subprocess.run(
            [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
             "--virtual-time-budget=4000",  # attende il caricamento dei Google Fonts
             f"--window-size={W},{H}", f"--screenshot={png_path}", "file://" + html_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        os.remove(html_path)
        print(f"  ✓ {png_path}")
    print(f"Carosello '{slug}': {total} slide in {outdir}")


# Copy più persuasivo (hook forti, specifici, emotivi).
EXAMPLE = {
    "slug": "12-domande",
    "slides": [
        {"type": "cover", "eyebrow": "Prima di pagare", "title": "12 domande che <b>smascherano</b> un robot-truffa"},
        {"type": "content", "title": "1. Ti mostrano lo storico <b>vero</b>…", "body": "…o solo gli screenshot dei mesi belli?"},
        {"type": "content", "title": "2. È validato <b>fuori campione</b>?", "body": "O è 'incollato' al passato e crollerà sul futuro?"},
        {"type": "content", "title": "3. Spiega <b>ogni operazione</b>?", "body": "O resti al buio quando perde?"},
        {"type": "content", "title": "4. Ti <b>promette</b> guadagni?", "body": "🚩 Allora scappa. Il trading ha sempre rischi."},
        {"type": "content", "title": "5. Puoi <b>provarlo</b> prima?", "body": "Senza pagare, senza carta?"},
        {"type": "content", "title": "6. Ti mostra anche i <b>drawdown</b>?", "body": "Chi nasconde le perdite ti vende un sogno."},
        {"type": "cta", "title": "PHAI risponde <b>sì</b> a tutte.", "body": "▶ Guardalo dal vivo"},
    ],
}

if __name__ == "__main__":
    data = json.load(open(sys.argv[1], encoding="utf-8")) if len(sys.argv) > 1 else EXAMPLE
    if len(sys.argv) <= 1:
        print("(nessun file: genero il carosello d'esempio)")
    render_carousel(data["slug"], data["slides"])
