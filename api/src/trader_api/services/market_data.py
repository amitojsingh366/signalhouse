"""Market data provider using yfinance — replaces the IBKR broker for data fetching."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# Map CDR symbols (.NE) to their US counterparts for premarket data.
_CDR_OVERRIDES: dict[str, str] = {
    "GOOG.NE": "GOOGL",
}


def _build_cdr_map(symbols: list[str]) -> dict[str, str]:
    """Build CDR→US map from symbol list. Any .NE symbol maps to its base."""
    mapping: dict[str, str] = {}
    for sym in symbols:
        if sym.endswith(".NE"):
            base = sym.removesuffix(".NE")
            mapping[sym] = _CDR_OVERRIDES.get(sym, base)
    return mapping


class MarketData:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

        # Build flat symbol list from sectors dict or legacy flat list
        sectors = config["strategy"].get("sectors")
        if sectors and isinstance(sectors, dict):
            self.symbols: list[str] = []
            for entries in sectors.values():
                for entry in entries:
                    sym = entry if isinstance(entry, str) else entry["symbol"]
                    if sym not in self.symbols:
                        self.symbols.append(sym)
        else:
            self.symbols = config["strategy"].get("symbols", [])

        self.cdr_to_us = _build_cdr_map(self.symbols)

    def _resolve_ticker(self, symbol: str) -> str:
        return symbol

    async def get_historical_data(
        self, symbol: str, period: str = "60d"
    ) -> pd.DataFrame | None:
        ticker = self._resolve_ticker(symbol)

        try:
            df = await asyncio.to_thread(self._fetch_history, ticker, period)
        except Exception:
            logger.exception("Failed to fetch history for %s", symbol)
            return None

        if df is None or df.empty:
            us_ticker = self.cdr_to_us.get(symbol)
            if us_ticker:
                logger.info("No data for %s, falling back to US ticker %s", symbol, us_ticker)
                try:
                    df = await asyncio.to_thread(self._fetch_history, us_ticker, period)
                except Exception:
                    logger.exception("Fallback fetch failed for %s", us_ticker)
                    return None

        if df is None or df.empty:
            logger.debug("No data available for %s", symbol)
            return None

        return df

    def _fetch_history(self, ticker: str, period: str) -> pd.DataFrame | None:
        t = yf.Ticker(ticker)
        df = t.history(period=period)
        if df.empty:
            return None
        df.columns = df.columns.str.lower()
        cols = ["open", "high", "low", "close", "volume"]
        df = df[[c for c in cols if c in df.columns]]
        return df

    async def get_current_price(self, symbol: str) -> float | None:
        df = await self.get_historical_data(symbol, period="5d")
        if df is None or df.empty:
            return None
        return float(df["close"].iloc[-1])

    async def get_batch_prices(self, symbols: list[str]) -> dict[str, float]:
        prices: dict[str, float] = {}

        tickers: list[str] = []
        ticker_to_symbol: dict[str, str] = {}
        for s in symbols:
            t = self._resolve_ticker(s)
            tickers.append(t)
            ticker_to_symbol[t] = s

        if not tickers:
            return prices

        try:
            df = await asyncio.to_thread(self._batch_download, tickers)
            if df is not None:
                for t in tickers:
                    sym = ticker_to_symbol[t]
                    try:
                        if isinstance(df.columns, pd.MultiIndex):
                            price = float(df[("Close", t)].dropna().iloc[-1])
                        else:
                            price = float(df["Close"].dropna().iloc[-1])
                        prices[sym] = price
                    except (KeyError, IndexError):
                        pass
        except Exception:
            logger.exception("Batch download failed")

        missing = [s for s in symbols if s not in prices]
        if missing:
            tasks = [self.get_current_price(s) for s in missing]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for s, result in zip(missing, results):
                if isinstance(result, float):
                    prices[s] = result

        return prices

    def _batch_download(self, tickers: list[str]) -> pd.DataFrame | None:
        df = yf.download(tickers, period="5d", progress=False, threads=True)
        if df.empty:
            return None
        return df

    async def get_premarket_movers(
        self, cdr_symbols: list[str] | None = None, threshold: float = 0.02
    ) -> list[dict[str, Any]]:
        if cdr_symbols is None:
            cdr_symbols = [s for s in self.symbols if s.endswith(".NE")]

        movers: list[dict[str, Any]] = []

        async def check_one(symbol: str) -> dict[str, Any] | None:
            us_ticker = self.cdr_to_us.get(symbol)
            if not us_ticker:
                return None
            try:
                info = await asyncio.to_thread(lambda: yf.Ticker(us_ticker).info)
                pre_price = info.get("preMarketPrice")
                prev_close = info.get("regularMarketPreviousClose") or info.get(
                    "previousClose"
                )
                if pre_price and prev_close and prev_close > 0:
                    change_pct = (pre_price - prev_close) / prev_close
                    if abs(change_pct) >= threshold:
                        return {
                            "cdr_symbol": symbol,
                            "us_symbol": us_ticker,
                            "premarket_price": pre_price,
                            "prev_close": prev_close,
                            "change_pct": change_pct,
                        }
            except Exception:
                logger.debug("Failed to get premarket data for %s", us_ticker)
            return None

        results = await asyncio.gather(
            *[check_one(s) for s in cdr_symbols], return_exceptions=True
        )
        for r in results:
            if isinstance(r, dict):
                movers.append(r)

        movers.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
        return movers

    async def resolve_symbol(self, raw_ticker: str) -> str | None:
        candidates = [f"{raw_ticker}.TO", f"{raw_ticker}.NE", raw_ticker]
        for candidate in candidates:
            try:
                df = await asyncio.to_thread(self._fetch_history, candidate, "5d")
                if df is not None and not df.empty:
                    return candidate
            except Exception:
                continue
        return None
