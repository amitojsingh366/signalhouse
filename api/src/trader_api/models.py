"""SQLAlchemy ORM models — replaces JSON file storage with PostgreSQL."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from trader_api.database import Base


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    avg_cost: Mapped[float] = mapped_column(Float, nullable=False)
    entry_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(4), nullable=False)  # BUY or SELL
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    total: Mapped[float] = mapped_column(Float, nullable=False)
    pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DailySnapshot(Base):
    __tablename__ = "daily_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    portfolio_value: Mapped[float] = mapped_column(Float, nullable=False)
    cash: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    positions_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class PortfolioMeta(Base):
    """Single-row table for portfolio-level metadata."""

    __tablename__ = "portfolio_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cash: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    initial_capital: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class AppSetting(Base):
    """Persistent runtime-configurable app settings."""

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SignalHistory(Base):
    """Store signal history for backtesting validation."""

    __tablename__ = "signal_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    signal: Mapped[str] = mapped_column(String(4), nullable=False)  # BUY/SELL/HOLD
    strength: Mapped[float] = mapped_column(Float, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reasons: Mapped[str] = mapped_column(Text, nullable=False, default="")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DeviceRegistration(Base):
    """Registered devices for push notifications."""

    __tablename__ = "device_registrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_token: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    push_token: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )  # Standard APNs token (separate from VoIP device_token)
    platform: Mapped[str] = mapped_column(String(10), nullable=False, default="ios")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    daily_disabled_date: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )  # "YYYY-MM-DD" or null
    daily_disabled_notifications_date: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )  # "YYYY-MM-DD" or null; mutes alert notifications for that day
    daily_disabled_calls_date: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )  # "YYYY-MM-DD" or null; mutes VoIP calls for that day
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def notifications_muted_on(self, date: str) -> bool:
        """True if alert notifications are muted for the given YYYY-MM-DD date."""
        if self.daily_disabled_notifications_date is not None:
            return self.daily_disabled_notifications_date == date
        return self.daily_disabled_date == date

    def calls_muted_on(self, date: str) -> bool:
        """True if VoIP call notifications are muted for the given YYYY-MM-DD date."""
        if self.daily_disabled_calls_date is not None:
            return self.daily_disabled_calls_date == date
        return self.daily_disabled_date == date


class NotificationLog(Base):
    """Log of push notifications sent to devices."""

    __tablename__ = "notification_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_token: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    notification_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="signal"
    )  # signal, premarket, briefing, close, recap
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    signal: Mapped[str] = mapped_column(String(4), nullable=False)
    strength: Mapped[float] = mapped_column(Float, nullable=False)
    caller_name: Mapped[str] = mapped_column(String(100), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    delivered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class NotificationDigest(Base):
    """Tracks what was last sent per channel+symbol to avoid duplicate notifications.

    A fingerprint (hash of key signal data) is stored so we only re-notify
    when something meaningful changes — not on every scan cycle.
    """

    __tablename__ = "notification_digests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # "push", "discord", future channels
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    fingerprint: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # SHA-256 hex of content
    trading_day: Mapped[str] = mapped_column(
        String(10), nullable=False, index=True
    )  # "YYYY-MM-DD" in ET
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SignalSnooze(Base):
    """Snoozed sell/stop-loss signals — temporarily hidden from action plan."""

    __tablename__ = "signal_snoozes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True
    )
    snoozed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    pnl_pct_at_snooze: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )  # P&L % when snoozed — auto-unsnooze if loss worsens by 3%
    indefinite: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )  # True = no time-based expiry
    phantom_trailing_stop: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )  # Auto-unsnooze + notify if loss worsens by 3%


class WebAuthnCredential(Base):
    """Registered passkeys for authentication."""

    __tablename__ = "webauthn_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    credential_id: Mapped[bytes] = mapped_column(
        LargeBinary, unique=True, nullable=False, index=True
    )
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sign_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    transports: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    name: Mapped[str] = mapped_column(String(100), nullable=False, default="Passkey")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
