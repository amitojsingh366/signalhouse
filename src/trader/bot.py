"""Discord bot — slash commands, recheck buttons, scheduled market scans."""

from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from trader.market_data import MarketData
from trader.portfolio import Portfolio
from trader.risk import RiskManager
from trader.signals import Signal
from trader.strategy import Strategy
from trader.vision import parse_holdings_screenshot

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_market_hours(config: dict) -> bool:
    """Check if current time is within market hours (ET), weekday only."""
    now = datetime.now(ET)
    if now.weekday() >= 5:
        return False
    market_open = datetime.strptime(config["schedule"]["market_open"], "%H:%M").time()
    market_close = datetime.strptime(config["schedule"]["market_close"], "%H:%M").time()
    return market_open <= now.time() <= market_close


def signal_emoji(sig: Signal) -> str:
    if sig == Signal.BUY:
        return "\U0001f7e2"  # green circle
    elif sig == Signal.SELL:
        return "\U0001f534"  # red circle
    return "\U0001f7e1"  # yellow circle


def pnl_color(pnl: float) -> int:
    """Return embed color based on P&L."""
    if pnl > 0:
        return 0x2ECC71  # green
    elif pnl < 0:
        return 0xE74C3C  # red
    return 0x95A5A6  # gray


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
        # Extract symbol from the embed title
        if not interaction.message or not interaction.message.embeds:
            await interaction.response.send_message(
                "Could not find signal data.", ephemeral=True
            )
            return

        embed = interaction.message.embeds[0]
        # Title format: "SYMBOL — BUY/SELL Signal"
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
# Confirmation View for Screenshot Upload
# ---------------------------------------------------------------------------

class ConfirmUploadView(discord.ui.View):
    """Yes/No buttons to confirm screenshot-parsed holdings."""

    def __init__(
        self,
        parsed: list[dict[str, Any]],
        portfolio: Portfolio,
        risk: RiskManager,
    ) -> None:
        super().__init__(timeout=120)
        self.parsed = parsed
        self.portfolio = portfolio
        self.risk = risk

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, emoji="\u2705")
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.defer()
        await self.portfolio.sync_from_snapshot(self.parsed, self.risk)
        await interaction.followup.send(
            f"Portfolio updated with {len(self.parsed)} holdings."
        )
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="\u274C")
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_message("Upload cancelled.", ephemeral=True)
        self.stop()


# ---------------------------------------------------------------------------
# Bot
# ---------------------------------------------------------------------------

class TraderBot(commands.Bot):
    def __init__(
        self,
        config: dict[str, Any],
        strategy: Strategy,
        portfolio: Portfolio,
        market_data: MarketData,
        risk: RiskManager,
    ) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.config = config
        self.strategy = strategy
        self.portfolio = portfolio
        self.market_data = market_data
        self.risk = risk
        self.channel_id = int(config["discord"]["channel_id"])
        self.start_time = datetime.now(ET)

    async def setup_hook(self) -> None:
        # Register persistent view so recheck buttons survive restarts
        self.add_view(RecheckView())

        # Register slash commands
        self.tree.add_command(buy_cmd)
        self.tree.add_command(sell_cmd)
        self.tree.add_command(upload_cmd)
        self.tree.add_command(holdings_cmd)
        self.tree.add_command(pnl_cmd)
        self.tree.add_command(recommend_cmd)
        self.tree.add_command(status_cmd)

        # Sync to guild (instant) rather than global (takes up to an hour)
        guild_id = self.config["discord"].get("guild_id")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

        # Start scheduled loops
        self.scan_loop.start()
        self.daily_status_loop.start()
        self.premarket_loop.start()

    async def on_ready(self) -> None:
        logger.info("Bot ready as %s", self.user)
        channel = self.get_channel(self.channel_id)
        if channel and isinstance(channel, discord.TextChannel):
            await channel.send(
                f"**Bot started** \u2014 tracking {len(self.strategy.symbols)} symbols. "
                f"Use `/recommend` for signals, `/holdings` to view portfolio."
            )

    # --- Scheduled Tasks ---

    @tasks.loop(minutes=15)
    async def scan_loop(self) -> None:
        if not is_market_hours(self.config):
            return

        channel = self.get_channel(self.channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            return

        try:
            # Check exit alerts for current holdings
            held_symbols = list(self.portfolio.holdings.keys())
            if held_symbols:
                prices = await self.market_data.get_batch_prices(held_symbols)
                alerts = await self.strategy.get_exit_alerts(prices)
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
            recs = await self.strategy.get_top_recommendations(n=3)
            for sig in recs["buys"]:
                embed = discord.Embed(
                    title=f"{sig.symbol} \u2014 BUY Signal",
                    description="\n".join(f"\u2022 {r}" for r in sig.reasons),
                    color=0x2ECC71,
                )
                embed.add_field(name="Strength", value=f"{sig.strength:.0%}", inline=True)
                embed.set_footer(text=datetime.now(ET).strftime("%H:%M ET"))
                await channel.send(embed=embed, view=RecheckView())

            for sig in recs["sells"]:
                embed = discord.Embed(
                    title=f"{sig.symbol} \u2014 SELL Signal",
                    description="\n".join(f"\u2022 {r}" for r in sig.reasons),
                    color=0xE74C3C,
                )
                embed.add_field(name="Strength", value=f"{sig.strength:.0%}", inline=True)
                embed.set_footer(text=datetime.now(ET).strftime("%H:%M ET"))
                await channel.send(embed=embed, view=RecheckView())

        except Exception:
            logger.exception("Error during scheduled scan")

    @scan_loop.before_loop
    async def before_scan(self) -> None:
        await self.wait_until_ready()

    @tasks.loop(time=time(15, 50, tzinfo=ET))
    async def daily_status_loop(self) -> None:
        now = datetime.now(ET)
        if now.weekday() >= 5:
            return

        channel = self.get_channel(self.channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            return

        try:
            held_symbols = list(self.portfolio.holdings.keys())
            prices = await self.market_data.get_batch_prices(held_symbols) if held_symbols else {}
            self.portfolio.record_daily_snapshot(prices)

            pnl_data = self.portfolio.get_daily_pnl(prices)
            holdings = self.portfolio.get_holdings_with_pnl(prices)

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

            if holdings:
                lines = []
                for h in holdings:
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

        except Exception:
            logger.exception("Error sending daily status")

    @daily_status_loop.before_loop
    async def before_daily(self) -> None:
        await self.wait_until_ready()

    @tasks.loop(time=time(8, 0, tzinfo=ET))
    async def premarket_loop(self) -> None:
        now = datetime.now(ET)
        if now.weekday() >= 5:
            return

        channel = self.get_channel(self.channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            return

        try:
            movers = await self.strategy.get_premarket_movers()
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

        except Exception:
            logger.exception("Error sending premarket movers")

    @premarket_loop.before_loop
    async def before_premarket(self) -> None:
        await self.wait_until_ready()


# ---------------------------------------------------------------------------
# Slash Commands (module-level so they can be added in setup_hook)
# ---------------------------------------------------------------------------

@app_commands.command(name="buy", description="Record a buy trade")
@app_commands.describe(
    symbol="Stock symbol (e.g. RY.TO, AMD.NE)",
    quantity="Number of shares (supports fractional)",
    price="Price per share in CAD",
)
async def buy_cmd(
    interaction: discord.Interaction, symbol: str, quantity: float, price: float
) -> None:
    bot: TraderBot = interaction.client  # type: ignore[assignment]
    symbol = symbol.upper()

    await interaction.response.defer()
    trade = await bot.portfolio.record_buy(symbol, quantity, price, bot.risk)

    embed = discord.Embed(
        title=f"\U0001f7e2 BUY Recorded \u2014 {symbol}",
        color=0x2ECC71,
    )
    embed.add_field(name="Quantity", value=f"{quantity:.4f}", inline=True)
    embed.add_field(name="Price", value=f"${price:.2f}", inline=True)
    embed.add_field(name="Total", value=f"${trade['total']:.2f}", inline=True)
    embed.add_field(
        name="Cash Remaining", value=f"${bot.portfolio.cash:.2f}", inline=False
    )
    await interaction.followup.send(embed=embed)


@app_commands.command(name="sell", description="Record a sell trade")
@app_commands.describe(
    symbol="Stock symbol (e.g. RY.TO, AMD.NE)",
    quantity="Number of shares to sell",
    price="Price per share in CAD",
)
async def sell_cmd(
    interaction: discord.Interaction, symbol: str, quantity: float, price: float
) -> None:
    bot: TraderBot = interaction.client  # type: ignore[assignment]
    symbol = symbol.upper()

    await interaction.response.defer()
    trade = await bot.portfolio.record_sell(symbol, quantity, price, bot.risk)

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


@app_commands.command(name="upload", description="Upload a screenshot of your holdings")
@app_commands.describe(image="Screenshot of your brokerage holdings")
async def upload_cmd(
    interaction: discord.Interaction, image: discord.Attachment
) -> None:
    bot: TraderBot = interaction.client  # type: ignore[assignment]
    api_key = bot.config.get("anthropic", {}).get("api_key", "")

    if not api_key:
        await interaction.response.send_message(
            "Anthropic API key not configured. Set ANTHROPIC_API_KEY.", ephemeral=True
        )
        return

    if not image.content_type or not image.content_type.startswith("image/"):
        await interaction.response.send_message(
            "Please upload an image file.", ephemeral=True
        )
        return

    await interaction.response.defer(thinking=True)

    # Download and parse
    image_data = await image.read()
    media_type = image.content_type or "image/png"
    parsed = await _parse_screenshot(image_data, api_key, media_type, bot.market_data)

    if not parsed:
        await interaction.followup.send("Could not parse any holdings from that screenshot.")
        return

    # Show parsed results for confirmation
    lines = []
    for h in parsed:
        lines.append(
            f"\u2022 **{h['symbol']}** \u2014 {h['quantity']:.4f} shares, "
            f"${h['market_value_cad']:.2f} CAD"
        )

    embed = discord.Embed(
        title="Parsed Holdings \u2014 Confirm?",
        description="\n".join(lines),
        color=0x3498DB,
    )
    embed.set_footer(text="This will replace all current holdings in the tracker.")

    view = ConfirmUploadView(parsed, bot.portfolio, bot.risk)
    await interaction.followup.send(embed=embed, view=view)


async def _parse_screenshot(
    image_data: bytes,
    api_key: str,
    media_type: str,
    market_data: MarketData,
) -> list[dict[str, Any]]:
    """Parse screenshot and resolve symbols."""
    parsed = await parse_holdings_screenshot(image_data, api_key, media_type)

    # Resolve each symbol to its exchange suffix
    resolved = []
    for h in parsed:
        raw = h["symbol"]
        # If already has a suffix, keep it
        if "." in raw:
            resolved.append(h)
            continue

        # Try .TO → .NE → bare
        sym = await market_data.resolve_symbol(raw)
        if sym:
            h["symbol"] = sym
        else:
            # Keep as-is if resolution fails
            logger.warning("Could not resolve symbol %s, keeping as-is", raw)
        resolved.append(h)

    return resolved


@app_commands.command(name="holdings", description="View current portfolio holdings")
async def holdings_cmd(interaction: discord.Interaction) -> None:
    bot: TraderBot = interaction.client  # type: ignore[assignment]

    if not bot.portfolio.holdings:
        await interaction.response.send_message(
            "No holdings tracked yet. Use `/buy` or `/upload` to add."
        )
        return

    await interaction.response.defer()

    symbols = list(bot.portfolio.holdings.keys())
    prices = await bot.market_data.get_batch_prices(symbols)
    holdings = bot.portfolio.get_holdings_with_pnl(prices)

    total_value = sum(h["market_value"] for h in holdings)
    total_pnl = sum(h["pnl"] for h in holdings)

    embed = discord.Embed(
        title="Current Holdings",
        color=pnl_color(total_pnl),
    )

    for h in holdings:
        emoji = "\U0001f7e2" if h["pnl_pct"] >= 0 else "\U0001f534"
        embed.add_field(
            name=f"{emoji} {h['symbol']}",
            value=(
                f"{h['quantity']:.4f} shares\n"
                f"Avg cost: ${h['avg_cost']:.2f}\n"
                f"Current: ${h['current_price']:.2f}\n"
                f"Value: ${h['market_value']:.2f}\n"
                f"P&L: ${h['pnl']:+.2f} ({h['pnl_pct']:+.1f}%)"
            ),
            inline=True,
        )

    embed.add_field(
        name="Total",
        value=f"${total_value:.2f} ({total_pnl:+.2f})",
        inline=False,
    )
    embed.add_field(name="Cash", value=f"${bot.portfolio.cash:.2f}", inline=True)
    embed.set_footer(text=datetime.now(ET).strftime("%H:%M ET"))
    await interaction.followup.send(embed=embed)


@app_commands.command(name="pnl", description="View P&L breakdown")
async def pnl_cmd(interaction: discord.Interaction) -> None:
    bot: TraderBot = interaction.client  # type: ignore[assignment]

    await interaction.response.defer()

    symbols = list(bot.portfolio.holdings.keys())
    prices = await bot.market_data.get_batch_prices(symbols) if symbols else {}
    pnl_data = bot.portfolio.get_daily_pnl(prices)

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

    # Recent trades
    recent = bot.portfolio.get_recent_trades(5)
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


@app_commands.command(name="recommend", description="Get current buy/sell recommendations")
async def recommend_cmd(interaction: discord.Interaction) -> None:
    bot: TraderBot = interaction.client  # type: ignore[assignment]

    await interaction.response.defer(thinking=True)

    recs = await bot.strategy.get_top_recommendations(n=5)

    if not recs["buys"] and not recs["sells"]:
        await interaction.followup.send("No actionable signals right now. Market may be quiet.")
        return

    for sig in recs["buys"]:
        embed = discord.Embed(
            title=f"{sig.symbol} \u2014 BUY Signal",
            description="\n".join(f"\u2022 {r}" for r in sig.reasons),
            color=0x2ECC71,
        )
        embed.add_field(name="Strength", value=f"{sig.strength:.0%}", inline=True)
        embed.set_footer(text=datetime.now(ET).strftime("%H:%M ET"))
        await interaction.followup.send(embed=embed, view=RecheckView())

    for sig in recs["sells"]:
        embed = discord.Embed(
            title=f"{sig.symbol} \u2014 SELL Signal",
            description="\n".join(f"\u2022 {r}" for r in sig.reasons),
            color=0xE74C3C,
        )
        embed.add_field(name="Strength", value=f"{sig.strength:.0%}", inline=True)
        embed.set_footer(text=datetime.now(ET).strftime("%H:%M ET"))
        await interaction.followup.send(embed=embed, view=RecheckView())


@app_commands.command(name="status", description="Bot status overview")
async def status_cmd(interaction: discord.Interaction) -> None:
    bot: TraderBot = interaction.client  # type: ignore[assignment]
    now = datetime.now(ET)
    uptime = now - bot.start_time

    embed = discord.Embed(title="Bot Status", color=0x3498DB)
    embed.add_field(
        name="Uptime",
        value=f"{uptime.days}d {uptime.seconds // 3600}h {(uptime.seconds % 3600) // 60}m",
        inline=True,
    )
    embed.add_field(
        name="Symbols Tracked",
        value=str(len(bot.strategy.symbols)),
        inline=True,
    )
    embed.add_field(
        name="Holdings",
        value=str(len(bot.portfolio.holdings)),
        inline=True,
    )
    embed.add_field(
        name="Market Hours",
        value="Open" if is_market_hours(bot.config) else "Closed",
        inline=True,
    )
    embed.add_field(
        name="Scan Interval",
        value=f"{bot.config['schedule']['scan_interval_minutes']}m",
        inline=True,
    )
    embed.set_footer(text=now.strftime("%Y-%m-%d %H:%M ET"))
    await interaction.response.send_message(embed=embed)
