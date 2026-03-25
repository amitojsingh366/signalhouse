"""Portfolio commands — /holdings and /pnl, plus inline edit views."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

from trader.bot import TraderBot
from trader.portfolio import Portfolio
from trader.risk import RiskManager

ET = ZoneInfo("America/New_York")


# ---------------------------------------------------------------------------
# Edit Holdings Views / Modals
# ---------------------------------------------------------------------------

class EditHoldingModal(discord.ui.Modal):
    """Modal to edit a single holding's data."""

    def __init__(
        self,
        holdings_list: list[dict[str, Any]],
        index: int,
        portfolio: Portfolio,
        risk: RiskManager,
    ) -> None:
        h = holdings_list[index]
        super().__init__(title=f"Edit Holding {index + 1}/{len(holdings_list)}")
        self.holdings_list = holdings_list
        self.index = index
        self.portfolio = portfolio
        self.risk = risk

        self.symbol_input = discord.ui.TextInput(
            label="Symbol",
            default=h["symbol"],
            required=True,
            max_length=20,
        )
        self.quantity_input = discord.ui.TextInput(
            label="Quantity (shares)",
            default=f"{h['quantity']:.4f}",
            required=True,
            max_length=20,
        )
        self.avg_cost_input = discord.ui.TextInput(
            label="Avg Cost per Share (CAD)",
            default=f"{h['avg_cost']:.2f}",
            required=True,
            max_length=20,
        )

        self.add_item(self.symbol_input)
        self.add_item(self.quantity_input)
        self.add_item(self.avg_cost_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            self.holdings_list[self.index] = {
                "symbol": self.symbol_input.value.strip().upper(),
                "quantity": float(self.quantity_input.value.strip()),
                "avg_cost": float(self.avg_cost_input.value.strip()),
            }
        except ValueError:
            await interaction.response.send_message(
                "Invalid number \u2014 quantity and cost must be numeric.", ephemeral=True
            )
            return

        next_idx = self.index + 1
        if next_idx < len(self.holdings_list):
            embed = _build_holdings_edit_progress(self.holdings_list, next_idx)
            view = EditNextHoldingView(
                self.holdings_list, next_idx, self.portfolio, self.risk
            )
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.defer()
            await self._apply_holdings(interaction)

    async def _apply_holdings(self, interaction: discord.Interaction) -> None:
        parsed = [
            {
                "symbol": h["symbol"],
                "quantity": h["quantity"],
                "market_value_cad": h["quantity"] * h["avg_cost"],
            }
            for h in self.holdings_list
        ]
        await self.portfolio.sync_from_snapshot(parsed, self.risk)
        await interaction.followup.send(
            f"Portfolio updated with {len(parsed)} holdings."
        )


def _build_holdings_edit_progress(
    holdings_list: list[dict[str, Any]], next_idx: int
) -> discord.Embed:
    """Show which holdings have been edited so far."""
    lines = []
    for i, h in enumerate(holdings_list):
        check = "\u2705" if i < next_idx else "\u270F\uFE0F"
        value = h["quantity"] * h["avg_cost"]
        lines.append(
            f"{check} **{h['symbol']}** \u2014 {h['quantity']:.4f} shares, "
            f"avg ${h['avg_cost']:.2f} (${value:.2f})"
        )
    embed = discord.Embed(
        title=f"Editing Holdings ({next_idx}/{len(holdings_list)} done)",
        description="\n".join(lines),
        color=0xF39C12,
    )
    embed.set_footer(text=f"Next: {holdings_list[next_idx]['symbol']}")
    return embed


class EditNextHoldingView(discord.ui.View):
    """Button to open the next holding's edit modal."""

    def __init__(
        self,
        holdings_list: list[dict[str, Any]],
        index: int,
        portfolio: Portfolio,
        risk: RiskManager,
    ) -> None:
        super().__init__(timeout=300)
        self.holdings_list = holdings_list
        self.index = index
        self.portfolio = portfolio
        self.risk = risk

    @discord.ui.button(
        label="Edit Next", style=discord.ButtonStyle.primary, emoji="\u270F\uFE0F"
    )
    async def edit_next(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        modal = EditHoldingModal(
            self.holdings_list, self.index, self.portfolio, self.risk
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="Save & Finish", style=discord.ButtonStyle.success, emoji="\u2705"
    )
    async def save_finish(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.defer()
        parsed = [
            {
                "symbol": h["symbol"],
                "quantity": h["quantity"],
                "market_value_cad": h["quantity"] * h["avg_cost"],
            }
            for h in self.holdings_list
        ]
        await self.portfolio.sync_from_snapshot(parsed, self.risk)
        await interaction.followup.send(
            f"Portfolio updated with {len(parsed)} holdings."
        )
        self.stop()


class HoldingsView(discord.ui.View):
    """Edit button for the /holdings display."""

    def __init__(self, portfolio: Portfolio, risk: RiskManager) -> None:
        super().__init__(timeout=300)
        self.portfolio = portfolio
        self.risk = risk

    @discord.ui.button(
        label="Edit Holdings", style=discord.ButtonStyle.primary, emoji="\u270F\uFE0F"
    )
    async def edit_holdings(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not self.portfolio.holdings:
            await interaction.response.send_message(
                "No holdings to edit.", ephemeral=True
            )
            return

        holdings_list = [
            {
                "symbol": sym,
                "quantity": h["quantity"],
                "avg_cost": h["avg_cost"],
            }
            for sym, h in self.portfolio.holdings.items()
        ]

        modal = EditHoldingModal(holdings_list, 0, self.portfolio, self.risk)
        await interaction.response.send_modal(modal)


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class PortfolioCog(commands.Cog):
    """Portfolio viewing and P&L commands."""

    def __init__(self, bot: TraderBot) -> None:
        self.bot = bot

    @app_commands.command(name="holdings", description="View current portfolio holdings")
    async def holdings(self, interaction: discord.Interaction) -> None:
        if not self.bot.portfolio.holdings:
            await interaction.response.send_message(
                "No holdings tracked yet. Use `/buy` or `/upload` to add."
            )
            return

        await interaction.response.defer(thinking=True)

        symbols = list(self.bot.portfolio.holdings.keys())
        prices = await self.bot.market_data.get_batch_prices(symbols)

        action_emojis = {
            "HOLD": "\U0001f7e1", "HOLD+": "\U0001f7e2",
            "SELL": "\U0001f534", "SWAP": "\U0001f504",
        }

        total_value = 0.0
        total_cost = 0.0

        embed = discord.Embed(title="Current Holdings", color=0x3498DB)

        for sym in symbols:
            h = self.bot.portfolio.holdings[sym]
            price = prices.get(sym, h["avg_cost"])
            value = h["quantity"] * price
            cost = h["quantity"] * h["avg_cost"]
            total_value += value
            total_cost += cost

            advice = await self.bot.strategy.get_holding_advice(
                sym, price, find_alternatives=False
            )

            action = advice["action"]
            action_emoji = action_emojis.get(action, "\u26AA")
            pnl_pct = advice["pnl_pct"]
            pnl_emoji = "\U0001f7e2" if pnl_pct >= 0 else "\U0001f534"

            top_reasons = [
                r for r in advice["reasons"][:3]
                if not r.startswith(("Price:", "ATR:", "Sector:"))
            ]
            reasons_str = " | ".join(top_reasons) if top_reasons else ""
            detail = advice.get("action_detail", "")

            value_lines = [
                f"{h['quantity']:.4f} sh @ ${price:.2f} {pnl_emoji} {pnl_pct:+.1f}%",
                f"Avg: ${h['avg_cost']:.2f} | Value: ${value:.2f}",
            ]
            if reasons_str:
                value_lines.append(reasons_str)
            if detail:
                value_lines.append(f"**\u27A1 {detail}**")

            embed.add_field(
                name=f"{action_emoji} {sym} \u2014 {action}",
                value="\n".join(value_lines),
                inline=False,
            )

        total_pnl = total_value - total_cost
        embed.add_field(
            name="Total",
            value=f"${total_value:.2f} ({total_pnl:+.2f})",
            inline=True,
        )
        embed.add_field(name="Cash", value=f"${self.bot.portfolio.cash:.2f}", inline=True)
        embed.set_footer(text=datetime.now(ET).strftime("%H:%M ET"))
        view = HoldingsView(self.bot.portfolio, self.bot.risk)
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="pnl", description="View P&L breakdown")
    async def pnl(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        symbols = list(self.bot.portfolio.holdings.keys())
        prices = await self.bot.market_data.get_batch_prices(symbols) if symbols else {}
        pnl_data = self.bot.portfolio.get_daily_pnl(prices)

        embed = discord.Embed(
            title="P&L Summary",
            color=pnl_color(pnl_data["total_pnl"]),
        )
        embed.add_field(
            name="Portfolio Value",
            value=f"${pnl_data['current_value']:.2f}",
            inline=True,
        )
        embed.add_field(
            name="Initial Capital",
            value=f"${pnl_data['initial_capital']:.2f}",
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
            inline=True,
        )

        recent = self.bot.portfolio.get_recent_trades(5)
        if recent:
            lines = []
            for t in reversed(recent):
                emoji = "\U0001f7e2" if t["action"] == "BUY" else "\U0001f534"
                pnl_str = ""
                if "pnl" in t:
                    pnl_str = f" (P&L: ${t['pnl']:+.2f})"
                lines.append(
                    f"{emoji} {t['action']} {t['quantity']:.4f} x {t['symbol']} "
                    f"@ ${t['price']:.2f}{pnl_str}"
                )
            embed.add_field(
                name="Recent Trades", value="\n".join(lines), inline=False
            )

        embed.set_footer(text=datetime.now(ET).strftime("%Y-%m-%d %H:%M ET"))
        await interaction.followup.send(embed=embed)


def pnl_color(pnl: float) -> int:
    """Return embed color based on P&L."""
    if pnl > 0:
        return 0x2ECC71
    elif pnl < 0:
        return 0xE74C3C
    return 0x95A5A6


async def setup(bot: TraderBot) -> None:
    await bot.add_cog(PortfolioCog(bot))
