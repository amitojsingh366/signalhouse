"""APNs push notification service — VoIP (signals) and standard alerts (scheduled)."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import jwt

from trader_api.models import NotificationLog

logger = logging.getLogger(__name__)


class APNsNotifier:
    """Sends VoIP push notifications via Apple Push Notification service."""

    APNS_PROD = "https://api.push.apple.com"
    APNS_SANDBOX = "https://api.sandbox.push.apple.com"
    JWT_ALGORITHM = "ES256"
    JWT_LIFETIME = 3600  # 1 hour

    def __init__(
        self,
        key_path: str,
        key_id: str,
        team_id: str,
        bundle_id: str,
        sandbox: bool = False,
        retry_delay: int = 30,
        max_retries: int = 1,
        cooldown_minutes: int = 60,
    ):
        self.key_id = key_id
        self.team_id = team_id
        self.bundle_id = bundle_id
        self.base_url = self.APNS_SANDBOX if sandbox else self.APNS_PROD
        self.retry_delay = retry_delay
        self.max_retries = max_retries
        self.cooldown_minutes = cooldown_minutes

        # Load the .p8 private key
        key_file = Path(key_path)
        if key_file.exists():
            self._private_key = key_file.read_text()
            logger.info("APNs notifier initialized (key: %s)", key_path)
        else:
            self._private_key = ""
            logger.warning("APNs key not found at %s — notifications disabled", key_path)

        self._jwt_token: str = ""
        self._jwt_expires: float = 0

        self._client: httpx.AsyncClient | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self._private_key and self.key_id and self.team_id)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(http2=True, timeout=30.0)
        return self._client

    def _get_jwt(self) -> str:
        """Get or refresh the APNs JWT token."""
        now = time.time()
        if self._jwt_token and now < self._jwt_expires - 60:
            return self._jwt_token

        payload = {
            "iss": self.team_id,
            "iat": int(now),
        }
        self._jwt_token = jwt.encode(
            payload,
            self._private_key,
            algorithm=self.JWT_ALGORITHM,
            headers={"kid": self.key_id},
        )
        self._jwt_expires = now + self.JWT_LIFETIME
        return self._jwt_token

    async def _send_push(
        self,
        device_token: str,
        payload: dict[str, Any],
        *,
        push_type: str = "voip",
    ) -> bool:
        """Send a push notification. push_type is 'voip' or 'alert'."""
        if not self.is_configured:
            logger.debug("APNs not configured, skipping push")
            return False

        client = await self._get_client()
        url = f"{self.base_url}/3/device/{device_token}"
        token = self._get_jwt()

        topic = (
            f"{self.bundle_id}.voip" if push_type == "voip" else self.bundle_id
        )
        headers = {
            "authorization": f"bearer {token}",
            "apns-topic": topic,
            "apns-push-type": push_type,
            "apns-priority": "10",
            "apns-expiration": "0",
        }

        try:
            response = await client.post(
                url,
                content=json.dumps(payload),
                headers=headers,
            )
            if response.status_code == 200:
                logger.info(
                    "%s push sent to %s…%s: %s",
                    push_type,
                    device_token[:8],
                    device_token[-4:],
                    payload.get("caller_name")
                    or payload.get("aps", {}).get("alert", {}).get("title", "?"),
                )
                return True
            else:
                body = response.text
                logger.warning(
                    "APNs rejected push (%d): %s", response.status_code, body
                )
                return False
        except Exception:
            logger.exception("Failed to send %s push", push_type)
            return False

    async def send_voip_push(
        self, device_token: str, payload: dict[str, Any]
    ) -> bool:
        """Send a VoIP push notification to a device. Returns True if accepted."""
        return await self._send_push(device_token, payload, push_type="voip")

    async def send_alert_push(
        self,
        push_token: str,
        *,
        title: str,
        body: str,
        category: str = "general",
        data: dict[str, Any] | None = None,
    ) -> bool:
        """Send a standard alert push notification. Returns True if accepted."""
        payload: dict[str, Any] = {
            "aps": {
                "alert": {"title": title, "body": body},
                "sound": "default",
                "category": category,
            },
        }
        if data:
            payload.update(data)
        return await self._send_push(push_token, payload, push_type="alert")

    async def notify_signal(
        self,
        db_session_factory: Any,
        symbol: str,
        signal: str,
        strength: float,
        score: float,
        device_token: str,
    ) -> None:
        """Build and send a VoIP push for a trading signal, with retry logic."""
        strength_pct = int(strength * 100)
        caller_name = f"{signal} {symbol} {strength_pct}%"

        call_uuid = str(uuid.uuid4())
        payload = {
            "aps": {},
            "uuid": call_uuid,
            "caller_name": caller_name,
            "symbol": symbol,
            "signal": signal,
            "strength": strength,
            "score": f"{score}/9",
            "handle": "trader-signal",
        }

        # Log to DB
        async with db_session_factory() as db:
            log_entry = NotificationLog(
                device_token=device_token,
                symbol=symbol,
                signal=signal,
                strength=strength,
                caller_name=caller_name,
                delivered=False,
                acknowledged=False,
                retry_count=0,
            )
            db.add(log_entry)
            await db.commit()
            await db.refresh(log_entry)
            notification_id = log_entry.id

        # Add notification_id to payload so iOS app can acknowledge
        payload["notification_id"] = notification_id

        delivered = await self.send_voip_push(device_token, payload)

        # Update delivery status
        async with db_session_factory() as db:
            log_entry = await db.get(NotificationLog, notification_id)
            if log_entry:
                log_entry.delivered = delivered
                await db.commit()

        # Schedule retry if not acknowledged
        if delivered and self.max_retries > 0:
            asyncio.create_task(
                self._retry_if_needed(
                    db_session_factory,
                    notification_id,
                    device_token,
                    payload,
                )
            )

    async def _retry_if_needed(
        self,
        db_session_factory: Any,
        notification_id: int,
        device_token: str,
        payload: dict[str, Any],
    ) -> None:
        """Wait, then retry once if the notification wasn't acknowledged."""
        await asyncio.sleep(self.retry_delay)

        async with db_session_factory() as db:
            log_entry = await db.get(NotificationLog, notification_id)
            if not log_entry or log_entry.acknowledged:
                return  # User already answered or log disappeared

            if log_entry.retry_count >= self.max_retries:
                return  # Already retried enough

            log_entry.retry_count += 1
            delivered = await self.send_voip_push(device_token, payload)
            log_entry.delivered = delivered
            await db.commit()

            logger.info(
                "Retry %d for notification %d (%s): %s",
                log_entry.retry_count,
                notification_id,
                payload.get("caller_name", "?"),
                "delivered" if delivered else "failed",
            )

    async def notify_scheduled(
        self,
        db_session_factory: Any,
        *,
        notification_type: str,
        title: str,
        body: str,
        category: str,
    ) -> int:
        """Send a standard alert push to all enabled devices. Returns count sent."""
        from datetime import UTC, datetime

        from sqlalchemy import or_, select

        from trader_api.models import DeviceRegistration

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        sent = 0

        async with db_session_factory() as db:
            result = await db.execute(
                select(DeviceRegistration).where(
                    DeviceRegistration.enabled.is_(True),
                    DeviceRegistration.push_token.isnot(None),
                    or_(
                        DeviceRegistration.daily_disabled_date.is_(None),
                        DeviceRegistration.daily_disabled_date != today,
                    ),
                )
            )
            devices = result.scalars().all()

            for device in devices:
                log_entry = NotificationLog(
                    device_token=device.push_token,
                    notification_type=notification_type,
                    symbol="",
                    signal="",
                    strength=0.0,
                    caller_name=title,
                    delivered=False,
                    acknowledged=False,
                    retry_count=0,
                )
                db.add(log_entry)
                await db.commit()
                await db.refresh(log_entry)

                delivered = await self.send_alert_push(
                    device.push_token,
                    title=title,
                    body=body,
                    category=category,
                    data={"notification_type": notification_type},
                )
                log_entry.delivered = delivered
                await db.commit()
                if delivered:
                    sent += 1

        logger.info("Scheduled push [%s] sent to %d devices", notification_type, sent)
        return sent

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
