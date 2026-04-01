"""Scheduled tasks — market scans, daily status, premarket, briefings, recaps."""

from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from trader_bot.bot import TraderBot, is_market_hours
from trader_bot.cogs.signals import RecheckView, _build_buy_embed, _build_sell_embed

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")
PT = ZoneInfo("America/Vancouver")


async def _send_scheduled_push(
    notification_type: str,
    title: str,
    body: str,
) -> None:
    """Send a standard alert push notification to all registered devices."""
    try:
        from trader_api.database import async_session
        from trader_api.deps import get_notifier

        notifier = get_notifier()
        if notifier is None or not notifier.is_configured:
            return

        await notifier.notify_scheduled(
            async_session,
            notification_type=notification_type,
            title=title,
            body=body,
            category=notification_type,
        )
    except Exception:
        logger.exception("Error sending scheduled push [%s]", notification_type)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def pnl_color(pnl: float) -> int:
    if pnl > 0:
        return 0x2ECC71
    elif pnl < 0:
        return 0xE74C3C
    return 0x95A5A6


async def _send_insights_embeds(
    channel: discord.TextChannel,
    insights: dict[str, Any],
    title: str,
) -> None:
    """Send market insights as a series of embeds."""
    now_str = datetime.now(ET).strftime("%Y-%m-%d %H:%M ET")

    # 1. Portfolio overview
    pnl_val = insights["total_pnl"]
    embed = discord.Embed(
        title=f"{title} \u2014 Portfolio",
        color=pnl_color(pnl_val),
    )
    embed.add_field(
        name="Value", value=f"${insights['portfolio_value']:.2f}", inline=True
    )
    embed.add_field(
        name="Cash", value=f"${insights['cash']:.2f}", inline=True
    )
    embed.add_field(
        name="Total P&L",
        value=f"${pnl_val:+.2f} ({insights['total_pnl_pct']:+.1f}%)",
        inline=True,
    )

    # Holdings with signals and actionable advice
    for h in insights["holdings"]:
        action = h.get("action", "HOLD")
        action_emojis = {
            "HOLD": "\U0001f7e1",
            "HOLD+": "\U0001f7e2",
            "SELL": "\U0001f534",
            "SWAP": "\U0001f504",
        }
        action_emoji = action_emojis.get(action, "\u26AA")
        pnl_emoji = "\U0001f7e2" if h["pnl_pct"] >= 0 else "\U0001f534"

        top_reasons = h["reasons"][:2]
        reasons_str = " | ".join(r for r in top_reasons if not r.startswith("Price:"))
        detail = h.get("action_detail", "")

        value_lines = [
            f"{h['quantity']:.4f} sh @ ${h['price']:.2f} "
            f"{pnl_emoji} {h['pnl_pct']:+.1f}%",
        ]
        if reasons_str:
            value_lines.append(reasons_str)
        if detail:
            value_lines.append(f"**\u27A1 {detail}**")

        alt = h.get("alternative")
        if alt:
            value_lines.append(
                f"\U0001f4A1 Consider **{alt['symbol']}** "
                f"(BUY {alt['strength']:.0%}, ${alt['price']:.2f})"
            )

        embed.add_field(
            name=f"{action_emoji} {h['symbol']} \u2014 {action}",
            value="\n".join(value_lines),
            inline=False,
        )

    embed.set_footer(text=now_str)
    await channel.send(embed=embed)

    # 2. Pre-market movers (morning only, if available)
    premarket = insights.get("premarket", [])
    if premarket:
        pm_embed = discord.Embed(
            title=f"{title} \u2014 Pre-Market Movers",
            color=0x3498DB,
        )
        for m in premarket:
            direction = "\U0001f7e2" if m["change_pct"] > 0 else "\U0001f534"
            pm_embed.add_field(
                name=f"{direction} {m['cdr_symbol']} ({m['us_symbol']})",
                value=f"${m['premarket_price']:.2f} ({m['change_pct']:+.1%})",
                inline=True,
            )
        pm_embed.set_footer(text=now_str)
        await channel.send(embed=pm_embed)

    # 3. Notable movers in tracked universe
    movers = insights.get("top_movers", [])
    if movers:
        mv_embed = discord.Embed(
            title=f"{title} \u2014 Notable Movers",
            description="Tracked stocks with significant moves:",
            color=0x9B59B6,
        )
        for m in movers[:8]:
            direction = "\U0001f7e2" if m["change_pct"] > 0 else "\U0001f534"
            mv_embed.add_field(
                name=f"{direction} {m['symbol']}",
                value=f"${m['price']:.2f} ({m['change_pct']:+.1f}%) [{m['sector']}]",
                inline=True,
            )
        mv_embed.set_footer(text=now_str)
        await channel.send(embed=mv_embed)

    # 4. Sector exposure
    exposure = insights.get("sector_exposure", {})
    if exposure:
        lines = []
        for sector, data in sorted(
            exposure.items(), key=lambda x: x[1]["pct"], reverse=True
        ):
            bar_len = int(data["pct"] * 20)
            bar = "\u2588" * bar_len + "\u2591" * (20 - bar_len)
            syms = ", ".join(data["symbols"])
            lines.append(f"`{bar}` **{sector}** {data['pct']:.0%} ({syms})")
        sec_embed = discord.Embed(
            title=f"{title} \u2014 Sector Exposure",
            description="\n".join(lines),
            color=0x3498DB,
        )
        sec_embed.set_footer(text=now_str)
        await channel.send(embed=sec_embed)


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class TasksCog(commands.Cog):
    """Scheduled background tasks."""

    def __init__(self, bot: TraderBot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.scan_loop.start()
        self.daily_status_loop.start()
        self.premarket_loop.start()
        self.morning_briefing_loop.start()
        self.evening_recap_loop.start()

    async def cog_unload(self) -> None:
        self.scan_loop.cancel()
        self.daily_status_loop.cancel()
        self.premarket_loop.cancel()
        self.morning_briefing_loop.cancel()
        self.evening_recap_loop.cancel()

    def _get_channel(self) -> discord.TextChannel | None:
        channel = self.bot.get_channel(self.bot.channel_id)
        if channel and isinstance(channel, discord.TextChannel):
            return channel
        return None

    # --- Market Scan (every 15 min) ---

    @tasks.loop(minutes=15)
    async def scan_loop(self) -> None:
        if not is_market_hours(self.bot.config):
            return

        channel = self._get_channel()
        if not channel:
            return

        strategy = None
        portfolio = None
        try:
            strategy = await self.bot.get_fresh_strategy()
            portfolio = await self.bot.get_fresh_portfolio()
            holdings = await portfolio.get_holdings_dict()

            # Check exit alerts for current holdings
            if holdings:
                held_symbols = list(holdings.keys())
                prices = await self.bot.market_data.get_batch_prices(held_symbols)
                alerts = await strategy.get_exit_alerts(prices)
                for alert in alerts:
                    embed = discord.Embed(
                        title=f"\u26A0 {alert['symbol']} \u2014 {alert['reason']}",
                        description=alert["detail"],
                        color=0xE74C3C if alert["severity"] == "high" else 0xF39C12,
                    )
                    embed.add_field(
                        name="Current",
                        value=f"${alert['current_price']:.2f}",
                        inline=True,
                    )
                    embed.add_field(
                        name="Entry",
                        value=f"${alert['entry_price']:.2f}",
                        inline=True,
                    )
                    embed.add_field(
                        name="P&L",
                        value=f"{alert['pnl_pct']:+.1f}%",
                        inline=True,
                    )
                    await channel.send(embed=embed)

            # Scan for new signals
            recs = await strategy.get_top_recommendations(n=3)
            funding = recs.get("funding", [])
            for sig in recs["buys"]:
                embed = _build_buy_embed(sig, funding)
                await channel.send(embed=embed, view=RecheckView())

            for sig in recs["sells"]:
                embed = _build_sell_embed(sig)
                await channel.send(embed=embed, view=RecheckView())

            # Trigger VoIP push notifications for high-confidence signals
            try:
                await strategy.notify_high_confidence_signals(recs)
            except Exception:
                logger.exception("Error sending push notifications")

        except Exception:
            logger.exception("Error during scheduled scan")
        finally:
            if portfolio:
                await portfolio.close()
            if strategy:
                await strategy.portfolio.close()

    @scan_loop.before_loop
    async def before_scan(self) -> None:
        await self.bot.wait_until_ready()

    # --- Daily Status (3:50 PM ET) ---

    @tasks.loop(time=time(15, 50, tzinfo=ET))
    async def daily_status_loop(self) -> None:
        now = datetime.now(ET)
        if now.weekday() >= 5:
            return

        channel = self._get_channel()
        if not channel:
            return

        portfolio = None
        try:
            portfolio = await self.bot.get_fresh_portfolio()
            holdings = await portfolio.get_holdings_dict()
            held_symbols = list(holdings.keys())
            prices = (
                await self.bot.market_data.get_batch_prices(held_symbols)
                if held_symbols else {}
            )
            await portfolio.record_daily_snapshot(prices)

            pnl_data = await portfolio.get_daily_pnl(prices)
            holdings_with_pnl = await portfolio.get_holdings_with_pnl(prices)

            embed = discord.Embed(
                title="Daily Portfolio Summary",
                color=pnl_color(pnl_data["total_pnl"]),
            )
            embed.add_field(
                name="Portfolio Value",
                value=f"${pnl_data['current_value']:.2f}",
                inline=True,
            )
            embed.add_field(
                name="Cash",
                value=f"${pnl_data['cash']:.2f}",
                inline=True,
            )
            embed.add_field(
                name="Daily P&L",
                value=f"${pnl_data['daily_pnl']:+.2f} ({pnl_data['daily_pnl_pct']:+.1f}%)",
                inline=True,
            )
            embed.add_field(
                name="Total P&L",
                value=f"${pnl_data['total_pnl']:+.2f} ({pnl_data['total_pnl_pct']:+.1f}%)",
                inline=False,
            )

            if holdings_with_pnl:
                lines = []
                for h in holdings_with_pnl:
                    emoji = "\U0001f7e2" if h["pnl_pct"] >= 0 else "\U0001f534"
                    lines.append(
                        f"{emoji} **{h['symbol']}** \u2014 {h['quantity']:.4f} shares "
                        f"@ ${h['current_price']:.2f} ({h['pnl_pct']:+.1f}%)"
                    )
                embed.add_field(
                    name="Holdings", value="\n".join(lines), inline=False
                )

            embed.set_footer(text=now.strftime("%Y-%m-%d %H:%M ET"))
            await channel.send(embed=embed)

            # Push notification to iOS
            daily = pnl_data["daily_pnl"]
            daily_pct = pnl_data["daily_pnl_pct"]
            total = pnl_data["total_pnl"]
            total_pct = pnl_data["total_pnl_pct"]
            close_body = (
                f"Daily: ${daily:+.2f} ({daily_pct:+.1f}%) · "
                f"Total: ${total:+.2f} ({total_pct:+.1f}%)"
            )
            await _send_scheduled_push("close", "Market Close", close_body)

        except Exception:
            logger.exception("Error sending daily status")
        finally:
            if portfolio:
                await portfolio.close()

    @daily_status_loop.before_loop
    async def before_daily(self) -> None:
        await self.bot.wait_until_ready()

    # --- Pre-Market Movers (8:00 AM ET) ---

    @tasks.loop(time=time(8, 0, tzinfo=ET))
    async def premarket_loop(self) -> None:
        now = datetime.now(ET)
        if now.weekday() >= 5:
            return

        channel = self._get_channel()
        if not channel:
            return

        strategy = None
        try:
            strategy = await self.bot.get_fresh_strategy()
            movers = await strategy.get_premarket_movers()
            if not movers:
                return

            embed = discord.Embed(
                title="Pre-Market Movers (CDR Counterparts)",
                description="Notable US premarket moves for CDR-tracked stocks:",
                color=0x3498DB,
            )
            for m in movers[:10]:
                direction = "\U0001f7e2" if m["change_pct"] > 0 else "\U0001f534"
                embed.add_field(
                    name=f"{direction} {m['cdr_symbol']} ({m['us_symbol']})",
                    value=(
                        f"Premarket: ${m['premarket_price']:.2f} "
                        f"({m['change_pct']:+.1%} from prev close)"
                    ),
                    inline=False,
                )

            footer = f"{now.strftime('%H:%M ET')} \u2014 premarket data via Yahoo Finance"
            embed.set_footer(text=footer)
            await channel.send(embed=embed)

            # Push notification to iOS
            top = movers[:3]
            summary = ", ".join(
                f"{m['cdr_symbol']} {m['change_pct']:+.1%}" for m in top
            )
            await _send_scheduled_push(
                "premarket",
                "Pre-Market Movers",
                summary,
            )

        except Exception:
            logger.exception("Error sending premarket movers")
        finally:
            if strategy:
                await strategy.portfolio.close()

    @premarket_loop.before_loop
    async def before_premarket(self) -> None:
        await self.bot.wait_until_ready()

    # --- Morning Briefing (8:30 AM ET) ---

    @tasks.loop(time=time(8, 30, tzinfo=ET))
    async def morning_briefing_loop(self) -> None:
        now = datetime.now(ET)
        if now.weekday() >= 5:
            return

        channel = self._get_channel()
        if not channel:
            return

        strategy = None
        try:
            strategy = await self.bot.get_fresh_strategy()
            insights = await strategy.get_daily_insights()
            await _send_insights_embeds(channel, insights, title="Morning Briefing")

            # Push notification to iOS
            pv = insights["portfolio_value"]
            pnl = insights["total_pnl"]
            pnl_pct = insights["total_pnl_pct"]
            n_holdings = len(insights["holdings"])
            await _send_scheduled_push(
                "briefing",
                "Morning Briefing",
                f"Portfolio: ${pv:,.2f} ({pnl:+.2f}, {pnl_pct:+.1f}%) · {n_holdings} holdings",
            )
        except Exception:
            logger.exception("Error sending morning briefing")
        finally:
            if strategy:
                await strategy.portfolio.close()

    @morning_briefing_loop.before_loop
    async def before_morning(self) -> None:
        await self.bot.wait_until_ready()

    # --- Evening Recap (10 PM Vancouver) ---

    @tasks.loop(time=time(22, 0, tzinfo=PT))
    async def evening_recap_loop(self) -> None:
        now = datetime.now(ET)
        if now.weekday() in (5, 6):
            return

        channel = self._get_channel()
        if not channel:
            return

        strategy = None
        try:
            strategy = await self.bot.get_fresh_strategy()
            insights = await strategy.get_daily_insights()
            await _send_insights_embeds(channel, insights, title="Evening Recap")

            # Push notification to iOS
            pv = insights["portfolio_value"]
            pnl = insights["total_pnl"]
            pnl_pct = insights["total_pnl_pct"]
            await _send_scheduled_push(
                "recap",
                "Evening Recap",
                f"Portfolio: ${pv:,.2f} ({pnl:+.2f}, {pnl_pct:+.1f}%)",
            )
        except Exception:
            logger.exception("Error sending evening recap")
        finally:
            if strategy:
                await strategy.portfolio.close()

    @evening_recap_loop.before_loop
    async def before_evening(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: TraderBot) -> None:
    await bot.add_cog(TasksCog(bot))
