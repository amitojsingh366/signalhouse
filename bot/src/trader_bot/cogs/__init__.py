"""Discord bot cogs — each module is a discord.py extension loaded at startup."""

EXTENSIONS = [
    "trader_bot.cogs.trading",
    "trader_bot.cogs.portfolio",
    "trader_bot.cogs.signals",
    "trader_bot.cogs.upload",
    "trader_bot.cogs.status",
    "trader_bot.cogs.tasks",
]
