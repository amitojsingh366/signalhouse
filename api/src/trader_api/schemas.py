"""Pydantic schemas for API request/response validation."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

# --- Portfolio ---

class HoldingOut(BaseModel):
    symbol: str
    quantity: float
    avg_cost: float
    entry_date: datetime | None = None
    current_price: float | None = None
    market_value: float | None = None
    pnl: float | None = None
    pnl_pct: float | None = None

    model_config = {"from_attributes": True}


class HoldingAdvice(BaseModel):
    symbol: str
    quantity: float
    avg_cost: float
    current_price: float
    market_value: float
    pnl: float
    pnl_pct: float
    signal: str
    strength: float
    technical_score: float = 0.0
    sentiment_score: float = 0.0
    commodity_score: float = 0.0
    action: str
    action_detail: str
    reasons: list[str]
    alternative: dict | None = None


class PortfolioSummary(BaseModel):
    holdings: list[HoldingAdvice]
    total_value: float
    cash: float
    total_cost: float
    total_pnl: float
    total_pnl_pct: float


class PnlSummary(BaseModel):
    current_value: float
    initial_capital: float
    cash: float
    daily_pnl: float
    daily_pnl_pct: float
    total_pnl: float
    total_pnl_pct: float
    recent_trades: list[TradeOut] = []


class HoldingUpdate(BaseModel):
    symbol: str
    quantity: float | None = None
    avg_cost: float | None = None


class CashUpdate(BaseModel):
    cash: float


# --- Trades ---

class TradeIn(BaseModel):
    symbol: str
    quantity: float
    price: float


class TradeOut(BaseModel):
    id: int | None = None
    symbol: str
    action: str
    quantity: float
    price: float
    total: float
    avg_cost: float | None = None
    pnl: float | None = None
    pnl_pct: float | None = None
    timestamp: datetime | None = None

    model_config = {"from_attributes": True}


# Fix forward reference
PnlSummary.model_rebuild()


# --- Signals ---

class SignalOut(BaseModel):
    symbol: str
    signal: str  # BUY / SELL / HOLD
    strength: float
    score: float = 0.0  # raw score out of ±9
    technical_score: float = 0.0
    sentiment_score: float = 0.0
    commodity_score: float = 0.0
    reasons: list[str]
    price: float | None = None
    sector: str | None = None


class ExitAlertOut(BaseModel):
    symbol: str
    reason: str  # Stop loss / Max hold / Sell signal / Take profit / Momentum lost
    detail: str
    severity: str  # "high", "medium", or "low"
    current_price: float
    entry_price: float
    pnl_pct: float
    quantity: float | None = None
    action: str | None = None
    action_detail: str | None = None


class RecommendationOut(BaseModel):
    exit_alerts: list[ExitAlertOut] = []
    buys: list[SignalOut]
    sells: list[SignalOut]
    watchlist_sells: list[SignalOut] = []
    funding: list[dict] = []
    sector_exposure: dict = {}


class ActionOut(BaseModel):
    type: str  # "BUY", "SELL", "SWAP"
    urgency: str  # "urgent", "normal", "low"
    symbol: str | None = None  # For BUY/SELL
    shares: float | None = None
    price: float | None = None
    dollar_amount: float | None = None
    pct_of_portfolio: float | None = None
    pnl_pct: float | None = None
    entry_price: float | None = None
    strength: float | None = None
    score: float | None = None
    technical_score: float | None = None
    sentiment_score: float | None = None
    commodity_score: float | None = None
    reason: str = ""
    detail: str = ""
    sector: str | None = None
    reasons: list[str] = []
    # SWAP-specific
    sell_symbol: str | None = None
    sell_shares: float | None = None
    sell_price: float | None = None
    sell_amount: float | None = None
    sell_pnl_pct: float | None = None
    buy_symbol: str | None = None
    buy_shares: float | None = None
    buy_price: float | None = None
    buy_amount: float | None = None
    buy_strength: float | None = None
    # Affordability
    actionable: bool = True  # False if signal is valid but can't be afforded with current cash
    # Snooze
    snoozed: bool = False


class ActionPlanOut(BaseModel):
    actions: list[ActionOut]
    portfolio_value: float
    cash: float
    num_positions: int
    max_positions: int
    sells_count: int = 0
    buys_count: int = 0
    swaps_count: int = 0
    sector_exposure: dict = {}


# --- Signal Snooze ---

class SnoozeIn(BaseModel):
    symbol: str
    hours: float = 4.0  # Default 4 hours
    indefinite: bool = False  # No time-based expiry
    phantom_trailing_stop: bool = True  # Auto-unsnooze if loss worsens by 3%


class SnoozeOut(BaseModel):
    symbol: str
    snoozed_at: datetime
    expires_at: datetime
    pnl_pct_at_snooze: float
    indefinite: bool = False
    phantom_trailing_stop: bool = True

    model_config = {"from_attributes": True}


# --- Daily Snapshots ---

class SnapshotOut(BaseModel):
    date: str
    portfolio_value: float
    cash: float
    positions_value: float

    model_config = {"from_attributes": True}


# --- Status ---

class StatusOut(BaseModel):
    symbols_tracked: int
    holdings_count: int
    market_open: bool
    uptime_seconds: float | None = None
    scan_interval_minutes: int
    risk_halted: bool
    risk_halt_reason: str


class ProfitTakingSettingsOut(BaseModel):
    hybrid_take_profit_enabled: bool
    hybrid_take_profit_min_buy_strength: float


class ProfitTakingSettingsIn(BaseModel):
    hybrid_take_profit_enabled: bool


# --- Upload ---

class UploadHolding(BaseModel):
    symbol: str
    quantity: float
    market_value_cad: float


class UploadConfirm(BaseModel):
    holdings: list[UploadHolding]


# --- Insights ---

class InsightsOut(BaseModel):
    holdings: list[dict]
    premarket: list[dict]
    top_movers: list[dict]
    sector_exposure: dict
    portfolio_value: float
    daily_pnl: float
    daily_pnl_pct: float
    total_pnl: float
    total_pnl_pct: float
    cash: float


# --- Notifications ---


class DeviceRegisterIn(BaseModel):
    device_token: str
    push_token: str | None = None  # Standard APNs token for alert notifications
    platform: str = "ios"


class NotificationPrefsIn(BaseModel):
    enabled: bool | None = None
    daily_disabled: bool | None = None  # True = disable for today
    daily_disabled_notifications: bool | None = None  # True = mute alerts for today
    daily_disabled_calls: bool | None = None  # True = mute calls for today


class NotificationPrefsOut(BaseModel):
    device_token: str
    enabled: bool
    daily_disabled_date: str | None = None
    daily_disabled_notifications_date: str | None = None
    daily_disabled_calls_date: str | None = None

    model_config = {"from_attributes": True}


class NotificationLogOut(BaseModel):
    id: int
    notification_type: str = "signal"
    symbol: str
    signal: str
    strength: float
    caller_name: str
    sent_at: datetime
    delivered: bool
    acknowledged: bool

    model_config = {"from_attributes": True}
