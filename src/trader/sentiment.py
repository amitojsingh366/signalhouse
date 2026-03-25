"""Market sentiment analysis — analyst consensus, Fear & Greed, news headlines.

All data comes from free sources (yfinance, CNN Fear & Greed Index).
Results are cached to avoid hitting rate limits.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import yfinance as yf

logger = logging.getLogger(__name__)

# Cache TTLs (seconds)
_FEAR_GREED_TTL = 3600  # 1 hour — market-wide, rarely changes fast
_ANALYST_TTL = 14400  # 4 hours — analyst ratings update infrequently
_NEWS_TTL = 1800  # 30 min — news is more dynamic

# Positive/negative keyword lists for simple headline scoring
_POSITIVE_KEYWORDS = {
    "upgrade", "upgrades", "upgraded", "beat", "beats", "exceeds", "exceeded",
    "outperform", "outperforms", "bullish", "rally", "rallies", "surge",
    "surges", "soars", "jumps", "gains", "profit", "growth", "record",
    "strong", "positive", "buy", "overweight", "raises", "raised",
    "boost", "boosted", "momentum", "breakout", "recovery", "rebounds",
}
_NEGATIVE_KEYWORDS = {
    "downgrade", "downgrades", "downgraded", "miss", "misses", "missed",
    "underperform", "underperforms", "bearish", "crash", "crashes",
    "plunge", "plunges", "drops", "falls", "loss", "losses", "decline",
    "declines", "weak", "negative", "sell", "underweight", "cuts", "cut",
    "warning", "warns", "risk", "fears", "slump", "slumps", "layoffs",
    "recall", "lawsuit", "fraud", "investigation", "bankruptcy",
}


@dataclass
class SentimentResult:
    """Aggregated sentiment score for a symbol."""

    analyst_score: float = 0.0  # -1.0 to +1.0
    analyst_summary: str = ""
    fear_greed_score: float = 0.0  # -0.5 to +0.5
    fear_greed_value: int = 50  # 0-100 raw value
    fear_greed_label: str = ""
    news_score: float = 0.0  # -0.5 to +0.5
    news_headlines: list[str] = field(default_factory=list)

    @property
    def total_score(self) -> float:
        """Combined sentiment score (max ±2.0)."""
        return self.analyst_score + self.fear_greed_score + self.news_score

    @property
    def reasons(self) -> list[str]:
        """Human-readable reasons for the sentiment score."""
        r: list[str] = []
        if self.analyst_summary:
            r.append(f"Analyst: {self.analyst_summary}")
        if self.fear_greed_label:
            r.append(f"Fear & Greed: {self.fear_greed_value} ({self.fear_greed_label})")
        if abs(self.news_score) >= 0.1:
            direction = "positive" if self.news_score > 0 else "negative"
            r.append(f"News sentiment: {direction}")
        return r


class _CacheEntry:
    """Simple TTL cache entry."""

    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, ttl: float) -> None:
        self.value = value
        self.expires_at = time.monotonic() + ttl

    @property
    def expired(self) -> bool:
        return time.monotonic() >= self.expires_at


class SentimentAnalyzer:
    """Fetches and caches sentiment data from free sources."""

    def __init__(self, cdr_to_us: dict[str, str] | None = None) -> None:
        self._cdr_to_us = cdr_to_us or {}
        self._analyst_cache: dict[str, _CacheEntry] = {}
        self._news_cache: dict[str, _CacheEntry] = {}
        self._fear_greed_cache: _CacheEntry | None = None

    def _resolve_us_ticker(self, symbol: str) -> str:
        """Get the US ticker for yfinance lookups (CDRs → US counterpart)."""
        if symbol in self._cdr_to_us:
            return self._cdr_to_us[symbol]
        if symbol.endswith(".NE"):
            return symbol.removesuffix(".NE")
        if symbol.endswith(".TO"):
            return symbol  # TSX tickers work directly
        return symbol

    # ------------------------------------------------------------------
    # Fear & Greed Index (market-wide, cached aggressively)
    # ------------------------------------------------------------------

    async def get_fear_greed(self) -> tuple[int, str]:
        """Fetch CNN Fear & Greed Index. Returns (value 0-100, label).

        Cached for 1 hour. Returns (50, "Neutral") on any error.
        """
        if self._fear_greed_cache and not self._fear_greed_cache.expired:
            return self._fear_greed_cache.value

        try:
            result = await asyncio.to_thread(self._fetch_fear_greed)
            self._fear_greed_cache = _CacheEntry(result, _FEAR_GREED_TTL)
            return result
        except Exception:
            logger.debug("Fear & Greed fetch failed, using neutral default")
            default = (50, "Neutral")
            # Cache the failure briefly so we don't hammer the endpoint
            self._fear_greed_cache = _CacheEntry(default, 300)
            return default

    @staticmethod
    def _fetch_fear_greed() -> tuple[int, str]:
        """Synchronous Fear & Greed fetch."""
        import fear_greed

        data = fear_greed.get()
        value = int(data.value)
        description = str(data.description)
        return value, description

    # ------------------------------------------------------------------
    # Analyst Consensus (per-ticker, via yfinance)
    # ------------------------------------------------------------------

    async def get_analyst_sentiment(self, symbol: str) -> tuple[float, str]:
        """Fetch analyst consensus for a symbol. Returns (score -1 to +1, summary).

        Uses yfinance .recommendations_summary. Cached for 4 hours.
        Returns (0.0, "") on any error.
        """
        cache_key = symbol
        cached = self._analyst_cache.get(cache_key)
        if cached and not cached.expired:
            return cached.value

        ticker = self._resolve_us_ticker(symbol)
        try:
            result = await asyncio.to_thread(self._fetch_analyst, ticker)
            self._analyst_cache[cache_key] = _CacheEntry(result, _ANALYST_TTL)
            return result
        except Exception:
            logger.debug("Analyst data unavailable for %s", symbol)
            default = (0.0, "")
            self._analyst_cache[cache_key] = _CacheEntry(default, _ANALYST_TTL)
            return default

    @staticmethod
    def _fetch_analyst(ticker: str) -> tuple[float, str]:
        """Synchronous analyst data fetch."""
        t = yf.Ticker(ticker)
        rec = t.recommendations
        if rec is None or rec.empty:
            return 0.0, ""

        # Get the most recent row
        latest = rec.iloc[-1]

        # Columns: strongBuy, buy, hold, sell, strongSell (or similar)
        # Normalize column names
        cols = {c.lower().replace(" ", ""): c for c in latest.index}

        strong_buy = int(latest.get(cols.get("strongbuy", ""), 0) or 0)
        buy = int(latest.get(cols.get("buy", ""), 0) or 0)
        hold = int(latest.get(cols.get("hold", ""), 0) or 0)
        sell = int(latest.get(cols.get("sell", ""), 0) or 0)
        strong_sell = int(latest.get(cols.get("strongsell", ""), 0) or 0)

        total = strong_buy + buy + hold + sell + strong_sell
        if total == 0:
            return 0.0, ""

        # Weighted score: strongBuy=2, buy=1, hold=0, sell=-1, strongSell=-2
        weighted = (strong_buy * 2 + buy * 1 + hold * 0 + sell * -1 + strong_sell * -2)
        # Normalize to -1.0 to +1.0 (max is 2*total, min is -2*total)
        score = weighted / (2 * total)

        # Build summary string
        parts = []
        if strong_buy:
            parts.append(f"{strong_buy} Strong Buy")
        if buy:
            parts.append(f"{buy} Buy")
        if hold:
            parts.append(f"{hold} Hold")
        if sell:
            parts.append(f"{sell} Sell")
        if strong_sell:
            parts.append(f"{strong_sell} Strong Sell")
        summary = ", ".join(parts)

        return score, summary

    # ------------------------------------------------------------------
    # News Headline Sentiment (per-ticker, via yfinance)
    # ------------------------------------------------------------------

    async def get_news_sentiment(self, symbol: str) -> tuple[float, list[str]]:
        """Score recent news headlines for a symbol. Returns (score -0.5 to +0.5, headlines).

        Uses simple keyword matching. Cached for 30 min.
        Returns (0.0, []) on any error.
        """
        cache_key = symbol
        cached = self._news_cache.get(cache_key)
        if cached and not cached.expired:
            return cached.value

        ticker = self._resolve_us_ticker(symbol)
        try:
            result = await asyncio.to_thread(self._fetch_news, ticker)
            self._news_cache[cache_key] = _CacheEntry(result, _NEWS_TTL)
            return result
        except Exception:
            logger.debug("News data unavailable for %s", symbol)
            default: tuple[float, list[str]] = (0.0, [])
            self._news_cache[cache_key] = _CacheEntry(default, _NEWS_TTL)
            return default

    @staticmethod
    def _fetch_news(ticker: str) -> tuple[float, list[str]]:
        """Synchronous news headline fetch and scoring."""
        t = yf.Ticker(ticker)
        news = t.news
        if not news:
            return 0.0, []

        headlines: list[str] = []
        pos_count = 0
        neg_count = 0

        for article in news[:10]:  # Limit to 10 most recent
            title = article.get("title", "")
            if not title:
                continue
            headlines.append(title)

            words = set(title.lower().split())
            if words & _POSITIVE_KEYWORDS:
                pos_count += 1
            if words & _NEGATIVE_KEYWORDS:
                neg_count += 1

        total = pos_count + neg_count
        if total == 0:
            return 0.0, headlines

        # Score: ranges from -0.5 to +0.5
        raw = (pos_count - neg_count) / total
        score = max(-0.5, min(0.5, raw * 0.5))
        return score, headlines

    # ------------------------------------------------------------------
    # Combined Sentiment
    # ------------------------------------------------------------------

    async def analyze(self, symbol: str) -> SentimentResult:
        """Get combined sentiment for a symbol (analyst + Fear & Greed + news).

        All fetches are parallelized. Failures in any source are silently
        handled — the corresponding score defaults to 0.
        """
        analyst_task = self.get_analyst_sentiment(symbol)
        fg_task = self.get_fear_greed()
        news_task = self.get_news_sentiment(symbol)

        (analyst_score, analyst_summary), (fg_value, fg_label), (news_score, headlines) = (
            await asyncio.gather(analyst_task, fg_task, news_task)
        )

        # Convert Fear & Greed 0-100 to a signal modifier:
        # <20 (Extreme Fear) → +0.5 (contrarian buy opportunity)
        # 20-40 (Fear) → +0.25
        # 40-60 (Neutral) → 0
        # 60-80 (Greed) → -0.25
        # >80 (Extreme Greed) → -0.5 (overheated, cautious on buys)
        if fg_value < 20:
            fg_score = 0.5
        elif fg_value < 40:
            fg_score = 0.25
        elif fg_value <= 60:
            fg_score = 0.0
        elif fg_value <= 80:
            fg_score = -0.25
        else:
            fg_score = -0.5

        return SentimentResult(
            analyst_score=analyst_score,
            analyst_summary=analyst_summary,
            fear_greed_score=fg_score,
            fear_greed_value=fg_value,
            fear_greed_label=fg_label,
            news_score=news_score,
            news_headlines=headlines,
        )
