"""Registry + persistence for runtime-editable configuration keys.

Editable settings are exposed through the API and persisted in `app_settings`
as dotted-path overrides. At app startup `load_runtime_settings` applies the
persisted overrides to the in-memory config dict. Each `set_setting_value`
mutates the same dict so live services (Strategy, RiskManager) see the change
on their next read without a restart.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trader_api.models import AppSetting

SettingType = Literal["bool", "int", "float"]


@dataclass(frozen=True)
class EditableSetting:
    key: str  # dotted path into the config dict
    type: SettingType
    group: str  # ui grouping id
    label: str
    description: str
    min: float | None = None
    max: float | None = None
    step: float | None = None

    def serialize(self, value: Any) -> str:
        if self.type == "bool":
            return "true" if bool(value) else "false"
        return str(value)

    def parse(self, raw: str) -> Any:
        if self.type == "bool":
            normalized = raw.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
            raise ValueError(f"invalid bool: {raw!r}")
        if self.type == "int":
            return int(float(raw))
        return float(raw)

    def coerce(self, value: Any) -> Any:
        if self.type == "bool":
            if isinstance(value, str):
                return self.parse(value)
            return bool(value)
        if self.type == "int":
            return int(value)
        return float(value)

    def validate(self, value: Any) -> Any:
        coerced = self.coerce(value)
        if self.type in {"int", "float"}:
            if self.min is not None and coerced < self.min:
                raise ValueError(f"{self.key} must be >= {self.min}")
            if self.max is not None and coerced > self.max:
                raise ValueError(f"{self.key} must be <= {self.max}")
        return coerced


# Group display metadata — keeps labels out of the frontend.
GROUPS: list[dict[str, str]] = [
    {"id": "profit_taking", "label": "Profit Taking"},
    {"id": "oversold_fastlane", "label": "Oversold Fast-Lane"},
    {"id": "momentum", "label": "Momentum Indicators"},
    {"id": "mean_reversion", "label": "Mean Reversion"},
    {"id": "holding_period", "label": "Holding Period"},
    {"id": "risk", "label": "Risk & Position Sizing"},
    {"id": "notifications", "label": "Notifications"},
]


REGISTRY: list[EditableSetting] = [
    # Profit Taking
    EditableSetting(
        key="risk.hybrid_take_profit_enabled",
        type="bool",
        group="profit_taking",
        label="Hybrid Take Profit",
        description=(
            "Defer take-profit sells while the symbol still has a strong BUY signal. "
            "Stops, trailing stops and other exits still apply."
        ),
    ),
    EditableSetting(
        key="risk.hybrid_take_profit_min_buy_strength",
        type="float",
        group="profit_taking",
        label="Min BUY Strength to Defer",
        description="Minimum BUY strength (0–1) required before hybrid holds past take-profit.",
        min=0.0,
        max=1.0,
        step=0.05,
    ),
    EditableSetting(
        key="risk.take_profit_pct",
        type="float",
        group="profit_taking",
        label="Take Profit %",
        description="Unrealized gain that triggers a full take-profit sell.",
        min=0.0,
        max=1.0,
        step=0.005,
    ),
    EditableSetting(
        key="risk.tighten_stop_at_pct",
        type="float",
        group="profit_taking",
        label="Tighten Stop At %",
        description="Unrealized gain at which the trailing stop tightens.",
        min=0.0,
        max=1.0,
        step=0.005,
    ),
    EditableSetting(
        key="risk.tightened_trail_pct",
        type="float",
        group="profit_taking",
        label="Tightened Trail %",
        description="Trailing-stop width after the tighten threshold is hit.",
        min=0.0,
        max=1.0,
        step=0.005,
    ),
    # Oversold Fast-Lane
    EditableSetting(
        key="strategy.oversold_fastlane.enabled",
        type="bool",
        group="oversold_fastlane",
        label="Oversold Fast-Lane",
        description=(
            "Allow earlier BUY recommendations on guarded oversold reversal setups, "
            "even below the normal 35% scan threshold."
        ),
    ),
    EditableSetting(
        key="strategy.oversold_fastlane.min_strength",
        type="float",
        group="oversold_fastlane",
        label="Min Strength",
        description="Lowered strength floor for oversold candidates.",
        min=0.0,
        max=1.0,
        step=0.01,
    ),
    EditableSetting(
        key="strategy.oversold_fastlane.max_negative_sentiment",
        type="float",
        group="oversold_fastlane",
        label="Max Negative Sentiment",
        description="Reject oversold candidates with sentiment below this floor.",
        min=-1.0,
        max=0.0,
        step=0.05,
    ),
    EditableSetting(
        key="strategy.oversold_fastlane.block_on_bearish_crossover",
        type="bool",
        group="oversold_fastlane",
        label="Block on Bearish Crossover",
        description="Skip oversold fast-lane when the fast EMA just crossed below slow.",
    ),
    # Momentum
    EditableSetting(
        key="strategy.momentum.fast_period",
        type="int",
        group="momentum",
        label="Fast EMA Period",
        description="Short-term EMA window.",
        min=2,
        max=200,
    ),
    EditableSetting(
        key="strategy.momentum.slow_period",
        type="int",
        group="momentum",
        label="Slow EMA Period",
        description="Long-term EMA window.",
        min=2,
        max=400,
    ),
    EditableSetting(
        key="strategy.momentum.rsi_period",
        type="int",
        group="momentum",
        label="RSI Period",
        description="Lookback used for RSI.",
        min=2,
        max=100,
    ),
    EditableSetting(
        key="strategy.momentum.rsi_oversold",
        type="int",
        group="momentum",
        label="RSI Oversold",
        description="RSI level that counts as oversold.",
        min=0,
        max=100,
    ),
    EditableSetting(
        key="strategy.momentum.rsi_overbought",
        type="int",
        group="momentum",
        label="RSI Overbought",
        description="RSI level that counts as overbought.",
        min=0,
        max=100,
    ),
    # Mean Reversion
    EditableSetting(
        key="strategy.mean_reversion.bb_period",
        type="int",
        group="mean_reversion",
        label="Bollinger Period",
        description="Lookback for Bollinger band midline.",
        min=2,
        max=200,
    ),
    EditableSetting(
        key="strategy.mean_reversion.bb_std",
        type="float",
        group="mean_reversion",
        label="Bollinger Std Devs",
        description="Band width in standard deviations.",
        min=0.5,
        max=5.0,
        step=0.1,
    ),
    EditableSetting(
        key="strategy.mean_reversion.lookback_days",
        type="int",
        group="mean_reversion",
        label="Lookback Days",
        description="History window for mean-reversion scoring.",
        min=5,
        max=365,
    ),
    # Holding Period
    EditableSetting(
        key="strategy.min_hold_days",
        type="int",
        group="holding_period",
        label="Min Hold Days",
        description="Minimum days to hold before taking a sell signal.",
        min=0,
        max=60,
    ),
    EditableSetting(
        key="strategy.max_hold_days",
        type="int",
        group="holding_period",
        label="Max Hold Days",
        description="Forces an exit after this many days held.",
        min=1,
        max=365,
    ),
    # Risk
    EditableSetting(
        key="strategy.max_sector_pct",
        type="float",
        group="risk",
        label="Max Sector %",
        description="Portfolio cap per sector.",
        min=0.0,
        max=1.0,
        step=0.05,
    ),
    EditableSetting(
        key="risk.max_position_pct",
        type="float",
        group="risk",
        label="Max Position %",
        description="Portfolio cap per single position.",
        min=0.0,
        max=1.0,
        step=0.05,
    ),
    EditableSetting(
        key="risk.max_positions",
        type="int",
        group="risk",
        label="Max Positions",
        description="Maximum simultaneous positions.",
        min=1,
        max=30,
    ),
    EditableSetting(
        key="risk.stop_loss_pct",
        type="float",
        group="risk",
        label="Stop Loss %",
        description="Hard stop loss as a fraction of entry price.",
        min=0.0,
        max=1.0,
        step=0.005,
    ),
    EditableSetting(
        key="risk.trailing_stop_pct",
        type="float",
        group="risk",
        label="Trailing Stop %",
        description="Default trailing stop width.",
        min=0.0,
        max=1.0,
        step=0.005,
    ),
    EditableSetting(
        key="risk.max_daily_loss_pct",
        type="float",
        group="risk",
        label="Max Daily Loss %",
        description="Halts new trading if today's drawdown exceeds this.",
        min=0.0,
        max=1.0,
        step=0.01,
    ),
    EditableSetting(
        key="risk.max_total_drawdown_pct",
        type="float",
        group="risk",
        label="Max Total Drawdown %",
        description="Halts all trading if peak drawdown exceeds this.",
        min=0.0,
        max=1.0,
        step=0.01,
    ),
    # Notifications
    EditableSetting(
        key="notifications.min_strength",
        type="float",
        group="notifications",
        label="Min Strength to Notify",
        description="Minimum signal strength before a push/alert is sent.",
        min=0.0,
        max=1.0,
        step=0.05,
    ),
    EditableSetting(
        key="notifications.cooldown_minutes",
        type="int",
        group="notifications",
        label="Cooldown (min)",
        description="Quiet period before the same symbol can notify again.",
        min=0,
        max=1440,
    ),
    EditableSetting(
        key="notifications.retry_delay_seconds",
        type="int",
        group="notifications",
        label="Retry Delay (s)",
        description="Wait before retrying an unacknowledged notification.",
        min=0,
        max=3600,
    ),
    EditableSetting(
        key="notifications.max_retries",
        type="int",
        group="notifications",
        label="Max Retries",
        description="Extra retry attempts when a notification isn't acknowledged.",
        min=0,
        max=10,
    ),
]


REGISTRY_BY_KEY: dict[str, EditableSetting] = {s.key: s for s in REGISTRY}


def _split_path(key: str) -> list[str]:
    return key.split(".")


def _get_from_config(config: dict[str, Any], key: str) -> Any:
    node: Any = config
    for part in _split_path(key):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _set_in_config(config: dict[str, Any], key: str, value: Any) -> None:
    parts = _split_path(key)
    node = config
    for part in parts[:-1]:
        next_node = node.get(part)
        if not isinstance(next_node, dict):
            next_node = {}
            node[part] = next_node
        node = next_node
    node[parts[-1]] = value


def get_setting_value(config: dict[str, Any], setting: EditableSetting) -> Any:
    """Return the current value from the live config, coerced to setting type."""
    raw = _get_from_config(config, setting.key)
    if raw is None:
        return None
    try:
        return setting.coerce(raw)
    except (TypeError, ValueError):
        return None


async def set_setting_value(
    db: AsyncSession,
    config: dict[str, Any],
    setting: EditableSetting,
    value: Any,
) -> Any:
    """Persist an override and apply it to the in-memory config."""
    coerced = setting.validate(value)
    serialized = setting.serialize(coerced)

    result = await db.execute(
        select(AppSetting).where(AppSetting.key == setting.key)
    )
    row = result.scalar_one_or_none()
    if row is None:
        db.add(AppSetting(key=setting.key, value=serialized))
    else:
        row.value = serialized

    await db.commit()
    _set_in_config(config, setting.key, coerced)
    return coerced


async def load_all_overrides(db: AsyncSession, config: dict[str, Any]) -> None:
    """Apply every persisted override in `app_settings` to the live config."""
    result = await db.execute(select(AppSetting))
    rows = result.scalars().all()
    for row in rows:
        setting = REGISTRY_BY_KEY.get(row.key)
        if setting is None:
            continue
        try:
            value = setting.parse(row.value)
        except (TypeError, ValueError):
            continue
        _set_in_config(config, setting.key, value)
