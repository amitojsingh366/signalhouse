"""FastAPI application — REST API for the trading bot."""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from trader_api.config import load_config
from trader_api.database import init_db
from trader_api.deps import get_market_data, get_risk, init_services, make_portfolio
from trader_api.routers import (
    auth,
    debug,
    notifications,
    portfolio,
    settings,
    signals,
    status,
    trades,
)
from trader_api.services.settings import load_runtime_settings
from trader_api.services.scheduler import Scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load config, init DB, init services, sync risk manager, start scheduler."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)

    config = load_config()
    init_services(config)

    await init_db()

    # Sync risk manager from DB holdings at startup
    from trader_api.database import async_session
    async with async_session() as db:
        await load_runtime_settings(db, config)
        p = make_portfolio(db)
        holdings = await p.get_holdings_dict()
        meta = await p._get_meta()
        p.sync_risk_manager(get_risk(), holdings, meta.initial_capital)

    logger = logging.getLogger(__name__)
    logger.info(
        "API started — tracking %d symbols",
        len(get_market_data().symbols),
    )

    scheduler = Scheduler()
    scheduler.start(config)
    try:
        yield
    finally:
        scheduler.stop()


app = FastAPI(
    title="signalhouse API",
    description="Trading recommendation and portfolio tracking API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)  # No auth required — handles its own access
app.include_router(portfolio.router)
app.include_router(trades.router)
app.include_router(signals.router)
app.include_router(settings.router)
app.include_router(status.router)
app.include_router(notifications.router)
app.include_router(debug.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
