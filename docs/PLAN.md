# Development Plan

Progress tracker and roadmap. For architecture details see [ARCHITECTURE.md](ARCHITECTURE.md). For trading strategy see [STRATEGY.md](STRATEGY.md).

---

## Completed

- [x] Split monolith into 3-package architecture (api, bot, web) with PostgreSQL
- [x] Build Next.js web dashboard (6 pages, shared UI, API client)
- [x] Config, env setup, testing, validation, deploy with Caddy + Cloudflare
- [x] Web polish: localStorage cache → TanStack Query, Cmd+K search, price charts, refresh buttons
- [x] Portfolio CRUD endpoints, cash tracking, dark theme, P&L fixes
- [x] Brand theme: purple primary, green/red P&L, amber warning, zinc surfaces, consistent across all components
- [x] Signal system enhancements: same-sector swap exemption, watchlist alerts, score breakdown display, exit alerts
- [x] Bug fixes: Fear & Greed library API change, daily P&L comparison, bot DB pool exhaustion
- [x] SwiftUI app (app/) — 6 tabs matching web, onboarding with configurable API URL, native SwiftUI components
- [x] VoIP push notifications — APNs HTTP/2 + ES256 JWT, PushKit + CallKit on iOS for DND bypass, 70% strength threshold, 60min cooldown, 30s retry
- [x] Passkey authentication — WebAuthn via py-webauthn, JWT token-gated API, web settings page, AuthGate overlay, iOS ASAuthorizationController, Associated Domains
- [x] iOS app polish — Symbol search suggestions (type-ahead from universe), signal detail with price chart, tappable cash edit, skeleton loading for all Dashboard sections
- [x] Scheduled push notifications + Pre-Market page — Standard APNs alerts for premarket (8 AM ET), morning briefing (8:30 AM), market close (3:50 PM), evening recap (10 PM PT). Pre-Market tab on iOS and `/premarket` page on web with tappable movers that navigate to signal check. Deep linking from notifications, AppDelegate for push token. DB: push_token on device_registrations, notification_type on notification_log.
- [x] Debug page on web — `/debug` page (hidden behind 10-tap footer easter egg, persisted in localStorage for 24h) to manually trigger test push notification or VoIP call for the top signal from cached recommendations. Device dropdown (per-device or all). API: `GET /api/debug/devices`, `POST /api/debug/test-push`.
- [x] Lower VoIP call threshold to 40% — both BUY and SELL signals now trigger CallKit push at ≥ 40% strength (was 70% buy / 50% sell). Updated `config/settings.yaml` and unified sell threshold to match buy.
- [x] Customizable snooze — replaced fixed 4h snooze with popup (web) / sheet (iOS) offering 1h/4h/8h/24h/3d/7d/indefinite durations. Added toggleable phantom trailing stop (auto-unsnooze + push notification if loss worsens 3%+ from snooze point). DB: `indefinite` and `phantom_trailing_stop` columns on `signal_snoozes`.
- [x] Strategy conformance audit — verified `STRATEGY.md` against signal/risk/action-plan code, fixed action ordering, kept averaged-position risk tracking aligned after add-on buys/partial sells, and corrected stale docs around drawdown gates, position sizing, oversold fast-lane guards, hybrid take-profit, and swap advice.
- [x] Suppressed signals visibility — action-plan payload now includes BUY/SELL signals that were generated but suppressed for missing scan thresholds; web Signals page has a dedicated Suppressed tab showing score, price, sector, and suppression reason.

**Notable observations:**
- Brand theme took 3 iterations — started with purple for everything, then split P&L to standard green/red
- Fear & Greed library silently changed return type (dict vs object), sentiment fell back to neutral for weeks
- Xcode 26 uses `SWIFT_DEFAULT_ACTOR_ISOLATION = MainActor` and `SWIFT_UPCOMING_FEATURE_MEMBER_IMPORT_VISIBILITY = YES` by default — requires explicit `import Combine` for `ObservableObject`
- `create_all` doesn't add columns to existing tables — new columns (push_token, notification_type, indefinite, phantom_trailing_stop) need manual ALTER TABLE on production

---

## Current / Next

_Check off items as they're completed. Break large items into sub-items as needed._

- [x] Cash-aware actions + iOS tab reorganization — `actionable` field on BUY actions (false if insufficient cash/slots), separate "Signals" section on web + iOS, actionPlan auto-refreshes on trade/cash/holding changes, Trades promoted to tab 3, Pre-Market to More
- [x] Fix equity curve + price chart rendering — iOS: explicit tight Y-axis domain with 10% padding (EquityChartView, SignalDetailView, ActionDetailView), Web: use `formatCurrency` for equity chart Y-axis tick labels
- [x] Treat manual portfolio edits as capital adjustments, not PnL — `total_pnl = current_value - initial_capital` with `initial_capital` shifted on `delete_holding` (−cost basis), `update_cash` (±delta), `update_holding` (±cost delta), and re-sync. All `DailySnapshot` rows shifted by the same market-value delta so daily PnL stays stable. Empty-state (no holdings, no cash) returns zeros cleanly; fallback to `realized + unrealized` when no baseline is set.
- [x] Consolidate settings page under a single Trading section; expose editable `settings.yaml` values — new `editable_settings` registry of dotted-path config keys (type, group, label, description, min/max/step) persisted in `app_settings`. Replaced `/api/settings/profit-taking` with generic `GET` / `PUT /api/settings/config`; router mutates the live config dict so Strategy/RiskManager pick up changes on next read. Web settings page now has one Trading card (TrendingUp icon) with grouped bool toggles + numeric inputs (commit on blur/Enter, optimistic update w/ rollback, TanStack Query invalidation). iOS `SettingsView` kept its 2-toggle UX but migrated onto the same generic endpoint via `TradingSettings.from(SettingsConfigOut)`.
- [x] Add Suppressed tab to web Signals — below-threshold BUY/SELL candidates are visible without becoming actionable trades.

---

## Roadmap

### Validate & Tune
- [ ] Monitor live signal quality over 1–2 weeks, compare BUY signals to subsequent price action
- [ ] Run backtester on all symbols with 6–12 months of data; analyze win rate, drawdown, best sectors
- [ ] Tune: EMA periods (try 8/21), RSI thresholds (try 25/75), strength threshold (try 50%), stop widths

### Strategy Improvements
- [ ] ADX filter — only trade when ADX > 20 (avoid choppy markets)
- [ ] Sector rotation — bias toward outperforming sector ETFs
- [ ] Earnings calendar — avoid entering before earnings
- [ ] Longer-term trend filter (50/200 EMA)
- [ ] NLP-based news scoring (replace keyword matching)
- [ ] LLM research overlay — feed structured scoring data, price/ATR/volume context, portfolio/risk gates, recent sourced news, earnings/events, and sector/macro context into an LLM that returns bounded JSON (`llm_adjustment`, confidence, catalysts, risk flags, veto). LLM can veto or modestly promote borderline candidates, but cannot override drawdown/regime/sector/cash gates; paper-trade/backtest before enabling actionability.
- [ ] Partial exits — sell half at 2% gain, trail the rest
- [ ] VIX-based market regime detection

### Scale Up
- [ ] Multi-strategy — add mean-reversion-only alongside momentum
- [ ] ML signals — gradient boosting on historical indicator data
- [ ] Covered calls on held positions for income
- [ ] Telegram bot as backup notification channel
