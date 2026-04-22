"""Market data provider using yfinance — replaces the IBKR broker for data fetching."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# Map CDR symbols (.NE) to their US counterparts for premarket data.
_CDR_OVERRIDES: dict[str, str] = {
    "GOOG.NE": "GOOGL",
}

_HISTORY_CACHE_TTL = 300  # 5 minutes
_QUOTE_CACHE_TTL = 60  # 1 minute
_FUNDAMENTALS_CACHE_TTL = 900  # 15 minutes


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
        self._history_cache: dict[str, tuple[float, pd.DataFrame]] = {}
        self._quote_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._fundamentals_cache: dict[str, tuple[float, dict[str, float | None]]] = {}

    def clear_caches(self) -> None:
        self._history_cache.clear()
        self._quote_cache.clear()
        self._fundamentals_cache.clear()

    def _resolve_ticker(self, symbol: str) -> str:
        return symbol

    async def get_historical_data(
        self, symbol: str, period: str = "60d"
    ) -> pd.DataFrame | None:
        cache_key = f"{symbol}:{period}"
        cached = self._history_cache.get(cache_key)
        if cached:
            ts, df = cached
            if time.monotonic() - ts < _HISTORY_CACHE_TTL:
                return df.copy()

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

        self._history_cache[cache_key] = (time.monotonic(), df)
        return df.copy()

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

    def _quote_candidates(self, symbol: str) -> list[str]:
        candidates = [self._resolve_ticker(symbol)]
        us_ticker = self.cdr_to_us.get(symbol)
        if us_ticker and us_ticker not in candidates:
            candidates.append(us_ticker)
        return candidates

    @staticmethod
    def _last_two_closes(df: pd.DataFrame) -> tuple[float, float] | None:
        closes = df.get("close")
        if closes is None:
            return None
        closes = closes.dropna()
        if closes.empty:
            return None
        latest = float(closes.iloc[-1])
        prev = float(closes.iloc[-2]) if len(closes) >= 2 else latest
        return latest, prev

    async def get_quote(self, symbol: str) -> dict[str, Any] | None:
        cached = self._quote_cache.get(symbol)
        if cached:
            ts, quote = cached
            if time.monotonic() - ts < _QUOTE_CACHE_TTL:
                return dict(quote)

        for ticker in self._quote_candidates(symbol):
            try:
                df = await asyncio.to_thread(self._fetch_history, ticker, "5d")
            except Exception:
                logger.debug("Quote fetch failed for %s", ticker)
                continue
            if df is None or df.empty:
                continue
            pair = self._last_two_closes(df)
            if pair is None:
                continue
            latest, prev = pair
            # Internal convention: store percentage moves as fractions (e.g., 0.05 for +5%)
            # to match get_premarket_movers and avoid mixed units in this service.
            change_fraction = ((latest - prev) / prev) if prev > 0 else 0.0
            as_of_idx = df.index[-1]
            as_of = as_of_idx.to_pydatetime() if hasattr(as_of_idx, "to_pydatetime") else as_of_idx
            quote = {
                "symbol": symbol,
                "price": latest,
                "change_pct": change_fraction,
                "change_pct_percent": change_fraction * 100.0,
                "as_of": as_of,
            }
            self._quote_cache[symbol] = (time.monotonic(), quote)
            return dict(quote)
        return None

    async def get_fundamentals(self, symbol: str) -> dict[str, float | None]:
        cached = self._fundamentals_cache.get(symbol)
        if cached:
            ts, fundamentals = cached
            if time.monotonic() - ts < _FUNDAMENTALS_CACHE_TTL:
                return dict(fundamentals)

        default: dict[str, float | None] = {
            "market_cap": None,
            "pe_ratio": None,
            "dividend_yield": None,
            "week_52_low": None,
            "week_52_high": None,
            "avg_volume": None,
        }

        for ticker in self._quote_candidates(symbol):
            try:
                fundamentals = await asyncio.to_thread(
                    self._fetch_fundamentals_for_ticker,
                    ticker,
                )
            except Exception:
                logger.debug("Fundamentals fetch failed for %s", ticker)
                continue
            if any(value is not None for value in fundamentals.values()):
                self._fundamentals_cache[symbol] = (time.monotonic(), fundamentals)
                return dict(fundamentals)

        self._fundamentals_cache[symbol] = (time.monotonic(), default)
        return dict(default)

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if number != number:  # NaN
            return None
        return number

    def _fetch_fundamentals_for_ticker(self, ticker: str) -> dict[str, float | None]:
        t = yf.Ticker(ticker)
        info = t.info or {}
        fast_info = dict(getattr(t, "fast_info", {}) or {})

        market_cap = self._coerce_float(
            fast_info.get("market_cap")
            or fast_info.get("marketCap")
            or info.get("marketCap")
        )
        pe_ratio = self._coerce_float(info.get("trailingPE") or info.get("forwardPE"))

        dividend_yield = self._coerce_float(info.get("dividendYield"))
        if dividend_yield is not None and dividend_yield > 1:
            dividend_yield /= 100.0

        week_52_low = self._coerce_float(
            fast_info.get("year_low")
            or fast_info.get("yearLow")
            or fast_info.get("fifty_two_week_low")
            or fast_info.get("fiftyTwoWeekLow")
            or info.get("fiftyTwoWeekLow")
        )
        week_52_high = self._coerce_float(
            fast_info.get("year_high")
            or fast_info.get("yearHigh")
            or fast_info.get("fifty_two_week_high")
            or fast_info.get("fiftyTwoWeekHigh")
            or info.get("fiftyTwoWeekHigh")
        )

        avg_volume = self._coerce_float(
            fast_info.get("three_month_average_volume")
            or fast_info.get("threeMonthAverageVolume")
            or fast_info.get("ten_day_average_volume")
            or fast_info.get("tenDayAverageVolume")
            or info.get("averageVolume")
            or info.get("threeMonthAverageVolume")
            or info.get("averageDailyVolume10Day")
        )

        # yfinance metadata can be sparse for TSX/CDR symbols. Backfill from 1Y candles.
        if week_52_low is None or week_52_high is None or avg_volume is None:
            history = t.history(period="1y")
            if history is not None and not history.empty:
                cols = {c.lower(): c for c in history.columns}
                low_col = cols.get("low")
                high_col = cols.get("high")
                vol_col = cols.get("volume")

                if week_52_low is None and low_col:
                    low_series = history[low_col].dropna()
                    if not low_series.empty:
                        week_52_low = self._coerce_float(low_series.min())

                if week_52_high is None and high_col:
                    high_series = history[high_col].dropna()
                    if not high_series.empty:
                        week_52_high = self._coerce_float(high_series.max())

                if avg_volume is None and vol_col:
                    vol_series = history[vol_col].dropna()
                    if not vol_series.empty:
                        avg_volume = self._coerce_float(vol_series.tail(63).mean())

        return {
            "market_cap": market_cap,
            "pe_ratio": pe_ratio,
            "dividend_yield": dividend_yield,
            "week_52_low": week_52_low,
            "week_52_high": week_52_high,
            "avg_volume": avg_volume,
        }
