import os
import json
import asyncio
from pathlib import Path
from datetime import datetime

LOG_PATH = os.getenv(
    "EA_LOG_PATH",
    str(
        Path.home()
        / ".wine/drive_c/users/pietro_giacobazzi/AppData/Roaming/MetaQuotes/Terminal/Common/Files/papp_ea_log.jsonl"
    ),
)


class LogTailer:
    """Legge TUTTI i file 'papp_ea_*.jsonl' nella cartella Common\\Files.

    Ogni EA scrive il PROPRIO file (papp_ea_<SIMBOLO>.jsonl): così più EA non si
    sovrascrivono a vicenda (la scrittura concorrente su un file condiviso perdeva
    righe e disallineava l'offset). Ogni file ha il suo offset indipendente.
    """

    PATTERN = "papp_ea_*.jsonl"

    def __init__(self, on_signal_callback):
        self.dir = Path(LOG_PATH).parent
        self.callback = on_signal_callback
        self._pos: dict[str, int] = {}     # path file -> offset in byte
        self._running = False

    def _files(self):
        try:
            return sorted(self.dir.glob(self.PATTERN))
        except Exception:
            return []

    async def _process_file(self, p):
        key = str(p)
        start = self._pos.get(key, 0)          # file mai visto -> leggi da capo
        size = p.stat().st_size
        if size < start:                       # troncato/ruotato: riparti da capo
            start = 0
        if size <= start:
            self._pos[key] = size
            return
        # Lettura binaria: il log MT5 può contenere byte non-UTF8; errors="replace".
        with open(p, "rb") as f:
            f.seek(start)
            chunk = f.read(size - start)
        nl = chunk.rfind(b"\n")
        if nl == -1:
            return                             # nessuna riga completa: ritenta dopo
        complete = chunk[: nl + 1]
        self._pos[key] = start + len(complete)
        text = complete.decode("utf-8", errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                data["t"] = datetime.fromtimestamp(data.get("t", 0))
                await self.callback(data)
            except json.JSONDecodeError:
                pass
            except Exception:
                # un singolo segnale malformato non blocca il tailer
                pass

    async def start(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        self._running = True
        # parti dalla FINE dei file gia' esistenti (non re-ingerire lo storico);
        # i file che compaiono dopo l'avvio vengono letti da capo.
        for p in self._files():
            try:
                self._pos[str(p)] = p.stat().st_size
            except Exception:
                self._pos[str(p)] = 0
        while self._running:
            try:
                for p in self._files():
                    try:
                        await self._process_file(p)
                    except Exception:
                        pass
            except Exception:
                pass
            await asyncio.sleep(0.5)

    def stop(self):
        self._running = False
