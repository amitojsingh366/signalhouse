"""Signal commands — /recommend, /check, and the recheck button view."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands
from trader_api.services.signals import Signal, SignalResult

from trader_bot.bot import TraderBot

ET = ZoneInfo("America/New_York")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def signal_emoji(sig: Signal) -> str:
    if sig == Signal.BUY:
        return "\U0001f7e2"
    elif sig == Signal.SELL:
        return "\U0001f534"
    return "\U0001f7e1"


def _build_buy_embed(
    sig: SignalResult, funding: list[dict[str, Any]]
) -> discord.Embed:
    """Build a BUY signal embed with optional sell-to-fund suggestion."""
    embed = discord.Embed(
        title=f"{sig.symbol} \u2014 BUY Signal",
        description="\n".join(f"\u2022 {r}" for r in sig.reasons),
        color=0x2ECC71,
    )
    embed.add_field(name="Strength", value=f"{sig.strength:.0%}", inline=True)

    fund = next((f for f in funding if f["buy"] == sig.symbol), None)
    if fund:
        s = fund["sell"]
        pnl_emoji = "\U0001f7e2" if s["pnl_pct"] >= 0 else "\U0001f534"
        sell_label = "Sell signal" if s["has_sell_signal"] else "Weakest holding"
        action = s.get("sell_action", "Sell all")

        sell_reasons = [
            r for r in s.get("reasons", [])[:2]
            if not r.startswith(("Price:", "ATR:", "Sector:"))
        ]
        reasons_str = " | ".join(sell_reasons) if sell_reasons else ""

        value_lines = [
            f"{sell_label} \u2014 {s['quantity']:.4f} sh @ ${s['price']:.2f}",
            f"Value: ${s['value']:.2f} {pnl_emoji} ({s['pnl_pct']:+.1f}%)",
        ]
        if reasons_str:
            value_lines.append(reasons_str)
        value_lines.append(
            f"Sector: {s['sector']} ({s['sector_pct']:.0%} of portfolio)"
        )

        embed.add_field(
            name=f"\U0001f4b0 {action} {s['symbol']} to fund",
            value="\n".join(value_lines),
            inline=False,
        )

    embed.set_footer(text=datetime.now(ET).strftime("%H:%M ET"))
    return embed


def _build_sell_embed(sig: SignalResult) -> discord.Embed:
    """Build a SELL signal embed for a held position."""
    embed = discord.Embed(
        title=f"{sig.symbol} \u2014 SELL Signal",
        description="\n".join(f"\u2022 {r}" for r in sig.reasons),
        color=0xE74C3C,
    )
    embed.add_field(name="Strength", value=f"{sig.strength:.0%}", inline=True)
    embed.set_footer(text=datetime.now(ET).strftime("%H:%M ET"))
    return embed


def _build_action_embed(action: dict[str, Any]) -> discord.Embed:
    """Build an embed for an action plan trade instruction."""
    action_type = action["type"]
    urgency = action.get("urgency", "normal")

    if action_type == "SELL":
        urgency_label = "\U0001f6a8 URGENT" if urgency == "urgent" else (
            "\u26A0\uFE0F" if urgency == "normal" else "\U0001f4AD"
        )
        embed = discord.Embed(
            title=f"{urgency_label} SELL {action['symbol']}",
            description=action.get("detail", ""),
            color=0xE74C3C,
        )
        embed.add_field(name="Shares", value=f"{action['shares']:.4f}", inline=True)
        embed.add_field(name="Price", value=f"${action['price']:.2f}", inline=True)
        embed.add_field(name="Value", value=f"${action['dollar_amount']:,.2f}", inline=True)
        if action.get("pnl_pct") is not None:
            pnl_emoji = "\U0001f7e2" if action["pnl_pct"] >= 0 else "\U0001f534"
            embed.add_field(
                name="P&L",
                value=f"{pnl_emoji} {action['pnl_pct']:+.1f}%",
                inline=True,
            )
        embed.add_field(name="Reason", value=action.get("reason", ""), inline=False)

    elif action_type == "BUY":
        embed = discord.Embed(
            title=f"\U0001f4B0 BUY {action['symbol']}",
            description=action.get("detail", ""),
            color=0x2ECC71,
        )
        embed.add_field(name="Shares", value=str(action["shares"]), inline=True)
        embed.add_field(name="Price", value=f"~${action['price']:.2f}", inline=True)
        embed.add_field(name="Cost", value=f"${action['dollar_amount']:,.2f}", inline=True)
        if action.get("pct_of_portfolio"):
            embed.add_field(
                name="% Portfolio", value=f"{action['pct_of_portfolio']:.1f}%", inline=True
            )
        if action.get("strength"):
            embed.add_field(
                name="Strength", value=f"{action['strength']:.0%}", inline=True
            )
        sector = action.get("sector")
        if sector:
            embed.add_field(name="Sector", value=sector, inline=True)

    elif action_type == "SWAP":
        embed = discord.Embed(
            title=(
                f"\U0001f504 SWAP {action.get('sell_symbol', '')} "
                f"\u2192 {action.get('buy_symbol', '')}"
            ),
            description=action.get("detail", ""),
            color=0x3498DB,
        )
        sell_pnl = action.get("sell_pnl_pct", 0)
        pnl_emoji = "\U0001f7e2" if sell_pnl >= 0 else "\U0001f534"
        embed.add_field(
            name=f"Sell {action.get('sell_symbol', '')}",
            value=(
                f"{action.get('sell_shares', 0):.4f} sh @ ${action.get('sell_price', 0):.2f}\n"
                f"${action.get('sell_amount', 0):,.2f} {pnl_emoji} {sell_pnl:+.1f}%"
            ),
            inline=True,
        )
        embed.add_field(
            name=f"Buy {action.get('buy_symbol', '')}",
            value=(
                f"{action.get('buy_shares', 0)} sh @ ~${action.get('buy_price', 0):.2f}\n"
                f"${action.get('buy_amount', 0):,.2f} ({action.get('buy_strength', 0):.0%} signal)"
            ),
            inline=True,
        )
    else:
        embed = discord.Embed(title=action_type, description=action.get("detail", ""))

    embed.set_footer(text=datetime.now(ET).strftime("%H:%M ET"))
    return embed


# ---------------------------------------------------------------------------
# Persistent Recheck Button
# ---------------------------------------------------------------------------

class RecheckView(discord.ui.View):
    """Button that re-analyzes a symbol when clicked. Survives bot restarts."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Recheck Signal",
        style=discord.ButtonStyle.primary,
        custom_id="recheck_signal",
        emoji="\U0001f504",
    )
    async def recheck(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not interaction.message or not interaction.message.embeds:
            await interaction.response.send_message(
                "Could not find signal data.", ephemeral=True
            )
            return

        embed = interaction.message.embeds[0]
        symbol = embed.title.split(" ")[0] if embed.title else None
        if not symbol:
            await interaction.response.send_message(
                "Could not determine symbol.", ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)

        bot: TraderBot = interaction.client  # type: ignore[assignment]
        strategy = await bot.get_fresh_strategy()
        try:
            result = await strategy.analyze_symbol(symbol)

            new_embed = discord.Embed(
                title=f"{symbol} \u2014 {result.signal.value} Signal (Recheck)",
                description="\n".join(f"\u2022 {r}" for r in result.reasons),
                color=0x2ECC71 if result.signal == Signal.BUY else (
                    0xE74C3C if result.signal == Signal.SELL else 0x95A5A6
                ),
            )
            new_embed.add_field(
                name="Strength", value=f"{result.strength:.0%}", inline=True
            )
            sig_val = f"{signal_emoji(result.signal)} {result.signal.value}"
            new_embed.add_field(name="Signal", value=sig_val, inline=True)
            new_embed.set_footer(text=f"Rechecked at {datetime.now(ET).strftime('%H:%M ET')}")

            await interaction.followup.send(embed=new_embed, view=RecheckView())
        finally:
            await strategy.portfolio.close()


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class SignalsCog(commands.Cog):
    """Signal recommendation commands."""

    def __init__(self, bot: TraderBot) -> None:
        self.bot = bot

    @app_commands.command(
        name="check",
        description="Check signal and sentiment for a specific symbol",
    )
    @app_commands.describe(symbol="Stock symbol (e.g. NVDA.NE, RY.TO, AAPL)")
    async def check(self, interaction: discord.Interaction, symbol: str) -> None:
        symbol = symbol.upper().strip()
        await interaction.response.defer(thinking=True)

        if "." not in symbol:
            resolved = await self.bot.market_data.resolve_symbol(symbol)
            if resolved:
                symbol = resolved
            else:
                await interaction.followup.send(
                    f"Could not find data for `{symbol}`. Try adding a suffix like `.TO` or `.NE`.",
                    ephemeral=True,
                )
                return

        strategy = await self.bot.get_fresh_strategy()
        portfolio = await self.bot.get_fresh_portfolio()
        try:
            result = await strategy.analyze_symbol(symbol)

            color = (
                0x2ECC71 if result.signal == Signal.BUY
                else 0xE74C3C if result.signal == Signal.SELL
                else 0x95A5A6
            )
            embed = discord.Embed(
                title=f"{symbol} \u2014 {result.signal.value} Signal",
                description="\n".join(f"\u2022 {r}" for r in result.reasons),
                color=color,
            )
            embed.add_field(
                name="Signal",
                value=f"{signal_emoji(result.signal)} {result.signal.value}",
                inline=True,
            )
            embed.add_field(name="Strength", value=f"{result.strength:.0%}", inline=True)

            # Show holding info + actionable advice if user holds this symbol
            holdings = await portfolio.get_holdings_dict()
            h = holdings.get(symbol)
            if h:
                prices = await self.bot.market_data.get_batch_prices([symbol])
                price = prices.get(symbol, h["avg_cost"])
                avg = h["avg_cost"]
                pnl_pct = (price - avg) / avg * 100 if avg > 0 else 0.0
                pnl_emoji = "\U0001f7e2" if pnl_pct >= 0 else "\U0001f534"

                embed.add_field(
                    name="Your Position",
                    value=(
                        f"{h['quantity']:.4f} shares @ ${h['avg_cost']:.2f}\n"
                        f"Current: ${price:.2f} {pnl_emoji} {pnl_pct:+.1f}%"
                    ),
                    inline=False,
                )

                alternative = None
                if result.signal != Signal.BUY:
                    alternative = await strategy._find_better_alternative(
                        symbol, result, {symbol: price}
                    )
                advice = strategy._holding_action(result, pnl_pct, alternative)

                action = advice["action"]
                action_emojis = {
                    "HOLD": "\U0001f7e1", "HOLD+": "\U0001f7e2",
                    "SELL": "\U0001f534", "SWAP": "\U0001f504",
                }
                action_emoji = action_emojis.get(action, "\u26AA")
                detail = advice.get("detail", "")
                if detail:
                    embed.add_field(
                        name=f"{action_emoji} Advice: {action}",
                        value=detail,
                        inline=False,
                    )

                alt = advice.get("alternative")
                if alt:
                    alt_reasons = " | ".join(
                        r for r in alt.get("reasons", [])[:2]
                        if not r.startswith(("Price:", "ATR:"))
                    )
                    alt_text = (
                        f"**{alt['symbol']}** \u2014 BUY {alt['strength']:.0%} "
                        f"@ ${alt['price']:.2f}"
                    )
                    if alt_reasons:
                        alt_text += f"\n{alt_reasons}"
                    embed.add_field(
                        name="\U0001f4a1 Consider Instead",
                        value=alt_text,
                        inline=False,
                    )

            embed.set_footer(text=datetime.now(ET).strftime("%H:%M ET"))
            await interaction.followup.send(embed=embed, view=RecheckView())
        finally:
            await portfolio.close()
            await strategy.portfolio.close()

    @check.autocomplete("symbol")
    async def check_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        current_upper = current.upper()
        choices: list[app_commands.Choice[str]] = []

        # Show held symbols first (use cached strategy symbols; autocomplete must be fast)
        portfolio = await self.bot.get_fresh_portfolio()
        try:
            holdings = await portfolio.get_holdings_dict()
            for sym in holdings:
                if current_upper in sym:
                    choices.append(app_commands.Choice(name=f"\u2B50 {sym} (held)", value=sym))

            for sym in self.bot.strategy.symbols:
                if sym in holdings:
                    continue
                if current_upper in sym:
                    choices.append(app_commands.Choice(name=sym, value=sym))
                if len(choices) >= 25:
                    break
        finally:
            await portfolio.close()

        return choices[:25]

    @app_commands.command(
        name="recommend",
        description="Get today's action plan",
    )
    async def recommend(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)

        strategy = await self.bot.get_fresh_strategy()
        portfolio = await self.bot.get_fresh_portfolio()
        try:
            plan = await strategy.get_action_plan()
            actions = plan["actions"]

            if not actions:
                await interaction.followup.send(
                    "\u2705 No trades needed right now. Portfolio is on track."
                )
                return

            # Summary header
            summary_embed = discord.Embed(
                title="\U0001f4CB Today's Action Plan",
                description=(
                    f"**{len(actions)} trade(s)** to execute"
                    f" \u2014 {plan['sells_count']} sell(s),"
                    f" {plan['swaps_count']} swap(s),"
                    f" {plan['buys_count']} buy(s)"
                ),
                color=0x8B5CF6,
            )
            summary_embed.add_field(
                name="Portfolio", value=f"${plan['portfolio_value']:,.2f}", inline=True
            )
            summary_embed.add_field(
                name="Cash", value=f"${plan['cash']:,.2f}", inline=True
            )
            summary_embed.add_field(
                name="Positions",
                value=f"{plan['num_positions']}/{plan['max_positions']}",
                inline=True,
            )
            await interaction.followup.send(embed=summary_embed)

            # Individual action embeds
            for action in actions:
                embed = _build_action_embed(action)
                await interaction.followup.send(embed=embed, view=RecheckView())

        finally:
            await portfolio.close()
            await strategy.portfolio.close()


async def setup(bot: TraderBot) -> None:
    bot.add_view(RecheckView())  # Register persistent view for recheck buttons
    await bot.add_cog(SignalsCog(bot))
