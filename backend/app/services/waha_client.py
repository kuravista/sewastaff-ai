import asyncio
import base64
from typing import Any

import httpx
from app.core.config import settings
from app.core.logging import get_logger

from app.services import telegram_notifier

logger = get_logger(__name__)


class WAHAClient:
    def __init__(self):
        self.base_url = settings.WAHA_BASE_URL
        self.api_key = settings.WAHA_API_KEY
        self.headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
        }

    async def send_text(
        self, session_id: str, group_id: str, text: str
    ) -> bool:
        url = f"{self.base_url}/api/sendText"
        payload = {
            "chatId": group_id,
            "text": text,
            "session": session_id,
        }

        for attempt in range(3):
            logger.info(
                "waha_send_start",
                session_id=session_id,
                group_id=group_id,
                attempt=attempt + 1,
            )
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        url, json=payload, headers=self.headers
                    )
                    resp.raise_for_status()
                logger.info(
                    "waha_send_success",
                    session_id=session_id,
                    group_id=group_id,
                    attempt=attempt + 1,
                )
                return True
            except Exception as e:
                logger.error(
                    "waha_send_failure",
                    session_id=session_id,
                    group_id=group_id,
                    attempt=attempt + 1,
                    error=str(e),
                )
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)

        # 3 failures → dead letter
        await telegram_notifier.alert_send_dead_letter(
            event_id=session_id, group_id=group_id
        )
        return False

    async def get_session_status(self, session_id: str) -> dict[str, Any]:
        url = f"{self.base_url}/api/sessions/{session_id}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers=self.headers)
                resp.raise_for_status()
                data = resp.json()
            return {"engine_state": data.get("status", "UNKNOWN")}
        except Exception as e:
            logger.error(
                "waha_session_status_error",
                session_id=session_id,
                error=str(e),
            )
            return {"engine_state": "ERROR"}

    async def download_media(self, media_url: str) -> bytes:
        media_url = media_url.replace("localhost:3000", "app-waha-1:3000")
        media_url = media_url.replace("http://localhost", "http://app-waha-1")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(media_url, headers=self.headers)
            resp.raise_for_status()
            return resp.content

    async def send_image(
        self,
        session_id: str,
        group_id: str,
        image_data: bytes,
        caption: str,
        mimetype: str = "image/jpeg",
        filename: str = "reminder.jpg",
    ) -> bool:
        url = f"{self.base_url}/api/sendImage"
        payload = {
            "chatId": group_id,
            "session": session_id,
            "caption": caption,
            "file": {
                "mimetype": mimetype or "image/jpeg",
                "filename": filename,
                "data": base64.b64encode(image_data).decode(),
            },
        }

        for attempt in range(3):
            logger.info("waha_send_image_start", session_id=session_id, group_id=group_id, attempt=attempt + 1)
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(url, json=payload, headers=self.headers)
                    resp.raise_for_status()
                logger.info("waha_send_image_success", session_id=session_id, group_id=group_id, attempt=attempt + 1)
                return True
            except Exception as e:
                logger.error("waha_send_image_failure", session_id=session_id, group_id=group_id, attempt=attempt + 1, error=str(e))
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)

        await telegram_notifier.alert_send_dead_letter(event_id=session_id, group_id=group_id)
        return False

    # ── Group management ───────────────────────────────────────────

    async def join_group(self, invite_code: str, session_id: str = "default") -> dict[str, Any]:
        """Join a WhatsApp group via invite code/link. Returns WAHA response with group info."""
        # WAHA docs: POST /api/{session}/groups/join with {"code": "invite_code_or_full_link"}
        url = f"{self.base_url}/api/{session_id}/groups/join"
        payload = {"code": invite_code}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload, headers=self.headers)
                resp.raise_for_status()
                data = resp.json()
            logger.info("waha_join_group_success", invite_code=invite_code)
            return data
        except httpx.HTTPStatusError as e:
            logger.error(
                "waha_join_group_http_error",
                invite_code=invite_code,
                status_code=e.response.status_code,
                body=e.response.text,
            )
            raise
        except Exception as e:
            logger.error("waha_join_group_error", invite_code=invite_code, error=str(e))
            raise

    async def get_group_info(self, group_id: str, session_id: str = "default") -> dict[str, Any]:
        """Get group details from WAHA."""
        url = f"{self.base_url}/api/{session_id}/groups/{group_id}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers=self.headers)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error("waha_get_group_info_error", group_id=group_id, error=str(e))
            raise

    async def leave_group(self, group_id: str, session_id: str = "default") -> dict[str, Any]:
        """Leave a WhatsApp group."""
        url = f"{self.base_url}/api/{session_id}/groups/{group_id}/leave"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, headers=self.headers)
                resp.raise_for_status()
                return resp.json() if resp.content else {}
        except Exception as e:
            logger.error("waha_leave_group_error", group_id=group_id, error=str(e))
            raise


waha_client = WAHAClient()
