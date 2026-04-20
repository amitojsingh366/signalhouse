"""Market data API endpoints used by dashboard widgets."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends

from trader_api.auth import require_auth
from trader_api.deps import get_config, get_market_data, get_sentiment
from trader_api.schemas import TickerStripItemOut

router = APIRouter(
    prefix="/api/market",
    tags=["market"],
    dependencies=[Depends(require_auth)],
)

_DEFAULT_TICKER_STRIP: list[dict[str, Any]] = [
    {"symbol": "^GSPTSE", "label": "TSX", "prefix": "", "decimals": 2},
    {"symbol": "CADUSD=X", "label": "CAD/USD", "prefix": "", "decimals": 4},
    {"symbol": "CL=F", "label": "OIL", "prefix": "$", "decimals": 2},
    {"symbol": "GC=F", "label": "GOLD", "prefix": "$", "decimals": 0},
    {"symbol": "BTC-USD", "label": "BTC", "prefix": "$", "decimals": 0},
    {"kind": "fear_greed", "symbol": "FNG", "label": "F&G"},
    {"symbol": "SHOP.TO", "label": "SHOP.TO", "prefix": "$", "decimals": 2},
    {"symbol": "CSU.TO", "label": "CSU.TO", "prefix": "$", "decimals": 0},
]


def _format_price(price: float, prefix: str = "", decimals: int = 2) -> str:
    if decimals == 0:
        return f"{prefix}{price:,.0f}"
    return f"{prefix}{price:,.{decimals}f}"


def _coerce_decimals(raw: Any, default: int = 2) -> int:
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return default
    return max(0, parsed)


def _ticker_strip_config() -> list[dict[str, Any]]:
    raw = get_config().get("dashboard", {}).get("ticker_strip")
    if not isinstance(raw, list) or not raw:
        return _DEFAULT_TICKER_STRIP
    items: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            items.append({"symbol": item, "label": item, "prefix": "$", "decimals": 2})
        elif isinstance(item, dict) and isinstance(item.get("symbol"), str):
            items.append(dict(item))
    return items or _DEFAULT_TICKER_STRIP


@router.get("/ticker-strip", response_model=list[TickerStripItemOut])
async def get_ticker_strip():
    market_data = get_market_data()
    sentiment = get_sentiment()

    items: list[TickerStripItemOut] = []
    for item in _ticker_strip_config():
        kind = str(item.get("kind", "")).lower()
        if kind == "fear_greed":
            value, label = await sentiment.get_fear_greed()
            items.append(
                TickerStripItemOut(
                    symbol=str(item.get("symbol", "FNG")),
                    label=str(item.get("label", "F&G")),
                    display_price=str(value),
                    change_pct=None,
                    change_label=label,
                    as_of=datetime.now(UTC),
                )
            )
            continue

        symbol = str(item.get("symbol", "")).strip()
        if not symbol:
            continue
        quote = await market_data.get_quote(symbol)
        label = str(item.get("label", symbol))
        if quote is None:
            items.append(
                TickerStripItemOut(
                    symbol=symbol,
                    label=label,
                    display_price="--",
                    change_pct=None,
                    change_label=None,
                    as_of=datetime.now(UTC),
                )
            )
            continue

        prefix = str(item.get("prefix", "$"))
        decimals = _coerce_decimals(item.get("decimals", 2))
        items.append(
            TickerStripItemOut(
                symbol=symbol,
                label=label,
                display_price=_format_price(
                    float(quote["price"]),
                    prefix=prefix,
                    decimals=decimals,
                ),
                # Public ticker-strip API keeps percent points for backward compatibility.
                change_pct=float(
                    quote.get("change_pct_percent", float(quote["change_pct"]) * 100.0)
                ),
                change_label=None,
                as_of=quote["as_of"],
            )
        )

    return items
