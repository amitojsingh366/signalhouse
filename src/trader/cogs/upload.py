"""Upload command — /upload with screenshot parsing and confirmation views."""

from __future__ import annotations

import logging
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from trader.bot import TraderBot
from trader.market_data import MarketData
from trader.portfolio import Portfolio
from trader.risk import RiskManager
from trader.vision import parse_holdings_screenshot

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_upload_embed(parsed: list[dict[str, Any]]) -> discord.Embed:
    """Build the confirmation embed showing parsed holdings."""
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
    return embed


def _build_edit_progress_embed(
    parsed: list[dict[str, Any]], next_idx: int
) -> discord.Embed:
    """Build embed showing edit progress and what's next."""
    lines = []
    for i, h in enumerate(parsed):
        check = "\u2705" if i < next_idx else "\u270F\uFE0F"
        lines.append(
            f"{check} **{h['symbol']}** \u2014 {h['quantity']:.4f} shares, "
            f"${h['market_value_cad']:.2f} CAD"
        )
    embed = discord.Embed(
        title=f"Editing Holdings ({next_idx}/{len(parsed)} done)",
        description="\n".join(lines),
        color=0xF39C12,
    )
    h = parsed[next_idx]
    embed.set_footer(text=f"Next: {h['symbol']}")
    return embed


async def _parse_screenshot(
    image_data: bytes,
    api_key: str,
    media_type: str,
    market_data: MarketData,
) -> list[dict[str, Any]]:
    """Parse screenshot and resolve symbols."""
    parsed = await parse_holdings_screenshot(image_data, api_key, media_type)

    resolved = []
    for h in parsed:
        raw = h["symbol"]
        if "." in raw:
            resolved.append(h)
            continue

        sym = await market_data.resolve_symbol(raw)
        if sym:
            h["symbol"] = sym
        else:
            logger.warning("Could not resolve symbol %s, keeping as-is", raw)
        resolved.append(h)

    return resolved


# ---------------------------------------------------------------------------
# Views / Modals
# ---------------------------------------------------------------------------

class EditSymbolModal(discord.ui.Modal):
    """Modal to edit a single symbol's parsed data."""

    def __init__(
        self,
        parsed: list[dict[str, Any]],
        index: int,
        portfolio: Portfolio,
        risk: RiskManager,
    ) -> None:
        h = parsed[index]
        super().__init__(title=f"Edit Symbol {index + 1}/{len(parsed)}")
        self.parsed = parsed
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
        self.value_input = discord.ui.TextInput(
            label="Market Value (CAD)",
            default=f"{h['market_value_cad']:.2f}",
            required=True,
            max_length=20,
        )

        self.add_item(self.symbol_input)
        self.add_item(self.quantity_input)
        self.add_item(self.value_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            self.parsed[self.index] = {
                "symbol": self.symbol_input.value.strip().upper(),
                "quantity": float(self.quantity_input.value.strip()),
                "market_value_cad": float(self.value_input.value.strip()),
            }
        except ValueError:
            await interaction.response.send_message(
                "Invalid number — quantity and value must be numeric.", ephemeral=True
            )
            return

        next_idx = self.index + 1
        if next_idx < len(self.parsed):
            embed = _build_edit_progress_embed(self.parsed, next_idx)
            view = EditNextView(self.parsed, next_idx, self.portfolio, self.risk)
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            embed = _build_upload_embed(self.parsed)
            view = ConfirmUploadView(self.parsed, self.portfolio, self.risk)
            await interaction.response.edit_message(embed=embed, view=view)


class EditNextView(discord.ui.View):
    """Button to open the modal for the next symbol (workaround for modal chaining)."""

    def __init__(
        self,
        parsed: list[dict[str, Any]],
        index: int,
        portfolio: Portfolio,
        risk: RiskManager,
    ) -> None:
        super().__init__(timeout=300)
        self.parsed = parsed
        self.index = index
        self.portfolio = portfolio
        self.risk = risk

    @discord.ui.button(
        label="Edit Next", style=discord.ButtonStyle.primary, emoji="\u270F\uFE0F"
    )
    async def edit_next(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        modal = EditSymbolModal(
            self.parsed, self.index, self.portfolio, self.risk
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="Skip Rest", style=discord.ButtonStyle.secondary, emoji="\u23ED\uFE0F"
    )
    async def skip_rest(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        embed = _build_upload_embed(self.parsed)
        view = ConfirmUploadView(self.parsed, self.portfolio, self.risk)
        await interaction.response.edit_message(embed=embed, view=view)


class ConfirmUploadView(discord.ui.View):
    """Confirm/Edit/Cancel buttons for screenshot-parsed holdings."""

    def __init__(
        self,
        parsed: list[dict[str, Any]],
        portfolio: Portfolio,
        risk: RiskManager,
    ) -> None:
        super().__init__(timeout=300)
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

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.primary, emoji="\u270F\uFE0F")
    async def edit(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not self.parsed:
            await interaction.response.send_message("Nothing to edit.", ephemeral=True)
            return
        modal = EditSymbolModal(self.parsed, 0, self.portfolio, self.risk)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="\u274C")
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_message("Upload cancelled.", ephemeral=True)
        self.stop()


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class UploadCog(commands.Cog):
    """Screenshot upload and parsing."""

    def __init__(self, bot: TraderBot) -> None:
        self.bot = bot

    @app_commands.command(name="upload", description="Upload a screenshot of your holdings")
    @app_commands.describe(image="Screenshot of your brokerage holdings")
    async def upload(
        self, interaction: discord.Interaction, image: discord.Attachment
    ) -> None:
        api_key = self.bot.config.get("anthropic", {}).get("api_key", "")

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

        image_data = await image.read()
        media_type = image.content_type or "image/png"
        parsed = await _parse_screenshot(
            image_data, api_key, media_type, self.bot.market_data
        )

        if not parsed:
            await interaction.followup.send(
                "Could not parse any holdings from that screenshot."
            )
            return

        embed = _build_upload_embed(parsed)
        view = ConfirmUploadView(parsed, self.bot.portfolio, self.bot.risk)
        await interaction.followup.send(embed=embed, view=view)


async def setup(bot: TraderBot) -> None:
    await bot.add_cog(UploadCog(bot))
