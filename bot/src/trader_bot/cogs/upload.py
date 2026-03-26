"""Upload command — /upload with screenshot parsing and confirmation views."""

from __future__ import annotations

import logging
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from trader_bot.bot import TraderBot
from trader_api.services.market_data import MarketData
from trader_api.services.vision import parse_holdings_screenshot

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


def _build_upload_edit_list(parsed: list[dict[str, Any]]) -> discord.Embed:
    """Show all parsed holdings in the edit view."""
    lines = []
    for h in parsed:
        lines.append(
            f"\u2022 **{h['symbol']}** \u2014 {h['quantity']:.4f} shares, "
            f"${h['market_value_cad']:.2f} CAD"
        )
    return discord.Embed(
        title="Edit Parsed Holdings",
        description="\n".join(lines),
        color=0xF39C12,
    ).set_footer(text="Select a holding to edit, or Done to go back.")


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

class EditSingleSymbolModal(discord.ui.Modal):
    """Modal to edit one parsed symbol, then return to the select view."""

    def __init__(
        self,
        parsed: list[dict[str, Any]],
        index: int,
        bot: TraderBot,
    ) -> None:
        h = parsed[index]
        super().__init__(title=f"Edit {h['symbol']}")
        self.parsed = parsed
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
                "Invalid number \u2014 quantity and value must be numeric.", ephemeral=True
            )
            return

        embed = _build_upload_edit_list(self.parsed)
        view = UploadEditSelectView(self.parsed, self._bot)
        await interaction.response.edit_message(embed=embed, view=view)


class UploadEditSelectView(discord.ui.View):
    """Dropdown to pick which parsed holding to edit + Done button."""

    def __init__(
        self,
        parsed: list[dict[str, Any]],
        bot: TraderBot,
    ) -> None:
        super().__init__(timeout=300)
        self.parsed = parsed
        self._bot = bot

        options = []
        for i, h in enumerate(parsed[:25]):
            options.append(discord.SelectOption(
                label=h["symbol"],
                description=f"{h['quantity']:.4f} sh, ${h['market_value_cad']:.2f} CAD",
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
        modal = EditSingleSymbolModal(
            self.parsed, index, self._bot
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(
        label="Done", style=discord.ButtonStyle.success, emoji="\u2705"
    )
    async def done(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        embed = _build_upload_embed(self.parsed)
        view = ConfirmUploadView(self.parsed, self._bot)
        await interaction.response.edit_message(embed=embed, view=view)


class ConfirmUploadView(discord.ui.View):
    """Confirm/Edit/Cancel buttons for screenshot-parsed holdings."""

    def __init__(
        self,
        parsed: list[dict[str, Any]],
        bot: TraderBot,
    ) -> None:
        super().__init__(timeout=300)
        self.parsed = parsed
        self._bot = bot

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, emoji="\u2705")
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.defer()
        portfolio = await self._bot.get_fresh_portfolio()
        try:
            await portfolio.sync_from_snapshot(self.parsed, self._bot.risk)
            await interaction.followup.send(
                f"Portfolio updated with {len(self.parsed)} holdings."
            )
        finally:
            await portfolio.close()
        self.stop()

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.primary, emoji="\u270F\uFE0F")
    async def edit(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if not self.parsed:
            await interaction.response.send_message("Nothing to edit.", ephemeral=True)
            return
        embed = _build_upload_edit_list(self.parsed)
        view = UploadEditSelectView(self.parsed, self._bot)
        await interaction.response.edit_message(embed=embed, view=view)

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
        view = ConfirmUploadView(parsed, self.bot)
        await interaction.followup.send(embed=embed, view=view)


async def setup(bot: TraderBot) -> None:
    await bot.add_cog(UploadCog(bot))
