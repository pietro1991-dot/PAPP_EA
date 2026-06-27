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
        "Hai comprato un robot di trading… e hai <b>perso</b>?",
        "Non è colpa tua. Te l'hanno venduto come una scatola nera.",
        "Zero storico, zero spiegazioni. Solo screenshot finti.",
        "Noi ti mostriamo <b>tutto</b>. Anche quando perdiamo.",
        "Smetti di fidarti alla cieca. <b>Guardalo dal vivo.</b>"]},
    {"slug": "out-of-sample", "lines": [
        "Il 90% dei robot di trading è una <b>fregatura</b>.",
        "Ecco la domanda che smaschera l'altro 10%:",
        "È testato su dati che <b>non ha mai visto</b>?",
        "Se no, ha funzionato solo sul passato. E crollerà.",
        "I nostri pattern passano il test. <b>Provalo.</b>"]},
    {"slug": "rumore-d1", "lines": [
        "Stai guardando il grafico <b>sbagliato</b>.",
        "Sui 5 minuti è quasi tutto rumore.",
        "Ansia, stop saltati, decisioni di pancia.",
        "Noi operiamo sul giornaliero: pochi colpi, ma <b>puliti</b>.",
        "E decide la macchina, non la paura. <b>Guarda.</b>"]},
    {"slug": "pazienza", "lines": [
        "Confessione: a volte non facciamo <b>nulla</b> per giorni.",
        "E i nostri clienti ne sono felici.",
        "I conti saltano quando operi per noia.",
        "Sopravvivono quando aspetti il momento <b>giusto</b>.",
        "Vuoi un sistema serio, non adrenalina? <b>Entra.</b>"]},
    {"slug": "app-ai", "lines": [
        "E se il tuo trading ti <b>parlasse</b>?",
        "Apro l'app e chiedo: «com'è il mio conto?»",
        "L'assistente AI risponde. Nella mia lingua. Subito.",
        "Ogni operazione spiegata. Zero scatole nere.",
        "Provalo tu stesso. <b>È gratis.</b>"]},
    {"slug": "confronto", "lines": [
        "EA da 30€ contro PHAI. Indovina la differenza.",
        "Quello da 30€: scatola nera, ti arrangi.",
        "PHAI: app, assistente AI, storico <b>reale</b>, ogni mossa spiegata.",
        "Non paghi per un robot. Paghi per <b>capire</b>.",
        "Vedi la differenza. <b>Demo gratis.</b>"]},
    {"slug": "pattern-spenti", "lines": [
        "Abbiamo <b>spento</b> i pattern che rendevano di più.",
        "Sì, hai letto bene.",
        "Rendevano… ma raddoppiavano il rischio di crollo.",
        "Far <b>durare</b> il tuo conto viene prima del numero grosso.",
        "Questa è la nostra ossessione. <b>Scoprila.</b>"]},
    {"slug": "storia", "lines": [
        "Ho perso i miei soldi con robot che non capivo.",
        "Al buio, mentre il conto scendeva.",
        "Così ne ho costruito uno che mostra <b>tutto</b>.",
        "Ogni trade, lo storico vero, anche le perdite.",
        "Se ci sei passato anche tu… <b>guarda qui.</b>"]},
]

# --- CAROSELLI ---
CAROUSELS = [
    carousels.EXAMPLE,  # 12-domande
    {"slug": "ea-vs-phai", "slides": [
        {"type": "cover", "eyebrow": "Il confronto", "title": "EA da 30€ <b>vs</b> PHAI"},
        {"type": "content", "title": "L'EA da <b>30€</b>", "body": "Scatola nera. Zero storico. Zero supporto. Quando perdi, ti arrangi."},
        {"type": "content", "title": "<b>PHAI</b>", "body": "Ogni mossa spiegata. App + assistente AI. Storico e backtest reali. Trasparenza totale."},
        {"type": "cta", "title": "Non paghi per un robot. Paghi per <b>capire</b>.", "body": "▶ Demo gratis"},
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
