# CLAUDE.md

## What This Is

Trading recommendation + portfolio tracking system for TSX stocks, CBOE Canada CDRs, and CAD-hedged ETFs. **Not an auto-trading bot** — provides buy/sell/swap signals and the user trades manually via their brokerage, then reports back.

Designed for Canadian TFSA accounts of any size, targeting safe aggressive growth. Scans ~333 symbols every 15 min during market hours.

## Components

| Component | Stack | Description |
|-----------|-------|-------------|
| `api/` | FastAPI, SQLAlchemy async, PostgreSQL | REST API + all shared business logic |
| `bot/` | discord.py | Discord slash commands + scheduled tasks (imports `trader_api`) |
| `web/` | Next.js 14, Bun, Tailwind, Recharts | Web dashboard at `yourdomain.com` |
| `app/` | SwiftUI, Swift Charts, PushKit/CallKit | iOS/macOS app (Xcode, not Docker) |

## Commands

```bash
# API
cd api && pip install -e ".[dev]"
uvicorn trader_api.main:app --reload

# Bot
cd bot && pip install -e .
python -m trader_bot.main

# Web (uses Bun, not npm)
cd web && bun install
bun run dev
bun run build          # verify before deploying

# Docker (all 5 services: postgres, api, bot, web, caddy)
docker compose up -d --build
docker compose logs -f

# Tests & lint
pytest
ruff check api/src/ bot/src/
mypy api/src/ bot/src/

# Swift build check (after app/ changes)
xcodebuild -project app/Trader.xcodeproj -scheme Trader \
  -destination 'platform=iOS Simulator,name=iPhone 16' build 2>&1 | tail -5

# Deploy
git push origin main
ssh -i your-ssh-key ubuntu@your-server \
  "cd ~/trader && git pull origin main && docker compose up -d --build"
```

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture, project structure, data flow, DB models, API endpoints, auth, Docker, design system |
| [docs/STRATEGY.md](docs/STRATEGY.md) | Trading strategy: signal pipeline, sentiment, commodity correlation, risk management, position sizing, symbol universe |
| [docs/PLAN.md](docs/PLAN.md) | Development progress tracker and roadmap |
| [docs/PROMPT.md](docs/PROMPT.md) | Copy-paste prompt to bootstrap a new Claude Code conversation |

## Quick Reference

**Signal pipeline:** Technical analysis (TA-Lib, ±6) → sentiment (analyst + F&G + news, ±2) → commodity correlation (±1) → score ≥ +2 = BUY, ≤ -2 = SELL. See [STRATEGY.md](docs/STRATEGY.md).

**Key files:**
- Business logic: `api/src/trader_api/services/` (signals, strategy, portfolio, risk, sentiment, commodity)
- API routes: `api/src/trader_api/routers/` (portfolio, trades, signals, status, auth, notifications)
- Bot commands: `bot/src/trader_bot/cogs/` (trading, portfolio, signals, upload, tasks)
- Web pages: `web/app/` (dashboard, portfolio, signals, trades, upload, status, settings)
- Web shared: `web/lib/privacy.tsx` (hide-numbers toggle context), `web/lib/utils.ts` (formatters)
- iOS views: `app/Trader/Views/Tabs/` (Dashboard, Portfolio, Signals, Trades, Upload, Status)
- Config: `config/settings.yaml` (symbol universe, risk params, schedules)

**Environment variables:** `DISCORD_BOT_TOKEN`, `DISCORD_CHANNEL_ID`, `DISCORD_GUILD_ID`, `ANTHROPIC_API_KEY`, `DATABASE_URL`, `POSTGRES_PASSWORD`, `NEXT_PUBLIC_API_URL`, `APNS_KEY_PATH`, `APNS_KEY_ID`, `APNS_TEAM_ID`, `APNS_BUNDLE_ID`

**Server:** `your-server` (Ubuntu ARM, your server). Repo at `/home/ubuntu/trader/`. Secrets in `.env` on server.

## Key Constraints

- No auto-execution — user trades manually via brokerage
- yfinance data is ~15 min delayed — fine for daily-bar swing trading
- Web uses **Bun** (not npm/yarn) for package management and builds
- 8% daily drawdown or 20% total drawdown halts all recommendations
- Anthropic API required for screenshot parsing (Claude Sonnet vision)
- CDR (`.NE`) data can be spotty — falls back to US counterpart ticker
