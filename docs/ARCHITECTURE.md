# Architecture

## System Overview

```
Internet → Cloudflare (SSL) → Caddy (:443) → web (:3000) for pages
                                             → api (:8000) for /api/*

Bot imports trader_api directly as a Python package (not HTTP).
Web + App communicate via REST API (web through Caddy, app directly via configured URL).
All share the same PostgreSQL database.

Signal scan (every 15 min) → if signal strength ≥ 40%:
  → APNs VoIP push → iOS CallKit incoming call → DND bypass
  → retry once after 30s if not acknowledged
```

### Components

| Component | Technology | Role |
|-----------|-----------|------|
| **API** (`api/`) | FastAPI, SQLAlchemy async, asyncpg | REST API + all shared business logic |
| **Bot** (`bot/`) | discord.py ≥ 2.3 | Discord slash commands, scheduled tasks |
| **Web** (`web/`) | Next.js 14, Bun, Tailwind, Recharts | Web dashboard |
| **App** (`app/`) | SwiftUI, Swift Charts, PushKit, CallKit | iOS/macOS native app |
| **DB** | PostgreSQL 16 | Shared persistence |
| **Proxy** | Caddy | SSL termination, reverse proxy |

---

## Project Structure

```
trader/
├── api/                              # FastAPI REST API + all shared business logic
│   ├── Dockerfile
│   ├── pyproject.toml                # deps: fastapi, sqlalchemy, yfinance, ta-lib, PyJWT, httpx[http2]
│   └── src/trader_api/
│       ├── app.py                    # FastAPI app, CORS, lifespan, router registration
│       ├── main.py                   # Uvicorn entry (port 8000)
│       ├── config.py                 # settings.yaml + settings.local.yaml loader
│       ├── database.py               # SQLAlchemy async engine, Base, init_db(), get_db()
│       ├── models.py                 # ORM models (see Database section)
│       ├── schemas.py                # Pydantic request/response models
│       ├── auth.py                   # JWT token management, require_auth dependency
│       ├── deps.py                   # Singleton services: market_data, risk, sentiment, commodity, notifier
│       ├── routers/
│       │   ├── auth.py               # WebAuthn registration/login endpoints
│       │   ├── portfolio.py          # Holdings, P&L, snapshots, cash management
│       │   ├── trades.py             # Buy/sell recording, trade history
│       │   ├── signals.py            # Signal check, recommendations, price history
│       │   ├── status.py             # System status, upload parsing, symbol universe
│       │   └── notifications.py      # Device registration, preferences, history
│       └── services/
│           ├── market_data.py        # yfinance wrapper, batch fetching, CDR fallback
│           ├── signals.py            # TA-Lib indicators, score → BUY/SELL/HOLD
│           ├── strategy.py           # Recommendations, caching, sell-to-fund, advice
│           ├── portfolio.py          # DB-backed portfolio CRUD (async SQLAlchemy)
│           ├── risk.py               # Position sizing (ATR), stop losses, drawdown
│           ├── sentiment.py          # Analyst consensus, Fear & Greed, news
│           ├── commodity.py          # Commodity/crypto correlation adjustments
│           ├── notifier.py           # APNs VoIP push (HTTP/2, ES256 JWT)
│           ├── vision.py             # Claude Sonnet vision (screenshot parsing)
│           └── backtest.py           # Historical replay
│
├── bot/                              # Discord bot (imports trader_api as Python dependency)
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── src/trader_bot/
│       ├── bot.py                    # TraderBot class, fresh-session-per-command pattern
│       ├── main.py                   # Entry point: init DB, load config, start bot
│       └── cogs/
│           ├── trading.py            # /buy, /sell
│           ├── portfolio.py          # /holdings, /pnl + dropdown edit
│           ├── signals.py            # /recommend, /check + recheck button
│           ├── upload.py             # /upload + screenshot parsing
│           ├── status.py             # /status
│           └── tasks.py              # Scheduled loops (scans, briefings, recaps) + notification trigger
│
├── web/                              # Next.js dashboard (Bun, App Router, Tailwind, Recharts)
│   ├── Dockerfile
│   ├── package.json
│   ├── tailwind.config.ts            # brand (purple), surface (zinc) color tokens
│   ├── app/                          # Pages: dashboard, portfolio, signals, trades, upload, status, settings
│   ├── components/ui/                # Reusable: stat-card, signal-badge, equity-chart, sidebar, auth-gate
│   └── lib/                          # api.ts (client + types), hooks.ts (TanStack Query), utils.ts
│
├── app/                              # SwiftUI app (iOS/macOS) — built via Xcode, not Docker
│   ├── Trader.xcodeproj/             # Xcode project (file-system-sync, auto-discovers Swift files)
│   └── Trader/
│       ├── TraderApp.swift           # @main entry, TabView (6 tabs), onboarding gate
│       ├── Info.plist                # UIBackgroundModes: voip, remote-notification
│       ├── Config/                   # AppConfig (API URL), Theme (design system colors)
│       ├── Models/APIModels.swift    # Codable structs matching Pydantic schemas
│       ├── Services/                 # APIClient, AuthManager (passkeys), PushManager (CallKit)
│       └── Views/                    # Onboarding, Tabs (6 views), Components (cards, charts, badges)
│
├── config/
│   ├── settings.yaml                 # Symbol universe (~333), risk params, schedules
│   └── settings.local.yaml           # Secrets (gitignored)
│
├── docker-compose.yml                # 5 services: postgres, api, bot, web, caddy
├── Caddyfile                         # Reverse proxy: /api/* → api:8000, /* → web:3000
└── .env.example                      # Required env vars
```

---

## Data Flow

### Signal Generation (every 15 min during market hours)

`cogs/tasks.py` → `strategy.get_top_recommendations()` → for each of ~333 symbols:

1. `market_data.get_historical_data()` — 60 days of daily bars via yfinance (cached 5 min)
2. `signals.compute_indicators()` — TA-Lib: EMA, RSI, MACD, Bollinger Bands, ATR
3. `sentiment.analyze()` — parallel fetch: analyst consensus + Fear & Greed + news headlines
4. `commodity.get_correlation()` — live futures (GC=F, CL=F, BTC-USD, etc.) for overnight moves
5. `signals.generate_signal()` — technical + sentiment + commodity → BUY/SELL/HOLD + strength %
6. Strategy filters, ranks by strength, adds sector diversification context
7. Generates sell-to-fund suggestions when cash is low
8. Caches results for cross-command consistency
9. Bot posts to Discord; if strength ≥ 40% → APNs VoIP push to iOS

### Trade Reporting

User executes trades via brokerage → reports via Discord `/buy`/`/sell`, web trade form, or iOS app → `portfolio` updates holdings and P&L in PostgreSQL → `risk` manager tracks stops.

### Screenshot Upload

Brokerage screenshot via Discord `/upload`, web upload page, or iOS PhotosPicker → `vision.py` calls Claude Sonnet API → parsed holdings shown with Confirm/Edit/Cancel → `portfolio.sync_from_snapshot()`.

---

## Database (PostgreSQL)

ORM models in `api/src/trader_api/models.py`:

| Model | Key Fields | Purpose |
|-------|-----------|---------|
| `Holding` | symbol (unique), quantity, avg_cost, entry_date | Current portfolio positions |
| `Trade` | symbol, action (BUY/SELL), quantity, price, total, pnl, pnl_pct | Trade audit trail |
| `DailySnapshot` | date (unique), portfolio_value, cash, positions_value | Equity curve data |
| `PortfolioMeta` | cash, initial_capital | Single-row portfolio state |
| `SignalHistory` | symbol, signal, strength, score, reasons | Signal audit trail |
| `DeviceRegistration` | device_token (unique), platform, enabled, daily_disabled_date | Push notification devices |
| `NotificationLog` | device_token, symbol, signal, strength, delivered, acknowledged | Push audit trail |
| `WebAuthnCredential` | credential_id (unique), public_key, sign_count, name | Registered passkeys |

---

## REST API Endpoints

### Portfolio

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portfolio/holdings` | Holdings with live prices, P&L, signal advice |
| GET | `/api/portfolio/pnl` | Daily & total P&L, cash, recent trades |
| GET | `/api/portfolio/snapshots` | Daily snapshots for equity curve |
| PUT | `/api/portfolio/holding` | Update holding quantity/avg_cost |
| DELETE | `/api/portfolio/holding/{symbol}` | Delete a holding |
| PUT | `/api/portfolio/cash` | Set cash balance |

### Trades

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/trades/buy` | Record buy (updates holding, deducts cash) |
| POST | `/api/trades/sell` | Record sell (calculates P&L, adds cash) |
| GET | `/api/trades/history` | Last N trades |

### Signals

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/signals/check/{symbol}` | Signal + sentiment for one symbol |
| GET | `/api/signals/recommend` | Top N buy/sell signals + funding pairs |
| GET | `/api/signals/price/{symbol}` | Current market price |
| GET | `/api/signals/history/{symbol}` | OHLCV price history (60d default) |
| GET | `/api/signals/insights` | Daily insights (all holdings, movers, sectors) |
| GET | `/api/signals/commodities` | Live commodity/crypto prices and overnight moves |

### System

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/status` | System status, risk state |
| POST | `/api/upload/parse` | Parse screenshot via Claude vision |
| POST | `/api/upload/confirm` | Sync portfolio from parsed holdings |
| GET | `/api/symbols` | Full symbol universe (~333) |

### Notifications

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/notifications/register` | Register device for push notifications |
| GET | `/api/notifications/preferences` | Get notification preferences for device |
| PUT | `/api/notifications/preferences` | Toggle enabled / daily mute |
| GET | `/api/notifications/history` | Recent notification log for device |
| POST | `/api/notifications/acknowledge/{id}` | Mark notification acknowledged (stops retry) |

### Debug

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/debug/devices` | List all registered devices |
| POST | `/api/debug/test-push` | Send a test notification or VoIP call for a given signal |

### Authentication

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/auth/status` | Check if passkeys registered (no auth) |
| POST | `/api/auth/register/options` | WebAuthn registration challenge |
| POST | `/api/auth/register/verify` | Verify registration, store credential, return JWT |
| POST | `/api/auth/login/options` | WebAuthn authentication challenge |
| POST | `/api/auth/login/verify` | Verify authentication, return JWT |
| DELETE | `/api/auth/credentials/{id}` | Delete a registered passkey |

---

## Authentication (Passkey / WebAuthn)

Single-user, token-gated authentication. If no passkey is registered, the API remains open (backward-compatible). Once a passkey is registered, all API requests (except `/api/auth/*` and `/api/health`) require a `Bearer` JWT token.

**Flow:**
1. User registers a passkey via web Settings page or iOS Status tab
2. Server stores `WebAuthnCredential` (public key, credential ID, sign count)
3. Server returns a JWT (30-day expiry, HS256)
4. All subsequent API requests include `Authorization: Bearer <token>`
5. On 401, web shows AuthGate overlay; iOS shows passkey login screen

**Components:**
- `api/auth.py` — `require_auth` dependency (checks JWT if any credential exists), token issuance
- `api/routers/auth.py` — WebAuthn registration/authentication endpoints using `py_webauthn`
- `web/components/ui/auth-gate.tsx` — intercepts 401s, shows passkey login overlay
- `web/app/settings/page.tsx` — passkey management (register, delete, list)
- `app/Services/AuthManager.swift` — `ASAuthorizationController` for iOS passkeys
- Apple Associated Domains (`webcredentials:yourdomain.com`) — cross-platform passkeys

---

## Dependency Injection (`deps.py`)

Singletons initialized at startup: `_config`, `_market_data`, `_risk`, `_sentiment`, `_commodity`, `_notifier`.
Session-scoped factories: `make_portfolio(db)`, `make_strategy(portfolio)`.
APNs notifier only initializes if `APNS_KEY_PATH` env var is set.

---

## Push Notifications

VoIP pushes via Apple Push Notification service (APNs):

- **Trigger:** Signal strength ≥ 40% during scheduled scan, with 60-min cooldown per symbol
- **Delivery:** HTTP/2 to APNs with ES256 JWT auth, retry once after 30s if not acknowledged
- **iOS:** PushKit VoIP registration → CallKit incoming call UI → bypasses DND/silent mode
- **Models:** `DeviceRegistration` (tokens), `NotificationLog` (delivery audit)

---

## Scheduled Tasks

| Task | Schedule | Description |
|------|----------|-------------|
| Market scan | Every 15 min, market hours (9:30 AM – 4:00 PM ET) | Exit alerts + top buy/sell signals |
| Pre-market movers | 8:00 AM ET, weekdays | US premarket moves for CDR counterparts |
| Morning briefing | 8:30 AM ET, weekdays | Full portfolio analysis + market overview |
| Daily status | 3:50 PM ET, weekdays | P&L summary, daily snapshot saved |
| Evening recap | 10:00 PM PT, weekdays | Full portfolio analysis + market overview |

---

## Discord Slash Commands

| Command | Description |
|---------|-------------|
| `/buy <symbol> <quantity> <price>` | Record a buy trade |
| `/sell <symbol> <quantity> <price>` | Record a sell trade |
| `/upload <image>` | Parse brokerage screenshot, confirm and sync |
| `/holdings` | Portfolio with live prices, per-holding advice, edit dropdown |
| `/pnl` | Daily + total P&L breakdown with recent trades |
| `/recommend` | Universe scan → top buy/sell signals with sell-to-fund suggestions |
| `/check <symbol>` | Signal + sentiment for any symbol (autocompletes held positions) |
| `/status` | Bot uptime, tracked symbols, market hours |

---

## Web Dashboard Pages

| Route | Description |
|-------|-------------|
| `/` | Dashboard — portfolio value, equity curve, daily P&L, latest signals |
| `/portfolio` | Holdings table with live prices, P&L, signal/advice per holding |
| `/signals` | Buy/sell recommendations, watchlist alerts, score breakdowns, symbol search |
| `/trades` | Buy/sell forms, trade history table |
| `/upload` | Screenshot dropzone, parsed holdings editor, confirm/cancel |
| `/status` | Uptime, market status, symbols tracked, risk status |
| `/settings` | Passkey management, authentication status |
| `/debug` | Test push notifications and VoIP calls (hidden; unlock by tapping footer 10×) |

---

## iOS App Tabs

| Tab | Description |
|-----|-------------|
| Dashboard | Stat cards, equity chart, latest signals, sector exposure |
| Portfolio | Holdings list with P&L, edit sheet, cash edit, signal badges |
| Signals | Recommendations, exit alerts, type-ahead symbol search → detail with price chart |
| Trades | Buy/sell form, trade history |
| Upload | PhotosPicker, Claude Vision parse, confirm |
| Status | System status, notification toggle, mute today, passkey login |

---

## Design System

| Role | Color | Token | Usage |
|------|-------|-------|-------|
| Primary / CTA | Purple | `brand-400` (#a78bfa), `brand-500` (#8b5cf6) | Badges, buttons, links, app tint |
| Positive / Success | Green | `emerald-400` (#34d399) | Profit numbers, success indicators |
| Negative / Error | Red | `red-400` (#f87171) | Loss numbers, sell badges, errors |
| Warning / Neutral | Amber | `amber-400` (#fbbf24) | Hold badges, warnings |
| Background | Black | `surface-950` (#09090b) | Page background |
| Cards | Zinc | `surface-900` (#18181b) | Glass cards: `bg-white/[0.03]` + border |
| Text | Zinc | `surface-50` (#fafafa) | Primary text |
| Muted text | Slate | `slate-400`–`slate-500` | Labels, secondary info |

**Web:** Tailwind CSS classes, glass-card CSS component, skeleton shimmer via CSS animation.
**App:** SwiftUI native components with `.tint(Theme.brand)`. Glass card for standalone cards. Lists use native `Section` grouping. `.preferredColorScheme(.dark)` at root.

---

## Configuration

`config/settings.yaml` has defaults (symbol universe, risk params, schedules). Create `config/settings.local.yaml` (gitignored) for local overrides.

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `DISCORD_BOT_TOKEN` | Discord bot authentication |
| `DISCORD_CHANNEL_ID` | Channel for signals/alerts |
| `DISCORD_GUILD_ID` | Server for slash commands |
| `ANTHROPIC_API_KEY` | Claude vision screenshot parsing |
| `DATABASE_URL` | PostgreSQL connection string |
| `POSTGRES_PASSWORD` | Used by docker-compose |
| `NEXT_PUBLIC_API_URL` | API URL for web dashboard |
| `APNS_KEY_PATH` | Path to APNs .p8 key file |
| `APNS_KEY_ID` | APNs key identifier |
| `APNS_TEAM_ID` | Apple Developer Team ID |
| `APNS_BUNDLE_ID` | iOS app bundle identifier |

---

## Docker Deployment

`docker-compose.yml` orchestrates 5 services:

| Service | Image | Port | Notes |
|---------|-------|------|-------|
| `postgres` | PostgreSQL 16 Alpine | 5432 (internal) | Healthcheck, persistent `pgdata` volume |
| `api` | Custom (FastAPI) | 8000 (internal) | Depends on postgres |
| `bot` | Custom (discord.py) | — | Depends on postgres |
| `web` | Custom (Next.js) | 3000 (internal) | Depends on api, Bun for builds |
| `caddy` | Caddy | 80, 443 | Routes `/api/*` → api, `/*` → web |

**Domain:** `yourdomain.com` — SSL terminated by Cloudflare, proxied to Caddy.

### Deploy from Local

```bash
git push origin main
ssh -i your-ssh-key ubuntu@your-server \
  "cd ~/trader && git pull origin main && docker compose up -d --build"
```

---

## Key Constraints

- **No auto-execution** — IBKR no longer allows Canadian securities via API. All trades are manual.
- **Commission drag** — ~$2,000 capital means each round-trip costs ~0.1%. High-frequency not viable.
- **yfinance data** — ~15 min delayed. Fine for daily-bar swing trading, not intraday.
- **Sentiment limitations** — Analyst data updates infrequently, news is keyword-based, Fear & Greed is market-wide.
- **CDR data gaps** — Some `.NE` symbols have spotty yfinance data. US fallback mitigates this.
- **Risk hard limits** — 8% daily drawdown or 20% total drawdown halts all recommendations.
- **Web uses Bun** — Not npm/yarn. `bun install`, `bun run dev`, `bun run build`.
- **Anthropic API** — Required for `/upload` screenshot parsing. Uses Claude Sonnet for vision.
