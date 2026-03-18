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
      IBKR_HOST → broker.host
      DISCORD_WEBHOOK_URL → notifications.discord_webhook_url
    """
    if config_dir is None:
        # Check working directory first (Docker), then source tree
        cwd_config = Path.cwd() / "config"
        src_config = Path(__file__).parent.parent.parent / "config"
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
    if host := os.environ.get("IBKR_HOST"):
        config["broker"]["host"] = host
    if webhook := os.environ.get("DISCORD_WEBHOOK_URL"):
        config["notifications"]["discord_webhook_url"] = webhook

    return config
