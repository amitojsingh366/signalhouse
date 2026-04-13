"""Recommendation engine — scans universe, generates signals, checks exits."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from trader_api.services.market_data import MarketData
from trader_api.services.portfolio import Portfolio
from trader_api.services.risk import RiskManager
from trader_api.services.sentiment import SentimentAnalyzer
from trader_api.services.signals import Signal, SignalResult, compute_indicators, generate_signal

logger = logging.getLogger(__name__)

# Max concurrent symbol scans — limits yfinance request pressure
_SCAN_CONCURRENCY = 20
ET = ZoneInfo("America/New_York")


class Strategy:
    # Shared in-process recommendation cache so separate Strategy instances
    # (per-request) can still reference the same funding suggestions.
    _shared_recommendations: dict[str, Any] | None = None
    _shared_recommendations_at: float = 0.0
    _shared_cache_ttl_seconds: float = 900.0  # 15 minutes
    _risk_daily_reset_date: str | None = None

    def __init__(
        self,
        market_data: MarketData,
        risk: RiskManager,
        portfolio: Portfolio,
        config: dict[str, Any],
        sentiment: SentimentAnalyzer | None = None,
    ) -> None:
        self.market_data = market_data
        self.risk = risk
        self.portfolio = portfolio
        self.config = config
        self.sentiment = sentiment or SentimentAnalyzer(
            cdr_to_us=getattr(market_data, "cdr_to_us", None)
        )
        self.max_sector_pct: float = config["strategy"].get("max_sector_pct", 0.40)

        self._cached_recommendations: dict[str, Any] | None = None

        self.symbol_to_sector: dict[str, str] = {}
        self.symbols: list[str] = []

        sectors = config["strategy"].get("sectors")
        if sectors and isinstance(sectors, dict):
            for sector_name, entries in sectors.items():
                for entry in entries:
                    sym = entry if isinstance(entry, str) else entry["symbol"]
                    self.symbols.append(sym)
                    self.symbol_to_sector[sym] = sector_name
        else:
            self.symbols = config["strategy"].get("symbols", [])

    @classmethod
    def _get_shared_recommendations(cls) -> dict[str, Any] | None:
        if cls._shared_recommendations is None:
            return None
        age = time.monotonic() - cls._shared_recommendations_at
        if age > cls._shared_cache_ttl_seconds:
            cls._shared_recommendations = None
            return None
        return cls._shared_recommendations

    @classmethod
    def _set_shared_recommendations(cls, recommendations: dict[str, Any]) -> None:
        cls._shared_recommendations = recommendations
        cls._shared_recommendations_at = time.monotonic()

    def get_sector(self, symbol: str) -> str:
        if symbol in self.symbol_to_sector:
            return self.symbol_to_sector[symbol]
        # Try alternate exchange suffixes (.TO, .NE, bare US ticker)
        base = symbol.rsplit(".", 1)[0] if "." in symbol else symbol
        for suffix in (".TO", ".NE", ""):
            alt = f"{base}{suffix}"
            if alt != symbol and alt in self.symbol_to_sector:
                return self.symbol_to_sector[alt]
        return "unknown"

    async def _check_risk_halt(self, portfolio_value: float) -> bool:
        current_date = datetime.now(ET).strftime("%Y-%m-%d")
        if current_date != self.__class__._risk_daily_reset_date:
            self.risk.reset_daily(portfolio_value)
            # Daily drawdown halts are reset each new market day.
            if self.risk.halt_reason.startswith("Daily drawdown limit hit"):
                self.risk.halted = False
                self.risk.halt_reason = ""
            self.__class__._risk_daily_reset_date = current_date
        elif self.risk.daily_start_value <= 0:
            self.risk.reset_daily(portfolio_value)
        self.risk.check_drawdown(portfolio_value)
        return self.risk.halted

    async def _market_regime_allows_buys(self) -> tuple[bool, str]:
        """Check broad market regime gate for new buys.

        Fail-open (allow buys) if data is unavailable.
        """
        regime_symbol = self.config["strategy"].get("regime_filter_symbol", "VFV.TO")
        sma_days = int(self.config["strategy"].get("regime_filter_sma_days", 200))
        period = self.config["strategy"].get("regime_filter_period", "300d")
        try:
            df = await self.market_data.get_historical_data(regime_symbol, period=period)
            if df is None or len(df) < sma_days:
                return True, ""
            close = float(df["close"].iloc[-1])
            sma = float(df["close"].tail(sma_days).mean())
            if close >= sma:
                return True, ""
            return (
                False,
                f"Regime filter risk-off: {regime_symbol} below {sma_days}-day average",
            )
        except Exception:
            logger.debug("Market regime filter unavailable, failing open")
            return True, ""

    def _passes_liquidity_filter(self, df) -> bool:
        """Require minimum trailing average dollar volume for BUY eligibility."""
        min_dollar_volume = float(
            self.config["strategy"].get("min_avg_dollar_volume", 500000.0)
        )
        if min_dollar_volume <= 0:
            return True
        if len(df) < 20:
            return False
        tail = df.tail(20)
        avg_dollar_volume = float((tail["close"] * tail["volume"]).mean())
        return avg_dollar_volume >= min_dollar_volume

    async def get_sector_exposure(
        self, live_prices: dict[str, float]
    ) -> dict[str, dict[str, Any]]:
        total_value = await self.portfolio.get_portfolio_value(live_prices)
        if total_value <= 0:
            return {}

        holdings = await self.portfolio.get_holdings_dict()
        exposure: dict[str, dict[str, Any]] = {}
        for symbol, h in holdings.items():
            price = live_prices.get(symbol, h["avg_cost"])
            value = h["quantity"] * price
            sector = self.get_sector(symbol)

            if sector not in exposure:
                exposure[sector] = {"value": 0.0, "pct": 0.0, "symbols": []}
            exposure[sector]["value"] += value
            exposure[sector]["symbols"].append(symbol)

        for sector_data in exposure.values():
            sector_data["pct"] = sector_data["value"] / total_value

        return exposure

    async def analyze_symbol(self, symbol: str) -> SignalResult:
        df = await self.market_data.get_historical_data(symbol, period="60d")
        if df is None or len(df) < 35:
            return SignalResult(
                symbol=symbol,
                signal=Signal.HOLD,
                strength=0.0,
                reasons=["Insufficient data"],
            )

        df = compute_indicators(df, self.config)
        sent = await self.sentiment.analyze(symbol)
        result = generate_signal(
            df,
            self.config,
            sentiment_score=sent.non_commodity_score,
            commodity_score=sent.commodity_score,
        )
        result.symbol = symbol
        result.commodity_reasons = list(sent.commodity_reasons)
        result.reasons.extend(sent.reasons)
        result.reasons.append(f"Price: ${df['close'].iloc[-1]:.2f}")
        atr = df["atr"].iloc[-1]
        if atr == atr:
            result.meta["atr"] = float(atr)
            result.reasons.append(f"ATR: ${atr:.2f}")

        sector = self.get_sector(symbol)
        if sector != "unknown":
            result.reasons.append(f"Sector: {sector}")

        return result

    async def _scan_one(
        self, symbol: str, sem: asyncio.Semaphore
    ) -> SignalResult | None:
        """Scan a single symbol (called concurrently with semaphore)."""
        async with sem:
            df = await self.market_data.get_historical_data(symbol, period="60d")
            if df is None or len(df) < 35:
                return None

            df = compute_indicators(df, self.config)
            sent = await self.sentiment.analyze(symbol)
            result = generate_signal(
                df,
                self.config,
                sentiment_score=sent.non_commodity_score,
                commodity_score=sent.commodity_score,
            )
            result.symbol = symbol
            result.commodity_reasons = list(sent.commodity_reasons)
            atr = df["atr"].iloc[-1]
            if atr == atr:
                result.meta["atr"] = float(atr)

            if result.signal == Signal.BUY and result.strength >= 0.35:
                if not self._passes_liquidity_filter(df):
                    return None
                result.reasons.extend(sent.reasons)
                result.reasons.append(f"Price: ${df['close'].iloc[-1]:.2f}")
                if atr == atr:
                    result.reasons.append(f"ATR: ${atr:.2f}")
                return result
            elif result.signal == Signal.SELL and result.strength >= 0.3:
                result.reasons.extend(sent.reasons)
                result.reasons.append(f"Price: ${df['close'].iloc[-1]:.2f}")
                if atr == atr:
                    result.reasons.append(f"ATR: ${atr:.2f}")
                return result
            return None

    async def scan_universe(self) -> list[SignalResult]:
        logger.info("Scanning %d symbols (%d concurrent)...", len(self.symbols), _SCAN_CONCURRENCY)
        sem = asyncio.Semaphore(_SCAN_CONCURRENCY)

        tasks = [self._scan_one(symbol, sem) for symbol in self.symbols]
        outcomes = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[SignalResult] = []
        errors = 0
        for outcome in outcomes:
            if isinstance(outcome, Exception):
                errors += 1
                logger.exception("Scan error: %s", outcome)
            elif outcome is not None:
                results.append(outcome)

        results.sort(key=lambda r: r.strength, reverse=True)
        logger.info("Scan complete: %d actionable signals, %d errors", len(results), errors)
        return results

    async def get_exit_alerts(
        self, live_prices: dict[str, float]
    ) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        holdings = await self.portfolio.get_holdings_dict()

        for symbol, h in holdings.items():
            current_price = live_prices.get(symbol)
            if current_price is None:
                continue

            pnl_pct = (current_price - h["avg_cost"]) / h["avg_cost"] * 100

            stop_hit = self.risk.update_stops(symbol, current_price)
            if stop_hit is not None:
                alerts.append({
                    "symbol": symbol,
                    "reason": "Stop loss hit",
                    "detail": f"Price ${current_price:.2f} hit stop at ${stop_hit:.2f}",
                    "severity": "high",
                    "current_price": current_price,
                    "entry_price": h["avg_cost"],
                    "pnl_pct": pnl_pct,
                    "quantity": h["quantity"],
                    "action": "SELL",
                    "action_detail": f"Sell all {h['quantity']:.4f} shares — stop loss triggered",
                })
                continue

            # Take profit — sell winners at configurable threshold
            if self.risk.should_take_profit(symbol, current_price):
                tp_pct = self.config["risk"].get("take_profit_pct", 0.08) * 100
                alerts.append({
                    "symbol": symbol,
                    "reason": "Take profit",
                    "detail": (
                        f"Gain {pnl_pct:+.1f}% exceeds {tp_pct:.0f}% "
                        f"target — lock in profits"
                    ),
                    "severity": "high",
                    "current_price": current_price,
                    "entry_price": h["avg_cost"],
                    "pnl_pct": pnl_pct,
                    "quantity": h["quantity"],
                    "action": "SELL",
                    "action_detail": (
                        f"Sell all {h['quantity']:.4f} shares "
                        f"— take profit at {pnl_pct:+.1f}%"
                    ),
                })
                continue

            min_hold_days = int(self.config["strategy"].get("min_hold_days", 0))
            open_trade = self.risk.open_trades.get(symbol)
            days_held = (
                (time.time() - open_trade.entry_time.timestamp()) / 86400.0
                if open_trade is not None
                else None
            )
            if self.risk.should_exit_time(symbol):
                alerts.append({
                    "symbol": symbol,
                    "reason": "Max hold time reached",
                    "detail": f"Held for {self.config['strategy']['max_hold_days']}+ days",
                    "severity": "medium",
                    "current_price": current_price,
                    "entry_price": h["avg_cost"],
                    "pnl_pct": pnl_pct,
                    "quantity": h["quantity"],
                    "action": "SELL",
                    "action_detail": f"Sell all {h['quantity']:.4f} shares — exceeded hold window",
                })
                continue

            try:
                df = await self.market_data.get_historical_data(symbol, period="60d")
                if df is not None and len(df) >= 35:
                    df = compute_indicators(df, self.config)
                    sent = await self.sentiment.analyze(symbol)
                    result = generate_signal(
                        df,
                        self.config,
                        sentiment_score=sent.non_commodity_score,
                        commodity_score=sent.commodity_score,
                    )
                    if (
                        result.signal == Signal.SELL
                        and result.strength >= 0.3
                        and (days_held is None or days_held >= min_hold_days)
                    ):
                        all_reasons = result.reasons + sent.reasons
                        alerts.append({
                            "symbol": symbol,
                            "reason": "Sell signal",
                            "detail": ", ".join(all_reasons),
                            "severity": "medium",
                            "current_price": current_price,
                            "entry_price": h["avg_cost"],
                            "pnl_pct": pnl_pct,
                            "quantity": h["quantity"],
                            "action": "SELL",
                            "action_detail": (
                                f"Sell all {h['quantity']:.4f} shares "
                                f"— technical sell signal"
                            ),
                        })
                    elif result.signal == Signal.HOLD and pnl_pct < 0:
                        # Momentum decay — holding is flat/negative with no buy signal
                        alerts.append({
                            "symbol": symbol,
                            "reason": "Momentum lost",
                            "detail": (
                            f"Signal weakened to HOLD while at "
                            f"{pnl_pct:+.1f}% — consider exiting"
                        ),
                            "severity": "low",
                            "current_price": current_price,
                            "entry_price": h["avg_cost"],
                            "pnl_pct": pnl_pct,
                            "quantity": h["quantity"],
                            "action": "SELL",
                            "action_detail": (
                            f"Sell all {h['quantity']:.4f} shares "
                            f"— no momentum, cutting loss"
                        ),
                        })
            except Exception:
                logger.exception("Error checking sell signal for %s", symbol)

        return alerts

    async def get_premarket_movers(self) -> list[dict[str, Any]]:
        return await self.market_data.get_premarket_movers()

    async def _rank_holdings_to_sell(
        self, live_prices: dict[str, float]
    ) -> list[dict[str, Any]]:
        ranked: list[dict[str, Any]] = []
        exposure = await self.get_sector_exposure(live_prices)
        holdings = await self.portfolio.get_holdings_dict()

        for symbol, h in holdings.items():
            price = live_prices.get(symbol, h["avg_cost"])
            value = h["quantity"] * price
            pnl_pct = (
                (price - h["avg_cost"]) / h["avg_cost"] * 100
                if h["avg_cost"] > 0 else 0.0
            )
            sector = self.get_sector(symbol)
            sector_pct = exposure.get(sector, {}).get("pct", 0.0)

            sell_score = 0.0
            signal_reasons: list[str] = []
            try:
                df = await self.market_data.get_historical_data(symbol, period="60d")
                if df is not None and len(df) >= 35:
                    df = compute_indicators(df, self.config)
                    sent = await self.sentiment.analyze(symbol)
                    result = generate_signal(
                        df,
                        self.config,
                        sentiment_score=sent.non_commodity_score,
                        commodity_score=sent.commodity_score,
                    )
                    signal_reasons = result.reasons + sent.reasons
                    if result.signal == Signal.SELL:
                        sell_score = result.strength
                    elif result.signal == Signal.HOLD:
                        sell_score = 0.1
            except Exception:
                pass

            score = sell_score * 2.0
            if sector_pct > self.max_sector_pct:
                score += 0.5
            if self.risk.should_exit_time(symbol):
                score += 0.3

            ranked.append({
                "symbol": symbol,
                "quantity": h["quantity"],
                "price": price,
                "value": value,
                "pnl_pct": pnl_pct,
                "sector": sector,
                "sector_pct": sector_pct,
                "sell_score": score,
                "has_sell_signal": sell_score >= 0.3,
                "reasons": signal_reasons,
            })

        ranked.sort(key=lambda x: x["sell_score"], reverse=True)
        return ranked

    async def get_top_recommendations(self, n: int = 5) -> dict[str, Any]:
        all_signals = await self.scan_universe()

        buys = [s for s in all_signals if s.signal == Signal.BUY]
        all_sells = [s for s in all_signals if s.signal == Signal.SELL]

        holdings = await self.portfolio.get_holdings_dict()
        held_symbols = list(holdings.keys())
        sells = [s for s in all_sells if s.symbol in held_symbols]
        # Non-held sell signals shown as watchlist alerts
        watchlist_sells = [s for s in all_sells if s.symbol not in held_symbols]

        logger.info(
            "Recommendations: %d signals → %d buys, %d sells (%d held, %d watchlist)",
            len(all_signals), len(buys), len(all_sells), len(sells), len(watchlist_sells),
        )

        prices = (
            await self.market_data.get_batch_prices(held_symbols)
            if held_symbols else {}
        )
        exposure = await self.get_sector_exposure(prices)
        portfolio_value = await self.portfolio.get_portfolio_value(prices)
        halted = await self._check_risk_halt(portfolio_value)
        regime_allows_buys, regime_reason = await self._market_regime_allows_buys()

        for sig in sells:
            h = holdings.get(sig.symbol)
            if h:
                sig.reasons.append(f"You hold {h['quantity']:.4f} shares — sell all")

        for sig in watchlist_sells:
            sig.reasons.append("Not held — sell signal for watchlist")

        if halted or not regime_allows_buys:
            block_reason = (
                f"Risk halt active — {self.risk.halt_reason}"
                if halted
                else (regime_reason or "Regime filter blocked new buys")
            )
            result = {
                "buys": [],
                "sells": sells[:n],
                "watchlist_sells": watchlist_sells[:n],
                "funding": [],
                "sector_exposure": exposure,
                "buy_block_reason": block_reason,
            }
            self._cached_recommendations = result
            self._set_shared_recommendations(result)
            return result

        # Track sector-capped buys but don't penalize yet — swaps within
        # the same sector shouldn't be penalized since they replace exposure
        # rather than adding to it.
        sector_capped: set[str] = set()
        filtered_buys: list[SignalResult] = []
        for sig in buys:
            sector = self.get_sector(sig.symbol)
            sector_pct = exposure.get(sector, {}).get("pct", 0.0)
            if sector_pct >= self.max_sector_pct:
                sector_capped.add(sig.symbol)
            if sector != "unknown":
                sig.reasons.append(f"Sector: {sector}")
            filtered_buys.append(sig)

        filtered_buys.sort(key=lambda r: r.strength, reverse=True)
        top_buys = filtered_buys
        top_sells = sells[:n]

        funding: list[dict[str, Any]] = []
        # Track which sector-capped buys got paired with a same-sector sell
        swap_exempted: set[str] = set()
        meta = await self.portfolio._get_meta()
        cash = meta.cash
        if top_buys and held_symbols and cash < 50.0:
            ranked_to_sell = await self._rank_holdings_to_sell(prices)
            if ranked_to_sell:
                for buy_sig in top_buys:
                    buy_price = self._extract_price(buy_sig)
                    buy_sector = self.get_sector(buy_sig.symbol)
                    best = None
                    for candidate in ranked_to_sell:
                        if candidate["symbol"] == buy_sig.symbol:
                            continue
                        if best is None:
                            best = candidate
                        elif (
                            candidate["sector"] == buy_sector
                            and best["sector"] != buy_sector
                        ):
                            best = candidate
                    if best:
                        sell_info = dict(best)
                        # If selling from the same sector, this is a swap —
                        # no net sector exposure increase
                        if (
                            buy_sig.symbol in sector_capped
                            and sell_info["sector"] == buy_sector
                        ):
                            swap_exempted.add(buy_sig.symbol)
                        if buy_price and buy_price > 0:
                            needed = buy_price
                            if sell_info["value"] <= needed * 1.5:
                                sell_info["sell_qty"] = sell_info["quantity"]
                                sell_info["sell_action"] = "Sell all"
                            else:
                                qty_to_sell = needed / sell_info["price"]
                                sell_info["sell_qty"] = round(qty_to_sell, 4)
                                sell_info["sell_action"] = (
                                    f"Sell {qty_to_sell:.4f} shares"
                                )
                        else:
                            sell_info["sell_qty"] = sell_info["quantity"]
                            sell_info["sell_action"] = "Sell all"
                        funding.append({"buy": buy_sig.symbol, "sell": sell_info})

        # Now apply sector cap penalty only to buys that aren't paired
        # with a same-sector sell (i.e. not a swap)
        for sig in top_buys:
            if sig.symbol in sector_capped and sig.symbol not in swap_exempted:
                sector = self.get_sector(sig.symbol)
                sector_pct = exposure.get(sector, {}).get("pct", 0.0)
                sig.reasons.append(
                    f"Sector '{sector}' already at {sector_pct:.0%} of portfolio"
                )
                sig.strength *= 0.5

        # Re-sort after applying penalties, then cap to top-N.
        top_buys.sort(key=lambda r: r.strength, reverse=True)
        top_buys = top_buys[:n]

        result = {
            "buys": top_buys,
            "sells": top_sells,
            "watchlist_sells": watchlist_sells[:n],
            "funding": funding,
            "sector_exposure": exposure,
        }
        self._cached_recommendations = result
        self._set_shared_recommendations(result)
        return result

    async def get_action_plan(self) -> dict[str, Any]:
        """Build a prioritized, position-sized action plan.

        Returns specific trade instructions ordered by urgency:
        1. Stop-loss / take-profit sells (urgent)
        2. Signal-based sells + time exits
        3. Momentum-decay sells (low urgency)
        4. Swaps (sell A, buy B)
        5. New buys (only if under max positions)
        """
        holdings = await self.portfolio.get_holdings_dict()
        held_symbols = list(holdings.keys())
        prices = (
            await self.market_data.get_batch_prices(held_symbols)
            if held_symbols else {}
        )
        meta = await self.portfolio._get_meta()
        cash = meta.cash
        portfolio_value = await self.portfolio.get_portfolio_value(prices)
        num_positions = len(holdings)
        max_positions = self.config["risk"]["max_positions"]

        actions: list[dict[str, Any]] = []

        halted = await self._check_risk_halt(portfolio_value)
        regime_allows_buys, regime_reason = await self._market_regime_allows_buys()

        # --- Phase 1: Exit alerts (sells) ---
        exit_alerts = await self.get_exit_alerts(prices) if holdings else []
        sell_symbols: set[str] = set()
        for alert in exit_alerts:
            sym = alert["symbol"]
            sell_symbols.add(sym)
            h = holdings[sym]
            value = h["quantity"] * alert["current_price"]
            urgency = "urgent" if alert["severity"] == "high" else (
                "normal" if alert["severity"] == "medium" else "low"
            )
            actions.append({
                "type": "SELL",
                "urgency": urgency,
                "symbol": sym,
                "shares": h["quantity"],
                "price": alert["current_price"],
                "dollar_amount": round(value, 2),
                "reason": alert["reason"],
                "detail": alert.get("action_detail", alert["detail"]),
                "pnl_pct": alert["pnl_pct"],
                "entry_price": h["avg_cost"],
                "actionable": True,
            })

        # --- Phase 2: Buys (only if room for positions, or as swaps) ---
        recs = await self.get_top_recommendations(n=5)
        available_slots = max_positions - (num_positions - len(sell_symbols))
        cash_after_sells = cash + sum(
            a["dollar_amount"] for a in actions if a["type"] == "SELL"
        )
        base_exposure = recs.get("sector_exposure", {})
        sectors_being_reduced = {
            self.get_sector(a["symbol"])
            for a in actions
            if a["type"] == "SELL" and a.get("symbol")
        }

        # Add swap suggestions from funding pairs
        if not halted and regime_allows_buys:
            for fund in recs.get("funding", []):
                buy_sym = fund["buy"]
                sell_info = fund["sell"]
                sell_sym = sell_info["symbol"]
                if sell_sym in sell_symbols:
                    continue  # Already selling this one

                buy_sig = next(
                    (b for b in recs["buys"] if b.symbol == buy_sym), None
                )
                if not buy_sig:
                    continue

                buy_price = self._extract_price(buy_sig)
                if not buy_price:
                    continue

                sell_value = sell_info["quantity"] * sell_info["price"]
                shares_to_buy = self._calculate_buy_shares_for_signal(
                    buy_sig,
                    buy_price,
                    portfolio_value,
                    sell_value,
                )
                if shares_to_buy <= 0:
                    continue

                sell_symbols.add(sell_sym)
                sectors_being_reduced.add(self.get_sector(sell_sym))
                actions.append({
                    "type": "SWAP",
                    "urgency": "normal",
                    "actionable": True,
                    "sell_symbol": sell_sym,
                    "sell_shares": sell_info["quantity"],
                    "sell_price": sell_info["price"],
                    "sell_amount": round(sell_value, 2),
                    "sell_pnl_pct": sell_info["pnl_pct"],
                    "buy_symbol": buy_sym,
                    "buy_shares": shares_to_buy,
                    "buy_price": buy_price,
                    "buy_amount": round(shares_to_buy * buy_price, 2),
                    "buy_strength": buy_sig.strength,
                    "score": buy_sig.score,
                    "technical_score": buy_sig.technical_score,
                    "sentiment_score": buy_sig.sentiment_score,
                    "commodity_score": buy_sig.commodity_score,
                    "reason": f"Swap: stronger opportunity ({buy_sig.strength:.0%} vs current)",
                    "detail": (
                        f"Sell {sell_info['quantity']:.4f} sh of {sell_sym} "
                        f"→ buy {shares_to_buy} sh of {buy_sym}"
                    ),
                })

        # New buys — always include signals, mark unaffordable ones as not actionable
        buy_symbols_added: set[str] = set()
        for sig in recs.get("buys", []):
            if sig.symbol in held_symbols or sig.symbol in buy_symbols_added:
                continue
            # Check if this buy is part of a swap already
            if any(
                a.get("buy_symbol") == sig.symbol
                for a in actions if a["type"] == "SWAP"
            ):
                continue

            price = self._extract_price(sig)
            if not price:
                continue

            # Calculate ideal position size
            shares = self._calculate_buy_shares_for_signal(
                sig,
                price,
                portfolio_value,
                cash_after_sells,
            )
            # Also calculate what we'd buy if unconstrained by cash
            max_dollars = portfolio_value * self.config["risk"]["max_position_pct"]
            ideal_shares = int(max_dollars / price) if price > 0 else 0

            can_afford = shares > 0 and (shares * price) <= cash_after_sells
            has_slot = available_slots > 0
            buy_sector = self.get_sector(sig.symbol)
            buy_sector_pct = (
                base_exposure.get(buy_sector, {}).get("pct", 0.0)
                if isinstance(base_exposure.get(buy_sector, {}), dict)
                else 0.0
            )
            sector_blocked = (
                buy_sector != "unknown"
                and buy_sector_pct >= self.max_sector_pct
                and buy_sector not in sectors_being_reduced
            )

            if halted:
                actions.append({
                    "type": "BUY",
                    "urgency": "normal",
                    "symbol": sig.symbol,
                    "shares": 0,
                    "price": price,
                    "dollar_amount": 0.0,
                    "pct_of_portfolio": 0.0,
                    "strength": sig.strength,
                    "score": sig.score,
                    "technical_score": sig.technical_score,
                    "sentiment_score": sig.sentiment_score,
                    "commodity_score": sig.commodity_score,
                    "reason": f"BUY signal ({sig.strength:.0%})",
                    "detail": f"Risk halt active — {self.risk.halt_reason}",
                    "sector": self.get_sector(sig.symbol),
                    "reasons": sig.reasons,
                    "actionable": False,
                })
                buy_symbols_added.add(sig.symbol)
            elif sector_blocked:
                actions.append({
                    "type": "BUY",
                    "urgency": "normal",
                    "symbol": sig.symbol,
                    "shares": 0,
                    "price": price,
                    "dollar_amount": 0.0,
                    "pct_of_portfolio": 0.0,
                    "strength": sig.strength,
                    "score": sig.score,
                    "technical_score": sig.technical_score,
                    "sentiment_score": sig.sentiment_score,
                    "commodity_score": sig.commodity_score,
                    "reason": f"BUY signal ({sig.strength:.0%})",
                    "detail": (
                        f"Sector cap reached: {buy_sector} at "
                        f"{buy_sector_pct:.0%} (max {self.max_sector_pct:.0%})"
                    ),
                    "sector": buy_sector,
                    "reasons": sig.reasons,
                    "actionable": False,
                })
                buy_symbols_added.add(sig.symbol)
            elif not regime_allows_buys:
                actions.append({
                    "type": "BUY",
                    "urgency": "normal",
                    "symbol": sig.symbol,
                    "shares": 0,
                    "price": price,
                    "dollar_amount": 0.0,
                    "pct_of_portfolio": 0.0,
                    "strength": sig.strength,
                    "score": sig.score,
                    "technical_score": sig.technical_score,
                    "sentiment_score": sig.sentiment_score,
                    "commodity_score": sig.commodity_score,
                    "reason": f"BUY signal ({sig.strength:.0%})",
                    "detail": regime_reason or "Regime filter blocked new buys",
                    "sector": self.get_sector(sig.symbol),
                    "reasons": sig.reasons,
                    "actionable": False,
                })
                buy_symbols_added.add(sig.symbol)
            elif can_afford and has_slot:
                cost = shares * price
                pct_of_portfolio = (cost / portfolio_value * 100) if portfolio_value > 0 else 0
                actions.append({
                    "type": "BUY",
                    "urgency": "normal",
                    "symbol": sig.symbol,
                    "shares": shares,
                    "price": price,
                    "dollar_amount": round(cost, 2),
                    "pct_of_portfolio": round(pct_of_portfolio, 1),
                    "strength": sig.strength,
                    "score": sig.score,
                    "technical_score": sig.technical_score,
                    "sentiment_score": sig.sentiment_score,
                    "commodity_score": sig.commodity_score,
                    "reason": f"BUY signal ({sig.strength:.0%})",
                    "detail": (
                        f"Buy {shares} shares of {sig.symbol} "
                        f"at ~${price:.2f} (${cost:,.2f})"
                    ),
                    "sector": self.get_sector(sig.symbol),
                    "reasons": sig.reasons,
                    "actionable": True,
                })
                buy_symbols_added.add(sig.symbol)
                cash_after_sells -= cost
                available_slots -= 1
            else:
                # Signal is valid but not affordable — include as non-actionable
                if ideal_shares > 0:
                    display_shares = ideal_shares
                elif price > 0:
                    display_shares = max(1, int(max_dollars / price))
                else:
                    display_shares = 0
                cost = display_shares * price if display_shares > 0 else price
                pct_of_portfolio = (cost / portfolio_value * 100) if portfolio_value > 0 else 0
                not_actionable_reason = (
                    f"Not enough cash (${cash_after_sells:,.2f} available, "
                    f"~${cost:,.2f} needed)"
                    if not can_afford else
                    f"Max positions reached ({max_positions})"
                )
                actions.append({
                    "type": "BUY",
                    "urgency": "normal",
                    "symbol": sig.symbol,
                    "shares": display_shares,
                    "price": price,
                    "dollar_amount": round(cost, 2),
                    "pct_of_portfolio": round(pct_of_portfolio, 1),
                    "strength": sig.strength,
                    "score": sig.score,
                    "technical_score": sig.technical_score,
                    "sentiment_score": sig.sentiment_score,
                    "commodity_score": sig.commodity_score,
                    "reason": f"BUY signal ({sig.strength:.0%})",
                    "detail": not_actionable_reason,
                    "sector": self.get_sector(sig.symbol),
                    "reasons": sig.reasons,
                    "actionable": False,
                })
                buy_symbols_added.add(sig.symbol)

        # Sort: actionable first, then by urgency (urgent → normal → low)
        urgency_order = {"urgent": 0, "normal": 1, "low": 2}
        actions.sort(key=lambda a: (
            0 if a.get("actionable", True) else 1,
            urgency_order.get(a.get("urgency", "low"), 3),
        ))

        exposure = await self.get_sector_exposure(prices)

        return {
            "actions": actions,
            "portfolio_value": round(portfolio_value, 2),
            "cash": round(cash, 2),
            "num_positions": num_positions,
            "max_positions": max_positions,
            "exit_alerts": exit_alerts,
            "sells_count": sum(1 for a in actions if a["type"] == "SELL"),
            "buys_count": sum(1 for a in actions if a["type"] == "BUY"),
            "swaps_count": sum(1 for a in actions if a["type"] == "SWAP"),
            "sector_exposure": exposure,
        }

    def _calculate_buy_shares(
        self, price: float, portfolio_value: float, available_cash: float
    ) -> int:
        """Calculate how many shares to buy, respecting position limits."""
        if price <= 0 or portfolio_value <= 0:
            return 0
        max_dollars = portfolio_value * self.config["risk"]["max_position_pct"]
        max_dollars = min(max_dollars, available_cash)
        shares = int(max_dollars / price)
        return max(shares, 1) if max_dollars >= price else 0

    def _extract_atr(self, sig: SignalResult) -> float | None:
        meta_atr = sig.meta.get("atr") if sig.meta else None
        if isinstance(meta_atr, (int, float)) and meta_atr > 0:
            return float(meta_atr)
        for r in sig.reasons:
            if r.startswith("ATR: $"):
                try:
                    return float(r.split("$")[1])
                except (ValueError, IndexError):
                    pass
        return None

    def _calculate_buy_shares_for_signal(
        self,
        sig: SignalResult,
        price: float,
        portfolio_value: float,
        available_cash: float,
    ) -> int:
        atr = self._extract_atr(sig)
        if atr is None or atr <= 0:
            return self._calculate_buy_shares(price, portfolio_value, available_cash)
        shares = int(self.risk.calculate_position_size(portfolio_value, price, atr))
        if shares <= 0:
            return 0
        affordable = int(available_cash / price) if price > 0 else 0
        return max(0, min(shares, affordable))

    @staticmethod
    def _extract_price(sig: SignalResult) -> float | None:
        for r in sig.reasons:
            if r.startswith("Price: $"):
                try:
                    return float(r.split("$")[1])
                except (ValueError, IndexError):
                    pass
        return None

    async def _find_better_alternative(
        self,
        symbol: str,
        holding_signal: SignalResult,
        live_prices: dict[str, float],
    ) -> dict[str, Any] | None:
        sector = self.get_sector(symbol)
        holdings = await self.portfolio.get_holdings_dict()
        held_symbols = set(holdings.keys())

        candidates: list[str] = []
        for sym in self.symbols:
            if sym in held_symbols or sym == symbol:
                continue
            if self.get_sector(sym) == sector:
                candidates.insert(0, sym)
            elif len(candidates) < 20:
                candidates.append(sym)

        best: dict[str, Any] | None = None
        for candidate in candidates[:15]:
            try:
                df = await self.market_data.get_historical_data(candidate, period="60d")
                if df is None or len(df) < 35:
                    continue
                df = compute_indicators(df, self.config)
                sent = await self.sentiment.analyze(candidate)
                result = generate_signal(
                    df,
                    self.config,
                    sentiment_score=sent.non_commodity_score,
                    commodity_score=sent.commodity_score,
                )
                if result.signal != Signal.BUY or result.strength < 0.4:
                    continue
                if not self._passes_liquidity_filter(df):
                    continue

                price = float(df["close"].iloc[-1])
                cand_sector = self.get_sector(candidate)
                is_same_sector = cand_sector == sector

                if best is None or (
                    result.strength > best["strength"]
                    or (is_same_sector and not best.get("same_sector"))
                ):
                    reasons = list(result.reasons) + sent.reasons
                    best = {
                        "symbol": candidate,
                        "signal": result.signal.value,
                        "strength": result.strength,
                        "price": price,
                        "sector": cand_sector,
                        "same_sector": is_same_sector,
                        "reasons": reasons[:3],
                    }
            except Exception:
                continue

        return best

    def _holding_action(
        self,
        signal_result: SignalResult,
        pnl_pct: float,
        alternative: dict[str, Any] | None,
    ) -> dict[str, Any]:
        sig = signal_result.signal
        strength = signal_result.strength

        if sig == Signal.SELL and strength >= 0.3:
            if alternative:
                return {
                    "action": "SWAP",
                    "detail": (
                        f"Sell signal ({strength:.0%}) — consider swapping to "
                        f"{alternative['symbol']} (BUY {alternative['strength']:.0%})"
                    ),
                    "alternative": alternative,
                }
            return {
                "action": "SELL",
                "detail": f"Sell signal ({strength:.0%}) — consider exiting",
                "alternative": None,
            }

        if sig == Signal.HOLD and alternative and alternative["strength"] >= 0.5:
            return {
                "action": "SWAP",
                "detail": (
                    f"Holding flat — {alternative['symbol']} has a stronger "
                    f"outlook (BUY {alternative['strength']:.0%})"
                ),
                "alternative": alternative,
            }

        if sig == Signal.BUY:
            return {
                "action": "HOLD+",
                "detail": f"Buy signal ({strength:.0%}) — hold or consider adding",
                "alternative": None,
            }

        return {
            "action": "HOLD",
            "detail": "No strong signal — continue holding",
            "alternative": None,
        }

    async def get_holding_advice(
        self,
        symbol: str,
        price: float,
        find_alternatives: bool = True,
    ) -> dict[str, Any]:
        holdings = await self.portfolio.get_holdings_dict()
        h = holdings.get(symbol)
        if not h:
            return {
                "signal": "HOLD",
                "strength": 0.0,
                "technical_score": 0.0,
                "sentiment_score": 0.0,
                "commodity_score": 0.0,
                "reasons": [],
                "pnl_pct": 0.0,
                "action": "HOLD",
                "action_detail": "Not currently held",
                "alternative": None,
            }

        pnl_pct = (
            (price - h["avg_cost"]) / h["avg_cost"] * 100
            if h["avg_cost"] > 0 else 0.0
        )
        signal_result = await self.analyze_symbol(symbol)

        alternative = None
        if find_alternatives and signal_result.signal != Signal.BUY:
            alternative = await self._find_better_alternative(
                symbol, signal_result, {symbol: price}
            )

        advice = self._holding_action(signal_result, pnl_pct, alternative)

        recommendation_cache = self._cached_recommendations or self._get_shared_recommendations()
        if advice["action"] == "HOLD" and recommendation_cache:
            for f in recommendation_cache.get("funding", []):
                if f["sell"]["symbol"] == symbol:
                    buy_sym = f["buy"]
                    buy_sig = next(
                        (b for b in recommendation_cache["buys"]
                         if b.symbol == buy_sym),
                        None,
                    )
                    if buy_sig:
                        alt_price = self._extract_price(buy_sig)
                        alt_reasons = [
                            r for r in buy_sig.reasons[:3]
                            if not r.startswith(("Price:", "ATR:", "Sector:"))
                        ]
                        advice = {
                            "action": "SWAP",
                            "detail": (
                                f"Better opportunity — consider swapping to "
                                f"{buy_sym} (BUY {buy_sig.strength:.0%})"
                            ),
                            "alternative": {
                                "symbol": buy_sym,
                                "strength": buy_sig.strength,
                                "price": alt_price,
                                "sector": self.get_sector(buy_sym),
                                "reasons": alt_reasons,
                            },
                        }
                    break

        return {
            "signal": signal_result.signal.value,
            "strength": signal_result.strength,
            "technical_score": signal_result.technical_score,
            "sentiment_score": signal_result.sentiment_score,
            "commodity_score": signal_result.commodity_score,
            "reasons": signal_result.reasons,
            "pnl_pct": pnl_pct,
            "action": advice["action"],
            "action_detail": advice["detail"],
            "alternative": advice.get("alternative"),
        }

    async def get_daily_insights(self) -> dict[str, Any]:
        holdings = await self.portfolio.get_holdings_dict()
        held_symbols = list(holdings.keys())
        prices = (
            await self.market_data.get_batch_prices(held_symbols)
            if held_symbols else {}
        )

        holding_insights: list[dict[str, Any]] = []
        for symbol, h in holdings.items():
            price = prices.get(symbol, h["avg_cost"])
            advice = await self.get_holding_advice(
                symbol, price, find_alternatives=True
            )

            holding_insights.append({
                "symbol": symbol,
                "quantity": h["quantity"],
                "price": price,
                "pnl_pct": advice["pnl_pct"],
                "value": h["quantity"] * price,
                "signal": advice["signal"],
                "strength": advice["strength"],
                "reasons": advice["reasons"],
                "sector": self.get_sector(symbol),
                "action": advice["action"],
                "action_detail": advice["action_detail"],
                "alternative": advice.get("alternative"),
            })

        premarket = await self.get_premarket_movers()
        exposure = await self.get_sector_exposure(prices)

        top_movers: list[dict[str, Any]] = []
        for symbol in self.symbols[:30]:
            if symbol in held_symbols:
                continue
            try:
                df = await self.market_data.get_historical_data(symbol, period="5d")
                if df is not None and len(df) >= 2:
                    prev = float(df["close"].iloc[-2])
                    curr = float(df["close"].iloc[-1])
                    if prev > 0:
                        change = (curr - prev) / prev * 100
                        if abs(change) >= 2.0:
                            top_movers.append({
                                "symbol": symbol,
                                "price": curr,
                                "change_pct": change,
                                "sector": self.get_sector(symbol),
                            })
            except Exception:
                continue
        top_movers.sort(key=lambda x: abs(x["change_pct"]), reverse=True)

        total_value = await self.portfolio.get_portfolio_value(prices)
        pnl_data = await self.portfolio.get_daily_pnl(prices)

        return {
            "holdings": holding_insights,
            "premarket": premarket[:5],
            "top_movers": top_movers[:8],
            "sector_exposure": exposure,
            "portfolio_value": total_value,
            "daily_pnl": pnl_data["daily_pnl"],
            "daily_pnl_pct": pnl_data["daily_pnl_pct"],
            "total_pnl": pnl_data["total_pnl"],
            "total_pnl_pct": pnl_data["total_pnl_pct"],
            "cash": pnl_data["cash"],
        }

    # notify_high_confidence_signals() has been moved to
    # services/notifications.py → NotificationDispatcher.dispatch_push_signals()
