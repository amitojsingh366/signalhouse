"""Discord bot cogs — each module is a discord.py extension loaded at startup."""

EXTENSIONS = [
    "trader.cogs.trading",
    "trader.cogs.portfolio",
    "trader.cogs.signals",
    "trader.cogs.upload",
    "trader.cogs.status",
    "trader.cogs.tasks",
]
