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
    def __init__(self, on_signal_callback):
        self.path = Path(LOG_PATH)
        self.callback = on_signal_callback
        self._pos = 0
        self._running = False

    async def start(self):
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.touch()
        self._running = True
        self._pos = self.path.stat().st_size
        while self._running:
            try:
                size = self.path.stat().st_size
                if size > self._pos:
                    with open(self.path, "r") as f:
                        f.seek(self._pos)
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    data = json.loads(line)
                                    data["t"] = datetime.fromtimestamp(
                                        data.get("t", 0)
                                    )
                                    await self.callback(data)
                                except json.JSONDecodeError:
                                    pass
                    self._pos = size
            except Exception:
                pass
            await asyncio.sleep(0.5)

    def stop(self):
        self._running = False
