import asyncio
import json
import os
import re
from typing import Optional

ATTACH_URL = os.getenv("ATTACH_URL", "http://127.0.0.1:34367")
USERNAME = os.getenv("OPENCODE_USERNAME", "opencode")
PASSWORD = os.getenv("OPENCODE_PASSWORD", "cc006c31-5748-40ae-b659-7081aa0e9ab8")
MODEL = os.getenv("API_MODEL", "opencode/deepseek-v4-flash-free")
WORK_DIR = os.getenv("WORK_DIR", "/home/pietro_giacobazzi/Desktop/PAPP_EA")

SYSTEM_PROMPT = (
    "Sei un assistente esperto di trading algoritmico su MetaTrader 5. "
    "Rispondi in italiano in modo chiaro e conciso. "
    "Usa i dati forniti di pattern, segnali e performance per rispondere. "
    "Se non hai dati sufficienti, dillo onestamente. "
    "Risposte brevi, massimo 3 paragrafi."
)


def build_prompt(question: str, context: Optional[str] = None) -> str:
    prompt = f"{SYSTEM_PROMPT}\n\n"
    if context:
        prompt += f"Contesto:\n{context}\n\n"
    prompt += f"Domanda: {question}\n\nRisposta:"
    return prompt


async def ask(question: str, context: Optional[str] = None) -> str:
    prompt = build_prompt(question, context)
    cmd = [
        "opencode", "run",
        "--attach", ATTACH_URL,
        "-u", USERNAME,
        "-p", PASSWORD,
        "--model", MODEL,
        prompt,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        cwd=WORK_DIR,
    )
    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
    text = stdout.decode("utf-8", errors="replace").strip()
    # Remove ANSI escape sequences
    text = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)
    return text
