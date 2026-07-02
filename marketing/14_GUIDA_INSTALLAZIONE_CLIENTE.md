# 14 · Guida installazione cliente — PHAI in 5 minuti

> Questa è la guida che riceve il cliente dopo l'acquisto. Linguaggio semplice,
> passi numerati, zero gergo. Da impaginare con screenshot prima della pubblicazione.

---

# 🚀 Benvenuto in PHAI Trading

Per attivare PHAI sul tuo conto bastano **5 minuti**. Segui i passi in ordine.
Non sei tecnico? Salta tutto: scegli **"Fatto-Per-Te"** e lo configuriamo noi. 👇

---

## ✅ Passo 1 — Crea il tuo account PHAI *(1 minuto)*
1. Vai su **[il tuo indirizzo PHAI]** *(es. https://app.phai.io)*.
2. Clicca **Registrati**.
3. Inserisci **email**, una **password** e la tua **License Key**
   (è nell'email d'acquisto, tipo `XXXXX-XXXXX-XXXXX-XXXXX`).
4. Fatto: ora hai la tua dashboard. **Tienila aperta**, la useremo alla fine.

> ⚠️ Importante: registra l'account **prima** di installare l'EA. Così i tuoi dati
> finiscono subito nella tua dashboard.

---

## ✅ Passo 2 — Installa MetaTrader 5 *(salta se ce l'hai già)*
1. Scarica MetaTrader 5 dal sito del tuo broker e installalo.
2. Accedi con i dati del **tuo conto** (login, password, server del broker).

> Non hai un conto? Te ne consigliamo uno compatibile nell'email. Il conto è
> **tuo**: i soldi restano sul tuo conto, noi non li tocchiamo mai.

---

## ✅ Passo 3 — Aggiungi PHAI a MetaTrader *(2 minuti)*
Ti abbiamo inviato 2 file: **`PHAI_EA.ex5`** e **`PHAI_Median.ex5`**.

1. In MetaTrader: menu **File → Apri cartella dati**.
2. Apri la cartella **MQL5**.
3. Copia **`PHAI_Median.ex5`** dentro la cartella **Indicators**.
4. Copia **`PHAI_EA.ex5`** dentro la cartella **Experts**.
5. Chiudi e riapri MetaTrader (oppure: tasto destro su "Expert Advisors" →
   **Aggiorna**).

---

## ✅ Passo 4 — Autorizza PHAI a comunicare *(30 secondi, una volta sola)*
MetaTrader, per sicurezza, chiede il permesso di contattare il nostro server.
1. Menu **Strumenti → Opzioni → Expert Advisors**.
2. Spunta **"Consenti WebRequest per i seguenti URL"**.
3. Clicca **Aggiungi** e incolla **esattamente** questo indirizzo:

   ```
   https://app.phai.io
   ```
   *(usa l'indirizzo PHAI che trovi nell'email; deve essere identico)*
4. Clicca **OK**.

> Se salti questo passo, l'EA ti avviserà con un messaggio che ti dice cosa fare.

---

## ✅ Passo 5 — Avvia PHAI sul grafico *(1 minuto)*
1. In alto in MetaTrader apri un grafico **EURUSD**.
2. Dalla finestra **Navigatore** (a sinistra), trascina **PHAI_EA** sul grafico.
3. Nella finestra che si apre, scheda **Comune**: spunta
   **"Consenti trading algoritmico"**.
4. Scheda **Parametri di Input**, imposta solo questi 3:
   - **InpUseServer** → `true`
   - **InpLicenseKey** → incolla la **tua License Key**
   - **InpServerUrl** → l'indirizzo PHAI (lo stesso del Passo 4)
   *(tutto il resto è già impostato correttamente: non toccare nient'altro)*
5. Clicca **OK**. In alto a destra del grafico deve comparire **PHAI con una
   faccina sorridente** 🙂 e il pulsante **"Trading algoritmico"** verde.

> Vuoi anche GBPUSD e USDCHF? Ripeti il Passo 5 su un grafico di quel simbolo con
> il file corrispondente. Puoi anche **iniziare solo con EURUSD** e aggiungerli dopo.

---

## ✅ Passo 6 — Non tenere il PC acceso *(consigliato, 1 click)*
Perché PHAI lavori **24 ore su 24 anche a PC spento**, usa il server virtuale di
MetaTrader (lo paghi a MetaTrader, ~10-15 $/mese):
1. Nella finestra **Navigatore**, tasto destro sul **tuo conto** →
   **"Affitta un server virtuale"**.
2. Segui la procedura guidata e scegli **"Migra"** (sposta PHAI sul server).
3. Da ora MetaTrader può restare chiuso: PHAI gira sul server. ✅

---

## ✅ Passo 7 — Guarda il tuo conto nell'app
Apri la tua dashboard PHAI (Passo 1): vedrai **conto, operazioni e performance in
tempo reale**, e potrai chiedere qualsiasi cosa all'**assistente AI**, nella tua
lingua. Puoi installarla sul telefono come app (icona "Installa").

🎉 **Finito! PHAI è attivo sul tuo conto.**

---

## 🆘 Se qualcosa non torna (messaggi dell'EA)
Apri in MetaTrader la scheda in basso **"Esperti"**: PHAI scrive lì cosa succede.
| Messaggio | Cosa significa / cosa fare |
|---|---|
| `PHAI: licenza OK ...` | Tutto a posto, PHAI è attivo. ✅ |
| `WebRequest fallita ... Autorizza ...` | Rifai il **Passo 4** (autorizza l'indirizzo). |
| `LICENZA NON VALIDA (register_app_first)` | Registra prima l'**account app** (Passo 1) con la stessa key. |
| `LICENZA NON VALIDA (bound_other_account)` | La key è già legata a un altro conto. Scrivici. |
| `LICENZA NON VALIDA (expired/inactive)` | Abbonamento scaduto/sospeso. Rinnova dall'area clienti. |

Hai bisogno di aiuto? Scrivici a **[supporto@phai.io]** o chiedi all'assistente AI.

---

## 🙌 Non vuoi farlo da solo?
Scegli **PHAI Fatto-Per-Te** (€20 una tantum): configuriamo noi tutto (broker, server, installazione).
Tu non tocchi niente. → *[link upsell]*

---

### Nota per il team (NON per il cliente)
- ⚠️ **Prerequisito tecnico**: il server PHAI deve avere un **dominio con HTTPS
  valido** (Let's Encrypt). MetaTrader **rifiuta i certificati self-signed** nelle
  WebRequest → con `https://77.81.226.151:8095` (self-signed) la licenza/telemetria
  NON funzionano sui conti dei clienti. Il dominio è quindi **prerequisito** per
  l'onboarding cliente (oltre che per PWA/notifiche su mobile).
- Rinominare gli `.ex5` consegnati al cliente in `PHAI_EA.ex5` (uno per simbolo, o
  un pacchetto con i 3) e l'indicatore in `PHAI_Median.ex5`.
- I pattern di default negli EA = configurazione canonica: il cliente NON deve
  configurare nulla oltre ai 3 input server.
- Preset `.set` (InpUseServer=true + URL) pronti da consegnare quando il dominio è
  deciso: riducono il Passo 5 a "incolla la key".

---

### Collegato a
- Architettura e scalabilità → [12_DELIVERY_ONBOARDING.md](12_DELIVERY_ONBOARDING.md) · [13_SCALABILITA_HOSTING.md](13_SCALABILITA_HOSTING.md)
- Upsell Fatto-Per-Te → [03_GODFATHER_OFFER.md](03_GODFATHER_OFFER.md)
