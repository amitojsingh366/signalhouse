"""Signal commands — /recommend, /check, and the recheck button view."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

from trader.bot import TraderBot
from trader.signals import Signal, SignalResult

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
        result = await bot.strategy.analyze_symbol(symbol)

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
        new_embed.add_field(
            name="Signal", value=f"{signal_emoji(result.signal)} {result.signal.value}", inline=True
        )
        new_embed.set_footer(text=f"Rechecked at {datetime.now(ET).strftime('%H:%M ET')}")

        await interaction.followup.send(embed=new_embed, view=RecheckView())


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

        result = await self.bot.strategy.analyze_symbol(symbol)

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
        h = self.bot.portfolio.holdings.get(symbol)
        if h:
            prices = await self.bot.market_data.get_batch_prices([symbol])
            price = prices.get(symbol, h["avg_cost"])
            pnl_pct = (price - h["avg_cost"]) / h["avg_cost"] * 100 if h["avg_cost"] > 0 else 0.0
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
                alternative = await self.bot.strategy._find_better_alternative(
                    symbol, result, {symbol: price}
                )
            advice = self.bot.strategy._holding_action(result, pnl_pct, alternative)

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

    @check.autocomplete("symbol")
    async def check_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        current_upper = current.upper()
        choices: list[app_commands.Choice[str]] = []

        for sym in self.bot.portfolio.holdings:
            if current_upper in sym:
                choices.append(app_commands.Choice(name=f"\u2B50 {sym} (held)", value=sym))

        for sym in self.bot.strategy.symbols:
            if sym in self.bot.portfolio.holdings:
                continue
            if current_upper in sym:
                choices.append(app_commands.Choice(name=sym, value=sym))
            if len(choices) >= 25:
                break

        return choices[:25]

    @app_commands.command(name="recommend", description="Get current buy/sell recommendations")
    async def recommend(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)

        recs = await self.bot.strategy.get_top_recommendations(n=5)

        if not recs["buys"] and not recs["sells"]:
            await interaction.followup.send("No actionable signals right now. Market may be quiet.")
            return

        exposure = recs.get("sector_exposure", {})
        if exposure:
            lines = []
            for sector, data in sorted(
                exposure.items(), key=lambda x: x[1]["pct"], reverse=True
            ):
                bar_len = int(data["pct"] * 20)
                bar = "\u2588" * bar_len + "\u2591" * (20 - bar_len)
                syms = ", ".join(data["symbols"])
                lines.append(f"`{bar}` **{sector}** {data['pct']:.0%} ({syms})")
            exp_embed = discord.Embed(
                title="Portfolio Sector Exposure",
                description="\n".join(lines),
                color=0x3498DB,
            )
            exp_embed.add_field(
                name="Cash", value=f"${self.bot.portfolio.cash:.2f}", inline=True
            )
            await interaction.followup.send(embed=exp_embed)

        funding = recs.get("funding", [])
        for sig in recs["buys"]:
            embed = _build_buy_embed(sig, funding)
            await interaction.followup.send(embed=embed, view=RecheckView())

        for sig in recs["sells"]:
            embed = _build_sell_embed(sig)
            await interaction.followup.send(embed=embed, view=RecheckView())


async def setup(bot: TraderBot) -> None:
    bot.add_view(RecheckView())  # Register persistent view for recheck buttons
    await bot.add_cog(SignalsCog(bot))
