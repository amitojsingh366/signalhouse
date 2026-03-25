"""Market data provider using yfinance — replaces the IBKR broker for data fetching."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# Map CDR symbols (.NE) to their US counterparts for premarket data
CDR_TO_US: dict[str, str] = {
    "AAPL.NE": "AAPL",
    "MSFT.NE": "MSFT",
    "GOOG.NE": "GOOG",
    "AMD.NE": "AMD",
    "ASML.NE": "ASML",
    "NVDA.NE": "NVDA",
    "AMZN.NE": "AMZN",
    "META.NE": "META",
    "TSLA.NE": "TSLA",
    "NFLX.NE": "NFLX",
}


class MarketData:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.symbols: list[str] = config["strategy"]["symbols"]

    def _resolve_ticker(self, symbol: str) -> str:
        """Resolve a symbol to a yfinance-compatible ticker.

        .TO symbols work directly. .NE symbols are tried as-is first
        (Yahoo Finance supports CBOE Canada), with US fallback for data gaps.
        """
        return symbol

    async def get_historical_data(
        self, symbol: str, period: str = "60d"
    ) -> pd.DataFrame | None:
        """Fetch daily OHLCV bars for a symbol.

        Returns a DataFrame with lowercase columns (open, high, low, close, volume)
        and a DatetimeIndex, matching the format expected by signals.py.
        Returns None if no data is available.
        """
        ticker = self._resolve_ticker(symbol)

        try:
            df = await asyncio.to_thread(self._fetch_history, ticker, period)
        except Exception:
            logger.exception("Failed to fetch history for %s", symbol)
            return None

        if df is None or df.empty:
            # For .NE symbols, fall back to US counterpart
            us_ticker = CDR_TO_US.get(symbol)
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
        """Synchronous yfinance fetch — run via asyncio.to_thread."""
        t = yf.Ticker(ticker)
        df = t.history(period=period)
        if df.empty:
            return None
        # Lowercase columns to match signals.py expectations
        df.columns = df.columns.str.lower()
        # Keep only OHLCV columns (yfinance may include dividends, stock splits)
        cols = ["open", "high", "low", "close", "volume"]
        df = df[[c for c in cols if c in df.columns]]
        return df

    async def get_current_price(self, symbol: str) -> float | None:
        """Get the latest closing price for a symbol."""
        df = await self.get_historical_data(symbol, period="5d")
        if df is None or df.empty:
            return None
        return float(df["close"].iloc[-1])

    async def get_batch_prices(self, symbols: list[str]) -> dict[str, float]:
        """Fetch current prices for multiple symbols efficiently."""
        prices: dict[str, float] = {}

        # Resolve tickers and build reverse map
        tickers: list[str] = []
        ticker_to_symbol: dict[str, str] = {}
        for s in symbols:
            t = self._resolve_ticker(s)
            tickers.append(t)
            ticker_to_symbol[t] = s

        if not tickers:
            return prices

        try:
            df = await asyncio.to_thread(
                self._batch_download, tickers
            )
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

        # Fill in missing prices individually (fallback for .NE symbols)
        missing = [s for s in symbols if s not in prices]
        if missing:
            tasks = [self.get_current_price(s) for s in missing]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for s, result in zip(missing, results):
                if isinstance(result, float):
                    prices[s] = result

        return prices

    def _batch_download(self, tickers: list[str]) -> pd.DataFrame | None:
        """Synchronous batch download — run via asyncio.to_thread."""
        df = yf.download(tickers, period="5d", progress=False, threads=True)
        if df.empty:
            return None
        return df

    async def get_premarket_movers(
        self, cdr_symbols: list[str] | None = None, threshold: float = 0.02
    ) -> list[dict[str, Any]]:
        """Check US premarket data for CDR counterparts.

        Returns a list of notable movers (>threshold % change) with their
        US premarket move, so the user can anticipate CDR price action.
        """
        if cdr_symbols is None:
            cdr_symbols = [s for s in self.symbols if s.endswith(".NE")]

        movers: list[dict[str, Any]] = []

        async def check_one(symbol: str) -> dict[str, Any] | None:
            us_ticker = CDR_TO_US.get(symbol)
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

        # Sort by absolute change
        movers.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
        return movers

    async def resolve_symbol(self, raw_ticker: str) -> str | None:
        """Resolve a bare ticker (e.g. 'AMD') to its exchange-suffixed form.

        Priority: .TO → .NE → US (bare).
        Returns the resolved symbol or None if no data found.
        """
        candidates = [f"{raw_ticker}.TO", f"{raw_ticker}.NE", raw_ticker]
        for candidate in candidates:
            try:
                df = await asyncio.to_thread(self._fetch_history, candidate, "5d")
                if df is not None and not df.empty:
                    return candidate
            except Exception:
                continue
        return None
