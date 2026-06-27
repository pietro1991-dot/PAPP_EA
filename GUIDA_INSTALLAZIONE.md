# Guida installazione — PaPP / PHAI

Due prodotti, due percorsi. Scegli in base al tuo piano.

---

## 🟢 Piano STARTER — Solo segnali (niente installazione)
Non installi nulla. Ricevi i segnali e li esegui a mano.

1. Vai su **http://77.81.226.151** (o il dominio PHAI) e **registrati** con la tua license key.
2. Sul telefono/PC, **attiva le notifiche** quando il sito le chiede (campanella).
3. Riceverai una notifica ad ogni segnale (es. *"SELL EURUSD @1.0850"*). Apri MT5/app del broker
   ed esegui l'ordine **manualmente**.

> Nessun PC acceso, nessuna VPS: il sistema gira da noi, tu ricevi e basta.

---

## 🔵 Piani PRO / ELITE — EA automatico (installazione)
L'EA trada da solo. Serve installarlo una volta e **tenerlo acceso 24/5**.

### Cosa ti serve
- MetaTrader 5 (dal tuo broker), un **conto** (demo o reale), la tua **license key**.
- I file: `PaPP_Median.ex5` (indicatore) e `EA_<SIMBOLO>.ex5` (es. `EA_EURUSD.ex5`).

### Passi
1. **Copia i file in MT5** (menu *File → Apri cartella dati*):
   - `PaPP_Median.ex5` → cartella `MQL5/Indicators/`
   - `EA_EURUSD.ex5` (o GBPUSD/USDCHF) → cartella `MQL5/Experts/`
   - Riavvia MT5 (o tasto destro sul Navigatore → *Aggiorna*).
2. **Autorizza il server PHAI**: *Strumenti → Opzioni → Expert Advisors* →
   spunta **"Consenti WebRequest"** e aggiungi `https://app.phai.io`.
3. **Apri un grafico del simbolo su timeframe D1** (es. EURUSD, D1).
4. **Trascina l'EA** `EA_EURUSD` sul grafico. Nei parametri imposta:
   - `InpUseServer = true`
   - `InpLicenseKey = "LA-TUA-KEY"`
   - `InpServerUrl = https://app.phai.io`
   - (Rischio e pattern arrivano dal server; puoi lasciarli di default.)
5. **Attiva AutoTrading** (pulsante in alto). Sul grafico deve comparire la **faccina sorridente**.
6. **Verifica licenza**: nella scheda *Esperti* deve apparire `PHAI: licenza valida`.
   Se vedi un errore WebRequest, rifai il punto 2.

### Tenerlo acceso 24/5 (senza tenere il PC sempre acceso)
- **VPS gratis del broker** (consigliato): molti broker la regalano se fai un minimo di
  volume/deposito. *Strumenti → Virtual Hosting* (oppure dal pannello del broker) → **Migra**
  l'EA. Da quel momento gira sul cloud del broker, **PC spento**.
- In alternativa: **MT5 Virtual Hosting** (~10-15€/mese da MetaQuotes), oppure tieni il PC acceso.
- **Non sai farlo?** Offriamo il **servizio di installazione** (a pagamento): lo configuriamo noi.

---

## Note
- **Un abbonamento attivo = EA/segnali attivi.** Se l'abbonamento scade, l'EA si ferma
  automaticamente (la licenza non è più valida).
- **Periodo di grazia**: se il nostro server è momentaneamente irraggiungibile, l'EA continua a
  operare con l'ultima configurazione valida (un nostro down non ti blocca). Si ferma solo se la
  licenza è davvero scaduta/revocata o dopo un lungo periodo senza contatto.
- **Sicurezza**: l'EA gira sul TUO conto, sul TUO terminale. Noi non tocchiamo i tuoi soldi:
  validiamo la licenza e (se attivo) riceviamo solo la telemetria delle operazioni per il chatbot.
