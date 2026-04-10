"""Central notification dispatch — dedup across all channels (push, Discord, etc.).

Every notification goes through this service. It fingerprints the content and
only dispatches when the data has actually changed since the last notification
for the same channel + symbol on the same trading day (ET).

Channels:
  - "push"    : APNs VoIP + alert push (handled by notifier.py)
  - "discord" : Discord channel embeds (handled by bot tasks.py)
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from trader_api.models import (
    DeviceRegistration,
    NotificationDigest,
)

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")


def _today_et() -> str:
    """Current trading day as YYYY-MM-DD in ET."""
    return datetime.now(ET).strftime("%Y-%m-%d")


def action_fingerprint(action: dict[str, Any]) -> str:
    """Generate a SHA-256 fingerprint for an action dict.

    Includes all fields that, if changed, warrant a new notification:
    type, symbol, signal, score, strength, reason, shares, urgency.
    """
    parts = [
        action.get("type", ""),
        action.get("symbol", "") or action.get("sell_symbol", ""),
        action.get("signal", ""),
        str(action.get("score", "")),
        str(int((action.get("strength", 0) or 0) * 100)),
        action.get("reason", ""),
        str(action.get("shares", "")),
        action.get("urgency", ""),
    ]
    # For swaps, include buy side too
    if action.get("type") == "SWAP":
        parts.extend([
            action.get("buy_symbol", ""),
            str(action.get("buy_score", "")),
        ])
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()


def signal_fingerprint(
    symbol: str,
    signal: str,
    strength: float,
    score: float,
) -> str:
    """Fingerprint for a raw signal (used by high-confidence push alerts)."""
    parts = [symbol, signal, str(int(strength * 100)), str(score)]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


class NotificationDispatcher:
    """Central dedup + dispatch for all notification channels."""

    async def is_new(
        self,
        db: AsyncSession,
        channel: str,
        symbol: str,
        fingerprint: str,
    ) -> bool:
        """Check if this notification is new or changed since last send today."""
        today = _today_et()
        result = await db.execute(
            select(NotificationDigest).where(
                and_(
                    NotificationDigest.channel == channel,
                    NotificationDigest.symbol == symbol,
                    NotificationDigest.trading_day == today,
                )
            )
        )
        prev = result.scalar_one_or_none()
        if prev is None:
            return True  # Never sent today
        return prev.fingerprint != fingerprint  # Changed

    async def record(
        self,
        db: AsyncSession,
        channel: str,
        symbol: str,
        fingerprint: str,
    ) -> None:
        """Record that a notification was sent (upsert for today)."""
        today = _today_et()
        now = datetime.now(UTC)
        result = await db.execute(
            select(NotificationDigest).where(
                and_(
                    NotificationDigest.channel == channel,
                    NotificationDigest.symbol == symbol,
                    NotificationDigest.trading_day == today,
                )
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.fingerprint = fingerprint
            existing.sent_at = now
        else:
            db.add(NotificationDigest(
                channel=channel,
                symbol=symbol,
                fingerprint=fingerprint,
                trading_day=today,
                sent_at=now,
            ))

    async def filter_new_actions(
        self,
        db: AsyncSession,
        channel: str,
        actions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Return only actions whose content has changed since last notification today."""
        new_actions = []
        for action in actions:
            sym = action.get("symbol") or action.get("sell_symbol") or ""
            fp = action_fingerprint(action)
            if await self.is_new(db, channel, sym, fp):
                new_actions.append(action)
        return new_actions

    async def record_actions(
        self,
        db: AsyncSession,
        channel: str,
        actions: list[dict[str, Any]],
    ) -> None:
        """Record that these actions were sent."""
        for action in actions:
            sym = action.get("symbol") or action.get("sell_symbol") or ""
            fp = action_fingerprint(action)
            await self.record(db, channel, sym, fp)
        await db.commit()

    async def dispatch_push_signals(
        self,
        db: AsyncSession,
        recs: dict[str, Any],
        config: dict[str, Any],
    ) -> None:
        """Send push notifications for high-confidence signals, with dedup.

        Replaces Strategy.notify_high_confidence_signals().
        """
        from trader_api.deps import get_notifier

        notifier = get_notifier()
        if notifier is None or not notifier.is_configured:
            return

        from sqlalchemy import or_

        notif_config = config.get("notifications", {})
        min_strength = notif_config.get("min_strength", 0.70)

        # Collect strong signals
        strong: list[dict[str, Any]] = []
        for sig in recs.get("buys", []):
            s = sig if isinstance(sig, dict) else sig.__dict__
            strength = s.get("strength", 0)
            if strength >= min_strength:
                strong.append({
                    "symbol": s.get("symbol", ""),
                    "signal": "BUY",
                    "strength": strength,
                    "score": s.get("score", 0),
                })
        for sig in recs.get("sells", []):
            s = sig if isinstance(sig, dict) else sig.__dict__
            strength = s.get("strength", 0)
            if strength >= min_strength:
                strong.append({
                    "symbol": s.get("symbol", ""),
                    "signal": "SELL",
                    "strength": strength,
                    "score": s.get("score", 0),
                })

        if not strong:
            return

        today = datetime.now(UTC).strftime("%Y-%m-%d")

        # Fetch enabled devices not muted today
        result = await db.execute(
            select(DeviceRegistration).where(
                DeviceRegistration.enabled.is_(True),
                or_(
                    DeviceRegistration.daily_disabled_date.is_(None),
                    DeviceRegistration.daily_disabled_date != today,
                ),
            )
        )
        devices = result.scalars().all()
        if not devices:
            return

        for sig_info in strong:
            fp = signal_fingerprint(
                sig_info["symbol"],
                sig_info["signal"],
                sig_info["strength"],
                sig_info["score"],
            )
            # Central dedup — same for all devices
            if not await self.is_new(db, "push", sig_info["symbol"], fp):
                continue

            for device in devices:
                await notifier.notify_signal(
                    db_session_factory=_make_session_factory(),
                    symbol=sig_info["symbol"],
                    signal=sig_info["signal"],
                    strength=sig_info["strength"],
                    score=sig_info["score"],
                    device_token=device.device_token,
                    push_token=device.push_token,
                )

            await self.record(db, "push", sig_info["symbol"], fp)

        await db.commit()


def _make_session_factory():
    """Lazy import to avoid circular deps."""
    from trader_api.database import async_session
    return async_session


# Module-level singleton
_dispatcher: NotificationDispatcher | None = None


def get_dispatcher() -> NotificationDispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = NotificationDispatcher()
    return _dispatcher
