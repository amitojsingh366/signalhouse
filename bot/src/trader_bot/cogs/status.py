"""Status command — /status."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

from trader_bot.bot import TraderBot, is_market_hours

ET = ZoneInfo("America/New_York")


class StatusCog(commands.Cog):
    """Bot status overview."""

    def __init__(self, bot: TraderBot) -> None:
        self.bot = bot

    @app_commands.command(name="status", description="Bot status overview")
    async def status(self, interaction: discord.Interaction) -> None:
        now = datetime.now(ET)
        uptime = now - self.bot.start_time

        portfolio = await self.bot.get_fresh_portfolio()
        try:
            holdings = await portfolio.get_holdings_dict()

            embed = discord.Embed(title="Bot Status", color=0x3498DB)
            embed.add_field(
                name="Uptime",
                value=f"{uptime.days}d {uptime.seconds // 3600}h {(uptime.seconds % 3600) // 60}m",
                inline=True,
            )
            embed.add_field(
                name="Symbols Tracked",
                value=str(len(self.bot.strategy.symbols)),
                inline=True,
            )
            embed.add_field(
                name="Holdings",
                value=str(len(holdings)),
                inline=True,
            )
            embed.add_field(
                name="Market Hours",
                value="Open" if is_market_hours(self.bot.config) else "Closed",
                inline=True,
            )
            embed.add_field(
                name="Scan Interval",
                value=f"{self.bot.config['schedule']['scan_interval_minutes']}m",
                inline=True,
            )
            embed.set_footer(text=now.strftime("%Y-%m-%d %H:%M ET"))
            await interaction.response.send_message(embed=embed)
        finally:
            await portfolio.close()


async def setup(bot: TraderBot) -> None:
    await bot.add_cog(StatusCog(bot))
