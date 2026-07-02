#!/usr/bin/env python3
"""Campagna email PHAI — TUTTE le email, stile Sabri Suby, una per ogni passo.

Formato strutturato = già automatizzabile:
  - export_json()      → importi in un CRM (Brevo/MailerLite) per i drip automatici
  - render_markdown()  → versione leggibile per revisione
  - send(id, to)       → invio singolo via SMTP (per test) — usa SMTP_* env

3 sequenze (vedi marketing/16 e 07):
  nurture     : lead → cliente (trigger: opt-in)
  onboarding  : cliente → EA attivo (trigger: acquisto / nessun dato / primo dato)
  retention   : cliente → resta e sale (trigger: ricorrente / eventi)

Uso:
  python3 email_campaign.py list
  python3 email_campaign.py md         # genera marketing/contenuti/EMAIL_CAMPAIGN.md
  python3 email_campaign.py json       # genera output/email_campaign.json
  python3 email_campaign.py send nurture-1 tu@email.com
"""
import os
import sys
import json

# Placeholder da sostituire nel CRM: [Nome], {{demo}}, {{sblocca}}, {{report}}, {{guida}}, {{dfy}}, {{app}}
FOOTER = (
    "\n\n— Il team PHAI\n"
    "---\n"
    "Il trading comporta rischi: puoi perdere parte o tutto il capitale. Nessun rendimento "
    "è garantito. I dati citati sono backtest storici, non indicativi di risultati futuri.\n"
    "Non vuoi più ricevere queste email? Disiscriviti qui: {{unsubscribe}}"
)

# =====================================================================================
# SEQUENZA 1 — NURTURE (lead → cliente). Soap opera sequence: valore → storia → prove
# → pazienza → meccanismo → obiezioni → offerta. Trigger: opt-in (Demo/report/quiz).
# =====================================================================================
NURTURE = [
    dict(id="nurture-1", step=1, delay_days=0, trigger="opt-in",
         subject="Ecco il tuo accesso PHAI 👀 (e una cosa che nessuno ti dice)",
         preview="Apri questo prima di guardare qualsiasi cosa.",
         body=(
"Ciao [Nome],\n\n"
"eccolo: il tuo accesso a PHAI 👉 {{demo}}\n\n"
"Un consiglio prima che tu lo apra: cerca la parte su **perché abbiamo SPENTO i 4 "
"pattern più redditizi** del nostro sistema. Sembra una follia… finché non capisci la "
"lezione di rischio che c'è dietro.\n\n"
"Nei prossimi giorni ti racconto una cosa che il 90% dei 'guru' del trading non ti dirà "
"mai — perché smaschera come funziona davvero il loro business.\n\n"
"A domani.")),

    dict(id="nurture-2", step=2, delay_days=1, trigger="opt-in",
         subject="Perché ho smesso di fidarmi degli EA (e cosa ho fatto)",
         preview="Una storia veloce. Forse ti ci ritrovi.",
         body=(
"[Nome], una storia veloce.\n\n"
"Come tanti, ho comprato robot di trading che promettevano meraviglie. Erano scatole "
"nere: non sapevo cosa facevano, perché entravano, quando uscivano.\n\n"
"E quando perdevano, restavo al buio. Quello è il vero incubo: vedere il conto scendere "
"e non capire perché.\n\n"
"Così ho deciso di costruire l'opposto. Un sistema che mostra **tutto**: ogni operazione "
"spiegata, lo storico vero, perfino gli anni in perdita. E un'AI che risponde a ogni "
"domanda, nella tua lingua.\n\n"
"Domani ti spiego il concetto che separa una strategia vera da una 'incollata' al passato. "
"È la differenza tra un sistema serio e una fregatura.")),

    dict(id="nurture-3", step=3, delay_days=2, trigger="opt-in",
         subject="Il rumore che frega il 90% dei trader",
         preview="Stai guardando il grafico sbagliato.",
         body=(
"[Nome], la maggior parte guarda grafici a 5 minuti. Risultato? **Rumore puro**: "
"decisioni emotive, stop saltati, panico.\n\n"
"Noi lavoriamo sul **grafico giornaliero**. Pochi segnali, ma puliti. PHAI osserva gli "
"incroci tra il prezzo e 8 linee chiave: quando il prezzo le incrocia in un certo modo, "
"scatta un pattern.\n\n"
"Semplice da capire. Difficile da eseguire con disciplina — ed è per questo che lo fa una "
"macchina, non le tue emozioni.\n\n"
"Domani: la parte che nessuno ti mostra mai. Le perdite.")),

    dict(id="nurture-4", step=4, delay_days=3, trigger="opt-in",
         subject="Ti mostro anche gli anni in rosso",
         preview="Chiunque ti mostra solo i mesi belli. Io no.",
         body=(
"[Nome], chiunque ti fa vedere solo i mesi buoni. Io ti mostro tutto.\n\n"
"Nel nostro backtest su EURUSD 2010–2025 *(simulazione storica)* il sistema ha generato "
"783 operazioni con un win rate del 96,9%. Ma ha avuto anche **anni in perdita** (2017, "
"2023, 2025) e un drawdown massimo intorno al 20%.\n\n"
"Perché te lo dico? Perché **un sistema che non perde mai non esiste**, e chi te lo "
"racconta sta mentendo.\n\n"
"La differenza è che con PHAI vedi tutto in chiaro, dalla dashboard, in tempo reale. "
"Guarda lo storico coi tuoi occhi 👉 {{demo}}\n\n"
"Domani ti svelo una cosa contro-intuitiva sul nostro sistema.")),

    dict(id="nurture-5", step=5, delay_days=4, trigger="opt-in",
         subject="Perché a volte PHAI non fa NIENTE (ed è un bene)",
         preview="Confessione contro-intuitiva.",
         body=(
"[Nome], confessione: ci sono settimane in cui PHAI **non apre nessuna operazione**. "
"E va benissimo.\n\n"
"PHAI aspetta il setup giusto invece di forzare trade per 'fare qualcosa'. I trader "
"perdenti hanno bisogno di azione continua. I sistemi che durano hanno bisogno di "
"**pazienza**.\n\n"
"Ed ecco la parte migliore: tu non devi sopportare l'attesa con ansia. Apri l'app, vedi "
"cosa sta osservando il sistema, lo chiedi all'AI — e torni a vivere.\n\n"
"Se cerchi il brivido quotidiano, non siamo per te. Se vuoi un sistema serio che lavora "
"in silenzio, continua a leggere domani.")),

    dict(id="nurture-6", step=6, delay_days=5, trigger="opt-in",
         subject="Cosa fa PHAI mentre tu vivi la tua vita",
         preview="Una giornata tipo (e i piani).",
         body=(
"[Nome], ecco com'è una giornata con PHAI:\n\n"
"• L'EA monitora EURUSD, GBPUSD e USDCHF e apre/chiude secondo i pattern validati.\n"
"• Ogni mossa arriva sul tuo telefono con una notifica e una **spiegazione**.\n"
"• Apri l'app (in 4 lingue) e vedi conto, segnali, storico. Un dubbio? Lo chiedi "
"all'assistente AI, che risponde subito.\n\n"
"Niente più scatole nere. Niente più 'ma perché ha fatto così?'.\n\n"
"Puoi iniziare in 3 modi: **Demo gratis** (la vedi dal vivo), **Assistente + Segnali a 3€/mese** "
"o una **strategia da 5€/mese** (segnali e assistente sempre inclusi). Guardala prima tu 👉 {{demo}}\n\n"
"Domani rispondo alle 6 domande che ricevo più spesso.")),

    dict(id="nurture-7", step=7, delay_days=6, trigger="opt-in",
         subject="Ma funziona davvero? Le tue 6 domande",
         preview="Risposte oneste, senza giri di parole.",
         body=(
"[Nome], le 6 domande che ricevo sempre — risposte oneste:\n\n"
"1. **È una truffa?** No, e per questo mostriamo storico, drawdown e una Demo dal vivo. "
"La fuffa nasconde; noi mostriamo.\n"
"2. **Garantite guadagni?** No, e diffida di chi lo fa. Garantiamo il software: 30 giorni "
"soddisfatti o rimborsati.\n"
"3. **Non capisco di trading.** L'AI ti spiega tutto, semplice, nella tua lingua.\n"
"4. **E se perdo?** Profilo prudente, educazione sul rischio, tutto trasparente. Ma il "
"trading comporta perdite: investi solo ciò che puoi permetterti.\n"
"5. **È difficile installarlo?** C'è la guida da 5 minuti; oppure lo facciamo noi.\n"
"6. **Quanto costa?** Provi gratis con la Demo. Domani ti mostro l'offerta completa.")),

    dict(id="nurture-8", step=8, delay_days=7, trigger="opt-in",
         subject="Ci siamo: oggi sblocchi PHAI (prezzo di lancio).",
         preview="Ci siamo. Oggi puoi sbloccare PHAI.",
         body=(
"[Nome], ci siamo.\n\n"
"Oggi puoi sbloccare **PHAI** completo: l'EA su 3 coppie, l'app multilingua, il tuo "
"**assistente AI 24/7**, l'indicatore, storico e backtest, le notifiche — più 4 bonus "
"(oltre 900€ di valore).\n\n"
"Valore totale ~3.888€. Oggi: il **Pacchetto Completo a 12€/mese** (tutti e 5 gli EA + "
"assistente premium), oppure una **singola strategia da 5€** — segnali e assistente sempre "
"inclusi. Protetto dalla **Garanzia Sereno 30 giorni**: se non è all'altezza, rimborso "
"totale. Il rischio me lo prendo io.\n\n"
"È il **prezzo di lancio**: bloccalo ora e resta tuo finché non disdici. Ogni mese che "
"rimandi è un mese di segnali e operazioni che non ricevi.\n\n"
"👉 {{sblocca}}\n\n"
"Preferisci vedere prima? 👉 {{demo}}\n\n"
"P.S. Nel trading l'unica cosa che non ti hanno mai dato è la verità. Noi partiamo da lì.")),
]

# =====================================================================================
# SEQUENZA 2 — ONBOARDING / ATTIVAZIONE (cliente → EA attivo). Lo snodo critico.
# =====================================================================================
ONBOARDING = [
    dict(id="onboarding-1", step=1, delay_days=0, trigger="acquisto",
         subject="Benvenuto in PHAI 🎉 (la tua licenza + 5 minuti)",
         preview="Tutto pronto. Ecco il primo passo.",
         body=(
"Benvenuto in PHAI, [Nome]! 🎉\n\n"
"La tua **License Key**: {{license_key}}\n\n"
"Ora un solo passo: **installa PHAI** (ci vogliono ~5 minuti). La guida passo-passo, "
"con screenshot, è qui 👉 {{guida}}\n\n"
"Lo step che blocca tutti è autorizzare l'indirizzo PHAI in MetaTrader: te lo spiego con "
"immagini, è questione di 30 secondi.\n\n"
"Non vuoi farlo da solo? Lo configuriamo noi 👉 {{dfy}}\n\n"
"Rispondi a questa email se ti serve una mano: ti aiuto io.")),

    dict(id="onboarding-2", step=2, delay_days=1, trigger="nessun_dato_24h",
         subject="Hai installato PHAI? (ti aiuto in 5 minuti)",
         preview="Vedo che il tuo conto non sta ancora inviando dati.",
         body=(
"[Nome], vedo che PHAI non sta ancora ricevendo dati dal tuo conto — nessun problema, "
"capita. Due strade:\n\n"
"1) **Fai da te in 5 minuti**: guida con screenshot 👉 {{guida}}. Lo step che ferma "
"tutti è autorizzare l'indirizzo PHAI in MetaTrader (Strumenti → Opzioni → Expert "
"Advisors).\n"
"2) **Lo facciamo noi**: con PHAI Fatto-Per-Te configuriamo broker, server e "
"installazione. Tu non tocchi niente 👉 {{dfy}}\n\n"
"Rispondi a questa email e ti do una mano di persona. Voglio vederti operativo.")),

    dict(id="onboarding-3", step=3, delay_days=0, trigger="primo_dato",
         subject="🎉 PHAI è attivo sul tuo conto",
         preview="Ci siamo: ora lavora per te.",
         body=(
"[Nome], ci siamo: PHAI sta monitorando il tuo conto. ✅\n\n"
"Da ora, ogni mossa arriva sul tuo telefono **con la spiegazione**, e puoi chiedere "
"qualsiasi cosa all'assistente AI.\n\n"
"Immagina la prossima volta che sei a cena: PHAI lavora, e se apre o chiude lo sai "
"subito, col perché. Niente più ansia da grafico.\n\n"
"Apri l'app e fai la tua prima domanda all'AI: «come sta il mio conto?» 👉 {{app}}")),

    dict(id="onboarding-4", step=4, delay_days=3, trigger="primo_dato",
         subject="3 cose che forse non sai fare con PHAI",
         preview="Piccoli trucchi, grande comodità.",
         body=(
"[Nome], 3 cose che rendono PHAI ancora più tuo:\n\n"
"1. **Cambia lingua** con un tocco (IT/EN/FR/ES): l'AI risponde nella lingua scelta.\n"
"2. **Attiva le notifiche push**: sai di ogni apertura/chiusura anche ad app chiusa.\n"
"3. **Apri lo Storico**: ogni operazione, anno per anno, con il perché.\n\n"
"E ricorda: quando il mercato è fermo e PHAI aspetta, è normale. Apri l'app e chiedi "
"all'AI cosa sta osservando 👉 {{app}}")),

    dict(id="onboarding-5", step=5, delay_days=7, trigger="primo_dato",
         subject="Aspettati pazienza (è la cosa giusta)",
         preview="Una settimana con PHAI: cosa è normale.",
         body=(
"[Nome], una settimana con PHAI. Mettiamo le aspettative giuste:\n\n"
"Ci saranno **giorni, a volte settimane, senza operazioni**. Non è un guasto: è il "
"sistema che aspetta il setup giusto invece di forzare.\n\n"
"I conti saltano quando si opera per noia. Durano quando si ha pazienza. Tu nel frattempo "
"hai PHAI che sorveglia 3 mercati 24/7 al posto tuo.\n\n"
"Dubbi su cosa sta succedendo? L'assistente AI te lo spiega in ogni momento 👉 {{app}}")),

    dict(id="onboarding-6", step=6, delay_days=14, trigger="primo_dato",
         subject="Come va con PHAI? (e un promemoria)",
         preview="Due settimane insieme.",
         body=(
"[Nome], siamo a due settimane. Come ti trovi?\n\n"
"Rispondi a questa email anche solo con una parola: voglio sapere com'è la tua esperienza "
"e migliorarla.\n\n"
"E un promemoria sereno: sei coperto dalla **Garanzia Sereno 30 giorni**. Sei qui per "
"provare con calma, senza pressione. Il mio compito è che PHAI ti sia davvero utile.\n\n"
"Una domanda all'AI che non hai ancora fatto? Provala 👉 {{app}}")),
]

# =====================================================================================
# SEQUENZA 3 — RETENTION / LIFECYCLE (cliente → resta e sale). Trigger vari/eventi.
# =====================================================================================
RETENTION = [
    dict(id="retention-weekly", step=1, delay_days=7, trigger="ricorrente_settimanale",
         subject="Il polso del mercato PHAI 📊",
         preview="Cosa sta osservando il sistema questa settimana.",
         body=(
"[Nome], il polso di questa settimana 📊\n\n"
"Ecco cosa sta osservando PHAI sui tuoi mercati e le operazioni (se ce ne sono state), "
"ognuna con il suo perché. Apri il riepilogo 👉 {{app}}\n\n"
"Vuoi capire una mossa nel dettaglio? Chiedilo all'assistente AI: c'è sempre, 24/7.")),

    dict(id="retention-win", step=2, delay_days=0, trigger="trade_chiuso_profit",
         subject="Com'è andata l'ultima operazione (e perché)",
         preview="Trasparenza, anche sulle vittorie.",
         body=(
"[Nome], PHAI ha appena chiuso un'operazione in profitto.\n\n"
"Ma più del risultato conta il **perché**: il pattern, l'ingresso, l'uscita. Lo trovi "
"spiegato nella tua dashboard 👉 {{app}}\n\n"
"È così che si costruisce fiducia: non con un numero, ma capendo ogni mossa.")),

    dict(id="retention-flat", step=3, delay_days=0, trigger="mese_piatto",
         subject="Questo mese PHAI ha aspettato. Ecco perché è un bene.",
         preview="La disciplina che stai pagando.",
         body=(
"[Nome], questo mese il sistema non ha trovato setup all'altezza dei suoi criteri, e "
"**non ha forzato nessun trade**.\n\n"
"So che la tentazione è pensare 'e allora perché pago?'. Ribalto la prospettiva: stai "
"pagando proprio per **questa disciplina**.\n\n"
"I conti esplodono quando si opera per noia; durano quando si aspetta il momento giusto. "
"Nel frattempo PHAI ha sorvegliato 3 mercati 24/7 per te.\n\n"
"Ecco cosa sta osservando ora 👉 {{app}}")),

    dict(id="retention-monthly", step=4, delay_days=30, trigger="ricorrente_mensile",
         subject="Il tuo mese in PHAI",
         preview="Riepilogo + un insight dall'AI.",
         body=(
"[Nome], ecco il tuo mese in PHAI: il riepilogo del conto e delle operazioni, con un "
"insight dall'assistente AI su come stanno i tuoi mercati 👉 {{app}}\n\n"
"Una domanda che vuoi fare al sistema questo mese? È lì che ti aspetta.")),

    dict(id="retention-upsell-pro", step=5, delay_days=0, trigger="starter_limite_coppie",
         subject="Sblocca le altre 2 coppie (passa a Pro)",
         preview="Stai usando 1 coppia su 3.",
         body=(
"[Nome], col piano Starter PHAI opera su **1 coppia**. Ma il sistema è validato anche su "
"**GBPUSD** e **USDCHF**.\n\n"
"Con **Pro** sblocchi tutte e 3 le coppie + l'assistente AI completo + priorità. Più "
"mercati sorvegliati, più opportunità colte — senza alzare un dito.\n\n"
"Passa a Pro 👉 {{sblocca}}")),

    dict(id="retention-upsell-annual", step=6, delay_days=90, trigger="pro_attivo_3mesi",
         subject="Vuoi 2 mesi gratis?",
         preview="Un'idea per chi resta.",
         body=(
"[Nome], sei con noi da qualche mese — grazie. 🙏\n\n"
"Se PHAI fa parte della tua routine, col piano **Annuale** ottieni **2 mesi gratis** "
"rispetto al mensile. Stesso Pro, meno spesa, e niente da ricordare ogni mese.\n\n"
"Passa all'Annuale 👉 {{sblocca}}")),

    dict(id="retention-elite", step=7, delay_days=0, trigger="heavy_user_ai",
         subject="Per chi usa molto l'assistente: PHAI Elite",
         preview="AI premium, priorità, pattern in anteprima.",
         body=(
"[Nome], usi spesso l'assistente AI — bene, è fatto per questo.\n\n"
"Se vuoi il massimo, **PHAI Elite** ti dà un'**AI più potente e prioritaria** (nessuna "
"coda nei picchi) e i **nuovi pattern in anteprima**.\n\n"
"Scopri Elite 👉 {{sblocca}}")),

    dict(id="retention-winback", step=8, delay_days=0, trigger="pre_disdetta_o_carta_fallita",
         subject="Prima che tu vada…",
         preview="Una proposta, e una domanda.",
         body=(
"[Nome], vedo che stai per lasciare PHAI (o c'è stato un problema col pagamento).\n\n"
"Prima di salutarci: che cosa non ha funzionato per te? Rispondi a questa email — mi "
"aiuti davvero a migliorare.\n\n"
"E se vuoi dargli un'altra possibilità, ti offro **1 mese a metà prezzo** per "
"rivalutare con calma 👉 {{sblocca}}\n\n"
"In ogni caso, grazie per aver provato PHAI.")),

    dict(id="retention-referral", step=9, delay_days=0, trigger="cliente_soddisfatto",
         subject="Porta un amico, un mese gratis a entrambi 🎁",
         preview="Il modo migliore per dire grazie.",
         body=(
"[Nome], se PHAI ti è utile, probabilmente conosci qualcuno stanco delle scatole nere "
"come lo eri tu.\n\n"
"Invitalo con il tuo link: quando entra, **un mese gratis a entrambi** 🎁\n\n"
"Il tuo link invito 👉 {{referral}}\n\n"
"Grazie per far crescere PHAI con le persone giuste.")),
]

# Per chi NON compra dopo la nurture: re-engagement (poi newsletter di valore).
POSTSEQ = [
    dict(id="post-1", step=1, delay_days=9, trigger="no_acquisto",
         subject="L'hai vista la Demo? (2 minuti)",
         preview="Nessuna pressione, solo curiosità.",
         body=(
"[Nome], non ti scrivo per vendere. Ti scrivo per chiederti: l'hai aperta la Demo? "
"È lì, gratis, senza registrazione 👉 {{demo}}\n\n"
"Guardala 2 minuti. Se non fa per te, nessun problema — continuerò a mandarti solo "
"cose utili sul trading trasparente.")),

    dict(id="post-2", step=2, delay_days=13, trigger="no_acquisto",
         subject="Ogni settimana di attesa è tempo perso",
         preview="Parti da 5€/mese, disdici quando vuoi.",
         body=(
"[Nome], non c'è nessun conto alla rovescia — ma ogni settimana che rimandi è una "
"settimana di segnali e operazioni che non ricevi.\n\n"
"Puoi partire da pochissimo: **una strategia a 5€/mese** o **Assistente + Segnali a 3€** "
"(segnali e assistente sempre inclusi), col rischio tutto dalla mia parte "
"(garanzia 30 giorni) 👉 {{sblocca}}\n\n"
"Preferisci ancora solo guardare? 👉 {{demo}}")),
]

CAMPAIGN = {"nurture": NURTURE, "onboarding": ONBOARDING, "retention": RETENTION, "postseq": POSTSEQ}


def _all():
    out = []
    for seq, items in CAMPAIGN.items():
        for e in items:
            out.append({"sequence": seq, **e, "body": e["body"] + FOOTER})
    return out


def export_json(path):
    json.dump(_all(), open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"  ✓ {len(_all())} email → {path}")


def render_markdown(path):
    L = ["# Campagna email PHAI — copy completo (stile Sabri Suby)\n",
         "Generato da `pipeline/email_campaign.py`. 3 sequenze, ogni email pronta per il CRM.",
         "Placeholder: `[Nome]`, `{{demo}}`, `{{sblocca}}`, `{{report}}`, `{{guida}}`, `{{dfy}}`, "
         "`{{app}}`, `{{license_key}}`, `{{referral}}`, `{{unsubscribe}}`.\n"]
    titles = {"nurture": "Sequenza 1 — NURTURE (lead → cliente)",
              "onboarding": "Sequenza 2 — ONBOARDING / ATTIVAZIONE (cliente → EA attivo)",
              "retention": "Sequenza 3 — RETENTION / LIFECYCLE (cliente → resta e sale)",
              "postseq": "Coda — chi NON compra (re-engagement)"}
    for seq, items in CAMPAIGN.items():
        L.append(f"\n---\n## {titles[seq]}\n")
        L.append("| # | Trigger | Ritardo | Oggetto |\n|---|---|---|---|")
        for e in items:
            L.append(f"| {e['step']} | {e['trigger']} | +{e['delay_days']}g | {e['subject']} |")
        for e in items:
            L.append(f"\n### {e['id']} — {e['subject']}")
            L.append(f"*Trigger: {e['trigger']} · invio: +{e['delay_days']} giorni · preview: {e['preview']}*\n")
            L.append("> " + (e["body"] + FOOTER).replace("\n", "\n> "))
    open(path, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"  ✓ {len(_all())} email → {path}")


def send(email_id, to_addr):
    """Invio singolo via SMTP (per test). Usa SMTP_HOST/PORT/USER/PASS/FROM."""
    import smtplib, ssl
    from email.message import EmailMessage
    e = next((x for x in _all() if x["id"] == email_id), None)
    if not e:
        print("Email id non trovato:", email_id); return
    host = os.getenv("SMTP_HOST")
    if not host:
        print("SMTP non configurato (SMTP_HOST). Email NON inviata."); return
    msg = EmailMessage()
    msg["From"] = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "no-reply@phai.io"))
    msg["To"] = to_addr
    msg["Subject"] = e["subject"]
    msg.set_content(e["body"].replace("[Nome]", "").replace("{{", "[").replace("}}", "]"))
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=15) as s:
        if os.getenv("SMTP_TLS", "1") == "1":
            s.starttls(context=ssl.create_default_context())
        if os.getenv("SMTP_USER"):
            s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS", ""))
        s.send_message(msg)
    print(f"  ✓ inviata '{email_id}' a {to_addr}")


if __name__ == "__main__":
    BASE = os.path.dirname(os.path.abspath(__file__))
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        for e in _all():
            print(f"  {e['id']:24} +{e['delay_days']:>2}g  {e['subject']}")
        print(f"\nTotale: {len(_all())} email in {len(CAMPAIGN)} sequenze.")
    elif cmd == "json":
        os.makedirs(os.path.join(BASE, "output"), exist_ok=True)
        export_json(os.path.join(BASE, "output", "email_campaign.json"))
    elif cmd == "md":
        render_markdown(os.path.join(BASE, "..", "marketing", "contenuti", "EMAIL_CAMPAIGN.md"))
    elif cmd == "send" and len(sys.argv) >= 4:
        send(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)
