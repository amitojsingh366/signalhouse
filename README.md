# signalhouse

A self-hosted trading signal system for Canadian investors. Scans ~333 TSX stocks, CBOE Canada CDRs, and CAD-hedged ETFs every 15 minutes during market hours, generating buy/sell recommendations with technical analysis, sentiment scoring, and commodity correlation.

**This is not an auto-trader.** It tells you what to trade and why -- you execute manually via your brokerage, then report back. Built for a Canadian TFSA account.

> Live at [yourdomain.com](https://yourdomain.com)

## How It Works

```
Every 15 min during market hours:

  333 symbols
    -> Technical analysis (EMA, RSI, MACD, Bollinger Bands, volume)
    -> Sentiment adjustment (analyst consensus, Fear & Greed, news)
    -> Commodity correlation (gold, oil, natgas, crypto futures)
    -> Score (-9 to +9) -> BUY / SELL / HOLD + strength %

  Score >= +2 = BUY    Score <= -2 = SELL    Otherwise = HOLD

Delivery:
  iOS app     -> VoIP push (bypasses DND via CallKit) for strong signals
              -> Standard alerts for pre-market, briefings, close, recap
  Web         -> Dashboard at yourdomain.com
  Discord bot -> Signal embeds + slash commands
```

You trade via your brokerage. Report trades back through the app, web, or Discord. Upload a brokerage screenshot and Claude Vision parses your holdings automatically.

## Architecture

```
Internet -> Cloudflare (SSL) -> Caddy -> web (:3000)  pages
                                      -> api (:8000)  /api/*

Bot imports api as a Python package (no HTTP between them).
Web + iOS app communicate via REST API.
All services share one PostgreSQL database.
```

| Component | Stack | Role |
|-----------|-------|------|
| **API** | FastAPI, SQLAlchemy async, asyncpg, TA-Lib | REST API + all business logic |
| **Bot** | discord.py | Discord slash commands + scheduled channel posts |
| **Web** | Next.js 14, Bun, Tailwind, Recharts | Web dashboard |
| **App** | SwiftUI, Swift Charts, PushKit, CallKit | iOS/macOS native app |
| **DB** | PostgreSQL 16 | Shared persistence |
| **Proxy** | Caddy | SSL termination, reverse proxy |

## Project Structure

```
signalhouse/
├── api/                    FastAPI REST API + all shared business logic
│   └── src/trader_api/
│       ├── routers/        portfolio, trades, signals, status, auth, notifications
│       └── services/       market data, signals, strategy, portfolio, risk,
│                           sentiment, commodity, notifier, scheduler, vision
├── bot/                    Discord bot (imports trader_api directly)
│   └── src/trader_bot/
│       └── cogs/           trading, portfolio, signals, upload, status, tasks
├── web/                    Next.js dashboard (Bun, App Router, Tailwind)
│   ├── app/                pages: dashboard, portfolio, signals, trades,
│   │                       upload, status, settings, debug, premarket
│   ├── components/ui/      stat cards, signal badges, equity chart, auth gate
│   └── lib/                API client, TanStack Query hooks, utils
├── app/                    SwiftUI iOS/macOS app (Xcode project)
│   └── Trader/
│       ├── Services/       API client, auth (passkeys), push (CallKit)
│       └── Views/Tabs/     Dashboard, Portfolio, Signals, Trades, Upload, Status
├── config/
│   ├── settings.yaml       symbol universe (~333), risk params, schedules
│   └── settings.local.yaml local overrides (gitignored)
├── docker-compose.yml      5 services: postgres, api, bot, web, caddy
├── Caddyfile               reverse proxy config
└── docs/                   architecture, strategy, dev plan
```

## Signal Pipeline

The system scores each symbol on a -9 to +9 scale across three stages:

### Technical Analysis (max +/-6)

| Indicator | Bullish | Bearish |
|-----------|---------|---------|
| EMA crossover (10/30) | +2.0 | -2.0 |
| EMA trend direction | +0.5 | -0.5 |
| RSI (14) oversold/overbought | +1.5 | -1.5 |
| MACD histogram cross | +1.0 | -1.0 |
| MACD persistent direction | +0.5 | -0.5 |
| Bollinger Band touch | +1.5 | -1.5 |
| Volume confirmation (>1.5x avg) | +0.5 | -0.5 |

### Sentiment (max +/-2)

- **Analyst consensus** -- weighted strongBuy/buy/hold/sell/strongSell score (per ticker, cached 4h)
- **Fear & Greed Index** -- contrarian: extreme fear = bullish, extreme greed = bearish (market-wide, cached 1h)
- **News headlines** -- keyword sentiment on recent yfinance headlines (per ticker, cached 30min)

### Commodity Correlation (max +/-1)

Live commodity/crypto futures (gold, oil, natgas, silver, BTC, ETH, SOL) adjust scores for correlated Canadian assets. Gold miners get boosted when gold futures rally overnight, oil producers track WTI, crypto ETFs follow BTC/ETH.

## Features

### Portfolio Tracking
- Record buys/sells via Discord, web, or iOS app
- Upload brokerage screenshots -- Claude Vision auto-parses holdings
- Cash tracking, daily P&L, equity curve snapshots
- Per-holding advice: HOLD, SELL, or SWAP with specific alternatives

### Risk Management
- ATR-based position sizing (2% risk per trade)
- Hard stops (5% below entry) and trailing stops (3% below peak)
- Circuit breakers: 8% daily drawdown or 20% total drawdown halts all signals
- Max 2 positions, 50% per position, 40% per sector

### Notifications
- **VoIP push** (CallKit) -- strong signals bypass Do Not Disturb on iOS
- **Standard alerts** -- pre-market movers (8 AM ET), morning briefing (8:30 AM), market close (3:50 PM), evening recap (10 PM PT)
- **Discord** -- signal embeds, exit alerts, daily summaries
- Once-per-day dedup per symbol (renotifies only when strength changes)

### Authentication
- Passkey/WebAuthn login -- no passwords
- Single-user, JWT-gated API
- Cross-platform passkeys (web + iOS via Associated Domains)

### Symbol Universe
~333 securities across 21 sectors: technology, financials, energy, materials, crypto, broad market ETFs, covered call ETFs, leveraged/inverse ETFs, and more. Configured in `config/settings.yaml`.

- `.TO` suffixed symbols are TSX-listed
- `.NE` suffixed symbols are CDRs on CBOE Canada (falls back to US data when spotty)

## Getting Started

### Prerequisites

- Python 3.11+
- [TA-Lib](https://ta-lib.github.io/ta-lib-python/) (C library + Python wrapper)
- PostgreSQL 16
- [Bun](https://bun.sh) (for web dashboard)
- Xcode 15+ (for iOS app, optional)
- Docker & Docker Compose (for deployment)

### Environment Setup

```bash
cp .env.example .env
# Fill in: DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID, DISCORD_GUILD_ID,
#          ANTHROPIC_API_KEY, POSTGRES_PASSWORD, JWT_SECRET
# Optional: APNS_KEY_ID, APNS_TEAM_ID, APNS_BUNDLE_ID (for iOS push)
```

### Local Development

```bash
# API
cd api && pip install -e ".[dev]"
uvicorn trader_api.main:app --reload

# Bot (in another terminal)
cd bot && pip install -e .
python -m trader_bot.main

# Web (in another terminal)
cd web && bun install && bun run dev
```

### Docker (Production)

```bash
docker compose up -d --build
docker compose logs -f
```

This starts all 5 services: PostgreSQL, API, bot, web dashboard, and Caddy reverse proxy.

### iOS App

Open `app/Trader.xcodeproj` in Xcode. The app connects to your API URL (configured during onboarding). Requires an Apple Developer account for push notifications.

## Verification

```bash
# Web -- must pass before deploying
cd web && bun run build

# Python lint
ruff check api/src/ bot/src/

# Type checking
mypy api/src/ bot/src/

# Tests
pytest

# Swift build check
xcodebuild -project app/Trader.xcodeproj -scheme Trader \
  -destination 'generic/platform=iOS' build 2>&1 | tail -5
```

## Deployment

Deployed on an your server ARM instance (Ubuntu) at `your-server`, served via Cloudflare at `yourdomain.com`.

```bash
git push origin main
ssh ubuntu@your-server "cd ~/trader && git pull origin main && docker compose up -d --build"
```

## Documentation

| Document | Description |
|----------|-------------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture, API endpoints, DB models, auth flow, Docker setup, design system |
| [docs/STRATEGY.md](docs/STRATEGY.md) | Signal pipeline deep-dive, scoring tables, risk parameters, symbol universe |
| [docs/PLAN.md](docs/PLAN.md) | Development progress and roadmap |

## Tech Stack

**Backend:** Python 3.11, FastAPI, SQLAlchemy (async), asyncpg, TA-Lib, yfinance, py-webauthn, PyJWT, httpx (HTTP/2 for APNs)

**Frontend:** Next.js 14, TypeScript, Tailwind CSS, Recharts, TanStack Query, Bun

**Mobile:** SwiftUI, Swift Charts, PushKit, CallKit, ASAuthorizationController (passkeys)

**Infrastructure:** PostgreSQL 16, Docker Compose, Caddy, Cloudflare, your server

**AI:** Anthropic Claude Sonnet (vision API for brokerage screenshot parsing)

## License

Private project. Not open source.
