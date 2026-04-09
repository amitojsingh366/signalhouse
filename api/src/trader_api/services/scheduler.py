"""API-side background scheduler — signal scans and push notifications.

All timed notification loops run here, inside the FastAPI lifespan. Completely
independent of the Discord bot — push notifications go out to every registered
device regardless of which clients (bot, web, app) are running.

Loops:
  - scan_loop      : every 15 min during market hours → VoIP signal pushes
  - premarket_loop : 8:00 AM ET weekdays → alert push with CDR movers
  - briefing_loop  : 8:30 AM ET weekdays → alert push with portfolio summary
  - close_loop     : 3:50 PM ET weekdays → alert push with daily P&L
  - recap_loop     : 10:00 PM PT weekdays → alert push with end-of-day summary
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")
PT = ZoneInfo("America/Vancouver")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seconds_until(target: time, tz: ZoneInfo) -> float:
    """Seconds until the next wall-clock occurrence of `target` in `tz`."""
    now = datetime.now(tz)
    dt = datetime.combine(now.date(), target, tzinfo=tz)
    if dt <= now:
        dt += timedelta(days=1)
    return (dt - now).total_seconds()


def _is_weekday_et() -> bool:
    return datetime.now(ET).weekday() < 5


def _is_market_hours(config: dict[str, Any]) -> bool:
    now = datetime.now(ET)
    if now.weekday() >= 5:
        return False
    open_t = datetime.strptime(config["schedule"]["market_open"], "%H:%M").time()
    close_t = datetime.strptime(config["schedule"]["market_close"], "%H:%M").time()
    return open_t <= now.time() <= close_t


async def _send_push(notification_type: str, title: str, body: str) -> None:
    """Send a standard alert push to all enabled devices."""
    try:
        from trader_api.database import async_session
        from trader_api.deps import get_notifier

        notifier = get_notifier()
        if notifier is None or not notifier.is_configured:
            logger.debug("Scheduler: notifier not configured, skipping [%s]", notification_type)
            return
        count = await notifier.notify_scheduled(
            async_session,
            notification_type=notification_type,
            title=title,
            body=body,
            category=notification_type,
        )
        logger.info("Scheduler: sent [%s] push to %d device(s)", notification_type, count)
    except Exception:
        logger.exception("Scheduler: push [%s] failed", notification_type)


async def _make_strategy() -> Any:
    """Create a short-lived Strategy with its own DB session."""
    from trader_api.database import async_session
    from trader_api.deps import get_config, get_market_data, get_risk, get_sentiment
    from trader_api.services.portfolio import Portfolio
    from trader_api.services.strategy import Strategy

    session = async_session()
    portfolio = Portfolio(session)
    return Strategy(
        market_data=get_market_data(),
        risk=get_risk(),
        portfolio=portfolio,
        config=get_config(),
        sentiment=get_sentiment(),
    )


# ---------------------------------------------------------------------------
# Task runners — one-shot async functions called by the loops
# ---------------------------------------------------------------------------

async def _run_scan(config: dict[str, Any]) -> None:
    """Scan universe, send VoIP pushes for high-confidence signals."""
    strategy = await _make_strategy()
    try:
        plan = await strategy.get_action_plan()
        # Still use top_recommendations for VoIP notification dedup logic
        recs = strategy._cached_recommendations
        if recs:
            await strategy.notify_high_confidence_signals(recs)
        n_actions = len(plan.get("actions", []))
        logger.info(
            "Scheduler scan: %d action(s) — %d sell, %d swap, %d buy",
            n_actions, plan["sells_count"], plan["swaps_count"], plan["buys_count"],
        )
    except Exception:
        logger.exception("Scheduler: scan task failed")
    finally:
        await strategy.portfolio.close()


async def _run_premarket() -> None:
    """Fetch premarket movers and send an alert push."""
    strategy = await _make_strategy()
    try:
        movers = await strategy.get_premarket_movers()
        if movers:
            top = movers[:3]
            summary = ", ".join(
                f"{m['cdr_symbol']} {m['change_pct']:+.1%}" for m in top
            )
            await _send_push("premarket", "Pre-Market Movers", summary)
        else:
            logger.info("Scheduler: no premarket movers today")
    except Exception:
        logger.exception("Scheduler: premarket task failed")
    finally:
        await strategy.portfolio.close()


async def _run_briefing() -> None:
    """Morning briefing — action plan summary push."""
    strategy = await _make_strategy()
    try:
        plan = await strategy.get_action_plan()
        actions = plan["actions"]
        pv = plan["portfolio_value"]

        if actions:
            sells = plan["sells_count"]
            buys = plan["buys_count"]
            swaps = plan["swaps_count"]
            parts = []
            if sells:
                parts.append(f"{sells} sell{'s' if sells > 1 else ''}")
            if swaps:
                parts.append(f"{swaps} swap{'s' if swaps > 1 else ''}")
            if buys:
                parts.append(f"{buys} buy{'s' if buys > 1 else ''}")
            summary = ", ".join(parts)
            # Show first urgent action detail
            urgent = [a for a in actions if a.get("urgency") == "urgent"]
            if urgent:
                first = urgent[0]
                detail = f" | {first['type']} {first.get('symbol', '')}: {first.get('reason', '')}"
            else:
                detail = ""
            await _send_push(
                "briefing",
                "Action Plan",
                f"{len(actions)} trade(s): {summary}{detail} · ${pv:,.0f}",
            )
        else:
            await _send_push(
                "briefing",
                "Morning Briefing",
                f"No trades needed · Portfolio: ${pv:,.0f}",
            )
    except Exception:
        logger.exception("Scheduler: briefing task failed")
    finally:
        await strategy.portfolio.close()


async def _run_close() -> None:
    """Market close — daily P&L push."""
    from trader_api.database import async_session
    from trader_api.deps import get_market_data
    from trader_api.services.portfolio import Portfolio

    async with async_session() as db:
        portfolio = Portfolio(db)
        try:
            holdings = await portfolio.get_holdings_dict()
            held_symbols = list(holdings.keys())
            prices = (
                await get_market_data().get_batch_prices(held_symbols)
                if held_symbols else {}
            )
            pnl_data = await portfolio.get_daily_pnl(prices)
            daily = pnl_data["daily_pnl"]
            daily_pct = pnl_data["daily_pnl_pct"]
            total = pnl_data["total_pnl"]
            total_pct = pnl_data["total_pnl_pct"]
            await _send_push(
                "close",
                "Market Close",
                f"Daily: ${daily:+.2f} ({daily_pct:+.1f}%) · "
                f"Total: ${total:+.2f} ({total_pct:+.1f}%)",
            )
        except Exception:
            logger.exception("Scheduler: close task failed")


async def _run_recap() -> None:
    """Evening recap — portfolio summary push."""
    strategy = await _make_strategy()
    try:
        insights = await strategy.get_daily_insights()
        pv = insights["portfolio_value"]
        pnl = insights["total_pnl"]
        pnl_pct = insights["total_pnl_pct"]
        await _send_push(
            "recap",
            "Evening Recap",
            f"Portfolio: ${pv:,.2f} ({pnl:+.2f}, {pnl_pct:+.1f}%)",
        )
    except Exception:
        logger.exception("Scheduler: recap task failed")
    finally:
        await strategy.portfolio.close()


# ---------------------------------------------------------------------------
# Loop coroutines — run forever, call task runners on schedule
# ---------------------------------------------------------------------------

async def _scan_loop(config: dict[str, Any]) -> None:
    """Every 15 min during market hours."""
    interval = config["schedule"].get("scan_interval_minutes", 15) * 60
    while True:
        try:
            await asyncio.sleep(interval)
            if not _is_market_hours(config):
                continue
            logger.info("Scheduler: starting market scan")
            await _run_scan(config)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Scheduler: scan loop error")


async def _daily_loop(
    target: time,
    tz: ZoneInfo,
    name: str,
    fn: Any,
) -> None:
    """Sleep until `target` time in `tz`, run `fn`, repeat next day."""
    while True:
        try:
            wait = _seconds_until(target, tz)
            logger.debug("Scheduler: %s fires in %.0fs", name, wait)
            await asyncio.sleep(wait)
            if not _is_weekday_et():
                logger.debug("Scheduler: %s skipped (weekend)", name)
                await asyncio.sleep(60)  # avoid re-firing immediately
                continue
            logger.info("Scheduler: running %s", name)
            await fn()
            await asyncio.sleep(60)  # prevent double-fire within the same minute
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Scheduler: %s loop error", name)
            await asyncio.sleep(60)


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class Scheduler:
    """Owns all background asyncio tasks for the API process."""

    def __init__(self) -> None:
        self._tasks: list[asyncio.Task[None]] = []

    def start(self, config: dict[str, Any]) -> None:
        self._tasks = [
            asyncio.create_task(
                _scan_loop(config), name="scheduler_scan"
            ),
            asyncio.create_task(
                _daily_loop(time(8, 0), ET, "premarket", _run_premarket),
                name="scheduler_premarket",
            ),
            asyncio.create_task(
                _daily_loop(time(8, 30), ET, "briefing", _run_briefing),
                name="scheduler_briefing",
            ),
            asyncio.create_task(
                _daily_loop(time(15, 50), ET, "close", _run_close),
                name="scheduler_close",
            ),
            asyncio.create_task(
                _daily_loop(time(22, 0), PT, "recap", _run_recap),
                name="scheduler_recap",
            ),
        ]
        logger.info("Scheduler started (%d tasks)", len(self._tasks))

    def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()
        logger.info("Scheduler stopped")
