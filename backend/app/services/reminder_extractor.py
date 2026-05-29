from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from app.services.llm_client import call_llm
from app.core.logging import get_logger

logger = get_logger(__name__)

JAKARTA_TZ = ZoneInfo("Asia/Jakarta")


async def extract_reminder(
    user_message: str, existing_context: str | None = None, has_media: bool = False
) -> dict:
    """Call cheap LLM to extract reminder intent from user message.

    Returns:
        {"has_reminder": False} if no reminder detected.
        {"has_reminder": True, "title": str, "fire_at": datetime (UTC),
         "recurrence": str|None, "description": str} otherwise.
    """
    now_jakarta = datetime.now(JAKARTA_TZ)
    now_iso = now_jakarta.isoformat()
    weekday_names = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
    today_name = weekday_names[now_jakarta.weekday()]

    context_block = ""
    if existing_context:
        context_block = f"\nKonteks tambahan:\n{existing_context}\n"
    media_block = "\nUser mengirim gambar bersama pesan/caption ini. Jika caption meminta reminder, buat reminder dengan title dari caption.\n" if has_media else ""

    prompt = f"""Kamu adalah parser reminder. Analisis pesan user dan tentukan apakah ada intent untuk membuat reminder/pengingat.

Waktu sekarang: {now_iso} (WIB / Asia/Jakarta)
Hari ini: {today_name}
Timezone: Asia/Jakarta (UTC+7)

Pesan user: {user_message}{context_block}
{media_block}

Tugas:
1. Deteksi apakah user ingin membuat reminder/pengingat
2. Parse waktu dari ekspresi Indonesia (contoh: "besok jam 9 pagi", "nanti jam 3 sore", "setiap hari jam 8 pagi", "senin depan jam 10", "1 jam lagi", "setiap minggu jam 9 pagi")
3. Konversi ke UTC (kurangi 7 jam dari WIB)

Return JSON saja, format:
{{"has_reminder": true/false}}

Jika has_reminder true, tambahkan:
{{"has_reminder": true, "title": "judul singkat reminder", "fire_at": "ISO datetime UTC", "recurrence": null/"daily"/"weekly"/"monthly", "description": "deskripsi opsional atau null"}}

Aturan:
- fire_at harus dalam format ISO 8601 UTC (akhiri Z)
- CRITICAL: Untuk waktu relatif ("X menit/jam lagi"), HITUNG dari waktu sekarang yang diberikan di atas. Contoh: jika sekarang 15:58 WIB dan user bilang "5 menit lagi", maka fire_at = 16:03 WIB = 09:03 UTC.
- JANGAN tebak waktu — selalu hitung berdasarkan "Waktu sekarang" di atas
- jam 1-12 tanpa AM/PM: konteks "pagi"=siang(06-11), "siang"=(11-14), "sore"=(14-17), "malam"=(18-23/0-5)
- "besok" = hari berikutnya
- "nanti" = hari ini (jika waktu sudah lewat, pindah ke besok)
- "setiap hari" = recurrence "daily"
- "setiap minggu" / "tiap [hari]" = recurrence "weekly"
- "setiap bulan" = recurrence "monthly"
- Jika tidak ada intent reminder, return {{"has_reminder": false}}
- HANYA return JSON, tidak ada teks lain"""

    try:
        messages = [{"role": "user", "content": prompt}]
        reply = await call_llm(messages, model_key="fallback")

        # Parse JSON from reply
        reply = reply.strip()
        if reply.startswith("```json"):
            reply = reply[7:]
        elif reply.startswith("```"):
            reply = reply[3:]
        if reply.endswith("```"):
            reply = reply[:-3]
        reply = reply.strip()

        data = json.loads(reply)

        if not data.get("has_reminder"):
            return {"has_reminder": False}

        fire_at_str = data.get("fire_at")
        if not fire_at_str:
            logger.warning("reminder_extractor_missing_fire_at", data=data)
            return {"has_reminder": False}

        # Parse fire_at to UTC datetime
        fire_at = _parse_iso_datetime(fire_at_str)

        # Validate: if fire_at is in the past, it's likely a parsing error
        now_utc = datetime.now(timezone.utc)
        if fire_at < now_utc:
            logger.warning("reminder_extractor_fire_at_in_past", fire_at=fire_at_str, now_utc=now_utc.isoformat())
            # If the LLM gave a past time, it likely mis-parsed a relative expression.
            # Reset to now + 5 minutes as safe default (better than silently sending immediately)
            fire_at = now_utc + timedelta(minutes=5)
            logger.info("reminder_extractor_corrected", corrected_fire_at=fire_at.isoformat())

        recurrence = data.get("recurrence")
        if recurrence and recurrence not in ("daily", "weekly", "monthly"):
            logger.warning("reminder_extractor_invalid_recurrence", recurrence=recurrence)
            recurrence = None

        return {
            "has_reminder": True,
            "title": data.get("title", "Reminder"),
            "fire_at": fire_at,
            "recurrence": recurrence,
            "description": data.get("description"),
        }

    except Exception as e:
        logger.error("reminder_extractor_failed", error=str(e), user_message=user_message[:200])
        return {"has_reminder": False}


def _parse_iso_datetime(s: str) -> datetime:
    """Parse ISO datetime string to timezone-aware UTC datetime."""
    s = s.strip()
    # Handle trailing Z
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    # If naive, assume UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    # Convert to UTC
    return dt.astimezone(timezone.utc)
