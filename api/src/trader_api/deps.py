"""Shared dependencies — singleton services accessible to routers and the bot."""

from __future__ import annotations

from typing import Any

from trader_api.services.market_data import MarketData
from trader_api.services.portfolio import Portfolio
from trader_api.services.risk import RiskManager
from trader_api.services.sentiment import SentimentAnalyzer
from trader_api.services.strategy import Strategy

# Singletons initialized at startup
_config: dict[str, Any] = {}
_market_data: MarketData | None = None
_risk: RiskManager | None = None
_sentiment: SentimentAnalyzer | None = None
_strategy: Strategy | None = None


def init_services(config: dict[str, Any]) -> None:
    """Initialize all singleton services. Called once at app startup."""
    global _config, _market_data, _risk, _sentiment
    _config = config
    _market_data = MarketData(config)
    _risk = RiskManager(config)
    _sentiment = SentimentAnalyzer(cdr_to_us=_market_data.cdr_to_us)


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
