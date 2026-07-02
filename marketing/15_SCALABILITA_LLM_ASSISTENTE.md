# 15 · L'assistente AI regge quando arrivano i clienti? (LLM: macchina, quota, scala)

> Domanda: "I modelli gratuiti funzioneranno anche quando i clienti acquistano e si
> iscrivono? La macchina che gira è sempre la stessa?"
> Risposta breve: **sì, è la stessa macchina e la stessa quota LLM condivisa**. Il
> sito e il database reggono tanti clienti senza problemi; **il collo di bottiglia
> è l'LLM gratuito**, che a volume va portato su un piano a pagamento. Spiegato qui.

---

## 1. Cosa è "la macchina" e cosa è condiviso
Una **sola VPS** fa girare un **solo processo** dell'app (FastAPI). Quel processo serve
**tutti** i clienti insieme. Due risorse vanno distinte:

| Risorsa | Condivisa o per-cliente? | Scala bene? |
|---|---|---|
| **Dati** (conto, segnali, chat) | **Isolati per cliente** (`user_id`) | ✅ sì |
| **Web server + Database** | Condivisi (un processo, un Postgres) | ✅ sì, regge **centinaia** di clienti su questa VPS |
| **Motore LLM** (l'assistente) | **Condiviso**: 1 chiave gratuita, 1 worker alla volta | ⚠️ **è il limite**: la quota gratuita è una sola per tutti |

Quindi: la parte "app" non è un problema. **L'assistente AI sì**, perché oggi tutti
i clienti attingono alla **stessa quota gratuita**.

## 2. Come funziona oggi l'LLM (e cosa lo protegge già)
L'assistente non chiama l'LLM "a caso": c'è un layer che fa da scudo
([`llm_worker.py`](../chat_bot/llm_worker.py)):
- **Cache** (memoria + DB): domande identiche/ripetute → risposta **immediata, 0 quota**.
  Le domande comuni ("come va oggi?") sono servite da un **riassunto precalcolato**
  uguale per tutti → **nessuna chiamata LLM**.
- **Rate limit globale** (`LLM_RPM=15`/min) e **per-utente** (`LLM_USER_RPM=5`/min):
  un cliente non può svuotare la quota di tutti.
- **Coda con un worker (concorrenza 1)**: le domande vere all'LLM sono gestite in
  ordine, una alla volta.
- **Fallback**: se il modello primario fallisce, ne prova un altro; se tutto fallisce,
  messaggio "servizio al limite" invece di un errore.

Con **pochi clienti** questo basta e avanza (gran parte delle risposte arriva dalla
cache). Il problema nasce con il **volume**.

## 3. Il limite onesto del piano gratuito
I modelli gratuiti di OpenCode Zen (`mimo-v2.5-free`, `deepseek-v4-flash-free`):
- hanno una **quota condivisa** (richieste/minuto e, possibilmente, un tetto
  giornaliero) valida per **l'unica chiave** che usiamo per tutti;
- con la **concorrenza a 1**, in un picco (tanti clienti che chiedono insieme) si
  forma **coda** → risposte più lente o messaggio "servizio al limite";
- sono **gratuiti senza garanzie**: il fornitore può limitarli o toglierli. Per un
  prodotto **a pagamento** dipendere solo dal gratis è un **rischio**.

> In sintesi: il free va bene per **lanciare** e per i **primi clienti**. Non regge,
> da solo, **centinaia di clienti attivi** che chattano nello stesso momento.

## 4. Come si scala (e perché è facile e conveniente)
Il bello: scalare l'LLM è **economico** rispetto a quanto incassi, e non richiede di
riscrivere niente — si cambiano **configurazione e piano**.

1. **Passa a un LLM a pagamento** (stesso codice, basta la chiave/piano):
   - piano **a pagamento di Zen**, oppure un'API diretta (DeepSeek paid, oppure
     **Claude Haiku** per qualità migliore). Più limiti, più affidabilità, niente "free cap".
2. **Alza la concorrenza** del worker (più richieste LLM in parallelo) e il
   `LLM_RPM`, una volta sul piano a pagamento.
3. **Quote per piano** (cost-control + upsell):
   - Assistente+Segnali/singolo EA = N domande/giorno · Pacchetti = di più · Completo = priorità + nessun limite pratico.
   - Così il costo LLM per cliente è **prevedibile e marginale**, e diventa una **leva
     di vendita** (chi vuole di più sale di piano).
4. **Cache sempre più aggressiva** + risposte precalcolate → ogni domanda servita
   dalla cache è **0 costo**.

### L'economia (perché il margine resta altissimo)
- Una domanda costa **frazioni di centesimo** su un modello economico a pagamento.
- Anche stimando **100 domande/cliente/mese**, sono **pochi centesimi** di costo LLM
  contro **4–12 €/mese** di abbonamento → margine in % ancora **alto** (la cache lo tiene basso;
  a questi prezzi tieni comunque d'occhio il costo LLM per-utente sul volume totale).
- La cache abbatte ulteriormente le chiamate reali (le domande comuni non costano nulla).

> Tradotto: l'abbonamento dei clienti **paga abbondantemente** l'LLM a pagamento.
> Il modello di business (doc 11) regge l'infrastruttura per costruzione.

## 5. Cosa fare e quando (trigger pratici)
| Situazione | Azione |
|---|---|
| Lancio / primi clienti (free regge) | Resta sul gratuito + cache + rate limit. **Monitora** "servizio al limite". |
| Vedi spesso "servizio al limite" o code | Passa l'`OPENCODE_API_KEY` a un **piano a pagamento**, alza `LLM_RPM` e la concorrenza. |
| Cresci (decine/centinaia di attivi) | **Quote per piano** (Assistente+Segnali/EA/Pacchetti/Completo) + cache aggressiva. Valuta **Claude Haiku** per qualità. |
| Il web/DB rallenta (molto più avanti) | Aumenta le risorse della VPS o separa il Postgres. (Succede **molto** dopo l'LLM.) |

## 6. Risposte secche alle tue domande
- **"La macchina è sempre la stessa?"** → Sì: una VPS, un processo, per tutti i clienti.
  I **dati** sono separati per cliente; **web e DB** reggono tanti clienti.
- **"I modelli gratuiti funzioneranno anche con i clienti paganti?"** → Per **pochi**
  clienti sì (grazie a cache e rate limit). Per **molti**, no da soli: vanno portati
  su un **piano LLM a pagamento** — che costa pochissimo rispetto agli incassi.
- **"Devo preoccuparmi ora?"** → No per partire. Sì da **pianificare**: tieni d'occhio
  i "servizio al limite"; quando compaiono spesso, è il segnale per fare l'upgrade
  (mezza giornata di lavoro, già predisposto).

## 7. Nota qualità (collegata)
I modelli gratuiti, oltre ai limiti di quota, ogni tanto sbagliano (es. caratteri
cinesi — già filtrati, vedi commit dedicato). Passando a un modello a pagamento
migliore (es. Claude Haiku) **migliora anche la qualità** delle risposte, non solo la
capacità. È un upgrade "due piccioni con una fava" quando il volume lo giustifica.

## 8. L'interruttore è già pronto (capacità costruita, costo zero)
Il codice **sceglie già il modello LLM in base al piano del cliente** (free/paid/premium),
guidato da `.env`. Di default **tutti restano sul free** (mimo/deepseek) → costo zero
finché non vendi. Per attivare Claude (o qualsiasi modello a pagamento):

```ini
# Modello per i clienti a pagamento (EA/pacchetti, tier "paid"). Vuoto = restano sul free.
LLM_PAID_MODEL=<id-modello-claude>
# Modello per i clienti Pacchetto Completo (tier "premium"). Vuoto = usa il paid.
LLM_PREMIUM_MODEL=<id-modello-claude-piu-capace>
# Se il modello NON passa da OpenCode Zen (es. API Anthropic OpenAI-compatibile):
LLM_PAID_BASE_URL=<endpoint>      # vuoto = stesso endpoint del free (Zen)
LLM_PAID_API_KEY=<chiave>         # vuoto = stessa chiave del free
```

Mappatura piano → modello: **Demo/Assistente+Segnali → free**, **singolo EA/Pacchetti (Difensivo/Bilanciato) → paid**, **Pacchetto Completo → premium**.
La cache è separata per tier (un cliente paid non riceve mai una risposta del free, e
viceversa). Nessuna riscrittura: basta riavviare il servizio dopo aver impostato le env.

> Strategia consigliata (doc): parti col free per tutti; al primo cliente pagante metti
> `LLM_PAID_MODEL` su un Claude economico (es. Haiku) → i paganti salgono di qualità e
> si **isolano** dalla fragilità del free; tieni il premium (Sonnet) come leva del Pacchetto Completo.

---

### Collegato a
- Modello di business e piani → [11_MODELLO_BUSINESS.md](11_MODELLO_BUSINESS.md)
- Scalabilità lato EA/hosting → [13_SCALABILITA_HOSTING.md](13_SCALABILITA_HOSTING.md)
- Layer LLM (cache/coda/rate limit) → [`chat_bot/llm_worker.py`](../chat_bot/llm_worker.py)
