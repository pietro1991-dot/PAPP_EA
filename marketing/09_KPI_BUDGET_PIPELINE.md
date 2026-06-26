# 09 · KPI, Budget e Funnel Math

> "Il marketing è matematica. Se conosci i tuoi numeri, puoi comprare clienti a
> volontà." — Sabri Suby

Questo documento rende la campagna **misurabile e scalabile**. Senza questi numeri
non stai facendo marketing, stai scommettendo.

> Tutti i valori qui sono **ipotesi di partenza** (benchmark realistici per
> info-prodotti/SaaS nel B2C). Vanno sostituiti con i TUOI dati reali appena il
> funnel gira. Il punto non è indovinare: è misurare e migliorare l'anello debole.

---

## 1. Le metriche che contano (per fase)
| Fase | Metrica | Target iniziale |
|---|---|---|
| Annunci | CTR (click-through rate) | > 1,5% (Meta) |
| Annunci | CPC (costo per click) | 0,30–1,00 € |
| Landing HVCO | Conversione visita→lead | 25–40% |
| Lead | CPL (costo per lead) | 3–6 € |
| Nurture | Open rate email | > 40% |
| Sales page | Conversione lead→cliente | 1–3% (freddo), 3–8% (caldo) |
| Globale | CAC (costo acquisizione cliente) | < 250 € (su core 997 €) |
| Cliente | AOV (valore medio ordine) | 997 € + upsell |
| Cliente | LTV (valore nel tempo) | > 1.300 € (con ascensione) |
| Salute | LTV : CAC | ≥ 3 : 1 |
| Globale | ROAS (ritorno sulla spesa pubbl.) | ≥ 3 : 1 a regime |

## 2. Funnel Math — esempio di scenario (1.000 € di ads)
Scenario prudente per leggere il modello (NON una promessa di risultati):

```
Spesa ads:                    1.000 €
CPC 0,50 €      → click:       2.000
Conv. landing 30% → lead:        600     (CPL ≈ 1,67 €)
Conv. lead→cliente 1,5%        →   9 clienti
Ricavo (9 × 997 €):           8.973 €
+ upsell (30% × 297 €):      ~  800 €
Ricavo totale:              ~ 9.773 €
ROAS ≈ 9,7x  (lordo, pre-costi/IVA/rimborsi)
```
> ⚠️ È uno **scenario illustrativo**. I tassi reali variano molto. Parti
> prudente, misura, e scala SOLO ciò che è profittevole. Considera IVA, fee di
> pagamento, rimborsi, costi server/AI nel calcolo del margine vero.

## 3. Budget per fasi di crescita
| Fase | Spesa ads/mese | Obiettivo | Focus |
|---|---|---|---|
| **0 — Validazione** | 300–1.000 € | Validare HVCO, CPL, prime vendite | Trovare 1 annuncio + 1 angolo che funzionano |
| **1 — Ottimizzazione** | 1.000–3.000 € | Stabilizzare CAC < LTV/3 | A/B test landing, email, sales page |
| **2 — Scalata** | 3.000–10.000 €+ | Aumentare volume mantenendo ROAS | Nuovi canali, nuovi angoli, lookalike |

> Regola di Sabri: **non scalare un funnel rotto.** Prima trovi numeri sani su
> piccolo budget, POI versi benzina.

## 4. La sequenza di lancio consigliata (primi 90 giorni)
| Settimane | Cosa | Risultato atteso |
|---|---|---|
| 1–2 | Dominio/HTTPS, sito, landing, checkout, licenze, tracciamento | Infrastruttura pronta |
| 3–4 | HVCO (report+video), sequenza email, sales page+VSL | Funnel completo |
| 5–6 | Lancio soft 300–500 €/mese ads, 3 angoli | Primi lead + primi clienti |
| 7–8 | Analisi numeri, taglia i perdenti, raddoppia i vincenti | CPL/CAC sotto controllo |
| 9–12 | Scala il budget, aggiungi canali, attiva ascensione/referral | Crescita prevedibile |

## 5. Cruscotto da monitorare ogni settimana
- Spesa, click, CTR, CPC per annuncio/angolo.
- Lead totali, CPL, sorgente.
- Vendite, AOV, CAC, ROAS.
- Tasso di rimborso (campanello d'allarme su onboarding/aspettative).
- Open/click email per step della sequenza.
- **Anello più debole** → priorità della settimana.

## 6. Leve per migliorare ogni numero
- **CTR basso** → cambia hook/creatività (doc 06).
- **Conv. landing bassa** → headline/offerta HVCO, meno frizione (doc 04).
- **Conv. vendita bassa** → prova, garanzia, VSL, obiezioni (doc 03/08).
- **CAC alto** → migliora conversioni a valle prima di toccare gli ads.
- **LTV basso** → rafforza ascensione/upsell/retention (doc 03 §7).

## 7. Strumenti di misura (dal doc 05)
GA4 + Meta Pixel + eventi del funnel; report nativi della piattaforma email; un
semplice foglio settimanale con queste righe è già sufficiente all'inizio. Non
serve uno stack complesso: serve **guardare i numeri ogni settimana e agire**.

---

### Collegato a
- Le fasi del funnel → [05_FUNNEL_PIPELINE.md](05_FUNNEL_PIPELINE.md)
- Cosa ottimizzare a ogni anello → tutti i doc precedenti
