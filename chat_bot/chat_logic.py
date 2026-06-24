import httpx
from typing import Optional
from fastapi.responses import StreamingResponse

OLLAMA_MODEL = "qwen2.5-coder:1.5b"
OLLAMA_URL = "http://localhost:11434/api/generate"

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


async def ask_ollama_stream(question: str, context: Optional[str] = None):
    prompt = build_prompt(question, context)
    async with httpx.AsyncClient(timeout=180) as client:
        async with client.stream(
            "POST",
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": True,
                "options": {"temperature": 0.3, "num_predict": 256},
            },
        ) as r:
            async for line in r.aiter_lines():
                if not line:
                    continue
                try:
                    data = __import__("json").loads(line)
                    chunk = data.get("response", "")
                    if chunk:
                        yield chunk
                except Exception:
                    pass

