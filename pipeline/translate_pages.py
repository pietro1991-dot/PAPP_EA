"""Traduce le PAGINE del sito (landing/squeeze/checkout) preservando HTML/CSS/JS.

Approccio robusto: con BeautifulSoup estrae SOLO i testi visibili (text node, <title>,
meta description, attributi alt/placeholder), li traduce a batch via LLM e li reinserisce.
Tag, classi, href, <style> e <script> restano identici → l'HTML non si rompe mai.

  python3 translate_pages.py landing en      # genera ../chat_bot/templates/landing.en.html
  python3 translate_pages.py squeeze fr
Variabili: OPENCODE_API_KEY, ZEN_BASE_URL, ZEN_MODEL (dal .env del chat_bot).
"""
import os
import re
import sys
import time
import httpx
from bs4 import BeautifulSoup, Comment, Doctype

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, "chat_bot", "templates")
ZEN_BASE = os.getenv("ZEN_BASE_URL", "https://opencode.ai/zen/v1")
MODEL = os.getenv("ZEN_MODEL", "mimo-v2.5-free")
KEY = os.getenv("OPENCODE_API_KEY")
LANGNAME = {"en": "English", "fr": "French (français)", "es": "Spanish (español)"}
_CJK = re.compile("[　-ヿ㐀-鿿豈-﫿＀-￯가-힯]")
HAS_LETTER = re.compile(r"[A-Za-zÀ-ÿ]{2,}")


def _strip_cjk(t):
    return _CJK.sub("", t)


def _llm(strings, lang):
    """Traduce una lista di stringhe; ritorna lista stessa lunghezza (fallback: originale)."""
    numbered = "\n".join(f"{i+1}» {s}" for i, s in enumerate(strings))
    sysmsg = (
        f"You are a professional marketing translator. Translate each numbered line into "
        f"{LANGNAME[lang]}, keeping a persuasive, natural tone. RULES: return EXACTLY the same "
        f"number of lines, each starting with 'N» ' (same numbering). Do NOT merge or split lines. "
        f"Keep placeholders like {{{{...}}}} and [Nome] and emojis unchanged. Translate only the text. "
        f"Return ONLY the numbered lines."
    )
    payload = {"model": MODEL, "messages": [{"role": "system", "content": sysmsg},
               {"role": "user", "content": numbered}], "max_tokens": 3000}
    try:
        r = httpx.post(f"{ZEN_BASE}/chat/completions",
                       headers={"Authorization": f"Bearer {KEY}"}, json=payload, timeout=60)
        out = r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print("   LLM err:", e); return strings
    res = {}
    for line in out.splitlines():
        m = re.match(r"\s*(\d+)»\s?(.*)", line)
        if m:
            res[int(m.group(1))] = _strip_cjk(m.group(2)).strip()
    return [res.get(i + 1, strings[i]) or strings[i] for i in range(len(strings))]


def translate_batched(strings, lang, batch=10):
    out = []
    for i in range(0, len(strings), batch):
        chunk = strings[i:i + batch]
        tr = _llm(chunk, lang)
        if len(tr) != len(chunk):       # conteggio sballato → tieni gli originali
            tr = chunk
        out.extend(tr)
        time.sleep(0.4)
    return out


def translate_page(name, lang):
    src = os.path.join(TPL, f"{name}.html")
    soup = BeautifulSoup(open(src, encoding="utf-8").read(), "html.parser")

    # raccogli i nodi/attributi traducibili
    nodes = []   # (kind, obj, original)
    for el in soup.find_all(string=True):
        if isinstance(el, (Comment, Doctype)) or el.parent.name in ("script", "style"):
            continue
        if HAS_LETTER.search(el):
            nodes.append(("text", el, str(el)))
    for tag in soup.find_all(attrs={"placeholder": True}):
        nodes.append(("attr-placeholder", tag, tag["placeholder"]))
    for tag in soup.find_all("meta", attrs={"name": "description"}):
        if tag.get("content"):
            nodes.append(("attr-content", tag, tag["content"]))

    originals = [n[2] for n in nodes]
    print(f"  {name}.{lang}: {len(originals)} stringhe da tradurre")
    translated = translate_batched(originals, lang)

    for (kind, obj, orig), tr in zip(nodes, translated):
        if kind == "text":
            lead = orig[:len(orig) - len(orig.lstrip())]   # preserva gli spazi attorno
            trail = orig[len(orig.rstrip()):]               # ai tag inline (<b>, <i>…)
            obj.replace_with(lead + tr.strip() + trail)
        elif kind == "attr-placeholder":
            obj["placeholder"] = tr
        elif kind == "attr-content":
            obj["content"] = tr
    if soup.html:
        soup.html["lang"] = lang

    dst = os.path.join(TPL, f"{name}.{lang}.html")
    open(dst, "w", encoding="utf-8").write(str(soup))
    print(f"  ✓ salvato {dst}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    translate_page(sys.argv[1], sys.argv[2])
