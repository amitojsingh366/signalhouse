"""Commodity price correlation — boosts signals for correlated assets using live futures data.

Gold futures (GC=F), crude oil (CL=F), natural gas (NG=F), silver (SI=F), and crypto
(BTC-USD, ETH-USD, SOL-USD) trade nearly 24/7. During off-hours this service checks
overnight moves and adjusts signal scores for correlated Canadian-listed stocks and ETFs.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import yfinance as yf

logger = logging.getLogger(__name__)

_CACHE_TTL = 300  # 5 minutes


@dataclass
class CommodityMove:
    commodity: str
    name: str
    price: float
    change_pct: float
    score_adjustment: float
    reason: str


@dataclass
class CommodityResult:
    moves: list[CommodityMove] = field(default_factory=list)

    @property
    def total_score(self) -> float:
        if not self.moves:
            return 0.0
        return max(-1.0, min(1.0, sum(m.score_adjustment for m in self.moves)))

    @property
    def reasons(self) -> list[str]:
        return [m.reason for m in self.moves if abs(m.score_adjustment) >= 0.05]


# Mapping: commodity ticker -> (display name, {sector: weight})
# Weight reflects how tightly correlated the sector is to that commodity.
COMMODITY_SECTORS: dict[str, tuple[str, dict[str, float]]] = {
    "GC=F": ("Gold", {
        "materials": 0.7,
        "etfs_commodities": 0.9,
        "etfs_leveraged": 0.5,
    }),
    "CL=F": ("Crude Oil", {
        "energy": 0.8,
        "etfs_commodities": 0.6,
        "etfs_leveraged": 0.5,
    }),
    "NG=F": ("Natural Gas", {
        "etfs_commodities": 0.5,
        "etfs_leveraged": 0.4,
    }),
    "SI=F": ("Silver", {
        "materials": 0.4,
        "etfs_commodities": 0.7,
    }),
    "BTC-USD": ("Bitcoin", {
        "crypto": 0.9,
    }),
    "ETH-USD": ("Ethereum", {
        "crypto": 0.6,
    }),
    "SOL-USD": ("Solana", {
        "crypto": 0.4,
    }),
}

# Per-symbol overrides for tighter correlations (these take priority over sector weights).
# symbol -> [(commodity_ticker, weight)]
SYMBOL_OVERRIDES: dict[str, list[tuple[str, float]]] = {
    # Gold miners — very tight gold correlation
    "AEM.TO":    [("GC=F", 0.85)],
    "ABX.TO":    [("GC=F", 0.85)],
    "FNV.TO":    [("GC=F", 0.80)],
    "WPM.TO":    [("GC=F", 0.75), ("SI=F", 0.50)],
    "K.TO":      [("GC=F", 0.80)],
    "SSL.TO":    [("GC=F", 0.75)],
    "PAAS.TO":   [("SI=F", 0.70), ("GC=F", 0.40)],
    "XGD.TO":    [("GC=F", 0.90)],
    # Gold ETFs — direct
    "ZGLD.TO":   [("GC=F", 0.95)],
    "CGL.TO":    [("GC=F", 0.95)],
    "KILO.TO":   [("GC=F", 0.95)],
    "MNT.TO":    [("GC=F", 0.95)],
    "HUG.TO":    [("GC=F", 0.90)],
    "ZGD.TO":    [("GC=F", 0.85)],
    "VALT.TO":   [("GC=F", 0.60), ("SI=F", 0.60)],
    # Gold leveraged
    "HBU.TO":    [("GC=F", 0.95)],
    "HBD.TO":    [("GC=F", -0.95)],  # Inverse
    # Silver
    "HUZ.TO":    [("SI=F", 0.90)],
    # Oil producers
    "SU.TO":     [("CL=F", 0.85)],
    "CNQ.TO":    [("CL=F", 0.80)],
    "CVE.TO":    [("CL=F", 0.80)],
    "IMO.TO":    [("CL=F", 0.80)],
    "MEG.TO":    [("CL=F", 0.75)],
    "BTE.TO":    [("CL=F", 0.75)],
    "VET.TO":    [("CL=F", 0.70)],
    "ARX.TO":    [("CL=F", 0.65), ("NG=F", 0.35)],
    "WCP.TO":    [("CL=F", 0.70)],
    "ERF.TO":    [("CL=F", 0.65)],
    "CR.TO":     [("NG=F", 0.60), ("CL=F", 0.30)],
    "BIR.TO":    [("NG=F", 0.60), ("CL=F", 0.30)],
    "XEG.TO":    [("CL=F", 0.85)],
    "XOM.NE":    [("CL=F", 0.80)],
    "CVX.NE":    [("CL=F", 0.80)],
    "COP.NE":    [("CL=F", 0.80)],
    # Natural gas focused
    "TOU.TO":    [("NG=F", 0.70), ("CL=F", 0.30)],
    "PEY.TO":    [("NG=F", 0.65)],
    "HUN.TO":    [("NG=F", 0.90)],
    # Oil/gas leveraged
    "HOU.TO":    [("CL=F", 0.95)],
    "HOD.TO":    [("CL=F", -0.95)],  # Inverse
    "HEU.TO":    [("CL=F", 0.80)],
    "HED.TO":    [("CL=F", -0.80)],  # Inverse
    "HNU.TO":    [("NG=F", 0.90)],
    "HND.TO":    [("NG=F", -0.90)],  # Inverse
    # Crude oil ETF
    "HUC.TO":    [("CL=F", 0.90)],
    # Bitcoin
    "BTCC-B.TO": [("BTC-USD", 0.95)],
    "BTCX-B.TO": [("BTC-USD", 0.95)],
    "FBTC.TO":   [("BTC-USD", 0.95)],
    "EBIT.TO":   [("BTC-USD", 0.95)],
    "BTCQ.TO":   [("BTC-USD", 0.95)],
    "BITI.TO":   [("BTC-USD", -0.95)],  # Inverse
    "IBIT.NE":   [("BTC-USD", 0.95)],
    "HUT.TO":    [("BTC-USD", 0.80)],
    # Ethereum
    "ETHX-B.TO": [("ETH-USD", 0.95)],
    "ETHH.TO":   [("ETH-USD", 0.95)],
    # Solana
    "SOLQ.TO":   [("SOL-USD", 0.90)],
    "SOLX.TO":   [("SOL-USD", 0.90)],
    "SOLA.TO":   [("SOL-USD", 0.90)],
    # XRP
    "XRPQ.TO":   [("BTC-USD", 0.50)],  # Proxy via BTC correlation
    # Multi-crypto
    "ETC.TO":    [("BTC-USD", 0.60), ("ETH-USD", 0.30)],
    # Coinbase CDR
    "COIN.NE":   [("BTC-USD", 0.70)],
    # Uranium — no direct futures, skip
    # Pipelines — moderate oil correlation
    "ENB.TO":    [("CL=F", 0.40)],
    "TRP.TO":    [("CL=F", 0.35)],
    "PPL.TO":    [("CL=F", 0.45)],
    "KEY.TO":    [("CL=F", 0.40)],
}


class _CacheEntry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, ttl: float) -> None:
        self.value = value
        self.expires_at = time.monotonic() + ttl

    @property
    def expired(self) -> bool:
        return time.monotonic() >= self.expires_at


class CommodityCorrelator:
    def __init__(self) -> None:
        self._cache: dict[str, _CacheEntry] = {}

    async def _get_overnight_change(self, commodity: str) -> tuple[float, float] | None:
        """Get (current_price, pct_change) for a commodity/crypto ticker."""
        cached = self._cache.get(commodity)
        if cached and not cached.expired:
            return cached.value

        try:
            result = await asyncio.to_thread(self._fetch_change, commodity)
            self._cache[commodity] = _CacheEntry(result, _CACHE_TTL)
            return result
        except Exception:
            logger.debug("Failed to fetch commodity data for %s", commodity)
            self._cache[commodity] = _CacheEntry(None, 60)  # Short TTL on failure
            return None

    @staticmethod
    def _fetch_change(commodity: str) -> tuple[float, float] | None:
        t = yf.Ticker(commodity)
        df = t.history(period="5d")
        if df is None or len(df) < 2:
            return None
        prev_close = float(df["Close"].iloc[-2])
        current = float(df["Close"].iloc[-1])
        if prev_close <= 0:
            return None
        pct_change = (current - prev_close) / prev_close
        return current, pct_change

    async def get_correlation(
        self, symbol: str, sector: str = ""
    ) -> CommodityResult:
        """Get commodity correlation adjustment for a symbol.

        Checks per-symbol overrides first, then falls back to sector-level correlation.
        Only produces a score adjustment when the commodity has moved >= 0.5%.
        """
        result = CommodityResult()

        # Determine which commodities to check
        correlations: list[tuple[str, float]] = []
        if symbol in SYMBOL_OVERRIDES:
            correlations = SYMBOL_OVERRIDES[symbol]
        elif sector:
            # Fall back to sector-level correlations
            for commodity, (_, sector_weights) in COMMODITY_SECTORS.items():
                weight = sector_weights.get(sector, 0.0)
                if weight > 0:
                    correlations.append((commodity, weight))

        if not correlations:
            return result

        # Fetch all commodity prices in parallel
        tasks = {
            commodity: self._get_overnight_change(commodity)
            for commodity, _ in correlations
        }
        fetched: dict[str, tuple[float, float] | None] = {}
        for commodity, task in tasks.items():
            fetched[commodity] = await task

        # Calculate score adjustments
        for commodity, weight in correlations:
            data = fetched.get(commodity)
            if data is None:
                continue

            price, pct_change = data
            # Only adjust if move is meaningful (>= 0.5%)
            if abs(pct_change) < 0.005:
                continue

            name = COMMODITY_SECTORS.get(commodity, (commodity, {}))[0]

            # Score = change% * weight * scale, capped at ±0.5 per commodity.
            # Scale of 15 means a 1% move with weight 0.85 → ~0.13 score.
            # Negative weights (inverse ETFs) naturally invert the signal.
            adjustment = pct_change * weight * 15.0
            adjustment = max(-0.5, min(0.5, adjustment))

            direction = "up" if pct_change > 0 else "down"
            result.moves.append(CommodityMove(
                commodity=commodity,
                name=name,
                price=price,
                change_pct=pct_change,
                score_adjustment=adjustment,
                reason=f"{name} {direction} {abs(pct_change):.1%} [{adjustment:+.2f}]",
            ))

        return result
