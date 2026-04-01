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
- [x] Debug page on web — `/debug` page to manually trigger test push notification or VoIP call for the highest-confidence current signal. Device dropdown (per-device or all devices), inline send result feedback. API endpoints: `GET /api/debug/devices`, `GET /api/debug/top-signal`, `POST /api/debug/test-push`.

**Notable observations:**
- Brand theme took 3 iterations — started with purple for everything, then split P&L to standard green/red
- Fear & Greed library silently changed return type (dict vs object), sentiment fell back to neutral for weeks
- Xcode 26 uses `SWIFT_DEFAULT_ACTOR_ISOLATION = MainActor` and `SWIFT_UPCOMING_FEATURE_MEMBER_IMPORT_VISIBILITY = YES` by default — requires explicit `import Combine` for `ObservableObject`
- `create_all` doesn't add columns to existing tables — new columns (push_token, notification_type) need manual ALTER TABLE on production

---

## Current / Next

_Check off items as they're completed. Break large items into sub-items as needed._


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
- [ ] Partial exits — sell half at 2% gain, trail the rest
- [ ] Dynamic position sizing by signal strength
- [ ] VIX-based market regime detection

### Scale Up
- [ ] Increase capital → lower commission drag, more positions (3–4), more sector diversity
- [ ] Multi-strategy — add mean-reversion-only alongside momentum
- [ ] ML signals — gradient boosting on historical indicator data
- [ ] Covered calls on held positions for income
- [ ] Telegram bot as backup notification channel
