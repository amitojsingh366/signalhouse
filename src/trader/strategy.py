"""Recommendation engine — scans universe, generates signals, checks exits.

Sector-aware: tracks portfolio diversification and suggests sell-to-fund
when cash is zero. No execution — recommendations only.
"""

from __future__ import annotations

import logging
from typing import Any

from trader.market_data import MarketData
from trader.portfolio import Portfolio
from trader.risk import RiskManager
from trader.sentiment import SentimentAnalyzer
from trader.signals import Signal, SignalResult, compute_indicators, generate_signal

logger = logging.getLogger(__name__)


class Strategy:
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

        # Cache last scan results so /holdings can reflect sell-to-fund suggestions
        self._cached_recommendations: dict[str, Any] | None = None

        # Build flat symbol list + sector lookup from config
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
            # Fallback: flat list (no sector info)
            self.symbols = config["strategy"].get("symbols", [])

    def get_sector(self, symbol: str) -> str:
        """Return sector for a symbol, or 'unknown'."""
        return self.symbol_to_sector.get(symbol, "unknown")

    def get_sector_exposure(
        self, live_prices: dict[str, float]
    ) -> dict[str, dict[str, Any]]:
        """Calculate current portfolio exposure by sector.

        Returns dict of sector -> {value, pct, symbols}.
        """
        total_value = self.portfolio.get_portfolio_value(live_prices)
        if total_value <= 0:
            return {}

        exposure: dict[str, dict[str, Any]] = {}
        for symbol, h in self.portfolio.holdings.items():
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
        """Run full signal analysis on a single symbol (used by recheck button)."""
        df = await self.market_data.get_historical_data(symbol, period="60d")
        if df is None or len(df) < 35:
            return SignalResult(
                symbol=symbol,
                signal=Signal.HOLD,
                strength=0.0,
                reasons=["Insufficient data"],
            )

        df = compute_indicators(df, self.config)

        # Fetch sentiment (parallel with nothing, but cached so usually instant)
        sent = await self.sentiment.analyze(symbol)
        result = generate_signal(df, self.config, sentiment_score=sent.total_score)
        result.symbol = symbol

        # Attach sentiment reasons
        result.reasons.extend(sent.reasons)

        # Attach current price and ATR for context
        result.reasons.append(f"Price: ${df['close'].iloc[-1]:.2f}")
        atr = df["atr"].iloc[-1]
        if atr == atr:  # not NaN
            result.reasons.append(f"ATR: ${atr:.2f}")

        sector = self.get_sector(symbol)
        if sector != "unknown":
            result.reasons.append(f"Sector: {sector}")

        return result

    async def scan_universe(self) -> list[SignalResult]:
        """Scan all symbols and return BUY/SELL signals sorted by strength."""
        logger.info("Scanning %d symbols...", len(self.symbols))
        results: list[SignalResult] = []
        errors = 0

        for symbol in self.symbols:
            try:
                df = await self.market_data.get_historical_data(symbol, period="60d")
                if df is None or len(df) < 35:
                    continue

                df = compute_indicators(df, self.config)

                # Fetch sentiment (cached, so fast for repeated calls)
                sent = await self.sentiment.analyze(symbol)
                result = generate_signal(
                    df, self.config, sentiment_score=sent.total_score
                )
                result.symbol = symbol

                # Only include actionable signals
                if result.signal == Signal.BUY and result.strength >= 0.4:
                    result.reasons.extend(sent.reasons)
                    result.reasons.append(f"Price: ${df['close'].iloc[-1]:.2f}")
                    results.append(result)
                elif result.signal == Signal.SELL and result.strength >= 0.3:
                    result.reasons.extend(sent.reasons)
                    result.reasons.append(f"Price: ${df['close'].iloc[-1]:.2f}")
                    results.append(result)

            except Exception:
                errors += 1
                logger.exception("Error scanning %s", symbol)

        results.sort(key=lambda r: r.strength, reverse=True)
        logger.info(
            "Scan complete: %d actionable signals, %d errors", len(results), errors
        )
        return results

    async def get_exit_alerts(
        self, live_prices: dict[str, float]
    ) -> list[dict[str, Any]]:
        """Check current holdings for exit conditions."""
        alerts: list[dict[str, Any]] = []

        for symbol, h in self.portfolio.holdings.items():
            current_price = live_prices.get(symbol)
            if current_price is None:
                continue

            # Check trailing stop
            stop_hit = self.risk.update_stops(symbol, current_price)
            if stop_hit is not None:
                alerts.append({
                    "symbol": symbol,
                    "reason": "Stop loss hit",
                    "detail": f"Price ${current_price:.2f} hit stop at ${stop_hit:.2f}",
                    "severity": "high",
                    "current_price": current_price,
                    "entry_price": h["avg_cost"],
                    "pnl_pct": (current_price - h["avg_cost"]) / h["avg_cost"] * 100,
                })
                continue

            # Check max hold time
            if self.risk.should_exit_time(symbol):
                alerts.append({
                    "symbol": symbol,
                    "reason": "Max hold time reached",
                    "detail": (
                        f"Held for {self.config['strategy']['max_hold_days']}+ days"
                    ),
                    "severity": "medium",
                    "current_price": current_price,
                    "entry_price": h["avg_cost"],
                    "pnl_pct": (current_price - h["avg_cost"]) / h["avg_cost"] * 100,
                })
                continue

            # Check for sell signal
            try:
                df = await self.market_data.get_historical_data(symbol, period="30d")
                if df is not None and len(df) >= 35:
                    df = compute_indicators(df, self.config)
                    sent = await self.sentiment.analyze(symbol)
                    result = generate_signal(
                        df, self.config, sentiment_score=sent.total_score
                    )
                    if result.signal == Signal.SELL and result.strength >= 0.3:
                        all_reasons = result.reasons + sent.reasons
                        alerts.append({
                            "symbol": symbol,
                            "reason": "Sell signal",
                            "detail": ", ".join(all_reasons),
                            "severity": "medium",
                            "current_price": current_price,
                            "entry_price": h["avg_cost"],
                            "pnl_pct": (
                                (current_price - h["avg_cost"]) / h["avg_cost"] * 100
                            ),
                        })
            except Exception:
                logger.exception("Error checking sell signal for %s", symbol)

        return alerts

    async def get_premarket_movers(self) -> list[dict[str, Any]]:
        """Get premarket movers for CDR symbols."""
        return await self.market_data.get_premarket_movers()

    async def _rank_holdings_to_sell(
        self, live_prices: dict[str, float]
    ) -> list[dict[str, Any]]:
        """Rank current holdings by desirability to sell (worst first).

        Considers: signal strength (sell signals rank higher), P&L %,
        sector over-concentration, and hold time.
        """
        ranked: list[dict[str, Any]] = []
        exposure = self.get_sector_exposure(live_prices)

        for symbol, h in self.portfolio.holdings.items():
            price = live_prices.get(symbol, h["avg_cost"])
            value = h["quantity"] * price
            pnl_pct = (
                (price - h["avg_cost"]) / h["avg_cost"] * 100
                if h["avg_cost"] > 0 else 0.0
            )
            sector = self.get_sector(symbol)
            sector_pct = exposure.get(sector, {}).get("pct", 0.0)

            # Run signal analysis on the held position
            sell_score = 0.0
            signal_reasons: list[str] = []
            try:
                df = await self.market_data.get_historical_data(symbol, period="30d")
                if df is not None and len(df) >= 35:
                    df = compute_indicators(df, self.config)
                    sent = await self.sentiment.analyze(symbol)
                    result = generate_signal(
                        df, self.config, sentiment_score=sent.total_score
                    )
                    signal_reasons = result.reasons + sent.reasons
                    if result.signal == Signal.SELL:
                        sell_score = result.strength
                    elif result.signal == Signal.HOLD:
                        sell_score = 0.1  # neutral
            except Exception:
                pass

            # Higher score = more desirable to sell
            score = sell_score * 2.0  # strong sell signal is top priority
            if sector_pct > self.max_sector_pct:
                score += 0.5  # over-concentrated sector
            if self.risk.should_exit_time(symbol):
                score += 0.3  # held too long

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

    async def get_top_recommendations(
        self, n: int = 5
    ) -> dict[str, Any]:
        """Get top recommendations with sell-to-fund suggestions and sector context.

        Returns:
            {
                "buys": [SignalResult, ...],
                "sells": [SignalResult, ...],
                "funding": [{"buy": symbol, "sell": {...holding info...}}, ...],
                "sector_exposure": {...},
            }
        """
        all_signals = await self.scan_universe()

        buys = [s for s in all_signals if s.signal == Signal.BUY]
        all_sells = [s for s in all_signals if s.signal == Signal.SELL]

        # Only show sell signals for stocks the user actually holds
        held_symbols = list(self.portfolio.holdings.keys())
        sells = [s for s in all_sells if s.symbol in held_symbols]

        # Get live prices for portfolio context
        prices = (
            await self.market_data.get_batch_prices(held_symbols)
            if held_symbols else {}
        )
        exposure = self.get_sector_exposure(prices)

        # Annotate sell signals with quantity info
        for sig in sells:
            h = self.portfolio.holdings.get(sig.symbol)
            if h:
                sig.reasons.append(f"You hold {h['quantity']:.4f} shares — sell all")

        # Filter buys: penalise signals that would over-concentrate a sector
        filtered_buys: list[SignalResult] = []
        for sig in buys:
            sector = self.get_sector(sig.symbol)
            sector_pct = exposure.get(sector, {}).get("pct", 0.0)
            if sector_pct >= self.max_sector_pct:
                sig.reasons.append(
                    f"Sector '{sector}' already at {sector_pct:.0%} of portfolio"
                )
                sig.strength *= 0.5  # demote but still show
            if sector != "unknown":
                sig.reasons.append(f"Sector: {sector}")
            filtered_buys.append(sig)

        # Re-sort after strength adjustment
        filtered_buys.sort(key=lambda r: r.strength, reverse=True)
        top_buys = filtered_buys[:n]
        top_sells = sells[:n]

        # Generate sell-to-fund suggestions if cash is low
        funding: list[dict[str, Any]] = []
        cash = self.portfolio.cash
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
                        # Calculate how many shares to sell to fund the buy
                        sell_info = dict(best)
                        if buy_price and buy_price > 0:
                            # Sell enough to buy ~1 share or all if holding is small
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

        result = {
            "buys": top_buys,
            "sells": top_sells,
            "funding": funding,
            "sector_exposure": exposure,
        }
        # Cache so /holdings and other commands reflect the same swap suggestions
        self._cached_recommendations = result
        return result

    @staticmethod
    def _extract_price(sig: SignalResult) -> float | None:
        """Extract price from a signal's reasons list (e.g. 'Price: $123.45')."""
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
        """Find a stronger BUY signal to potentially replace a weak holding.

        Looks in the same sector first, then the broader universe.
        Returns info about the best alternative, or None.
        """
        sector = self.get_sector(symbol)
        held_symbols = set(self.portfolio.holdings.keys())

        # Get sector peers first, then a sample of the broader universe
        candidates: list[str] = []
        for sym in self.symbols:
            if sym in held_symbols or sym == symbol:
                continue
            if self.get_sector(sym) == sector:
                candidates.insert(0, sym)  # sector peers first
            elif len(candidates) < 20:
                candidates.append(sym)

        best: dict[str, Any] | None = None
        for candidate in candidates[:15]:  # limit for speed
            try:
                df = await self.market_data.get_historical_data(
                    candidate, period="60d"
                )
                if df is None or len(df) < 35:
                    continue
                df = compute_indicators(df, self.config)
                sent = await self.sentiment.analyze(candidate)
                result = generate_signal(
                    df, self.config, sentiment_score=sent.total_score
                )
                if result.signal != Signal.BUY or result.strength < 0.4:
                    continue

                price = float(df["close"].iloc[-1])
                cand_sector = self.get_sector(candidate)
                is_same_sector = cand_sector == sector

                # Pick the strongest buy, preferring same-sector swaps
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
        """Decide actionable advice for a holding: HOLD, SELL, or SWAP.

        Returns {"action": str, "detail": str, "alternative": ... | None}.
        """
        sig = signal_result.signal
        strength = signal_result.strength

        # Strong sell signal → recommend selling
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

        # Weak hold with a much better alternative → suggest swap
        if sig == Signal.HOLD and alternative and alternative["strength"] >= 0.5:
            return {
                "action": "SWAP",
                "detail": (
                    f"Holding flat — {alternative['symbol']} has a stronger "
                    f"outlook (BUY {alternative['strength']:.0%})"
                ),
                "alternative": alternative,
            }

        # Buy signal on current holding → hold or add
        if sig == Signal.BUY:
            return {
                "action": "HOLD+",
                "detail": f"Buy signal ({strength:.0%}) — hold or consider adding",
                "alternative": None,
            }

        # Default hold
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
        """Get actionable advice for a held symbol.

        Reusable by /holdings (find_alternatives=False for speed),
        /check, and scheduled recaps (find_alternatives=True).
        Returns signal, action (HOLD/HOLD+/SELL/SWAP), reasons, and alternative.
        """
        h = self.portfolio.holdings.get(symbol)
        if not h:
            return {
                "signal": "HOLD",
                "strength": 0.0,
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

        # If individual analysis says HOLD, check if the last universe scan
        # found a better buy that this holding should fund (sell-to-fund).
        # This keeps /holdings consistent with /recommend and scheduled scans.
        if advice["action"] == "HOLD" and self._cached_recommendations:
            for f in self._cached_recommendations.get("funding", []):
                if f["sell"]["symbol"] == symbol:
                    buy_sym = f["buy"]
                    buy_sig = next(
                        (b for b in self._cached_recommendations["buys"]
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
            "reasons": signal_result.reasons,
            "pnl_pct": pnl_pct,
            "action": advice["action"],
            "action_detail": advice["detail"],
            "alternative": advice.get("alternative"),
        }

    async def get_daily_insights(self) -> dict[str, Any]:
        """Generate market insights for holdings and notable movers.

        Used for morning pre-market briefing and evening recap.
        Each holding includes an actionable recommendation (hold/sell/swap)
        and a potential better alternative if one exists.
        """
        held_symbols = list(self.portfolio.holdings.keys())
        prices = (
            await self.market_data.get_batch_prices(held_symbols)
            if held_symbols else {}
        )

        # Analyse each holding with actionable advice
        holding_insights: list[dict[str, Any]] = []
        for symbol, h in self.portfolio.holdings.items():
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

        # Get premarket movers
        premarket = await self.get_premarket_movers()

        # Get sector exposure
        exposure = self.get_sector_exposure(prices)

        # Get top universe movers (scan a subset for speed)
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

        total_value = self.portfolio.get_portfolio_value(prices)
        pnl_data = self.portfolio.get_daily_pnl(prices)

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
            "cash": self.portfolio.cash,
        }
