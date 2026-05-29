import os
import httpx

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

async def get_embedding(text: str) -> list[float]:
    """Get embedding vector for text via OpenRouter."""
    if not text or not text.strip():
        return []
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/embeddings",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            json={"model": "openai/text-embedding-3-small", "input": text[:2000]}
        )
        if resp.status_code == 200:
            data = resp.json()
            return data["data"][0]["embedding"]
        return []
