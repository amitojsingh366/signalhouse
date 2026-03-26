"""Trading commands — /buy and /sell."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from trader_bot.bot import TraderBot


class TradingCog(commands.Cog):
    """Record buy and sell trades."""

    def __init__(self, bot: TraderBot) -> None:
        self.bot = bot

    @app_commands.command(name="buy", description="Record a buy trade")
    @app_commands.describe(
        symbol="Stock symbol (e.g. RY.TO, AMD.NE)",
        quantity="Number of shares (supports fractional)",
        price="Price per share in CAD",
    )
    async def buy(
        self, interaction: discord.Interaction, symbol: str, quantity: float, price: float
    ) -> None:
        symbol = symbol.upper()
        await interaction.response.defer()

        portfolio = await self.bot.get_fresh_portfolio()
        trade = await portfolio.record_buy(symbol, quantity, price, self.bot.risk)
        meta = await portfolio._get_meta()

        embed = discord.Embed(
            title=f"\U0001f7e2 BUY Recorded \u2014 {symbol}",
            color=0x2ECC71,
        )
        embed.add_field(name="Quantity", value=f"{quantity:.4f}", inline=True)
        embed.add_field(name="Price", value=f"${price:.2f}", inline=True)
        embed.add_field(name="Total", value=f"${trade['total']:.2f}", inline=True)
        embed.add_field(
            name="Cash Remaining", value=f"${meta.cash:.2f}", inline=False
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="sell", description="Record a sell trade")
    @app_commands.describe(
        symbol="Stock symbol (e.g. RY.TO, AMD.NE)",
        quantity="Number of shares to sell",
        price="Price per share in CAD",
    )
    async def sell(
        self, interaction: discord.Interaction, symbol: str, quantity: float, price: float
    ) -> None:
        symbol = symbol.upper()
        await interaction.response.defer()

        portfolio = await self.bot.get_fresh_portfolio()
        trade = await portfolio.record_sell(symbol, quantity, price, self.bot.risk)

        if trade is None:
            await interaction.followup.send(
                f"Cannot sell {symbol} \u2014 insufficient holdings.", ephemeral=True
            )
            return

        color = 0x2ECC71 if trade["pnl"] >= 0 else 0xE74C3C
        embed = discord.Embed(
            title=f"\U0001f534 SELL Recorded \u2014 {symbol}",
            color=color,
        )
        embed.add_field(name="Quantity", value=f"{quantity:.4f}", inline=True)
        embed.add_field(name="Price", value=f"${price:.2f}", inline=True)
        embed.add_field(name="Total", value=f"${trade['total']:.2f}", inline=True)
        embed.add_field(
            name="P&L",
            value=f"${trade['pnl']:+.2f} ({trade['pnl_pct']:+.1f}%)",
            inline=True,
        )
        await interaction.followup.send(embed=embed)


async def setup(bot: TraderBot) -> None:
    await bot.add_cog(TradingCog(bot))
