# Contenuti marketing — kit di lancio PHAI Trading

Asset creativi **pronti all'uso** per riempire i canali e alimentare il funnel (doc 05/16).
Tutto in italiano (mercato di lancio); la localizzazione EN/FR/ES è un pass successivo.

## File
| File | Contenuto |
|---|---|
| [POST_SOCIAL.md](POST_SOCIAL.md) | Libreria post (IG/FB/TikTok/X/LinkedIn) per 7 angoli + caroselli + bio |
| [VIDEO_SCRIPT.md](VIDEO_SCRIPT.md) | 8 short verticali + VSL completo + explainer YouTube + walkthrough Demo |
| [EMAIL_CAMPAIGN.md](EMAIL_CAMPAIGN.md) | **25 email pronte** (nurture/onboarding/retention) — sorgente `pipeline/email_campaign.py` |

## Landing / pagine (servite dall'app)
| Pagina | URL | Scopo |
|---|---|---|
| **Landing/Sales** | `/` | Porta d'ingresso completa (hero→prova→prezzi→FAQ) — `templates/landing.html` |
| **Squeeze report** | `/report` | Un solo obiettivo: email in cambio del report (traffico freddo) — `templates/squeeze.html` |
| **Demo** | `/demo` | Dashboard read-only dal vivo (l'esca-eroe) |
| **Checkout** | `/checkout?plan=…` | Pagamento PayPal → license key |

> Dove mandare il traffico: annunci "educativi/anti-truffa" → **/report** (cattura email);
> annunci "guardalo dal vivo" → **/demo**; retargeting/caldo → **/** (sales) o `/checkout`.

---

## Calendario editoriale — 4 settimane (ruota gli angoli, non ripeterti)

### Settimana 1 — Autorità & Trasparenza (riscalda il pubblico)
| Giorno | Canale | Asset |
|---|---|---|
| Lun | IG/FB feed | Post 1 (Anti-truffa) |
| Mar | Reel/TikTok | Short A (Anti-truffa) |
| Mer | IG/FB feed | Post 4 (Trasparenza — "anche le perdite") |
| Gio | Reel/TikTok | Short B (Out-of-sample) |
| Ven | IG/FB feed | Post 7 (Storia/Dietro le quinte) |
| Sab | Story / X | Thread educativo (Angolo 2) |
| Dom | Carosello | "12 domande prima di comprare un EA" |

### Settimana 2 — Metodo & Prodotto
| Giorno | Canale | Asset |
|---|---|---|
| Lun | IG/FB feed | Post 3 (Il rumore del D1) |
| Mar | Reel/TikTok | Short C (Il rumore del D1) |
| Mer | IG/FB feed | Post 5 (Comodità / app+AI) |
| Gio | Reel/TikTok | Short E (App + AI, screen) |
| Ven | IG/FB feed | Post 2 (Out-of-sample, educativo) |
| Sab | YouTube | Explainer "Come funziona PHAI" |
| Dom | Carosello | "EA da 30€ vs PHAI" (Confronto) |

### Settimana 3 — Qualifica & Pazienza (attira il cliente giusto)
| Giorno | Canale | Asset |
|---|---|---|
| Lun | IG/FB feed | Post 6 (Pazienza) |
| Mar | Reel/TikTok | Short D (Vendi la pazienza) |
| Mer | IG/FB feed | Post 4 var. (Trasparenza/drawdown) |
| Gio | Reel/TikTok | Short G (Perché abbiamo spento i pattern) |
| Ven | YouTube | Demo Walkthrough |
| Sab | Story / X | Dietro le quinte (Short H come testo) |
| Dom | Carosello | Educativo (recap settimana) |

### Settimana 4 — Conversione (spingi Demo/offerta)
| Giorno | Canale | Asset |
|---|---|---|
| Lun | IG/FB feed | Post 5 (Comodità) + CTA Demo |
| Mar | Reel/TikTok | Short F (Confronto) |
| Mer | IG/FB feed | Post 1 var. (Anti-truffa) + CTA Demo |
| Gio | Reel/TikTok | Short A var. (Anti-truffa) |
| Ven | IG/FB feed | Storia + offerta soft (50 posti) |
| Sab | Story | Countdown "posti del mese" |
| Dom | Tutti | Recap + CTA forte (Demo / report) |

> Poi si ricomincia il ciclo con varianti. **Misura** cosa funziona (salvataggi,
> click in bio, lead) e raddoppia sugli angoli vincenti (doc 09).

## Regole d'oro (Sabri + compliance)
- **Hook nei primi 3 secondi** (video) / prima riga (post).
- **Una CTA sola** per contenuto.
- **Dai valore prima di vendere** (educa, mostra, smaschera).
- **Disclaimer sempre**: "Il trading comporta rischi. Nessun rendimento è garantito."
- Numeri = **backtest etichettato**. Mai promesse di guadagno (doc 10).

---

### Collegato a
- Annunci a pagamento → [../06_COPY_ANNUNCI.md](../06_COPY_ANNUNCI.md)
- Funnel e dove mandare il traffico → [../05_FUNNEL_PIPELINE.md](../05_FUNNEL_PIPELINE.md)
- Email → [../07_EMAIL_SEQUENCE.md](../07_EMAIL_SEQUENCE.md) · Strategia SaaS → [../16_STRATEGIA_RIVISTA_SAAS.md](../16_STRATEGIA_RIVISTA_SAAS.md)
