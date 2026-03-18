"""Entry point — connects to IBKR, runs strategy on schedule during market hours."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from datetime import datetime, time
from zoneinfo import ZoneInfo

from trader.broker import Broker
from trader.config import load_config
from trader.notifier import Notifier
from trader.risk import RiskManager
from trader.strategy import Strategy

ET = ZoneInfo("America/Toronto")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("trader.log"),
    ],
)
logger = logging.getLogger(__name__)


def is_market_hours(config: dict) -> bool:
    """Check if current time is within market hours (Eastern Time)."""
    now = datetime.now(ET).time()
    market_open = time.fromisoformat(config["schedule"]["market_open"])
    market_close = time.fromisoformat(config["schedule"]["market_close"])
    return market_open <= now <= market_close


def is_weekday() -> bool:
    return datetime.now(ET).weekday() < 5


async def run() -> None:
    config = load_config()

    broker = Broker(config)
    risk = RiskManager(config)
    notifier = Notifier(config)
    strategy = Strategy(broker, risk, notifier, config)

    # Graceful shutdown
    shutdown = asyncio.Event()

    def handle_signal(sig: int, frame: object) -> None:
        logger.info("Received signal %s, shutting down...", sig)
        shutdown.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Connect to IBKR with retries (IB Gateway may take time to start)
    max_retries = 10
    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Connecting to IBKR (attempt %d/%d)...", attempt, max_retries)
            await broker.connect()
            break
        except Exception:
            if attempt == max_retries:
                logger.exception("Failed to connect to IBKR after %d attempts", max_retries)
                await notifier.error_alert("Failed to connect to IBKR — giving up")
                sys.exit(1)
            logger.warning(
                "Connection attempt %d failed, retrying in 15s...", attempt, exc_info=True
            )
            await asyncio.sleep(15)

    # Initialize strategy (tolerates read-only mode)
    try:
        await strategy.initialize()
    except Exception:
        logger.warning("Strategy init had errors (possibly read-only mode), continuing anyway")

    await notifier.send("**Bot started** — connected to IBKR")

    # Test order: buy 1 share of RY.TO and immediately sell it
    await test_order(broker, notifier)

    interval = config["schedule"]["scan_interval_minutes"] * 60
    daily_status_sent = False

    logger.info("Bot running — scanning every %d minutes during market hours", interval // 60)

    try:
        while not shutdown.is_set():
            now = datetime.now(ET)

            if is_weekday() and is_market_hours(config):
                # Reset daily tracking at market open
                if now.time() < time(9, 45):
                    risk.reset_daily(broker.get_account_value())
                    daily_status_sent = False

                # Run strategy scan
                try:
                    await strategy.scan_and_trade()
                except Exception:
                    logger.exception("Error during scan")
                    await notifier.error_alert("Error during scan — check logs")

                # Send daily status near market close
                if now.time() >= time(15, 50) and not daily_status_sent:
                    await strategy.send_daily_status()
                    daily_status_sent = True

            # Wait for next scan or shutdown
            try:
                await asyncio.wait_for(shutdown.wait(), timeout=interval)
                break  # shutdown was set
            except TimeoutError:
                pass  # Normal: just time to scan again

    finally:
        await notifier.send("**Bot stopped**")
        broker.disconnect()
        logger.info("Bot shut down cleanly")


async def test_order(broker: Broker, notifier: Notifier) -> None:
    """Buy 1 share of RY.TO and sell it back to verify API trading works."""
    symbol = "RY.TO"
    logger.info("=== TEST ORDER: Buying 1 x %s ===", symbol)
    try:
        trade = await broker.buy(symbol, 1)
        fill_price = trade.orderStatus.avgFillPrice
        logger.info("=== TEST ORDER: Buy filled @ $%.2f ===", fill_price)
        await notifier.send(f"**Test order**: Bought 1 x {symbol} @ ${fill_price:.2f}")
    except Exception:
        logger.exception("=== TEST ORDER: Buy FAILED ===")
        await notifier.error_alert(f"Test order FAILED for {symbol} — check API permissions")
        return

    # Sell it back
    logger.info("=== TEST ORDER: Selling 1 x %s ===", symbol)
    try:
        trade = await broker.sell(symbol, 1)
        fill_price = trade.orderStatus.avgFillPrice
        logger.info("=== TEST ORDER: Sell filled @ $%.2f — test PASSED ===", fill_price)
        await notifier.send(f"**Test order**: Sold 1 x {symbol} @ ${fill_price:.2f} — API trading works!")
    except Exception:
        logger.exception("=== TEST ORDER: Sell FAILED ===")
        await notifier.error_alert(f"Test sell FAILED for {symbol}")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
