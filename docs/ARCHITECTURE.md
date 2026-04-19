# Architecture

## System Overview

```
Internet → Cloudflare (SSL) → Caddy (:443) → web (:3000) for pages
                                             → api (:8000) for /api/*

Bot imports trader_api directly as a Python package (not HTTP).
Web + App communicate via REST API (web through Caddy, app directly via configured URL).
All share the same PostgreSQL database.

API scheduler (every 15 min, market hours) → signal scan:
  → Central NotificationDispatcher deduplicates across all channels
  → Only notifies once per day per channel per symbol (re-sends if data changes)
  → Push: strength ≥ 40% → APNs VoIP push → iOS CallKit (DND bypass) + alert
  → Discord: bot posts only new/changed actions (not every scan)

Scheduler runs inside FastAPI lifespan — notifications fire regardless of
whether the Discord bot is up.
```

### Components

| Component | Technology | Role |
|-----------|-----------|------|
| **API** (`api/`) | FastAPI, SQLAlchemy async, asyncpg | REST API + all shared business logic |
| **Bot** (`bot/`) | discord.py ≥ 2.3 | Discord slash commands, scheduled tasks (single event loop) |
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
│           ├── sentiment.py          # Analyst consensus, Fear & Greed, news, commodity
│           ├── commodity.py          # Commodity/crypto correlation adjustments
│           ├── notifications.py      # Central notification dedup: fingerprint-based, per-channel, per-day
│           ├── notifier.py           # APNs push: VoIP signals + standard alerts (HTTP/2, ES256 JWT)
│           ├── scheduler.py          # Background asyncio loops: scan + premarket/briefing/close/recap
│           ├── vision.py             # Claude Sonnet vision (screenshot parsing)
│           └── backtest.py           # Historical replay
│
├── bot/                              # Discord bot (imports trader_api as Python dependency)
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── src/trader_bot/
│       ├── bot.py                    # TraderBot class, fresh-session-per-command pattern
│       ├── main.py                   # Entry point: single asyncio.run() for init + bot
│       └── cogs/
│           ├── trading.py            # /buy, /sell
│           ├── portfolio.py          # /holdings, /pnl + dropdown edit
│           ├── signals.py            # /recommend, /check + recheck button
│           ├── upload.py             # /upload + screenshot parsing
│           ├── status.py             # /status
│           └── tasks.py              # Scheduled loops: exit alerts + Discord channel posting (no push logic)
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
├── docker-compose.yml                # 5 services; web port configurable via WEB_PORT
├── Caddyfile                         # Production reverse proxy (domain/HTTPS)
├── Caddyfile.local                   # Local reverse proxy (HTTP-only, host:port friendly)
└── .env.example                      # Required env vars
```

---

## Data Flow

### Signal Generation (every 15 min during market hours)

Two independent consumers fire simultaneously:
- **`scheduler.py` (API)** — sends push notifications to all registered devices
- **`cogs/tasks.py` (Bot)** — posts signal embeds to the Discord channel

Both call `strategy.get_top_recommendations()` → for each of ~333 symbols:

1. `market_data.get_historical_data()` — 60 days of daily bars via yfinance (cached 5 min)
2. `signals.compute_indicators()` — TA-Lib: EMA, RSI, MACD, Bollinger Bands, ATR, volume
3. `sentiment.analyze()` — parallel: analyst consensus + Fear & Greed + news headlines + commodity correlation
4. `signals.generate_signal()` — scores each indicator, sums to final score (max ±9)
5. Score ≥ +2.0 → BUY, ≤ -2.0 → SELL, else HOLD. Strength = `|score| / 9`
6. Scanner filters: BUY ≥ 35% strength, SELL ≥ 30% strength
7. Strategy ranks by strength, applies sector cap penalty (>40% exposure → halved), adds sell-to-fund suggestions
8. Caches results for cross-command consistency
9. **Central dedup:** `NotificationDispatcher` fingerprints each signal/action (symbol + score + strength + reason + …) — only dispatches if new or changed today
10. **API scheduler:** strength ≥ 40% → `notifier.notify_signal()` → APNs VoIP push → iOS CallKit
11. **Bot:** posts only new/changed action embeds with Recheck button to Discord channel

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
| `DeviceRegistration` | device_token (unique), platform, enabled, daily_disabled_notifications_date, daily_disabled_calls_date | Push notification devices with per-channel daily mute controls |
| `NotificationLog` | device_token, symbol, signal, strength, delivered, acknowledged | Push audit trail |
| `NotificationDigest` | channel, symbol, fingerprint (SHA-256), trading_day (ET) | Central dedup: once per day per channel per symbol, re-send on data change |
| `SignalSnooze` | symbol (unique), snoozed_at, expires_at, pnl_pct_at_snooze, indefinite, phantom_trailing_stop | Snoozed sell signals with customizable duration and optional phantom trailing stop |
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
| GET | `/api/signals/recommend` | Top N buy/sell/watchlist signals + exit alerts + funding pairs |
| GET | `/api/signals/actions` | Prioritized, position-sized action plan (sells → swaps → buys); BUY actions include `actionable` flag (false if insufficient cash/slots) |
| GET | `/api/signals/price/{symbol}` | Current market price |
| GET | `/api/signals/history/{symbol}` | OHLCV price history (60d default) |
| GET | `/api/signals/insights` | Daily insights (all holdings, movers, sectors) |
| POST | `/api/signals/snooze` | Snooze a sell signal (customizable: 1h–7d or indefinite), optional phantom trailing stop |
| DELETE | `/api/signals/snooze/{symbol}` | Remove snooze for a symbol |
| GET | `/api/signals/snoozed` | List all active (non-expired) snoozes |
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
- Apple Associated Domains (`webcredentials:<your-domain>`) — cross-platform passkeys

---

## Dependency Injection (`deps.py`)

Singletons initialized at startup: `_config`, `_market_data`, `_risk`, `_sentiment`, `_commodity`, `_notifier`.
Session-scoped factories: `make_portfolio(db)`, `make_strategy(portfolio)`.
APNs notifier only initializes if `APNS_KEY_PATH` env var is set.

---

## Notification System

All notifications (push + Discord) go through a central dedup layer (`api/services/notifications.py`) before dispatch. This ensures you only receive a notification once per day per channel per symbol — unless the underlying data changes.

**Central dedup (`NotificationDispatcher`):**
- Fingerprints each action/signal by hashing: type, symbol, signal, score, strength, reason, shares, urgency
- Stores fingerprint per channel + symbol + trading day (ET) in `notification_digests` table
- Re-notifies only when the fingerprint changes (e.g. score shifts, new reason, price target moves)
- Channels: `"push"` (APNs), `"discord"` (bot) — extensible to future channels (Telegram, etc.)

**VoIP signal pushes** (CallKit — bypasses DND):
- Trigger: strength ≥ 40% on BUY or SELL signals during the 15-min scan, after dedup check
- Delivery: HTTP/2 to `api.push.apple.com` with ES256 JWT, retry once after 30s if unacknowledged
- iOS: PushKit → `PKPushRegistry` → `CXProvider.reportNewIncomingCall()` → CallKit UI
- Also sends a standard alert push so it appears in notification center

**Standard alert pushes** (banner/sound):
- Premarket movers: 8:00 AM ET weekdays
- Morning briefing: 8:30 AM ET weekdays
- Market close summary: 3:50 PM ET weekdays
- Evening recap: 10:00 PM PT weekdays
- Delivery: standard APNs alert push (not VoIP), `aps.alert` payload with `sound: default`

**Models:** `DeviceRegistration` (VoIP token + push token per device), `NotificationLog` (delivery + ack audit trail), `NotificationDigest` (central dedup fingerprints)

---

## Scheduled Tasks

Two independent schedulers run the same logical events. Both go through `NotificationDispatcher` for dedup. The API scheduler handles push notifications; the bot scheduler handles Discord posting. Both are fault-tolerant — if the bot is down, push notifications still fire; if the API is down, nothing works (it's the central service).

| Event | Schedule | API scheduler (`scheduler.py`) | Bot scheduler (`tasks.py`) |
|-------|----------|---------------------------------|---------------------------|
| Market scan | Every 15 min, market hours | VoIP + alert push (≥ 40% strength, deduped) | New/changed action embeds to Discord (deduped) |
| Pre-market movers | 8:00 AM ET, weekdays | Alert push with top 3 CDR movers | Pre-market embed to Discord |
| Morning briefing | 8:30 AM ET, weekdays | Alert push with portfolio summary | Full insights embeds to Discord |
| Market close | 3:50 PM ET, weekdays | Alert push with daily P&L | Daily status embed + record daily snapshot |
| Evening recap | 10:00 PM PT, weekdays | Alert push with portfolio summary | Full insights embeds to Discord |

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

### Privacy Toggle

Eye icon in the sidebar header toggles a "hide numbers" mode (`web/lib/privacy.tsx`). When active, portfolio-sensitive numbers (value, cash, P&L, quantities, avg cost, equity chart Y-axis/tooltips) are masked — digits replaced with `••••` while preserving `$`, `%`, `+`, `-` signs. Market-fact data (current stock prices, price charts, premarket movers) remains visible. State persists in `localStorage`.

---

## iOS App Tabs

| Tab | Position | Description |
|-----|----------|-------------|
| Dashboard | Main | Stat cards, equity chart, latest signals, sector exposure |
| Portfolio | Main | Holdings list with P&L, edit sheet, cash edit, signal badges |
| Actions | Main | Action plan: sells, swaps, actionable buys, signal-only buys (not enough cash), snoozed |
| Trades | Main | Buy/sell form, trade history |
| Upload | More | PhotosPicker, Claude Vision parse, confirm |
| Pre-Market | More | CDR counterpart US premarket movers |
| Status | More | System status, notification toggle, mute today, passkey login |

Tabs 0–3 appear in the main tab bar; tabs 4–6 appear in the iOS "More" section. Portfolio changes (trades, cash edits, holding edits) trigger an automatic refresh of the action plan via `NotificationCenter`.

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

`docker-compose.yml` orchestrates 5 services by default:

| Service | Image | Port | Notes |
|---------|-------|------|-------|
| `postgres` | PostgreSQL 16 Alpine | 5432 (internal) | Healthcheck, persistent `pgdata` volume |
| `api` | Custom (FastAPI) | 8000 (internal) | Depends on postgres |
| `bot` | Custom (discord.py) | — | Starts by default; self-skips when Discord env vars are missing |
| `web` | Custom (Next.js) | `${WEB_PORT}` (internal) | Depends on api, Bun for builds |
| `caddy` | Caddy | 80, 443 | Routes `/api/*` → api, `/*` → web |

**Domain:** Set via `DOMAIN` env var in your Caddy config. SSL terminated by Cloudflare (or Caddy auto-HTTPS), proxied to Caddy.
**Web port:** `WEB_PORT` controls the port the web container listens on (and the Caddy upstream).
**Caddy host ports:** `CADDY_HTTP_PORT` and `CADDY_HTTPS_PORT` control where Caddy binds on the host (defaults `80`/`443`).
**Local Caddy behavior:** `docker-compose.local.yml` replaces both base Caddy `ports` and `volumes`, mounting `Caddyfile.local` and binding only HTTP on `CADDY_LOCAL_HTTP_PORT` (default `3000`). This avoids local auto-HTTPS redirects and preserves host:port URLs for LAN/IP access.

### Deploy

```bash
git push origin main
ssh user@your-server "cd ~/trader && git pull origin main && docker compose up -d --build"
```

Discord automation is env-driven: if required Discord vars are set, bot starts; if missing, bot exits cleanly without impacting API/web.

---

## Key Constraints

- **No auto-execution** — IBKR no longer allows Canadian securities via API. All trades are manual.
- **Commission drag** — commission-free brokerages (Wealthsimple) are assumed. On fee-based brokerages, round-trip costs should be factored into position sizing.
- **yfinance data** — ~15 min delayed. Fine for daily-bar swing trading, not intraday.
- **Sentiment limitations** — Analyst data updates infrequently, news is keyword-based, Fear & Greed is market-wide.
- **CDR data gaps** — Some `.NE` symbols have spotty yfinance data. US fallback mitigates this.
- **Risk hard limits** — 8% daily drawdown or 20% total drawdown halts all recommendations.
- **Web uses Bun** — Not npm/yarn. `bun install`, `bun run dev`, `bun run build`.
- **Anthropic API** — Required for `/upload` screenshot parsing. Uses Claude Sonnet for vision.
- **Bot single event loop** — Bot must run init + start on one `asyncio.run()` call. asyncpg connections are bound to the event loop they were created on; a second loop causes `InterfaceError`.
- **Sector resolution** — `get_sector()` tries alternate exchange suffixes (`.TO` ↔ `.NE` ↔ bare), so holdings don't need to match the exact config symbol to get the right sector.
