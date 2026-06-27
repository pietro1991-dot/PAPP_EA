#!/usr/bin/env python3
"""Mattone 2 — Caroselli/grafiche on-brand (HTML → PNG via Chrome headless).

Genera slide IG/FB (4:5, 1080x1350) col brand PHAI (navy + oro), testo perfetto,
zero AI, zero costo. Niente chiavi, niente pacchetti extra: serve solo Chrome.

Uso:
  python3 carousels.py                      # genera il carosello d'esempio
  python3 carousels.py mio.json             # genera da un file JSON di slide
JSON: {"slug":"nome","slides":[{"type":"cover|content|cta","eyebrow":"..","title":"..","body":".."}]}
"""
import os
import sys
import json
import subprocess
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "output")
W, H = 1080, 1350  # formato 4:5 Instagram

CHROME = shutil.which("google-chrome-stable") or shutil.which("google-chrome") or shutil.which("chromium")

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:%(W)dpx;height:%(H)dpx;overflow:hidden}
body{font-family:'Segoe UI',system-ui,-apple-system,Roboto,sans-serif;
 background:radial-gradient(900px 600px at 50%% -8%%,rgba(203,166,92,.16),transparent),#0a0e18;
 color:#e9ebf2;display:flex;flex-direction:column;justify-content:center;
 padding:96px 84px;position:relative}
.brand{position:absolute;top:54px;left:84px;display:flex;align-items:center;gap:12px;font-weight:800;letter-spacing:3px;font-size:26px}
.brand i{font-style:normal;color:#cba65c;font-size:13px;letter-spacing:4px}
.brand .mk{width:40px;height:40px;border:2px solid #cba65c;border-radius:9px;display:flex;align-items:center;justify-content:center;color:#cba65c;font-weight:800}
.eyebrow{color:#cba65c;font-weight:800;letter-spacing:3px;font-size:22px;text-transform:uppercase;margin-bottom:26px}
h1{font-size:74px;line-height:1.1;letter-spacing:-1px;font-weight:800}
h1 b{color:#cba65c}
.body{color:#aab2c5;font-size:36px;line-height:1.45;margin-top:28px}
.num{position:absolute;bottom:54px;right:84px;color:#3a4258;font-weight:800;font-size:30px}
.disc{position:absolute;bottom:54px;left:84px;color:#3a4258;font-size:20px;max-width:680px}
.cta-box{background:rgba(203,166,92,.12);border:2px solid #cba65c;border-radius:22px;padding:26px 34px;display:inline-block;margin-top:30px;color:#cba65c;font-weight:800;font-size:40px}
.cover h1{font-size:88px}
""" % {"W": W, "H": H}


def _html(slide, idx, total):
    t = slide.get("type", "content")
    eyebrow = slide.get("eyebrow", "")
    title = slide.get("title", "")
    body = slide.get("body", "")
    cls = "cover" if t == "cover" else ""
    inner = ""
    if eyebrow:
        inner += f'<div class="eyebrow">{eyebrow}</div>'
    inner += f"<h1>{title}</h1>"
    if body and t != "cta":
        inner += f'<div class="body">{body}</div>'
    if t == "cta":
        inner += f'<div class="cta-box">{body or "▶ Apri la Demo"}</div>'
    disc = '<div class="disc">Il trading comporta rischi. Nessun rendimento è garantito.</div>' if t in ("cover", "cta") else ""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head>
<body class="{cls}">
<div class="brand"><span class="mk">P</span>PHAI <i>TRADING</i></div>
{inner}
<div class="num">{idx}/{total}</div>
{disc}
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
            [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             f"--window-size={W},{H}", f"--screenshot={png_path}", "file://" + html_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        os.remove(html_path)
        print(f"  ✓ {png_path}")
    print(f"Carosello '{slug}': {total} slide in {outdir}")


# Carosello d'esempio: "12 domande prima di comprare un EA" (da POST_SOCIAL.md)
EXAMPLE = {
    "slug": "12-domande",
    "slides": [
        {"type": "cover", "eyebrow": "Guida", "title": "12 domande <b>PRIMA</b> di comprare un robot di trading"},
        {"type": "content", "title": "1. Ti mostrano lo storico <b>reale</b> o solo i mesi belli?"},
        {"type": "content", "title": "2. C'è la <b>validazione fuori campione</b> o backtest 'incollati'?"},
        {"type": "content", "title": "3. Ti spiegano <b>ogni operazione</b> o è una scatola nera?"},
        {"type": "content", "title": "4. Ti promettono guadagni?", "body": "🚩 Scappa. Il trading ha rischi, sempre."},
        {"type": "content", "title": "5. Puoi <b>provarlo</b> prima di pagare?"},
        {"type": "content", "title": "6. Vedi i <b>drawdown</b> e gli anni in perdita?"},
        {"type": "cta", "title": "PHAI risponde <b>sì</b> a tutte.", "body": "▶ Guarda la Demo"},
    ],
}

if __name__ == "__main__":
    if len(sys.argv) > 1:
        data = json.load(open(sys.argv[1], encoding="utf-8"))
    else:
        data = EXAMPLE
        print("(nessun file: genero il carosello d'esempio '12-domande')")
    render_carousel(data["slug"], data["slides"])
