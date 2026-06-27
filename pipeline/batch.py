#!/usr/bin/env python3
"""Genera in serie TUTTO il batch di lancio: short verticali + caroselli.
Keyless (edge-tts + Chrome + ffmpeg). Output in pipeline/output/.
Uso:  .venv/bin/python batch.py [it|en|fr|es]
"""
import sys
import carousels
import short

LANG = sys.argv[1] if len(sys.argv) > 1 else "it"

# --- 8 SHORT (angoli da VIDEO_SCRIPT.md). lines = caption a schermo = voce ---
SHORTS = [
    {"slug": "anti-truffa", "lines": [
        "I robot di trading su Instagram? Quasi tutti <b>finti</b>.",
        "Ti mostrano solo i profitti. Mai i drawdown, mai gli anni in perdita.",
        "Noi facciamo l'opposto: storico <b>reale</b>, anche quando il sistema ha perso.",
        "Un sistema che non perde mai non esiste.",
        "Guardalo dal vivo nella Demo. <b>Link in bio.</b>"]},
    {"slug": "out-of-sample", "lines": [
        "Come capire se un robot di trading è serio o fuffa?",
        "Una sola domanda: è validato <b>fuori campione</b>?",
        "Allenato fino a una data, testato su dati MAI visti dopo.",
        "Se sì, ha un metodo. Se no, crollerà.",
        "I pattern di PHAI passano questo test. <b>Demo in bio.</b>"]},
    {"slug": "rumore-d1", "lines": [
        "Smetti di guardare i grafici a 5 minuti.",
        "Il <b>90% è rumore</b>: ti porta a decisioni emotive.",
        "PHAI lavora sul giornaliero: pochi segnali, ma puliti.",
        "E li esegue una macchina, non le tue emozioni.",
        "Vedi com'è fatto. <b>Link in bio.</b>"]},
    {"slug": "pazienza", "lines": [
        "A volte il nostro sistema non fa <b>niente</b> per giorni.",
        "Ed è la cosa giusta.",
        "I conti esplodono quando si opera per noia.",
        "Durano quando si ha <b>pazienza</b>.",
        "Se cerchi serietà, non il brivido: <b>Demo in bio.</b>"]},
    {"slug": "app-ai", "lines": [
        "Così dovrebbe essere il trading automatico.",
        "Apro l'app e chiedo all'<b>assistente AI</b>: com'è il mio conto?",
        "Mi risponde nella mia lingua, spiegando ogni operazione.",
        "Niente più scatole nere.",
        "Provalo nella Demo. <b>Link in bio.</b>"]},
    {"slug": "confronto", "lines": [
        "EA da 30€ contro PHAI.",
        "L'EA da 30€: scatola nera, zero storico, ti arrangi.",
        "PHAI: ogni operazione <b>spiegata</b>, app, assistente AI, storico reale.",
        "Non paghi di più per un robot. Paghi per <b>capire</b>.",
        "Guarda la differenza. <b>Demo in bio.</b>"]},
    {"slug": "pattern-spenti", "lines": [
        "Abbiamo <b>spento</b> i pattern più redditizi del nostro sistema.",
        "Sembra una follia.",
        "Aggiungevano profitto, ma quasi tutto il drawdown.",
        "Far durare il conto vale più di un numero gonfiato.",
        "Le nostre scelte, spiegate nella <b>Demo</b>."]},
    {"slug": "storia", "lines": [
        "Ho perso soldi con robot di trading che non capivo.",
        "Quando perdevano, ero al buio.",
        "Così ne ho costruito uno che mostra <b>tutto</b>.",
        "Ogni operazione, lo storico vero, anche gli anni negativi.",
        "Se ti riconosci, guarda la Demo. <b>Link in bio.</b>"]},
]

# --- CAROSELLI ---
CAROUSELS = [
    carousels.EXAMPLE,  # 12-domande
    {"slug": "ea-vs-phai", "slides": [
        {"type": "cover", "eyebrow": "Confronto", "title": "EA da 30€ <b>vs</b> PHAI"},
        {"type": "content", "title": "EA da 30€", "body": "Scatola nera. Zero storico. Zero supporto. Ti arrangi."},
        {"type": "content", "title": "PHAI", "body": "Ogni operazione spiegata · App + assistente AI · Storico e backtest reali · Trasparenza totale."},
        {"type": "cta", "title": "Non paghi di più per un robot.", "body": "Paghi per CAPIRE — ▶ Demo"},
    ]},
]


def run():
    print(f"=== BATCH contenuti (lang={LANG}) ===")
    print(f"\n>> {len(CAROUSELS)} caroselli")
    for c in CAROUSELS:
        carousels.render_carousel(c["slug"], c["slides"])
    print(f"\n>> {len(SHORTS)} short")
    for s in SHORTS:
        try:
            short.make_short(s["slug"], s["lines"], LANG)
        except Exception as e:
            print(f"  ✗ {s['slug']}: {e}")
    print("\n=== FATTO. Output in pipeline/output/ ===")


if __name__ == "__main__":
    run()
