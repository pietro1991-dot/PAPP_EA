# Pipeline contenuti — generazione automatica (gratis, CPU)

Genera **caroselli**, **voci** e **short verticali** on-brand via codice. Tutto gratis
e su CPU (nessuna GPU). I mattoni base **non richiedono chiavi**; Pexels (b-roll) è un
upgrade opzionale. Analisi completa dello stack in
[../marketing/contenuti/PIPELINE_AUTOMATICA.md](../marketing/contenuti/PIPELINE_AUTOMATICA.md).

## Requisiti
- **Chrome** (`google-chrome-stable`) e **ffmpeg/ffprobe** → già presenti sulla VPS.
- Un **venv** per i pacchetti Python:
  ```bash
  cd pipeline
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
  ```

## I 3 mattoni

### 1) Voce — `voiceover.py`  (nessuna chiave)
```bash
.venv/bin/python voiceover.py "Testo da leggere" output/voce.mp3 --voice it-IT-DiegoNeural
.venv/bin/python voiceover.py --file script.txt output/voce.mp3 --lang it
```
- Default: **edge-tts** (gratis, voci IT/EN/FR/ES). Per uso commerciale intensivo →
  imposta `VOICE_PROVIDER=piper` + `PIPER_BIN`/`PIPER_MODEL` (open-source, commercial-safe).

### 2) Caroselli — `carousels.py`  (nessuna chiave)
```bash
.venv/bin/python carousels.py            # esempio "12 domande"
.venv/bin/python carousels.py mio.json   # {"slug":"..","slides":[{"type":"cover|content|cta","eyebrow":"..","title":"..","body":".."}]}
```
→ PNG 1080×1350 (4:5) in `output/<slug>/`. Testo dei caroselli pronti in
[../marketing/contenuti/POST_SOCIAL.md](../marketing/contenuti/POST_SOCIAL.md).

### 3) Short verticali — `short.py`  (nessuna chiave; Pexels opzionale)
```bash
.venv/bin/python short.py                # esempio "anti-truffa"
.venv/bin/python short.py mio.json       # {"slug":"..","lang":"it","lines":["hook","riga","..","cta"]}
```
→ MP4 **1080×1920** in `output/short_<slug>.mp4`: voce AI + frame brand + disclaimer.
- **Upgrade b-roll Pexels** (opzionale): esporta `PEXELS_API_KEY` (gratis) e lo sfondo
  userà clip video reali. Senza chiave → sfondo brand (già ottimo).

## Multilingua
`--lang en|fr|es` (voce) e traduci le `lines`/`slides` → stessi contenuti in 4 lingue.

## Dove prendere i testi
- Short/VSL: [../marketing/contenuti/VIDEO_SCRIPT.md](../marketing/contenuti/VIDEO_SCRIPT.md)
- Post/caroselli: [../marketing/contenuti/POST_SOCIAL.md](../marketing/contenuti/POST_SOCIAL.md)
- Calendario: [../marketing/contenuti/README.md](../marketing/contenuti/README.md)

## Output
Tutto in `pipeline/output/` (ignorato da git — sono file generati).

## Cosa NON copre (per scelta)
- **Avatar parlante** (talking-head): serve HeyGen (pagamento) o GPU self-host. All'inizio
  si usano short faceless + screen recording della Demo. Vedi l'analisi nel doc pipeline.
