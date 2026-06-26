# Miner `pattern_mining.py` — come funziona

> Documento di **solo funzionamento**: cosa fa il miner, con quale metodo, e come leggerne il
> risultato. Riferimento codice: [src/symbols/analysis/pattern_mining.py](../src/symbols/analysis/pattern_mining.py).

---

## In una frase

Legge il CSV prodotto dall'export, prova **tutte le combinazioni** di pattern (un modo di entrare
+ un modo di uscire), le **simula con costi reali** su un periodo di addestramento, le **ri-testa**
su un periodo separato mai visto, e tiene **solo quelle che funzionano su entrambi** — la difesa
principale contro l'illusione (overfitting).

In una riga: trova le regole di trading che hanno un vantaggio **vero e ripetibile**, non quelle
che sembravano buone solo per fortuna sul passato.

---

## 1. Cosa fa, passo per passo

1. **Carica il CSV** (una riga per giornata, con prezzi, medie, crossover, metriche).
2. **Divide la storia in due**: *training* (per cercare i pattern) e *test* (per verificarli).
3. **Rileva le entrate**: ogni crossover è una possibile entrata.
4. **Simula 3 modi di uscire** da ogni entrata, sottraendo i costi.
5. **Aggrega per pattern** e calcola le metriche (vincite, Sharpe, profit factor…).
6. **Simula a portafoglio** (una posizione alla volta) per misurare il **vero drawdown**.
7. **Valida sul test** e tiene solo i pattern **robusti** (positivi su training *e* test).

---

## 2. L'entrata: sempre un crossover

Un'entrata è il momento in cui il **prezzo taglia una linea** (una delle 7 medie o la mediana).
Queste informazioni sono già pronte nel CSV (colonne `crossMA365 … crossMA3`, `crossMed`): il miner
non le ricalcola, le legge. Ogni crossover diventa un candidato trade, con la sua direzione
(rialzista o ribassista).

> In modalità walk-forward (`--robust`) il miner aggiunge anche i **crossover linea-linea** (due
> medie che si incrociano tra loro, colonne `MA3_7 … MA182_365`).

---

## 3. Le 3 strategie di uscita (le "3 analisi")

L'entrata è sempre un crossover; ciò che cambia è **come si esce**. Il miner prova tre famiglie:

- **ANALISI 1** — esci al **primo crossover opposto** su una linea *qualsiasi*. (Uscita "naturale":
  resti dentro finché il mercato non gira.)
- **ANALISI 2** — esci al crossover di una **linea specifica** (es. entra su MA14, esci quando il
  prezzo incrocia la MA182). Permette uscite più lente o più veloci scegliendo la linea.
- **ANALISI 3** — esci con uno **stop loss dinamico** appoggiato a una linea **+ un take profit
  fisso**. Il miner prova una **griglia** di combinazioni (5 linee di SL × 9 valori di TP).

---

## 4. Come viene simulato un singolo trade

Dall'entrata si va avanti **barra per barra**:
- a ogni barra si sottraggono i **costi** (spread + commissione una tantum, swap per ogni barra tenuta);
- per l'**SL dinamico** si usa il valore della linea della **barra precedente** (così non c'è
  "sguardo nel futuro") e si controlla se il minimo/massimo della barra lo tocca;
- il **TP** si controlla sul massimo/minimo della barra (quindi un TP colpito a metà giornata viene
  catturato, non solo a chiusura);
- se né SL né TP scattano entro un limite di barre, il trade si chiude **a mercato** all'ultima
  barra (mark-to-market: non si scarta, per non nascondere i trade-zombie).

---

## 5. Le metriche calcolate

Per ogni pattern (gruppo di trade con la stessa regola):

- **Win%**, **AvgPts** (profitto medio/trade), **TotPnl**, **AvgBars** (durata media).
- **Profit Factor** = profitti lordi / perdite lorde (>1 = in attivo).
- **Sharpe per-trade** = profitto medio / deviazione standard dei trade. **Non** è annualizzato.
  - Difesa: se la dispersione è quasi nulla (coefficiente di variazione < 10%) lo Sharpe viene
    **azzerato**. Serve a smascherare gli Sharpe "finti" dei pattern dominati da un TP fisso (quasi
    tutti i trade chiudono allo stesso valore → Sharpe gonfiato artificialmente).

---

## 6. La simulazione a portafoglio (una posizione alla volta)

Le statistiche per-trade possono **ingannare**: se molti segnali correlati scattano insieme, si
contano più volte lo stesso movimento e profitto/Sharpe sembrano migliori del reale.

Per evitarlo, il miner simula un **capitale unico, una posizione alla volta**: i segnali che
arrivano mentre una posizione è già aperta vengono **ignorati**. Su questa equity misura:
- **MaxDD** (massima perdita picco→minimo, in punti),
- **Ret/DD** (TotPnl / MaxDD — il rendimento per unità di rischio),
- **Expo%** (frazione di tempo effettivamente a mercato).

Sono numeri **onesti**, impossibili da ottenere dalle sole medie per-trade.

---

## 7. La validazione train/test (la difesa anti-overfitting)

La storia è divisa in **training** (es. ≤ 2020) e **test** (> 2020). I pattern migliori vengono
trovati sul training e poi **ri-eseguiti sul test**, che non è mai stato usato per sceglierli.

Logica: un pattern che è bellissimo sul training ma **perde sul test** non aveva un vantaggio vero
— si era solo adattato al passato. Viene scartato.

---

## 8. La selezione robusta

Tiene **solo** i pattern che restano in **attivo su training *e* test**. Il punteggio è il
**minimo** tra lo Sharpe (penalizzato) del training e quello del test: premia chi è buono su
*entrambi*, non chi spicca solo da una parte.

> **Sharpe penalizzato**: lo Sharpe viene "ridotto verso zero" quando i trade sono pochi
> (`sharpe × n/(n+10)`). Con pochi trade la stima è rumorosa: questa penalità riduce il rischio di
> premiare pattern fortunati con poche operazioni.

---

## 9. Modalità walk-forward (`--robust`)

È il test più severo. Divide **tutta** la storia in **N finestre** cronologiche e dichiara un
pattern **ROBUSTO** solo se è positivo in **tutte** (o quasi) le finestre, con Ret/DD ≥ 1. Così non
basta funzionare in un periodo fortunato: deve reggere in più regimi di mercato diversi. Questa
modalità considera anche le entrate **linea-linea**.

---

## 10. Le difese anti-overfitting (riepilogo)

Il miner accumula più protezioni perché testa **centinaia di combinazioni** (e testandone tante,
qualcuna sembra buona per puro caso):

| Difesa | A cosa serve |
|---|---|
| Split train/test | scarta chi non regge fuori dal periodo di ricerca |
| Walk-forward N finestre | pretende coerenza in più regimi |
| Sharpe penalizzato | non si fida dei pattern con pochi trade |
| Azzeramento Sharpe (CV<10%) | smaschera gli Sharpe finti da TP fisso |
| Portafoglio 1-pos | niente profitti gonfiati da trade correlati sovrapposti |
| Costi reali | spread/commissione/swap sottratti a ogni trade |

---

## 11. Come si usa

```
python3 pattern_mining.py <CSV> [opzioni]

  --split-date=YYYY.MM.DD   confine train/test (consigliato)
  --train-pct=0.7           in alternativa, split in percentuale
  --spread=N --commission=N --swap=N    costi (in punti)
  --min-trades=N            minimo trade per considerare un pattern
  --robust --folds=N        modalità walk-forward a N finestre
  --output=FILE             salva il report su file (oltre che a video)
```

Esempio (quello usato per i simboli):
```
python3 ../analysis/pattern_mining.py PAPP_Export.csv \
        --spread=15 --commission=7 --split-date=2020.01.01 --output=analisi_oos.txt
```

---

## 12. Come leggere il report prodotto

Il report inizia con una **LEGENDA E METODOLOGIA** (spiega entrata, le 3 analisi, i costi, e ogni
colonna) ed è organizzato in sezioni:
1. caricamento, split, conteggio entrate;
2. **ANALISI 1/2/3** — le tabelle dei pattern per ciascuna strategia di uscita;
3. **RIEPILOGO** — il miglior pattern per ogni linea d'ingresso;
4. **ANALISI PORTAFOGLIO** — equity reale, MaxDD, Ret/DD;
5. **VALIDAZIONE TEST SET** — gli stessi pattern ri-testati fuori campione;
6. **SELEZIONE ROBUSTA** — i pattern che reggono su training *e* test (i candidati veri).

> Importante: i pattern da prendere sul serio sono quelli della **SELEZIONE ROBUSTA** / della
> modalità **--robust**, non i "migliori del training" (che soffrono di selection bias).

---

## 13. Cosa il miner NON fa

- **Non fa trading**: produce solo l'analisi. I pattern validati vengono poi messi a mano nei
  default dell'EA del simbolo.
- **Non rigenera i dati**: lavora sul CSV così com'è (prodotto dall'export). Se cambia l'indicatore
  o l'export, va ri-esportato il CSV prima di ri-minare.
