from datetime import UTC, datetime

from trader_api.services.portfolio import Portfolio


def test_snapshot_date_uses_et_market_day_after_utc_midnight() -> None:
    assert Portfolio._snapshot_date(datetime(2026, 5, 16, 0, 30, tzinfo=UTC)) == "2026-05-15"


def test_snapshot_date_advances_after_et_midnight() -> None:
    assert Portfolio._snapshot_date(datetime(2026, 5, 16, 5, 0, tzinfo=UTC)) == "2026-05-16"
