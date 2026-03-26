"""Load and merge configuration from settings.yaml and settings.local.yaml."""

import os
from pathlib import Path
from typing import Any

import yaml


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, preferring override values."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_dir: Path | None = None) -> dict[str, Any]:
    """Load settings.yaml, then overlay settings.local.yaml if it exists.

    Environment variables override config values:
      DISCORD_BOT_TOKEN → discord.bot_token
      DISCORD_CHANNEL_ID → discord.channel_id
      DISCORD_GUILD_ID → discord.guild_id
      OLLAMA_URL → ollama.url
      DATABASE_URL → database.url
    """
    if config_dir is None:
        # Check working directory first (Docker), then source tree
        cwd_config = Path.cwd() / "config"
        src_config = Path(__file__).parent.parent.parent.parent / "config"
        config_dir = cwd_config if (cwd_config / "settings.yaml").exists() else src_config

    base_path = config_dir / "settings.yaml"
    local_path = config_dir / "settings.local.yaml"

    with open(base_path) as f:
        config = yaml.safe_load(f)

    if local_path.exists():
        with open(local_path) as f:
            local = yaml.safe_load(f)
            if local:
                config = _deep_merge(config, local)

    # Environment variable overrides (useful in Docker)
    if token := os.environ.get("DISCORD_BOT_TOKEN"):
        config.setdefault("discord", {})["bot_token"] = token
    if channel := os.environ.get("DISCORD_CHANNEL_ID"):
        config.setdefault("discord", {})["channel_id"] = channel
    if guild := os.environ.get("DISCORD_GUILD_ID"):
        config.setdefault("discord", {})["guild_id"] = guild
    if ollama_url := os.environ.get("OLLAMA_URL"):
        config.setdefault("ollama", {})["url"] = ollama_url
    if db_url := os.environ.get("DATABASE_URL"):
        config.setdefault("database", {})["url"] = db_url

    return config
