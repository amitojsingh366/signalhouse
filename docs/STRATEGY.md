# Trading Strategy & Technical Documentation

## Overview

Discord-based swing trading recommendation bot for TSX-listed stocks, CBOE Canada CDRs, and CAD-hedged ETFs. Designed for a Canadian TFSA account with ~$2,000 CAD portfolio. The bot provides actionable buy/sell/swap recommendations — the user executes trades manually via their brokerage (Wealthsimple, IBKR, etc.) and reports them back via Discord slash commands or screenshot uploads.

**Key characteristics:**
- Recommendation-only — no automated execution
- Swing trading with 2–7 day holding periods
- Scans ~92 symbols every 15 minutes during market hours
- Combines technical analysis with market sentiment for signal generation
- Sector-aware portfolio management with sell-to-fund suggestions

---

## Signal Generation Pipeline

Every signal flows through three stages: **technical analysis** → **sentiment adjustment** → **score conversion**. The pipeline produces a score from approximately -8 to +8, which maps to a BUY, SELL, or HOLD signal with a strength percentage.

### Stage 1: Technical Analysis (`signals.py`)

Six TA-Lib indicators are computed on 60 days of daily OHLCV bars. Each contributes a positive (bullish) or negative (bearish) score.

#### Momentum Signals (trend-following)

| Indicator | Condition | Score | Reason |
|-----------|-----------|-------|--------|
| **EMA Crossover** | 10-day EMA crosses above 30-day EMA | +2.0 | "EMA bullish crossover" |
| **EMA Crossover** | 10-day EMA crosses below 30-day EMA | -2.0 | "EMA bearish crossover" |
| **EMA Trend** | Fast EMA above slow EMA (existing uptrend) | +0.5 | "Price above slow EMA (uptrend)" |
| **EMA Trend** | Fast EMA below slow EMA (existing downtrend) | -0.5 | "Price below slow EMA (downtrend)" |
| **RSI** (14-period) | RSI < 30 (oversold) | +1.5 | "RSI oversold (X.X)" |
| **RSI** (14-period) | RSI > 70 (overbought) | -1.5 | "RSI overbought (X.X)" |
| **MACD Histogram** | Histogram crosses above zero | +1.0 | "MACD histogram turned positive" |
| **MACD Histogram** | Histogram crosses below zero | -1.0 | "MACD histogram turned negative" |

#### Mean Reversion Signals (counter-trend)

| Indicator | Condition | Score | Reason |
|-----------|-----------|-------|--------|
| **Bollinger Band** (20-period, 2σ) | Price at or below lower band | +1.5 | "Price at lower Bollinger Band (oversold)" |
| **Bollinger Band** (20-period, 2σ) | Price at or above upper band | -1.5 | "Price at upper Bollinger Band (overbought)" |

#### Volume Confirmation

| Condition | Effect | Reason |
|-----------|--------|--------|
| Volume > 1.5× 20-day average, score > 0 | +0.5 | "High volume confirms (X.Xx avg)" |
| Volume > 1.5× 20-day average, score < 0 | -0.5 | "High volume confirms (X.Xx avg)" |

**Maximum technical score: ±6.0** (all momentum + mean reversion + volume aligned).

### Stage 2: Sentiment Adjustment (`sentiment.py`)

Three sentiment sources are evaluated in parallel and added to the technical score. All use caching to respect rate limits, and all fail silently to neutral (0) if data is unavailable.

#### Analyst Consensus (per-ticker, cached 4 hours)

Fetches the latest analyst recommendation counts from yfinance (`strongBuy`, `buy`, `hold`, `sell`, `strongSell`). Computes a weighted score:

```
weighted = strongBuy×2 + buy×1 + hold×0 + sell×(-1) + strongSell×(-2)
score = weighted / (2 × total_analysts)
```

**Range: -1.0 to +1.0.** A stock with 10 Strong Buy and 2 Hold analysts scores approximately +0.83.

For CDR symbols (`.NE`), the US counterpart ticker is used for the lookup (e.g., `NVDA.NE` → `NVDA`).

#### CNN Fear & Greed Index (market-wide, cached 1 hour)

A contrarian market-wide modifier fetched via the `fear-greed` library. Converts the 0–100 index to a signal:

| Fear & Greed Value | Label | Score | Rationale |
|--------------------|-------|-------|-----------|
| < 20 | Extreme Fear | +0.5 | Contrarian buy opportunity |
| 20–39 | Fear | +0.25 | Slightly bullish contrarian signal |
| 40–60 | Neutral | 0.0 | No adjustment |
| 61–80 | Greed | -0.25 | Market heating up, be cautious |
| > 80 | Extreme Greed | -0.5 | Contrarian sell/caution signal |

**Range: -0.5 to +0.5.** This is the same for every symbol in a given scan since it's a market-wide indicator.

#### News Headline Sentiment (per-ticker, cached 30 min)

Fetches the 10 most recent news headlines from yfinance and scores them using keyword matching against two dictionaries:

- **Positive keywords** (32 words): upgrade, beat, outperform, bullish, rally, surge, growth, record, buy, overweight, boost, momentum, breakout, recovery, etc.
- **Negative keywords** (34 words): downgrade, miss, underperform, bearish, crash, plunge, decline, sell, underweight, warning, risk, layoffs, bankruptcy, fraud, etc.

Scoring: `raw = (positive_count - negative_count) / total_matched`, then clamped to ±0.5.

**Range: -0.5 to +0.5.**

#### Combined Sentiment

```
total_sentiment = analyst_score + fear_greed_score + news_score
```

**Maximum sentiment contribution: ±2.0.** This is added directly to the technical score.

### Stage 3: Score → Signal Conversion

```
total_score = technical_score + sentiment_score
strength = min(|total_score| / 8.0, 1.0)
```

| Score Range | Signal | Meaning |
|-------------|--------|---------|
| ≥ +2.0 | **BUY** | Bullish — multiple indicators aligned |
| ≤ -2.0 | **SELL** | Bearish — multiple indicators aligned |
| -2.0 to +2.0 | **HOLD** | Insufficient conviction either way |

**Strength** is a 0–100% value representing how far the score is from the maximum possible ±8. A +4.0 score yields 50% strength; +8.0 yields 100%.

### Score Display

Every signal displays its total score (e.g. `-2.5/8`) alongside the strength percentage. Each contributing factor shows its individual score contribution (e.g. `[+1.5]`, `[-0.5]`) color-coded green/red in the web UI.

### Filtering Thresholds

Not all signals are surfaced to the user:

| Signal Type | Minimum Strength | Context |
|-------------|-----------------|---------|
| BUY (universe scan) | 35% (score ≥ ~2.8) | `/recommend` and scheduled scans |
| SELL (universe scan) | 30% (score ≤ ~-2.4) | Held positions shown as sell signals, non-held shown as watchlist alerts |
| BUY (recheck/check) | None — always shown | `/check` and recheck button |

---

## Recommendation Engine (`strategy.py`)

The strategy layer sits above signal generation and adds portfolio context: sector diversification, sell-to-fund suggestions, and actionable advice per holding.

### Universe Scan (`scan_universe()`)

Runs every 15 minutes during market hours (9:30 AM – 4:00 PM ET, weekdays) and on-demand via `/recommend`:

1. Iterates all ~92 symbols in the configured universe
2. Fetches 60 days of daily bars via yfinance
3. Computes indicators and generates a signal + sentiment for each
4. Filters to BUY signals ≥ 35% strength and SELL signals ≥ 30% strength
5. Sorts by strength descending

### Top Recommendations (`get_top_recommendations()`)

Builds on `scan_universe()` to produce portfolio-aware recommendations:

1. **Buy signals**: Penalizes symbols in over-concentrated sectors (>40% of portfolio) by halving their strength — **except** when paired with a same-sector sell-to-fund (swaps don't increase sector exposure)
2. **Sell signals**: Sell signals for held stocks shown as actionable sells; sell signals for non-held stocks shown as "Watchlist Alerts" (avoid buying these)
3. **Sell-to-fund suggestions**: When cash < $50, ranks held positions by "sell desirability" and suggests which to sell to fund each buy opportunity

#### Sell-to-Fund Ranking

Each held position gets a sell desirability score:

| Factor | Score Contribution |
|--------|-------------------|
| Active SELL signal on the holding | `signal_strength × 2.0` |
| Holding in an over-concentrated sector | +0.5 |
| Holding has exceeded max hold time | +0.3 |
| HOLD signal (neutral) | +0.1 |

The highest-scoring holding is suggested as the funding source. Same-sector swaps are preferred (sell energy to buy energy) to maintain diversification balance.

#### Recommendation Caching

`get_top_recommendations()` caches its output on the Strategy instance (`_cached_recommendations`). This cache is used by `get_holding_advice()` so that `/holdings` reflects the same sell-to-fund suggestions as `/recommend`. The cache is refreshed every 15 minutes by the scheduled scan, and immediately by `/recommend`.

### Per-Holding Advice (`get_holding_advice()`)

Used by `/holdings`, `/check`, and daily briefings/recaps. For each held position:

1. **Analyze the holding** — runs full signal+sentiment analysis
2. **Find alternatives** (optional) — scans up to 15 sector peers + other universe symbols for stronger BUY signals
3. **Determine action** — one of four recommendations:

| Action | Condition | Meaning |
|--------|-----------|---------|
| **SELL** | Sell signal ≥ 30% strength, no better alternative | Exit the position |
| **SWAP** | Sell signal + better alternative found, OR cached sell-to-fund match | Sell this, buy the alternative |
| **HOLD+** | Buy signal on current holding | Keep holding or consider adding |
| **HOLD** | No strong signal either way | Continue holding |

4. **Cross-reference cache** — if individual analysis says HOLD but the last universe scan identified this holding as a sell-to-fund candidate, upgrades the advice to SWAP. This ensures consistency between `/recommend` and `/holdings`.

### Exit Alerts (`get_exit_alerts()`)

Checked every 15 minutes during the scheduled scan. Alerts are posted for:

1. **Stop loss hit** — price dropped below the trailing/hard stop (severity: high)
2. **Max hold time** — position held for 7+ days (severity: medium)
3. **Sell signal** — technical analysis generates a sell signal for a held position (severity: medium)

Alerts are checked in priority order — a stop loss hit takes precedence over a sell signal for the same position.

### Daily Insights (`get_daily_insights()`)

Used by the 8:30 AM morning briefing and 10 PM evening recap. Generates a comprehensive market overview:

- Each holding with full signal analysis, action recommendation, and alternatives
- Pre-market movers (US counterparts for CDR positions)
- Notable movers in the tracked universe (non-held stocks with >2% daily move)
- Sector exposure breakdown
- Portfolio value, cash, and P&L summary

---

## Position Sizing (ATR-Based)

When the bot recommends a buy, position sizing is calculated using the 14-period Average True Range:

```
risk_per_trade = portfolio_value × 2%
shares = risk_per_trade / (2 × ATR)
```

Constrained by:
- **Max position size**: 50% of total portfolio value
- **Minimum**: 1 share if affordable

**Example**: $2,000 portfolio, stock at $50, ATR = $1.50
- Risk amount: $2,000 × 0.02 = $40
- Shares via ATR: $40 / (2 × $1.50) = 13 shares ($650 position, 32.5% of portfolio)

---

## Risk Management

### Per-Position Stops

| Stop Type | Threshold | Behavior |
|-----------|-----------|----------|
| **Hard stop loss** | 5% below entry price | Set on entry, never moves down |
| **Trailing stop** | 3% below highest price since entry | Ratchets up as price rises, never moves down |

The trailing stop starts at the hard stop level and climbs as the position gains. If the stock rises 10% then retraces 3% from its peak, the trailing stop triggers.

### Portfolio-Level Circuit Breakers

| Rule | Threshold | Effect |
|------|-----------|--------|
| **Daily drawdown** | 8% loss from day's opening value | Halt all trading recommendations |
| **Total drawdown** | 20% loss from peak portfolio value | Halt all trading until manual reset |

When halted, the bot stops generating buy recommendations but continues monitoring positions and posting alerts.

### Position Limits

| Limit | Value |
|-------|-------|
| Max simultaneous positions | 2 |
| Max portfolio % in one position | 50% |
| Max portfolio % in one sector | 40% |
| Holding period | 2–7 days (alerts after 7) |

---

## Sector Diversification

The universe of ~92 symbols is organized into 12 sectors:

| Sector | Count | Examples |
|--------|-------|---------|
| Technology | 21 | NVDA.NE, SHOP.TO, MSFT.NE |
| Financials | 10 | RY.TO, TD.TO, V.NE |
| Energy | 7 | SU.TO, ENB.TO, XOM.NE |
| Industrials | 8 | CNR.TO, CP.TO, CAT.NE |
| Consumer | 11 | ATD.TO, DOL.TO, COST.NE |
| Materials | 7 | AEM.TO, ABX.TO, NTR.TO |
| Healthcare | 5 | JNJ.NE, LLY.NE, UNH.NE |
| Aerospace & Defense | 4 | LMT.NE, BA.NE, CAE.TO |
| Telecom | 3 | T.TO, BCE.TO, RCI-B.TO |
| Utilities | 4 | FTS.TO, H.TO, NEE.NE |
| Real Estate | 4 | BAM.TO, REI-UN.TO, CAR-UN.TO |
| Crypto | 3 | IBIT.NE, BTCX-B.TO, ETHX-B.TO |
| ETFs | 5 | XSP.TO, ZQQ.TO, XQQ.TO |

The 40% sector cap prevents over-concentration. Buy signals in an already-concentrated sector are demoted (strength halved) but still shown — unless they are paired with a same-sector sell-to-fund (swaps don't change net sector exposure).

---

## Market Data (`market_data.py`)

### Data Source

All market data comes from **yfinance** (free, ~15 minute delay). This is adequate for daily-bar swing trading signals.

### Symbol Resolution

| Suffix | Exchange | yfinance Behavior |
|--------|----------|-------------------|
| `.TO` | Toronto Stock Exchange | Direct lookup |
| `.NE` | CBOE Canada (CDRs) | Try as-is first, fall back to US counterpart |
| None | US exchanges | Direct lookup |

CDRs (Canadian Depositary Receipts) on `.NE` trade at prices proportional to their US counterparts. When `.NE` data is unavailable in yfinance, the bot falls back to the US ticker for price history and signal computation.

### Pre-Market Data

At 8:00 AM ET on weekdays, the bot fetches `preMarketPrice` from yfinance `.info` for all US counterparts of CDR symbols. Moves >2% are reported to help anticipate CDR price action at market open.

### Batch Fetching

For portfolio display, prices are fetched via `yfinance.download()` in a single batch call for efficiency. Any symbols that fail in the batch are retried individually.

---

## Screenshot Parsing (`vision.py`)

The `/upload` command parses brokerage screenshots using Claude's vision API:

1. User attaches an image to the `/upload` command
2. Image bytes are base64-encoded and sent to Claude Sonnet with a structured extraction prompt
3. Claude returns a JSON array: `[{symbol, quantity, market_value_cad}, ...]`
4. Each bare ticker is resolved to its exchange suffix (`.TO` → `.NE` → US)
5. User sees parsed results in a confirmation embed with Confirm/Edit/Cancel buttons
6. Edit opens a dropdown select to modify individual holdings before confirming

Works with any brokerage screenshot (Wealthsimple, Questrade, IBKR, etc.) — Claude handles layout differences.

---

## Scheduled Tasks (`cogs/tasks.py`)

| Task | Schedule | Description |
|------|----------|-------------|
| **Market scan** | Every 15 min, market hours only | Exit alerts for holdings + top buy/sell signals |
| **Pre-market movers** | 8:00 AM ET, weekdays | US premarket moves for CDR counterparts |
| **Morning briefing** | 8:30 AM ET, weekdays | Full portfolio analysis + market overview |
| **Daily status** | 3:50 PM ET, weekdays | Portfolio value, P&L, daily snapshot saved |
| **Evening recap** | 10:00 PM PT, weekdays | Full portfolio analysis + market overview |

---

## Discord Interaction Model

### Slash Commands

| Command | Description |
|---------|-------------|
| `/buy <symbol> <quantity> <price>` | Record a buy trade |
| `/sell <symbol> <quantity> <price>` | Record a sell trade |
| `/upload <image>` | Parse brokerage screenshot, confirm and sync holdings |
| `/holdings` | View portfolio with live prices, per-holding advice, and edit button |
| `/pnl` | Daily + total P&L breakdown with recent trades |
| `/recommend` | On-demand universe scan with buy/sell/swap recommendations |
| `/check <symbol>` | Signal + sentiment for any symbol, with autocomplete for held positions |
| `/status` | Bot uptime, tracked symbols, market hours |

### Interactive Components

- **Recheck button**: Every signal embed gets a persistent "Recheck Signal" button that re-runs analysis on click. Survives bot restarts via `custom_id`.
- **Edit dropdown**: `/holdings` Edit button opens a dropdown select to pick which holding to edit, then a modal for the fields. Same pattern for `/upload` edit flow.
- **Confirmation view**: `/upload` parsed results show Confirm/Edit/Cancel buttons.

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Language | Python 3.11 | Trading ecosystem compatibility |
| Bot Framework | `discord.py` ≥ 2.3 | Slash commands, views, persistent buttons |
| Market Data | `yfinance` ≥ 0.2.36 | Price history, analyst data, news headlines |
| Technical Analysis | `TA-Lib` (C library + Python bindings) | EMA, RSI, MACD, Bollinger Bands, ATR |
| Sentiment | `yfinance` + `fear-greed` | Analyst consensus, Fear & Greed Index, news |
| Screenshot Parsing | `anthropic` SDK + Claude Sonnet | Vision API for brokerage screenshot extraction |
| Data Processing | `pandas`, `numpy` | Price data manipulation and indicator DataFrames |
| Configuration | `PyYAML` | Layered config (settings.yaml + settings.local.yaml) |
| Persistence | PostgreSQL 16 | Holdings, trades, snapshots, portfolio meta, signal history |
| Web Dashboard | Next.js 14, Bun, Tailwind CSS, Recharts | App Router, standalone Docker output |
| Containerization | Docker Compose (5 services) | postgres, api, bot, web, caddy |
| Testing | `pytest` + `pytest-asyncio` | Unit tests for signals and risk management |
| Linting | `ruff` | Fast Python linter and formatter |
| Type Checking | `mypy` (strict mode) | Static type analysis |

---

## Architecture

```
                          Discord
                            │
                   ┌────────┴────────┐
                   │   TraderBot     │  (bot.py)
                   │  discord.Bot    │
                   └───────┬────────┘
                           │ loads
            ┌──────────────┼──────────────┐
            │              │              │
     ┌──────┴──────┐ ┌────┴────┐ ┌──────┴──────┐
     │    Cogs     │ │ Strategy│ │  Portfolio  │
     │ (commands,  │ │ (recs,  │ │ (holdings,  │
     │  tasks)     │ │ advice) │ │  trades)    │
     └──────┬──────┘ └────┬────┘ └──────┬──────┘
            │              │              │
            │        ┌─────┴─────┐        │
            │        │           │        │
     ┌──────┴──┐ ┌───┴───┐ ┌───┴────┐ ┌─┴──────┐
     │ Signals │ │Market │ │Sentim- │ │  Risk  │
     │  (TA)   │ │ Data  │ │  ent   │ │Manager │
     └─────────┘ └───┬───┘ └───┬────┘ └────────┘
                     │         │
                  yfinance  yfinance + fear-greed
```

**Data flow for a scheduled scan:**
1. `cogs/tasks.py` fires every 15 min → calls `strategy.get_top_recommendations()`
2. Strategy calls `scan_universe()` → iterates all symbols
3. For each symbol: `market_data.get_historical_data()` → 60 days of daily bars via yfinance
4. `signals.compute_indicators()` → TA-Lib computes EMA, RSI, MACD, Bollinger Bands, ATR
5. `sentiment.analyze()` → parallel fetch of analyst consensus, Fear & Greed, news headlines
6. `signals.generate_signal()` → combines technical score + sentiment → BUY/SELL/HOLD + strength
7. Strategy filters, ranks, adds sector context, generates sell-to-fund suggestions
8. Results cached for cross-command consistency
9. Bot posts top signals as embeds with recheck buttons

---

## Deployment

- **Server**: `your-server` (Ubuntu ARM, your server)
- **Containers**: Docker Compose with 5 services (postgres, api, bot, web, caddy)
- **Persistence**: PostgreSQL 16 with persistent volume
- **Secrets**: `.env` file on server (DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID, DISCORD_GUILD_ID, ANTHROPIC_API_KEY)
- **Deploy workflow**: `git push` → SSH → `git pull && docker compose up -d --build`

---

## Key Constraints

1. **No auto-execution** — IBKR no longer allows Canadian securities via API. All trades are manual.
2. **Commission drag** — With ~$2,000 capital, each round-trip trade costs ~0.1%. High-frequency strategies are not viable.
3. **Data delay** — yfinance provides ~15 min delayed data. Acceptable for daily-bar swing trading, not suitable for intraday strategies.
4. **Sentiment limitations** — Analyst consensus updates infrequently. News keyword matching is simplistic (no NLP). Fear & Greed is a single market-wide number. These are directional nudges, not precision instruments.
5. **CDR data gaps** — Some `.NE` symbols have spotty data in yfinance. The US fallback mitigates this but means signals may be based on USD prices rather than actual CDR prices.
6. **Risk hard limits** — 8% daily drawdown or 20% total drawdown halts all trading recommendations until manual reset.
