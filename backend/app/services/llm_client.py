import asyncio
import time

import httpx
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

MODELS = {
    "primary": "google/gemini-2.5-flash",
    "fallback": "openai/gpt-4o-mini",
}
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


async def call_llm(
    messages: list[dict], model_key: str = "primary"
) -> str:
    model_id = MODELS[model_key]
    logger.info("llm_call_start", model=model_id, model_key=model_key)
    t0 = time.monotonic()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                OPENROUTER_URL,
                json={"model": model_id, "messages": messages},
                headers={
                    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                    "HTTP-Referer": "https://sewastaffai.wuz.web.id",
                    "X-Title": "SewaStaff AI",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        latency = int((time.monotonic() - t0) * 1000)
        tokens = data.get("usage", {}).get("total_tokens", 0)
        logger.info(
            "llm_call_success",
            model=model_id,
            latency_ms=latency,
            tokens=tokens,
        )
        return data["choices"][0]["message"]["content"]

    except Exception as e:
        logger.error(
            "llm_call_failure",
            model=model_id,
            error=str(e),
            fallback_triggered=(model_key == "primary"),
        )
        if model_key == "primary":
            return await call_llm(messages, "fallback")
        raise
