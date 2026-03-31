"""Shared dependencies — singleton services accessible to routers and the bot."""

from __future__ import annotations

import os
from typing import Any

from trader_api.services.commodity import CommodityCorrelator
from trader_api.services.market_data import MarketData
from trader_api.services.notifier import APNsNotifier
from trader_api.services.portfolio import Portfolio
from trader_api.services.risk import RiskManager
from trader_api.services.sentiment import SentimentAnalyzer
from trader_api.services.strategy import Strategy

# Singletons initialized at startup
_config: dict[str, Any] = {}
_market_data: MarketData | None = None
_risk: RiskManager | None = None
_sentiment: SentimentAnalyzer | None = None
_commodity: CommodityCorrelator | None = None
_strategy: Strategy | None = None
_notifier: APNsNotifier | None = None


def init_services(config: dict[str, Any]) -> None:
    """Initialize all singleton services. Called once at app startup."""
    global _config, _market_data, _risk, _sentiment, _commodity, _notifier
    _config = config
    _market_data = MarketData(config)
    _risk = RiskManager(config)
    _commodity = CommodityCorrelator()

    # Build symbol-to-sector map for commodity correlations
    symbol_to_sector: dict[str, str] = {}
    sectors = config["strategy"].get("sectors")
    if sectors and isinstance(sectors, dict):
        for sector_name, entries in sectors.items():
            for entry in entries:
                sym = entry if isinstance(entry, str) else entry["symbol"]
                symbol_to_sector[sym] = sector_name

    _sentiment = SentimentAnalyzer(
        cdr_to_us=_market_data.cdr_to_us,
        commodity_correlator=_commodity,
        symbol_to_sector=symbol_to_sector,
    )

    # APNs notifier — only initializes if credentials are provided
    apns_key = os.environ.get("APNS_KEY_PATH", "")
    if apns_key:
        notif_config = config.get("notifications", {})
        _notifier = APNsNotifier(
            key_path=apns_key,
            key_id=os.environ.get("APNS_KEY_ID", ""),
            team_id=os.environ.get("APNS_TEAM_ID", ""),
            bundle_id=os.environ.get("APNS_BUNDLE_ID", ""),
            sandbox=os.environ.get("APNS_SANDBOX", "false").lower() == "true",
            retry_delay=notif_config.get("retry_delay_seconds", 30),
            max_retries=notif_config.get("max_retries", 1),
            cooldown_minutes=notif_config.get("cooldown_minutes", 60),
        )


def get_config() -> dict[str, Any]:
    return _config


def get_market_data() -> MarketData:
    assert _market_data is not None
    return _market_data


def get_risk() -> RiskManager:
    assert _risk is not None
    return _risk


def get_sentiment() -> SentimentAnalyzer:
    assert _sentiment is not None
    return _sentiment


def get_commodity() -> CommodityCorrelator:
    assert _commodity is not None
    return _commodity


def get_notifier() -> APNsNotifier | None:
    return _notifier


def make_strategy(portfolio: Portfolio) -> Strategy:
    """Create a Strategy instance with a given portfolio (db-session-scoped)."""
    return Strategy(
        market_data=get_market_data(),
        risk=get_risk(),
        portfolio=portfolio,
        config=get_config(),
        sentiment=get_sentiment(),
    )


def make_portfolio(db) -> Portfolio:  # type: ignore[type-arg]
    """Create a Portfolio instance with a given db session."""
    return Portfolio(db)
