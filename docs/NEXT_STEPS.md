# Next Steps

## Current Status (March 25, 2026)

The bot is deployed and running on Ubuntu ARM server (`your-server`) as **Trader#9391**. It operates as a Discord-based recommendation system — no auto-execution. The user trades manually via their brokerage and reports trades back through slash commands or screenshot uploads.

**Architecture**: 3-component system — FastAPI REST API (`api/`), Discord bot (`bot/`), and Next.js web dashboard (`web/`). All backed by PostgreSQL. Docker Compose runs 4 services: postgres, api, bot, web. Market data via yfinance, sentiment via yfinance + Fear & Greed, screenshot parsing via Claude Sonnet vision.

**Universe**: ~92 symbols across 12 sectors (TSX, CBOE Canada CDRs, CAD-hedged ETFs).

---

## Phase 1: Validate & Tune (Current)

### 1.1 Monitor Live Recommendations
- [ ] Watch Discord for signal quality over 1–2 weeks
- [ ] Compare recommended BUY signals against subsequent price action
- [ ] Check that sell-to-fund suggestions make sense (selling the weakest holding)
- [ ] Verify exit alerts fire correctly when stops are hit
- [ ] Review logs: `ssh phoenix → cd ~/trader && docker compose logs -f trader`

### 1.2 Run Backtests
- [ ] Run the backtester on all 92 symbols with 6–12 months of historical data
- [ ] Analyze win rate, average win/loss, max drawdown per symbol
- [ ] Identify which symbols/sectors the strategy works best on
- [ ] Consider trimming the universe to top performers

### 1.3 Tune Parameters
Based on observation and backtest results:
- [ ] EMA periods (currently 10/30) — try 8/21 for faster signals
- [ ] RSI thresholds (currently 30/70) — try 25/75 for fewer but higher-quality signals
- [ ] Signal strength threshold (currently 40% for buy) — increase to 50% for fewer trades
- [ ] Stop loss (currently 5%) — may be too wide for small positions
- [ ] Trailing stop (currently 3%) — may be too tight, causing premature exits
- [ ] Sentiment weights — analyst, F&G, and news are currently unweighted; consider scaling

---

## Phase 2: Improve the Strategy

### 2.1 Additional Signal Factors
- [ ] **ADX**: Average Directional Index to filter choppy/sideways markets (only trade when ADX > 20)
- [ ] **Sector rotation**: Track sector ETFs and bias toward outperforming sectors
- [ ] **Earnings calendar**: Avoid entering positions before earnings announcements
- [ ] **Moving average convergence**: Add longer-term trend filter (50/200 EMA)

### 2.2 Improve Sentiment
- [ ] **NLP-based news scoring**: Replace keyword matching with a lightweight sentiment model
- [ ] **Options flow**: Monitor unusual options activity as a signal input
- [ ] **Insider trading data**: SEC/SEDAR filings as a long-term signal

### 2.3 Improve Position Management
- [ ] **Partial exits**: Sell half at first target (e.g., 2% gain), let rest ride with trailing stop
- [ ] **Re-entry logic**: If stopped out and signal is still strong, consider re-entering
- [ ] **Correlation filter**: Don't hold two highly correlated positions (e.g., RY + TD)
- [ ] **Dynamic position sizing**: Scale position size by signal strength (stronger signal = larger position)

### 2.4 Market Regime Detection
- [ ] Use VIX to detect high-volatility regimes
- [ ] Reduce recommendations or widen stops in extreme volatility
- [ ] Use 200-day moving average on XIU.TO (TSX index) as bull/bear filter

---

## Phase 3: Scale Up

### 3.1 More Capital
- [ ] With $5,000+, commission drag drops significantly
- [ ] Can increase max_positions from 2 to 3–4
- [ ] Can add more sector diversity to holdings

### 3.2 Database Backend
- [x] Replace JSON file with PostgreSQL for trade history
- [x] Enable historical P&L queries and equity curve visualization
- [x] Store signal history for backtesting validation

### 3.3 Web Dashboard
- [x] Next.js dashboard showing portfolio, recent trades, equity curve
- [x] Signal display without needing Discord (signals page with search)
- [x] Historical performance charts (equity curve with time range selector)
- [x] Trade recording via web (buy/sell forms)
- [x] Screenshot upload via web with confirm/edit flow

---

## Phase 4: Advanced Features (Ongoing)

- [ ] **Multi-strategy**: Add a separate mean-reversion-only strategy alongside momentum
- [ ] **ML signals**: Train a gradient boosting model on historical indicator data to predict next-day returns
- [ ] **Options strategies**: Covered calls on held positions for income generation
- [ ] **Alerting backup**: Telegram bot as secondary notification channel
- [x] **REST API**: Portfolio data exposed via FastAPI REST endpoints (used by web dashboard)

---

## Useful Commands

```bash
# SSH to server
ssh -i your-ssh-key ubuntu@your-server

# View logs (all services or specific)
docker compose logs -f
docker compose logs -f bot
docker compose logs -f api

# Restart all
docker compose down && docker compose up -d

# Rebuild after code changes
docker compose up -d --build

# Deploy from local
git push
ssh phoenix "cd ~/trader && git pull origin main && docker compose up -d --build"

# Web dashboard local dev (uses Bun)
cd web && bun install && bun run dev

# Run tests locally
pytest
pytest tests/test_risk.py
pytest -k "stop_loss"
```
