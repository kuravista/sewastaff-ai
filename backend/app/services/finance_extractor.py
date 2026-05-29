import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.logging import get_logger
from app.services.llm_client import call_llm

logger = get_logger(__name__)

JAKARTA_TZ = ZoneInfo("Asia/Jakarta")

def _normalize_amount(amount_str: str) -> int:
    s = amount_str.lower().replace(" ", "").replace(".", "").replace(",", "")
    multiplier = 1
    if "rb" in s or "ribu" in s or "k" in s:
        multiplier = 1000
        s = re.sub(r'rb|ribu|k', '', s)
    elif "jt" in s or "juta" in s or "m" in s:
        multiplier = 1000000
        s = re.sub(r'jt|juta|m', '', s)
    try:
        return int(float(s) * multiplier)
    except ValueError:
        return 0

_QUERY_REGEX = re.compile(
    r"(?i)(pengeluaran|pemasukan|penghasilan|profit|omzet|transaksi|rekap|laporan|saldo|sisa)\s*(hari ini|minggu ini|bulan ini|mei|juni|juli|agustus|september|oktober|november|desember|terbesar|list|brp|berapa|saja)?"
)

async def extract_finance_query(user_message: str) -> dict:
    # Relaxed gatekeeper since listener already checked it
    text = user_message.lower()
    metric = "summary"
    if "pengeluaran" in text:
        metric = "expense_total"
    elif "pemasukan" in text or "omzet" in text or "penghasilan" in text:
        metric = "income_total"
    elif "profit" in text:
        metric = "profit"
    elif "transaksi" in text or "list" in text:
        metric = "list_transactions"
    elif "terbesar" in text or "kategori" in text:
        metric = "top_categories"
    elif "saldo" in text or "sisa" in text:
        metric = "balance"
        
    period = "this_month"
    if "hari ini" in text:
        period = "today"
    elif "minggu ini" in text:
        period = "this_week"
    elif "kemarin" in text:
        period = "yesterday"
    elif "bulan lalu" in text:
        period = "last_month"
        
    # use LLM for more complex parsing
    system_prompt = """You are a financial query extractor for an Indonesian assistant.
Extract the user's intent to view financial data. Return JSON only.
If it's not a financial query, return {"has_query": false}.
If it is, return:
{
  "has_query": true,
  "metric": "expense_total" | "income_total" | "profit" | "summary" | "top_categories" | "list_transactions" | "balance",
  "period": "today" | "this_week" | "this_month" | "last_month" | "custom",
  "category": "category_name_or_null",
  "limit": number_or_10
}"""
    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        response = await call_llm(messages, model_key="fallback")
        # Try to find JSON block
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            if data.get("has_query"):
                return data
    except Exception as e:
        logger.error(f"extract_finance_query error: {e}")
        
    return {"has_query": True, "metric": metric, "period": period, "category": None, "limit": 10}

async def extract_finance_transaction(user_message: str, has_media: bool=False, image_context: str|None=None) -> dict:
    now_jakarta = datetime.now(JAKARTA_TZ)
    now_str = now_jakarta.isoformat()
    
    system_prompt = f"""You are a financial transaction extractor for an Indonesian assistant.
Current time in Jakarta: {now_str}
Extract details from the user's message.
Amounts must be integers (normalize Indonesian shorthand like 50rb=50000, 2 juta=2000000).
If it does NOT contain a transaction to record, return {{"has_transaction": false}}.
Otherwise return ONLY valid JSON:
{{
  "has_transaction": true,
  "tx_type": "income" | "expense" | "transfer" | "adjustment",
  "amount_idr": integer,
  "category": "string like Makanan, Bensin, Iklan, Gaji",
  "merchant": "string or null",
  "description": "string",
  "transaction_date": "ISO UTC datetime string",
  "confidence": float between 0.0 and 1.0,
  "status": "confirmed"
}}"""
    try:
        content = user_message
        if has_media:
            content += f"\n[User attached an image. Additional context: {image_context or 'None'}]"
            
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content}
        ]
        response = await call_llm(messages, model_key="fallback")
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
            if data.get("has_transaction") and "amount_idr" in data:
                if isinstance(data["amount_idr"], str):
                    data["amount_idr"] = _normalize_amount(data["amount_idr"])
                if "transaction_date" not in data:
                    data["transaction_date"] = datetime.utcnow().isoformat()
                return data
    except Exception as e:
        logger.error(f"extract_finance_transaction error: {e}")
        
    return {"has_transaction": False}
