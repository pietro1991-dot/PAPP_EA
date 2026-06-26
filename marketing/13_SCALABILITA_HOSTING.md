# 13 · Scalabilità & Hosting — "il cliente non vuole tenere il PC acceso"

> Il problema operativo reale: il cliente NON vuole un computer sempre acceso, e
> costruirgli una VPS a testa **non scala** (ore-uomo + costi per ogni cliente).
> Questo documento risolve il nodo e definisce l'architettura che scala davvero,
> con **controllo centralizzato** che resta in mano tua.

---

## 1. Il punto che cambia tutto
Ci sono due cose che **non devi** costruire tu:
1. **Non devi tenere acceso il PC del cliente** → lo risolve la **VPS integrata di
   MetaTrader** (one-click, la paga il cliente, ~10–15 $/mese). Tu non ospiti niente.
2. **Non devi costruire una VPS per ogni cliente** → è proprio l'errore che porta al
   non-scalabile. La VPS per-cliente, semmai, è solo il **tier premium "Fatto-Per-Te"**
   a pagamento, non il modello base.

E il "controllo centralizzato" vero **non è** controllare la macchina del cliente.
È controllare il **cervello**: licenza + configurazione strategia + telemetria, dal
TUO server. Tu comandi il sistema; l'esecuzione gira a casa loro.

> **Controlla il cervello, non la scatola.**

---

## 2. La soluzione al "PC sempre acceso": la VPS di MetaTrader
MetaTrader 5 ha l'**hosting virtuale integrato** ("Virtual Hosting" / *Affitta un
server virtuale*, dal menu del terminale):
- Il cliente clicca col destro sul conto → **"Affitta un server virtuale"**.
- Il terminale **migra** automaticamente grafici, EA e indicatori sul server.
- Gira **24/7** vicino al broker (bassa latenza), **col PC del cliente spento**.
- Costo ~**10–15 $/mese**, **lo paga il cliente** direttamente a MetaQuotes.
- **Tu non ospiti, non gestisci, non scali nulla**: l'esecuzione è esternalizzata
  al network di MetaQuotes.

Questo è **lo standard del settore** per gli EA: è esattamente la risposta al
cliente che dice "non voglio tenere il computer acceso".

**Alternativa** (per chi vuole più flessibilità o gira più EA): una **Forex VPS di
terze parti** (ForexVPS, Contabo, ecc.), Windows, ~10–30 $/mese, sempre pagata dal
cliente. Più potente, un filo più di setup.

> ⚠️ Dettaglio tecnico da testare: sulla VPS MetaQuotes la **whitelist WebRequest**
> (per licenza/telemetria, doc 12 §4.3) va impostata **prima** della migrazione, così
> viaggia con la configurazione. Da verificare in fase di test; se ci fossero
> limiti, si usa la Forex VPS di terze parti (dove la whitelist è piena Windows).

---

## 3. Il "controllo centralizzato" che conta (e che scala)
Non controlli il PC del cliente. Controlli queste tre cose dal TUO server, e ti
bastano per comandare tutto:

### 3.1 Licenza centrale (acceso/spento istantaneo)
Dal tuo pannello attivi/revochi qualsiasi cliente. L'EA valida la licenza
periodicamente (doc 12 §4.1) → se revochi/scade, **smette di operare**, ovunque
giri. Controllo totale sull'accesso, da un posto solo.

### 3.2 Configurazione remota della strategia (la chiave della scalabilità) ⭐
L'EA **non** ha i pattern "cablati" dentro. All'avvio (e ogni X ore) chiede al tuo
server: `GET /api/ea/config` → riceve **quali pattern sono attivi e con quali
parametri** per il suo simbolo.
- Migliori/aggiorni una strategia? **La pubblichi UNA volta sul server** e **tutti
  i clienti** si aggiornano da soli, senza toccare le loro macchine.
- Vuoi spegnere un pattern diventato rischioso? Un click, vale per tutti.
- È **questo** il vero controllo centralizzato: governi il comportamento di mille
  installazioni da un'unica dashboard.

### 3.3 Telemetria centrale (vedi tutto da un posto)
Ogni EA invia i dati a `POST /api/ea/ingest` (doc 12 §4.2). Tu hai un **pannello
admin** con TUTTI i conti, performance, anomalie. Il cliente vede solo il suo; tu
vedi la flotta.

> Con questi tre, comandi il sistema centralmente **senza** ospitare o gestire
> nessuna macchina del cliente. Ecco perché scala.

---

## 4. Perché QUESTO scala (e la VPS-per-cliente no)
| | VPS per cliente (tu la costruisci) | Distribuito + MT5 VPS + cervello centrale |
|---|---|---|
| Costo per nuovo cliente | Una VPS + ore di setup ogni volta | ~0 (il cliente attiva la sua MT5 VPS) |
| Tuo carico operativo | Cresce **linearmente** coi clienti | **Piatto** (un'API + un DB per tutti) |
| Credenziali broker | Le tieni tu (rischio/responsabilità) | Restano al cliente (sei software vendor) |
| Aggiornare la strategia | Macchina per macchina | **Una volta**, vale per tutti |
| Limite di crescita | Ti fermi a poche decine | Migliaia, stesso sforzo |

La tua infrastruttura resta **una sola** (l'API + Postgres che hai già): 10 clienti
o 10.000, il TUO costo e lavoro cambiano pochissimo. Questo è un business SaaS che
scala; la VPS-per-cliente è una società di servizi che non scala.

---

## 5. "Ma io voglio gestire tutto io, il cliente non tocca niente"
Esiste, ed è un **modello diverso e più pesante**. Onestà totale:

### Opzione managed — Copy-trading / MAM/PAMM dal broker
Tu fai girare la strategia su **un conto master**; i conti dei clienti **copiano**
le operazioni a livello broker (sistema copy/MAM/PAMM del broker).
- ✅ Il cliente **non installa e non tiene acceso nulla**: collega il conto e basta.
- ✅ Controllo di esecuzione **totalmente centralizzato** (un master, mille copie).
- ❌ **Regolamentazione**: gestire/allocare per conto altrui ti fa diventare
  (in molte giurisdizioni) un **gestore/consulente autorizzato** → serve licenza,
  compliance, broker partner. Barriera alta.
- ❌ **Lock-in** sul broker che offre il MAM/copy; dipendenza forte.
- Verdetto: è il **tier premium "PHAI Managed"** del futuro, da attivare **dopo**
  aver costruito brand, numeri e il setup legale. **Non** il punto di partenza.

> Regola: parti **software vendor** (scalabile, basso rischio). Diventi **managed**
> solo quando hai scala e struttura legale per reggerlo.

---

## 6. La scala a 3 livelli (componi i modelli per profilo cliente)
| Livello | Per chi | Come gira | Chi paga l'hosting |
|---|---|---|---|
| **Self-serve** | Tecnico/autonomo | EA sul suo MT5 + **MT5 VPS one-click** | Cliente (~10–15 $/mese a MetaQuotes) |
| **Fatto-Per-Te** (upsell) | Non vuole toccare niente | Glielo configuri tu (MT5 VPS o Forex VPS) | Cliente, ma lo imposti tu (+297 € una tantum, doc 03) |
| **Managed** (futuro) | Vuole zero coinvolgimento | Copy/MAM da master, a livello broker | Modello regolamentato, tier premium |

La **maggioranza** sta nel Self-serve (scala da sola). Il DFY monetizza i
non-tecnici **senza** caricarti di VPS gratuite. Il Managed è il futuro premium.

---

## 7. Cosa aggiungere all'MVP (rispetto al doc 12)
Un solo pezzo in più rende il tutto centralmente governabile:
- **`GET /api/ea/config`** — l'EA scarica i pattern attivi/parametri dal server
  (config remota, §3.2). Piccola aggiunta, enorme leva: aggiorni tutti da un punto.

Il resto è il doc 12: `validate` (licenza), `ingest` (telemetria), modifiche EA,
guida installazione (che includerà lo step **"Affitta server virtuale"** di MT5 per
risolvere il PC-sempre-acceso).

---

## 8. In una frase
> **Non costruire VPS.** Fai installare l'EA al cliente con un clic e fallo girare
> sulla **VPS integrata di MetaTrader** (la paga lui, PC spento, 24/7). Tu controlli
> **licenza + configurazione + telemetria** dal tuo server: comandi mille
> installazioni da un'unica dashboard, con una sola infrastruttura. Il "tutto
> gestito io" (copy/MAM) è il tier premium regolamentato, da fare dopo.

---

### Collegato a
- L'architettura di delivery → [12_DELIVERY_ONBOARDING.md](12_DELIVERY_ONBOARDING.md)
- I tier e i prezzi → [11_MODELLO_BUSINESS.md](11_MODELLO_BUSINESS.md) · [03_GODFATHER_OFFER.md](03_GODFATHER_OFFER.md)
- Confine software-vs-gestione regolamentata → [10_COMPLIANCE_DISCLAIMER.md](10_COMPLIANCE_DISCLAIMER.md)
