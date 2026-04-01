# Trading Dashboard — Development Plan

## Quick Start

This file is the primary context document for new Claude Code conversations. Read it first, then dive into specific files as needed.

**What this is:** A trading recommendation and portfolio tracking system for TSX stocks, CBOE Canada CDRs, and CAD-hedged ETFs. It provides buy/sell/swap signals — the user trades manually and reports back.

**4-component architecture:**
- `api/` — FastAPI REST API + all shared business logic + PostgreSQL
- `bot/` — Discord bot that imports `trader_api` as a Python package
- `web/` — Next.js web dashboard that communicates via REST API
- `app/` — SwiftUI app (iOS/macOS) with VoIP push notifications via CallKit

**Deployed at:** `yourdomain.com` on `your-server` (Ubuntu ARM, your server)

---

## Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| **API** | FastAPI, SQLAlchemy (async), asyncpg | Python 3.11, port 8000 |
| **Bot** | discord.py ≥ 2.3 | Slash commands, persistent buttons |
| **Web** | Next.js 14, Bun, Tailwind CSS, Recharts | App Router, standalone Docker output |
| **App** | SwiftUI, Swift Charts, PushKit, CallKit | iOS 26+, macOS-ready, Xcode project |
| **DB** | PostgreSQL 16 | Shared by api + bot |
| **Market data** | yfinance | ~15 min delay, daily bars |
| **TA** | TA-Lib (C library + Python) | EMA, RSI, MACD, BB, ATR |
| **Sentiment** | yfinance + fear-greed lib | Analyst consensus, F&G, news |
| **Vision** | Anthropic Claude Sonnet | Brokerage screenshot parsing |
| **Auth** | py-webauthn, PyJWT, @simplewebauthn/browser, ASAuthorization | Passkey (WebAuthn) registration/login, JWT tokens |
| **Push** | APNs (HTTP/2, ES256 JWT) | VoIP pushes → CallKit incoming calls |
| **Proxy** | Caddy | SSL via Cloudflare, routes /api/* and /* |
| **Infra** | Docker Compose (5 services) | postgres, api, bot, web, caddy |

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
│       ├── models.py                 # ORM: Holding, Trade, DailySnapshot, PortfolioMeta, SignalHistory, DeviceRegistration, NotificationLog, WebAuthnCredential
│       ├── schemas.py                # Pydantic request/response models (incl. notification schemas)
│       ├── auth.py                   # JWT token management, require_auth dependency (skips if no passkey registered)
│       ├── deps.py                   # Singleton services: market_data, risk, sentiment, commodity, notifier
│       ├── routers/
│       │   ├── auth.py               # POST register/login options+verify, GET status, DELETE credentials
│       │   ├── portfolio.py          # GET /api/portfolio/{holdings,pnl,snapshots}, PUT holding/cash, DELETE holding
│       │   ├── trades.py             # POST /api/trades/{buy,sell}, GET /api/trades/history
│       │   ├── signals.py            # GET /api/signals/{check,recommend,insights,price}
│       │   ├── status.py             # GET /api/status, POST /api/upload/{parse,confirm}, GET /api/symbols
│       │   └── notifications.py      # POST register, GET/PUT preferences, GET history, POST acknowledge
│       └── services/
│           ├── market_data.py        # yfinance wrapper, batch price fetching, CDR fallback
│           ├── signals.py            # TA-Lib indicators, score → BUY/SELL/HOLD conversion
│           ├── strategy.py           # Recommendations, caching, sell-to-fund, advice, notification hook
│           ├── portfolio.py          # DB-backed portfolio (async SQLAlchemy CRUD)
│           ├── risk.py               # Position sizing (ATR), stop losses, drawdown circuit breakers
│           ├── sentiment.py          # Analyst consensus (4h cache), Fear & Greed (1h), news (30m)
│           ├── commodity.py          # Commodity/crypto correlation adjustments
│           ├── notifier.py           # APNs VoIP push (HTTP/2, ES256 JWT, retry logic)
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
│   ├── components/ui/                # Reusable: stat-card, signal-badge, equity-chart, sidebar, etc.
│   └── lib/                          # api.ts (client + types), hooks.ts (TanStack Query), utils.ts
│
├── app/                              # SwiftUI app (iOS/macOS) — built via Xcode, not Docker
│   ├── Trader.xcodeproj/             # Xcode project (file-system-sync, auto-discovers Swift files)
│   ├── Trader/                       # Main source (all auto-discovered by Xcode)
│   │   ├── TraderApp.swift           # @main entry, TabView (6 tabs), onboarding gate
│   │   ├── Info.plist                # UIBackgroundModes: voip, remote-notification
│   │   ├── Trader.entitlements       # aps-environment: development
│   │   ├── Assets.xcassets/          # App icon, accent color
│   │   ├── Config/
│   │   │   ├── AppConfig.swift       # API URL stored in UserDefaults
│   │   │   └── Theme.swift           # Design system colors matching web (brand, positive, negative, etc.)
│   │   ├── Models/
│   │   │   └── APIModels.swift       # Codable structs matching all Pydantic schemas (incl. auth)
│   │   ├── Services/
│   │   │   ├── APIClient.swift       # URLSession REST client with Bearer token injection + 401 handling
│   │   │   ├── AuthManager.swift     # Passkey registration/login via ASAuthorizationController, JWT token storage
│   │   │   └── PushManager.swift     # PushKit VoIP registration + CallKit incoming call UI
│   │   └── Views/
│   │       ├── Onboarding/
│   │       │   └── OnboardingView.swift  # First-launch API URL input + health check
│   │       ├── Tabs/
│   │       │   ├── DashboardView.swift   # Stat cards, equity chart, signals, sector exposure
│   │       │   ├── PortfolioView.swift   # Holdings list, P&L, edit sheet, signal badges
│   │       │   ├── SignalsView.swift     # Recommendations, exit alerts, symbol search
│   │       │   ├── TradesView.swift      # Buy/sell form, trade history
│   │       │   ├── UploadView.swift      # PhotosPicker, Claude Vision parse, confirm
│   │       │   └── StatusView.swift      # System status, notification toggle, mute today
│   │       └── Components/
│   │           ├── StatCardView.swift    # Glass card with value + change %
│   │           ├── SignalBadgeView.swift  # BUY/SELL/HOLD capsule badge
│   │           ├── EquityChartView.swift  # Swift Charts LineMark + AreaMark
│   │           ├── SectorChartView.swift  # Horizontal bar chart, purple gradient
│   │           ├── Formatting.swift      # currency(), percent(), pnlColor() helpers
│   │           └── LoadingView.swift     # Shimmer skeleton modifier
│   ├── TraderTests/
│   └── TraderUITests/
│
├── config/
│   ├── settings.yaml                 # Symbol universe (~333), risk params, schedules, notification config
│   └── settings.local.yaml           # Secrets (gitignored)
│
├── docker-compose.yml                # 5 services: postgres, api, bot, web, caddy
├── Caddyfile                         # Reverse proxy: /api/* → api:8000, /* → web:3000
├── .env.example                      # Required env vars (incl. APNS_KEY_ID, APNS_TEAM_ID, etc.)
├── CLAUDE.md                         # Full project docs for Claude Code
└── docs/
    ├── PLAN.md                       # This file
    ├── STRATEGY.md                   # Signal scoring, sentiment, position sizing
    └── NEXT_STEPS.md                 # Roadmap
```

---

## Architecture

```
Internet → Cloudflare (SSL) → Caddy (:443) → web (:3000) for pages
                                             → api (:8000) for /api/*

Bot imports trader_api directly as a Python package (not HTTP).
Web + App communicate via REST API (web through Caddy, app directly via configured URL).
All share the same PostgreSQL database.

Signal scan (every 15 min) → if signal strength ≥ 70%:
  → APNs VoIP push → iOS CallKit incoming call → DND bypass
  → retry once after 30s if not acknowledged
```

### Database Models (PostgreSQL)

| Model | Key Fields | Purpose |
|-------|-----------|---------|
| `Holding` | symbol (unique), quantity, avg_cost, entry_date | Current portfolio positions |
| `Trade` | symbol, action (BUY/SELL), quantity, price, total, pnl, pnl_pct | Trade audit trail |
| `DailySnapshot` | date (unique), portfolio_value, cash, positions_value | Equity curve data |
| `PortfolioMeta` | cash, initial_capital | Single-row portfolio state |
| `SignalHistory` | symbol, signal, strength, score, reasons | Signal audit trail |
| `DeviceRegistration` | device_token (unique), platform, enabled, daily_disabled_date | Push notification devices |
| `NotificationLog` | device_token, symbol, signal, strength, caller_name, delivered, acknowledged | Push notification audit trail |
| `WebAuthnCredential` | credential_id (unique), public_key, sign_count, transports, name | Registered passkeys |

### API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/portfolio/holdings` | Holdings with live prices, P&L, signal advice |
| GET | `/api/portfolio/pnl` | Daily & total P&L, cash, recent trades |
| GET | `/api/portfolio/snapshots` | Daily snapshots for equity curve |
| PUT | `/api/portfolio/holding` | Update holding quantity/avg_cost |
| DELETE | `/api/portfolio/holding/{symbol}` | Delete a holding |
| PUT | `/api/portfolio/cash` | Set cash balance |
| POST | `/api/trades/buy` | Record buy (updates holding, deducts cash) |
| POST | `/api/trades/sell` | Record sell (calculates P&L, adds cash) |
| GET | `/api/trades/history` | Last N trades |
| GET | `/api/signals/check/{symbol}` | Signal for one symbol |
| GET | `/api/signals/recommend` | Top N buy/sell signals + funding pairs |
| GET | `/api/signals/price/{symbol}` | Current market price |
| GET | `/api/signals/insights` | Daily insights (all holdings, movers, sectors) |
| GET | `/api/status` | System status, risk state |
| POST | `/api/upload/parse` | Parse screenshot via Claude vision |
| POST | `/api/upload/confirm` | Sync portfolio from parsed holdings |
| GET | `/api/symbols` | Full symbol universe |
| POST | `/api/notifications/register` | Register device for push notifications |
| GET | `/api/notifications/preferences` | Get notification preferences for device |
| PUT | `/api/notifications/preferences` | Toggle enabled / daily mute |
| GET | `/api/notifications/history` | Recent notification log for device |
| POST | `/api/notifications/acknowledge/{id}` | Mark notification acknowledged (stops retry) |
| GET | `/api/auth/status` | Check if passkeys registered (no auth) |
| POST | `/api/auth/register/options` | WebAuthn registration challenge |
| POST | `/api/auth/register/verify` | Verify registration, store credential, return JWT |
| POST | `/api/auth/login/options` | WebAuthn authentication challenge |
| POST | `/api/auth/login/verify` | Verify authentication, return JWT |
| DELETE | `/api/auth/credentials/{id}` | Delete a registered passkey |

### Authentication (Passkey / WebAuthn)

Single-user, token-gated authentication. If no passkey is registered, the API remains open (backward-compatible). Once a passkey is registered, all API requests (except `/api/auth/*` and `/api/health`) require a `Bearer` JWT token.

**Flow:**
1. User registers a passkey via web Settings page or iOS Status tab
2. Server stores `WebAuthnCredential` (public key, credential ID, sign count)
3. Server returns a JWT (30-day expiry, HS256)
4. All subsequent API requests include `Authorization: Bearer <token>`
5. On 401, web shows AuthGate overlay; iOS shows passkey login screen

**Components:**
- `auth.py` — `require_auth` dependency (checks JWT if any credential exists), token issuance
- `routers/auth.py` — WebAuthn registration/authentication endpoints using `py_webauthn`
- `web/components/ui/auth-gate.tsx` — intercepts 401s, shows passkey login overlay
- `web/app/settings/page.tsx` — passkey management (register, delete, list)
- `app/Trader/Services/AuthManager.swift` — `ASAuthorizationController` for iOS passkeys
- Apple Associated Domains (`webcredentials:yourdomain.com`) — enables cross-platform passkeys

### Dependency Injection (`deps.py`)

Singletons initialized at startup: `_config`, `_market_data`, `_risk`, `_sentiment`, `_commodity`, `_notifier`.
Session-scoped factories: `make_portfolio(db)`, `make_strategy(portfolio)`.
APNs notifier only initializes if `APNS_KEY_PATH` env var is set.

---

## Design System

| Role | Color | Token | Usage |
|------|-------|-------|-------|
| Primary action / CTA | Purple | `brand-400` (#a78bfa), `brand-500` (#8b5cf6) | Buy badges, confirm buttons, CTAs, links, sidebar active, app tint |
| Positive P&L / Success | Green | `emerald-400` (#34d399) | Profit numbers, success toasts, status indicators |
| Negative P&L / Error | Red | `red-400` (#f87171), `red-500` (#ef4444) | Loss numbers, sell badges, error toasts, delete buttons |
| Warning / Neutral | Amber | `amber-400` (#fbbf24) | Hold badges, warning toasts |
| Background | Black | `surface-950` (#09090b) | Page background |
| Cards | Zinc | `surface-900` (#18181b) | Glass cards with `bg-white/[0.03]` + border |
| Text | Zinc | `surface-50` (#fafafa) | Primary text |
| Muted text | Zinc | `slate-400`–`slate-500` | Labels, secondary info |

**Web:** Tailwind CSS classes, glass-card CSS component, skeleton shimmer via CSS animation.
**App:** SwiftUI native components (NavigationStack, TabView, List, .searchable, .refreshable) with `.tint(Theme.brand)` globally. Glass card only for standalone cards (dashboard stats, signal cards). Lists use native `Section` grouping. `.preferredColorScheme(.dark)` at root.

---

## Commands

```bash
# API (local dev)
cd api && pip install -e ".[dev]"
uvicorn trader_api.main:app --reload

# Bot (local dev)
cd bot && pip install -e .
python -m trader_bot.main

# Web dashboard (local dev — uses Bun, not npm)
cd web && bun install
bun run dev            # http://localhost:3000
bun run build          # verify build passes

# App (Xcode — open app/Trader.xcodeproj, build to device)
# Requires: Push Notifications + Background Modes (VoIP, Remote notifications) capabilities
# APNs key (.p8) in config/, env vars: APNS_KEY_ID, APNS_TEAM_ID, APNS_BUNDLE_ID

# Docker deployment (all 5 services)
docker compose up -d --build
docker compose logs -f

# Tests & lint
pytest
ruff check api/src/ bot/src/
mypy api/src/ bot/src/

# Deploy from local
git push
ssh -i your-ssh-key ubuntu@your-server \
  "cd ~/trader && git pull origin main && docker compose up -d --build"
```

---

## Completed Steps

- [x] Split monolith into 3-package architecture (api, bot, web) with PostgreSQL
- [x] Build Next.js web dashboard (6 pages, shared UI, API client)
- [x] Config, env setup, testing, validation, deploy with Caddy + Cloudflare
- [x] Web polish: localStorage cache → TanStack Query, Cmd+K search, price charts, refresh buttons
- [x] Portfolio CRUD endpoints, cash tracking, dark theme, P&L fixes
- [x] Brand theme: purple primary, green/red P&L, amber warning, zinc surfaces, consistent across all components
- [x] Signal system enhancements: same-sector swap exemption, watchlist alerts, score breakdown display, exit alerts
- [x] Bug fixes: Fear & Greed library API change, daily P&L comparison, bot DB pool exhaustion
- [x] SwiftUI app (app/) — 6 tabs matching web, onboarding with configurable API URL, native SwiftUI components
- [x] VoIP push notifications — APNs notifier service (HTTP/2, ES256 JWT), DeviceRegistration + NotificationLog models, notification router (5 endpoints), signal scan hook with 70% strength threshold + 60min cooldown, PushKit + CallKit on iOS for DND bypass with 30s retry

- [x] Passkey authentication — WebAuthn registration/login via py-webauthn, JWT token-gated API (auto-skips if no passkey registered), web settings page with passkey management, AuthGate overlay on 401, iOS ASAuthorizationController integration with Associated Domains, apple-app-site-association via Caddy

- [x] iOS app polish — Symbol search suggestions (type-ahead from tracked universe), signal detail view with price history chart (area+line, range picker), tappable cash edit on Portfolio page, skeleton loading for all Dashboard sections (stat cards, signals, equity chart, sector exposure)

**Notable observations:**
- Brand theme took 3 iterations — started with purple for everything, then split P&L to standard green/red
- Fear & Greed library silently changed return type (dict vs object), sentiment fell back to neutral for weeks
- Xcode 26 uses `SWIFT_DEFAULT_ACTOR_ISOLATION = MainActor` and `SWIFT_UPCOMING_FEATURE_MEMBER_IMPORT_VISIBILITY = YES` by default — requires explicit `import Combine` for `ObservableObject` conformance

---
