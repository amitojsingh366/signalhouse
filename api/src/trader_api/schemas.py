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
    score: float = 0.0  # raw score out of ±8
    reasons: list[str]
    price: float | None = None
    sector: str | None = None


class ExitAlertOut(BaseModel):
    symbol: str
    reason: str  # "Stop loss hit", "Max hold time reached", "Sell signal"
    detail: str
    severity: str  # "high" or "medium"
    current_price: float
    entry_price: float
    pnl_pct: float


class RecommendationOut(BaseModel):
    exit_alerts: list[ExitAlertOut] = []
    buys: list[SignalOut]
    sells: list[SignalOut]
    watchlist_sells: list[SignalOut] = []
    funding: list[dict] = []
    sector_exposure: dict = {}


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
