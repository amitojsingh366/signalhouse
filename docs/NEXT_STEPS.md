# Next Steps

## Current Status (March 18, 2026)

The bot is deployed and running on the Ubuntu server (`your-server`). IB Gateway is connected to IBKR paper trading account `DUP468689`. The bot scans every 15 minutes during market hours (9:30 AM - 4:00 PM ET).

---

## Phase 1: Validate on Paper (Weeks 1-2)

### 1.1 Monitor Paper Trading
- [ ] Watch Discord notifications for the first few trading days
- [ ] Check that buy/sell orders execute correctly in paper mode
- [ ] Verify daily status messages arrive at ~3:50 PM ET
- [ ] Review logs: `ssh ubuntu@your-server "cd ~/trader && docker compose logs -f trader"`

### 1.2 Run Backtests
- [ ] Run the backtester on all 30 symbols with 6-12 months of historical data
- [ ] Analyze win rate, average win/loss, max drawdown per symbol
- [ ] Identify which symbols the strategy works best on
- [ ] Trim the universe to the top 10-15 performers

### 1.3 Tune Parameters
Based on backtest results, consider adjusting:
- [ ] EMA periods (currently 10/30) — try 8/21 for faster signals
- [ ] RSI thresholds (currently 30/70) — try 25/75 for fewer but higher-quality signals
- [ ] Signal strength threshold (currently 0.4 for buy) — increase to 0.5 for fewer trades
- [ ] Stop loss (currently 5%) — may be too wide for small positions
- [ ] Trailing stop (currently 3%) — may be too tight, causing premature exits

---

## Phase 2: Improve the Strategy (Weeks 2-4)

### 2.1 Add More Signal Factors
- [ ] **VWAP**: Volume-weighted average price as intraday support/resistance
- [ ] **ADX**: Average Directional Index to filter out choppy/sideways markets (only trade when ADX > 20)
- [ ] **Sector rotation**: Track sector ETFs and bias toward outperforming sectors
- [ ] **Earnings calendar**: Avoid entering positions before earnings announcements

### 2.2 Improve Position Management
- [ ] **Partial exits**: Sell half at first target (e.g., 2% gain), let rest ride with trailing stop
- [ ] **Re-entry logic**: If stopped out and signal is still strong, consider re-entering
- [ ] **Correlation filter**: Don't hold two highly correlated positions (e.g., RY + TD)

### 2.3 Add Market Regime Detection
- [ ] Use VIX (or Canadian equivalent) to detect high-volatility regimes
- [ ] Reduce position sizes or pause trading in extreme volatility
- [ ] Use 200-day moving average on XIU.TO (TSX index) as bull/bear filter

---

## Phase 3: Go Live (Week 4+)

### 3.1 Pre-Live Checklist
- [ ] Paper trading for at least 2 weeks with positive results
- [ ] Backtests show positive expectancy after commissions
- [ ] All Discord alerts working correctly
- [ ] Drawdown circuit breakers tested (manually trigger in paper)
- [ ] Understand IBKR commission structure for your account

### 3.2 Switch to Live
1. Update `.env` on the server:
   ```
   TRADING_MODE=live
   ```
2. Update `config/settings.yaml`:
   ```yaml
   broker:
     port: 4001  # Live port
   ```
3. Restart: `docker compose down && docker compose up -d`
4. Start with half the universe (15 symbols) to limit risk
5. Monitor closely for the first week

### 3.3 Scale Up
- [ ] After 1 month of profitable live trading, consider adding more capital
- [ ] With $5,000+, commission drag drops from 0.2% to 0.04% per round trip
- [ ] Can increase max_positions from 2 to 3-4
- [ ] Can diversify into US-listed ETFs (requires currency conversion consideration)

---

## Phase 4: Advanced Features (Ongoing)

- [ ] **Web dashboard**: Simple Flask/FastAPI app showing portfolio, recent trades, equity curve
- [ ] **Database**: Store trade history in SQLite/Postgres instead of just logs
- [ ] **Multi-strategy**: Add a separate mean-reversion-only strategy that runs alongside momentum
- [ ] **ML signals**: Train a simple model (e.g., gradient boosting) on historical indicator data to predict next-day returns
- [ ] **Options strategies**: Covered calls on held positions to generate additional income (requires options permissions at IBKR)
- [ ] **Alerting improvements**: Telegram bot as backup to Discord, email alerts for critical errors

---

## Useful Commands

```bash
# SSH to server
ssh -i your-ssh-key ubuntu@your-server

# View bot logs
docker compose logs -f trader

# View IB Gateway logs
docker compose logs -f ib-gateway

# Restart everything
docker compose down && docker compose up -d

# Rebuild after code changes
docker compose up -d --build trader

# VNC to IB Gateway (view the GUI)
# SSH tunnel: ssh -L 5900:localhost:5900 ubuntu@your-server
# Then connect VNC viewer to localhost:5900 (password: trader)

# Run backtest locally
python -c "
from trader.backtest import run_backtest, print_backtest_report
# ... (need historical data)
"

# Check paper trading account
# Login at ibkr.com with paper trading credentials
```

---

## Deploying Code Changes

The server has a copy of the repo at `~/trader/`. To deploy changes:

```bash
# Option 1: Push to git and pull on server
git push
ssh ubuntu@your-server "cd ~/trader && git pull && docker compose up -d --build trader"

# Option 2: Direct scp
scp -i your-ssh-key -r src/ ubuntu@your-server:~/trader/src/
ssh ubuntu@your-server "cd ~/trader && docker compose up -d --build trader"
```
