"""Portfolio commands — /holdings and /pnl, plus inline edit views."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

from trader_bot.bot import TraderBot
from trader_api.services.portfolio import Portfolio
from trader_api.services.risk import RiskManager

ET = ZoneInfo("America/New_York")


# ---------------------------------------------------------------------------
# Edit Holdings Views / Modals
# ---------------------------------------------------------------------------

def _build_holdings_edit_list(holdings_list: list[dict[str, Any]]) -> discord.Embed:
    """Show all holdings in the edit view."""
    lines = []
    for h in holdings_list:
        value = h["quantity"] * h["avg_cost"]
        lines.append(
            f"\u2022 **{h['symbol']}** \u2014 {h['quantity']:.4f} shares, "
            f"avg ${h['avg_cost']:.2f} (${value:.2f})"
        )
    return discord.Embed(
        title="Edit Holdings",
        description="\n".join(lines),
        color=0xF39C12,
    ).set_footer(text="Select a holding to edit, or Save to apply changes.")


class EditSingleHoldingModal(discord.ui.Modal):
    """Modal to edit one holding, then return to the select view."""

    def __init__(
        self,
        holdings_list: list[dict[str, Any]],
        index: int,
        bot: TraderBot,
    ) -> None:
        h = holdings_list[index]
        super().__init__(title=f"Edit {h['symbol']}")
        self.holdings_list = holdings_list
        self.index = index
        self._bot = bot

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

        embed = _build_holdings_edit_list(self.holdings_list)
        view = HoldingSelectView(self.holdings_list, self._bot)
        await interaction.response.edit_message(embed=embed, view=view)


class HoldingSelectView(discord.ui.View):
    """Dropdown to pick which holding to edit + Save button."""

    def __init__(
        self,
        holdings_list: list[dict[str, Any]],
        bot: TraderBot,
    ) -> None:
        super().__init__(timeout=300)
        self.holdings_list = holdings_list
        self._bot = bot

        options = []
        for i, h in enumerate(holdings_list[:25]):
            value = h["quantity"] * h["avg_cost"]
            options.append(discord.SelectOption(
                label=h["symbol"],
                description=f"{h['quantity']:.4f} sh @ ${h['avg_cost']:.2f} (${value:.2f})",
                value=str(i),
            ))

        self.select = discord.ui.Select(
            placeholder="Select a holding to edit\u2026",
            options=options,
        )
        self.select.callback = self._on_select
        self.add_item(self.select)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        index = int(self.select.values[0])
        modal = EditSingleHoldingModal(
            self.holdings_list, index, self._bot
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="Save", style=discord.ButtonStyle.success, emoji="\u2705"
    )
    async def save(
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
        portfolio = await self._bot.get_fresh_portfolio()
        try:
            await portfolio.sync_from_snapshot(parsed, self._bot.risk)
            await interaction.followup.send(
                f"Portfolio updated with {len(parsed)} holdings."
            )
        finally:
            await portfolio.close()
        self.stop()


class HoldingsView(discord.ui.View):
    """Edit button for the /holdings display."""

    def __init__(self, bot: TraderBot) -> None:
        super().__init__(timeout=300)
        self._bot = bot

    @discord.ui.button(
        label="Edit Holdings", style=discord.ButtonStyle.primary, emoji="\u270F\uFE0F"
    )
    async def edit_holdings(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        portfolio = await self._bot.get_fresh_portfolio()
        try:
            holdings = await portfolio.get_holdings_dict()

            if not holdings:
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
                for sym, h in holdings.items()
            ]

            embed = _build_holdings_edit_list(holdings_list)
            view = HoldingSelectView(holdings_list, self._bot)
            await interaction.response.edit_message(embed=embed, view=view)
        finally:
            await portfolio.close()


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class PortfolioCog(commands.Cog):
    """Portfolio viewing and P&L commands."""

    def __init__(self, bot: TraderBot) -> None:
        self.bot = bot

    @app_commands.command(name="holdings", description="View current portfolio holdings")
    async def holdings(self, interaction: discord.Interaction) -> None:
        portfolio = await self.bot.get_fresh_portfolio()
        strategy = None
        try:
            holdings = await portfolio.get_holdings_dict()

            if not holdings:
                await interaction.response.send_message(
                    "No holdings tracked yet. Use `/buy` or `/upload` to add."
                )
                return

            await interaction.response.defer(thinking=True)

            strategy = await self.bot.get_fresh_strategy()
            symbols = list(holdings.keys())
            prices = await self.bot.market_data.get_batch_prices(symbols)

            action_emojis = {
                "HOLD": "\U0001f7e1", "HOLD+": "\U0001f7e2",
                "SELL": "\U0001f534", "SWAP": "\U0001f504",
            }

            total_value = 0.0
            total_cost = 0.0

            embed = discord.Embed(title="Current Holdings", color=0x3498DB)

            for sym in symbols:
                h = holdings[sym]
                price = prices.get(sym, h["avg_cost"])
                value = h["quantity"] * price
                cost = h["quantity"] * h["avg_cost"]
                total_value += value
                total_cost += cost

                advice = await strategy.get_holding_advice(
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

            meta = await portfolio._get_meta()
            total_pnl = total_value - total_cost
            embed.add_field(
                name="Total",
                value=f"${total_value:.2f} ({total_pnl:+.2f})",
                inline=True,
            )
            embed.add_field(name="Cash", value=f"${meta.cash:.2f}", inline=True)
            embed.set_footer(text=datetime.now(ET).strftime("%H:%M ET"))
            view = HoldingsView(self.bot)
            await interaction.followup.send(embed=embed, view=view)
        finally:
            await portfolio.close()
            if strategy:
                await strategy.portfolio.close()

    @app_commands.command(name="pnl", description="View P&L breakdown")
    async def pnl(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        portfolio = await self.bot.get_fresh_portfolio()
        try:
            holdings = await portfolio.get_holdings_dict()
            symbols = list(holdings.keys())
            prices = await self.bot.market_data.get_batch_prices(symbols) if symbols else {}
            pnl_data = await portfolio.get_daily_pnl(prices)

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

            recent = await portfolio.get_recent_trades(5)
            if recent:
                lines = []
                for t in reversed(recent):
                    emoji = "\U0001f7e2" if t["action"] == "BUY" else "\U0001f534"
                    pnl_str = ""
                    if t.get("pnl"):
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
        finally:
            await portfolio.close()


def pnl_color(pnl: float) -> int:
    """Return embed color based on P&L."""
    if pnl > 0:
        return 0x2ECC71
    elif pnl < 0:
        return 0xE74C3C
    return 0x95A5A6


async def setup(bot: TraderBot) -> None:
    await bot.add_cog(PortfolioCog(bot))
