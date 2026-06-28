"""Genera le email tradotte da email_campaign.json (IT) → email_campaign.<lang>.json.
Usa l'LLM (chat_logic.translate), preserva i segnaposto. Ri-eseguibile quando cambi l'IT.

  python3 translate_campaign.py en      # (o fr / es)
"""
import os
import re
import sys
import json
import asyncio

import chat_logic


def _norm(t):
    """Normalizza i segnaposto nome tradotti ([Name]/[Nom]/[Nombre]) → [Nome]."""
    return re.sub(r"\[(?:Name|Nom|Nombre|name)\]", "[Nome]", t or "")

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = json.load(open(os.path.join(BASE, "email_campaign.json"), encoding="utf-8"))


async def run(lang):
    out = []
    for e in SRC:
        combined = f"[SUBJECT]\n{e['subject']}\n[BODY]\n{e['body']}"
        tr = await chat_logic.translate(combined, lang)
        subj, body = e["subject"], e["body"]
        if tr and "[BODY]" in tr:
            head, _, b = tr.partition("[BODY]")
            subj = head.replace("[SUBJECT]", "").strip() or subj
            body = b.strip() or body
        elif tr:
            body = tr.strip()
        else:
            print(f"  ! {e['id']}: traduzione fallita, resto in IT")
        out.append({**e, "subject": _norm(subj), "body": _norm(body)})
        print(f"  ✓ {e['id']:24} → {subj[:46]}")
        await asyncio.sleep(0.4)
    p = os.path.join(BASE, f"email_campaign.{lang}.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Salvate {len(out)} email → {p}")


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1] if len(sys.argv) > 1 else "en"))
