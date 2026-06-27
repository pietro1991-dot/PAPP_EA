# Pipeline automatica di contenuti — analisi free vs a pagamento + architettura

Obiettivo: generare i contenuti **via codice** (script → media finito), restando il più
possibile su **strumenti gratuiti** e **utilizzabili commercialmente**. Qui ragioniamo
PRIMA su cosa è davvero fattibile gratis e automatizzabile, e cosa no.

> Distinzione chiave: per una pipeline serve un'**API gratuita** o un **open-source
> self-hostabile**, non solo un sito gratis. Molti tool (HeyGen, InVideo, Suno) hanno una
> versione web gratis ma **API solo a pagamento** → non li possiamo automatizzare gratis.
> E attenzione alla **licenza**: "gratis per uso personale" ≠ "gratis per uso commerciale".

---

## 1. Componente per componente

### 🎙️ Voce / TTS (testo → audio)
| Opzione | Gratis? | Uso commerciale | API/automazione | Note |
|---|---|---|---|---|
| **Piper TTS** (open-source) | ✅ totale, self-host | ✅ (voci con licenza permissiva) | ✅ via codice | Gira su **CPU**, leggero, voci IT. **La scelta commercial-safe.** |
| **edge-tts** (lib Python) | ✅ no key | ⚠️ zona grigia (servizio Microsoft non ufficiale) | ✅ facilissimo | Qualità ottima, voci IT. Per test/volumi bassi. |
| **Coqui XTTS-v2** | ✅ self-host | ❌ licenza modello **non commerciale** | ✅ | Voice cloning ottimo ma **non commerciale** → evitare. |
| **ElevenLabs** | tier free piccolo | ❌ free = attribuzione/non comm. | ✅ API | Qualità top, ma per commerciale serve **pagamento**. |
| OpenAI/Google/Azure TTS | ❌ | ✅ | ✅ API | Solo a pagamento (con credito iniziale). |
**Verdetto voce**: **GRATIS e commercial-safe = Piper** (CPU, self-host). edge-tts per i test.

### 🎬 Short verticali "faceless" (script → short con b-roll + sottotitoli)
Qui **non serve un tool a pagamento**: lo **assembliamo noi via codice** con pezzi gratis.
| Pezzo | Strumento gratis | Commerciale | Note |
|---|---|---|---|
| Voce | Piper (sopra) | ✅ | |
| B-roll (clip video) | **Pexels API** / **Pixabay API** | ✅ libero | Key gratuita, enormi librerie finanza/astratto |
| I nostri visual | **screen recording della Demo** | ✅ (è nostro) | il contenuto migliore |
| Sottotitoli | **Whisper** (open-source) | ✅ | trascrive la voce → SRT, gira su CPU |
| Montaggio | **FFmpeg** / **MoviePy** | ✅ | unisce clip+voce+sottotitoli+logo |
**Verdetto short**: ✅ **100% gratis e automatizzabile** (Piper + Pexels/Pixabay + Whisper + FFmpeg).

### 🖼️ Caroselli e grafiche con TESTO
Gli image-gen AI **scrivono male il testo** e costano. Soluzione migliore e gratis:
generarli **via HTML/CSS col nostro brand → screenshot con Chrome headless** (lo facciamo
già!). Testo perfetto, on-brand, riproducibile, **costo zero**.
**Verdetto caroselli**: ✅ **gratis e perfetto** (template HTML + screenshot), nessuna AI.

### 🎨 Immagini "creative" (sfondi/scene generate)
| Opzione | Gratis? | Commerciale | API |
|---|---|---|---|
| **Pollinations.ai** | ✅ no key | ⚠️ da verificare | ✅ | Gratis ma qualità/licenza variabili |
| **Stable Diffusion/FLUX self-host** | ✅ | ✅ (modelli open) | ✅ | Vuole **GPU** (su CPU lentissimo) |
| Hugging Face Inference | tier free | dipende | ✅ | rate-limit stretto |
| Midjourney / DALL·E | ❌ | ✅ | MJ no API ufficiale | a pagamento |
**Verdetto immagini**: per il brand bastano i **caroselli HTML** (sopra) + **stock Pexels**.
Le immagini AI generate sono **opzionali** e, se gratis, richiedono GPU o hanno limiti.

### 🗣️ Video con PRESENTATORE (avatar talking-head)
| Opzione | Gratis? | Commerciale | API |
|---|---|---|---|
| **HeyGen / Synthesia / D-ID** | ❌ (web free limitato) | ✅ | ✅ ma **API a pagamento** |
| **SadTalker / Wav2Lip** (open-source) | ✅ self-host | ✅ | ✅ | richiede **GPU**, setup, qualità inferiore |
| **La tua faccia** (registri tu) | ✅ | ✅ | — | zero costo, massima autenticità |
**Verdetto avatar**: ⚠️ **è l'unico pezzo difficile da fare gratis+automatico** senza GPU.
→ All'inizio: **niente avatar AND** (usa short faceless + screen Demo + eventualmente la tua
faccia). L'avatar AI lo aggiungi dopo con HeyGen (pagamento) o self-host se avrai una GPU.

### 🎵 Musica
**Pixabay Music / YouTube Audio Library** = royalty-free, gratis, uso commerciale. Si scarica
una cartella di tracce e si riusano. (Generazione AI come MusicGen = self-host/GPU, non serve.)

---

## 2. Il vincolo vero: la POTENZA DI CALCOLO
- Girano bene su **CPU** (quindi anche sulla VPS attuale): **Piper, edge-tts, Pexels/Pixabay,
  Whisper, FFmpeg/MoviePy, caroselli HTML**. → tutta la parte "short + caroselli + voce".
- Vogliono **GPU**: Stable Diffusion/FLUX (immagini AI), SadTalker/Wav2Lip (avatar). → li
  lasciamo fuori dalla pipeline gratis iniziale.
- ⚠️ La generazione video è pesante: meglio farla con uno **script separato on-demand** (non
  sul processo dell'app), o sul tuo PC, per non rubare risorse alla dashboard.

---

## 3. L'architettura proposta (gratis, CPU, commercial-safe)

```
                 ┌──────────────────────────────────────────────┐
  INPUT          │  Gli script che ho già scritto:              │
                 │  VIDEO_SCRIPT.md (VO) · POST_SOCIAL.md (testi)│
                 └───────────────────────┬──────────────────────┘
                                         ▼
  SHORT FACELESS   Piper (voce) → Pexels/Pixabay (b-roll) + screen Demo
  (100% gratis)    → Whisper (sottotitoli) → FFmpeg/MoviePy (montaggio+logo)
                   → output MP4 9:16 con caption e disclaimer a schermo
                                         ▼
  CAROSELLI        testo (POST_SOCIAL) → template HTML brand → Chrome screenshot
  (100% gratis)    → PNG 4:5 pronte (cover + slide)
                                         ▼
  VOCE STANDALONE  Piper → MP3 (per i tuoi screen recording)
                                         ▼
  MUSICA           cartella tracce royalty-free (Pixabay) → mix in FFmpeg
                                         ▼
  [MANUALE/PAGAM.] Avatar talking-head → HeyGen (a pagamento) o la tua faccia
```

### Cosa copre GRATIS la pipeline
✅ Short verticali (TikTok/Reels/Shorts) · ✅ Caroselli IG/FB · ✅ Speakerati/voci ·
✅ Sottotitoli automatici · ✅ Musica royalty-free · ✅ Multilingua (Piper/Whisper supportano
più lingue → stessi short in EN/FR/ES).
### Cosa resta fuori (per ora)
⚠️ Video con avatar AI parlante → manuale (tua faccia) o HeyGen a pagamento.

---

## 4. Cosa mi servirà da te (tutto con tier gratuito)
- **Pexels API key** (gratis, registrazione) — b-roll video/foto.
- **Pixabay API key** (gratis) — b-roll + musica.
- *(opzionale)* **ElevenLabs free key** se vuoi voci più espressive dei test (ma per il
  commerciale meglio Piper, gratis).
- Niente chiavi a pagamento per la pipeline base.

## 5. Raccomandazione
1. **Costruiamo la pipeline gratis CPU** per **short + caroselli + voce + sottotitoli**:
   copre la stragrande maggioranza del fabbisogno, a costo zero, automatizzata.
2. **Avatar video**: per ora **manuale** (faceless o tua faccia). Aggiungiamo HeyGen
   (pagamento) o self-host GPU **solo se** serve davvero.
3. Se la pipeline si rivelasse troppo onerosa da girare sulla VPS, ripieghiamo sul **batch
   "tool-ready"** ([PROMPT_PACK.md](PROMPT_PACK.md)) — stesso risultato, incollando a mano.

> In sintesi: **una pipeline automatica GRATIS è fattibile per ~90% dei contenuti**
> (short faceless, caroselli, voce, sottotitoli, multilingua) con open-source + API gratuite
> su CPU. L'unico pezzo realmente "a pagamento o GPU" è l'**avatar parlante** — che all'inizio
> possiamo evitare.

---

### Collegato a
- Script da dare in pasto alla pipeline → [VIDEO_SCRIPT.md](VIDEO_SCRIPT.md) · [POST_SOCIAL.md](POST_SOCIAL.md)
- Alternativa manuale → [PROMPT_PACK.md](PROMPT_PACK.md) · Compliance → [../10_COMPLIANCE_DISCLAIMER.md](../10_COMPLIANCE_DISCLAIMER.md)
