# PaPP / PHAI — Il progetto in un colpo d'occhio

Documento unico: **cos'è, com'è fatto, come funziona, come si vende/condivide.**
Semplice ma preciso. (Dettagli tecnici approfonditi: `docs/DOCUMENTAZIONE.md`.)

---

## 1. Cos'è
Un **sistema di trading automatico per MetaTrader 5** basato su **crossover di medie mobili
ancorate al giornaliero (D1)**, più un **assistente web (chatbot)** che mostra performance e
risponde a domande. Si vende come **prodotto in abbonamento** (PHAI): l'utente riceve una
**license key**, installa l'EA e usa il chatbot.

Tre simboli pronti: **EURUSD, GBPUSD, USDCHF** (un EA per simbolo).

---

## 2. Schema generale (i tre mondi)

```
┌──────────────────────────┐   ┌──────────────────────────┐   ┌──────────────────────────┐
│   A. RICERCA (offline)   │   │  B. ESECUZIONE (MT5)     │   │  C. PRODOTTO (vendita)   │
│   trovare i pattern      │   │  far girare l'EA         │   │  licenze + chatbot       │
├──────────────────────────┤   ├──────────────────────────┤   ├──────────────────────────┤
│ Indicatore PaPP_Median   │   │ EA per simbolo           │   │ Server PHAI (app.phai.io)│
│        ↓ (Export)        │   │ (motore base prezzo-     │   │  - valida licenza        │
│ PAPP_Export.csv          │   │  linea)                  │   │  - kill-switch           │
│        ↓ (Miner)         │──▶│        ↓                 │──▶│  - riceve telemetria     │
│ pattern validati OOS     │   │ apre/chiude ordini in MT5│   │ Chatbot web (assistente) │
│        ↓ (genera_schede) │   │        ↓                 │   │ Pagamenti PayPal→licenza │
│ PATTERNS_<SIM>.md        │   │ log + export CSV         │   │ Storico/performance      │
└──────────────────────────┘   └──────────────────────────┘   └──────────────────────────┘
        (lo facciamo NOI)            (gira dal cliente)             (la nostra VPS)
```

---

## 3. Parte A — Ricerca (come nascono i pattern)

Pipeline in 4 passi (codice condiviso in `Motore base _linea-prezzo/Indicatore/`):

| Passo | File | Cosa fa | Output |
|---|---|---|---|
| 1. Indicatore | `PaPP_Median.mq5` | 7 medie mobili del **close D1** (3,7,14,30,121,182,365 gg) + la loro **mediana**. Ancorate a D1 → identiche su ogni timeframe. | linee sul grafico |
| 2. Export | `Export_PAPP.mq5` | Dump di una riga per barra: prezzi, medie, **crossover**, metriche. | `PAPP_Export.csv` |
| 3. Miner | `pattern_mining.py` | Prova migliaia di combinazioni entrata/uscita, le valida **out-of-sample** (train ≤2020, test >2020), seleziona le robuste. | `analisi_oos.txt` |
| 4. Schede | `genera_schede.py` | Documenta i pattern dell'EA con statistiche. | `PATTERNS_<SIM>.md` |

> **Motore base** = entra/esce solo su **prezzo che taglia una linea** (crossover prezzo-linea).
> Niente linea-linea (quello è il "motore esteso", non usato).
> **Unità: tutte le distanze (TP, SL, spread, fallback) sono in PIP**; PnL/drawdown in punti.

---

## 4. Parte B — Esecuzione (l'EA in MT5)

Un **EA per simbolo** (`EA_EURUSD.mq5`, `EA_GBPUSD.mq5`, `EA_USDCHF.mq5`): stessa logica,
pattern diversi. Ogni pattern ha: **entrata** (su cross), **uscita** (cross di un'altra linea
o SL/TP), **stop** (linea o disaster fisso), **TP**, direzione.

Decide **una volta al giorno** (nuova barra D1). Apre solo sui **giorni di taglio** (non a ogni barra).

**Controlli di rischio chiave** (lezioni imparate sul campo):
- `RiskPct` = % di rischio per trade. `MaxPerPattern` = **quante posizioni per pattern** (1 = niente impilamento). **L'impilamento illimitato è ciò che ha fatto esplodere USDCHF** → tenerlo controllato.
- `InpFallbackRiskPips` = distanza di rischio per i pattern senza stop (dimensiona il lotto).

### Configurazioni attuali (backtest 2010-2025, 10.000 € per conto)
| Simbolo | Pattern attivi | Profilo | Risultato |
|---|---|---|---|
| **EURUSD** | P1-P6 (SL=MA365/MA121 + TP stretto) | win ~97%, TP stretto/SL largo | **+92.236 € · DD 20% · PF 2.34** |
| **GBPUSD** | 3 trend (SELL→cross + disaster stop) | trend-following, win ~44% | **+34.758 € · DD ~60% · PF 1.46** |
| **USDCHF** | P1+P7 (SELL→crossMA182), MaxPerPattern=3 | trend, edge sottile | **+19.786 € · DD 24,5%** |

---

## 5. Parte C — Prodotto e condivisione (come vendiamo)

### Modello commerciale: TUTTO in abbonamento (ricorrente)
Tre piani, una scala naturale (l'EA è "i segnali automatizzati"):

| Piano | Modello | Cosa include | Serve PC/VPS acceso? |
|---|---|---|---|
| **Starter** | abbonamento (~1€+/mese) | **solo segnali** (notifiche; esegue a mano) | **No** (gira il nostro master) |
| **Pro** | abbonamento /mese | **EA in licenza** (auto) + segnali + chatbot | Sì (PC suo / VPS broker) |
| **Elite** | abbonamento /mese | EA + segnali + **chatbot premium** (LLM migliore) | Sì |

- **Tutto ricorrente**: niente una-tantum. Se l'abbonamento scade → la licenza scade → l'EA si ferma (kill-switch). Già supportato dal sistema (`plan` + `expires_at` + validazione).
- **Setup: opzionale.** Default self-service (guida + VPS gratis del broker). Installazione fatta da noi solo **a richiesta, a pagamento extra**.
- I piani `starter/pro/elite` e i tier chatbot `free/paid/premium` **esistono già** nel codice.

### Come arriva l'EA al cliente
```
  Cliente paga (PayPal)
        │  webhook
        ▼
  Server PHAI emette una LICENSE KEY ──(email automatica)──▶ cliente
        │
        ▼
  Cliente installa l'EA (.ex5) nel suo MetaTrader 5
  e inserisce la sua license key:
        InpUseServer  = true
        InpLicenseKey = "XXXXX-XXXXX-..."
        InpServerUrl  = https://app.phai.io
        │
        ▼
  Ad ogni barra l'EA chiama il server PHAI:
        /api/ea/validate  → licenza valida? conto giusto? (+ kill-switch)
        /api/ea/config    → rischio e pattern attivi (modificabili da noi a distanza)
        /api/ea/ingest    → invia telemetria (decisioni, conto) per il chatbot
```

- **Licenza ricorrente, per piano**: un key = un account; scade con l'abbonamento.
- **Kill-switch**: dal server possiamo **disattivare** un EA (abbonamento scaduto/revocato).
- **Config remota**: rischio e pattern attivi si possono cambiare **senza ridistribuire l'EA**.
- **Periodo di grazia** (robustezza, implementato): se il *nostro* server è irraggiungibile, l'EA
  **mantiene l'ultimo stato valido** e continua a operare (un nostro down non ferma i clienti).
  Si mette in pausa solo se la licenza è scaduta/revocata **o** se non c'è contatto col server da
  oltre **7 giorni** (`LICENSE_GRACE_SEC`, anti-abuso). Vedi `GUIDA_INSTALLAZIONE.md`.

### Il chatbot (l'assistente che vede il cliente)
- App web (FastAPI + PostgreSQL) sulla **nostra VPS**, pubblica su **https://77.81.226.151** (oggi).
- Mostra **storico backtest** (euro + crescita % per anno, dettaglio per simbolo) e risponde a domande.
- **Tier LLM per piano**: `free` (modello gratuito) · `pro`→paid · `elite`→premium (modello migliore).
- Registrazione **gated da license key**. Login con cookie.

### Pagamenti
- **PayPal** (carte + PayPal) via webhook → emissione automatica della licenza (`licensing.py`).
- Vendite manuali/bonifici: endpoint admin per emettere la key con un click.

---

## 6. Infrastruttura (la nostra VPS)

```
VPS 77.81.226.151
├── MetaTrader 5 (sotto Wine)   → dove giriamo i NOSTRI backtest/ricerca
├── PostgreSQL                  → dati chatbot (utenti, licenze, backtest, telemetria)
├── papp-chat.service (FastAPI) → l'app web, porta 8090 interna
├── opencode-serve.service      → motore LLM (free) per il chatbot
└── nginx                       → espone il chatbot su porta 80/443 (IP pubblico)
```
- **Link pubblico**: http://77.81.226.151 (o https). Gestione: `./chatbot-ctl.sh {start|stop|restart|status}`.
- Solo PHAI è attivo sulla VPS (gli altri progetti sono in panchina; `ripristina-altri-progetti.sh` per riattivarli).

---

## 7. Aggiungere/aggiornare un simbolo (workflow)
1. `Export_PAPP` su grafico **D1** del simbolo → `PAPP_Export.csv`.
2. `pattern_mining.py` → trova e valida i pattern OOS.
3. Copia un `EA_*.mq5`, imposta i pattern validati (input **in pip**).
4. `genera_schede.py` → `PATTERNS_<SIM>.md`.
5. Compila in MetaEditor, **backtesta**, poi importa nel chatbot: `import_backtests.py`.

> ⚠️ Le copie EA dentro MT5 (es. `euro1`, `sterlina`, `svizzero_4`) sono **separate** dai sorgenti
> del progetto: dopo una modifica al sorgente vanno **ricompilate** per allinearsi.

---

## 8. Mappa file principali
| Cosa | Dove |
|---|---|
| Codice condiviso (indicatore, export, miner, schede) | `Motore base _linea-prezzo/Indicatore/` |
| EA + dati + config per simbolo | `Motore base _linea-prezzo/<SIMBOLO>/` (`CONFIG_VINCENTE.md`) |
| Backtest importati + analisi | `backtests/` |
| Chatbot (app web) | `chat_bot/` (`app.py`, `ea_knowledge.md`, `licensing.py`) |
| Controllo chatbot + link | `chatbot-ctl.sh`, `CHATBOT_LINK.md` |
| Documentazione tecnica completa | `docs/DOCUMENTAZIONE.md`, `docs/MAPPA_FILE.md` |

---

## 9. In una riga
**Noi** facciamo ricerca (indicatore→miner→pattern validati) e li mettiamo in un EA per simbolo;
**il cliente** compra una licenza, installa l'EA che si valida sul nostro server e manda i dati;
**il chatbot** sulla nostra VPS gli mostra performance e risponde alle domande.
