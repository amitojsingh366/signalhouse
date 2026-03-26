"""Recommendation engine — scans universe, generates signals, checks exits."""

from __future__ import annotations

import logging
from typing import Any

from trader_api.services.market_data import MarketData
from trader_api.services.portfolio import Portfolio
from trader_api.services.risk import RiskManager
from trader_api.services.sentiment import SentimentAnalyzer
from trader_api.services.signals import Signal, SignalResult, compute_indicators, generate_signal

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

    def get_sector(self, symbol: str) -> str:
        return self.symbol_to_sector.get(symbol, "unknown")

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
        result = generate_signal(df, self.config, sentiment_score=sent.total_score)
        result.symbol = symbol
        result.reasons.extend(sent.reasons)
        result.reasons.append(f"Price: ${df['close'].iloc[-1]:.2f}")
        atr = df["atr"].iloc[-1]
        if atr == atr:
            result.reasons.append(f"ATR: ${atr:.2f}")

        sector = self.get_sector(symbol)
        if sector != "unknown":
            result.reasons.append(f"Sector: {sector}")

        return result

    async def scan_universe(self) -> list[SignalResult]:
        logger.info("Scanning %d symbols...", len(self.symbols))
        results: list[SignalResult] = []
        errors = 0

        for symbol in self.symbols:
            try:
                df = await self.market_data.get_historical_data(symbol, period="60d")
                if df is None or len(df) < 35:
                    continue

                df = compute_indicators(df, self.config)
                sent = await self.sentiment.analyze(symbol)
                result = generate_signal(
                    df, self.config, sentiment_score=sent.total_score
                )
                result.symbol = symbol

                if result.signal == Signal.BUY and result.strength >= 0.35:
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

            if self.risk.should_exit_time(symbol):
                alerts.append({
                    "symbol": symbol,
                    "reason": "Max hold time reached",
                    "detail": f"Held for {self.config['strategy']['max_hold_days']}+ days",
                    "severity": "medium",
                    "current_price": current_price,
                    "entry_price": h["avg_cost"],
                    "pnl_pct": (current_price - h["avg_cost"]) / h["avg_cost"] * 100,
                })
                continue

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

        for sig in sells:
            h = holdings.get(sig.symbol)
            if h:
                sig.reasons.append(f"You hold {h['quantity']:.4f} shares — sell all")

        for sig in watchlist_sells:
            sig.reasons.append("Not held — sell signal for watchlist")

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
        top_buys = filtered_buys[:n]
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

        # Re-sort after applying penalties
        top_buys.sort(key=lambda r: r.strength, reverse=True)

        result = {
            "buys": top_buys,
            "sells": top_sells,
            "watchlist_sells": watchlist_sells[:n],
            "funding": funding,
            "sector_exposure": exposure,
        }
        self._cached_recommendations = result
        return result

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
                    df, self.config, sentiment_score=sent.total_score
                )
                if result.signal != Signal.BUY or result.strength < 0.4:
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
