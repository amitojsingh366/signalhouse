# Trading Strategy

Swing trading recommendation system for TSX-listed stocks, CBOE Canada CDRs, and CAD-hedged ETFs. Designed for Canadian TFSA accounts of any size, targeting safe aggressive growth with 2-7 day holding periods. Scans ~333 symbols every 15 minutes during market hours.

**This is recommendation-only** — no automated execution. The user trades manually via their brokerage (Wealthsimple, IBKR, etc.) and reports trades back.

---

## Signal Generation Pipeline

Every signal flows through four stages: **technical analysis** → **sentiment adjustment** → **commodity correlation** → **score conversion**. The pipeline produces a score from approximately -9 to +9, which maps to a BUY, SELL, or HOLD signal with a strength percentage.

### Stage 1: Technical Analysis (`services/signals.py`)

Six TA-Lib indicators computed on 60 days of daily OHLCV bars. Maximum technical score: **±6.0**.

#### Momentum Signals

| Indicator | Condition | Score |
|-----------|-----------|-------|
| **EMA Crossover** (10/30) | 10-day crosses above 30-day | +2.0 |
| **EMA Crossover** (10/30) | 10-day crosses below 30-day | -2.0 |
| **EMA Trend** | Fast above slow (uptrend) | +0.5 |
| **EMA Trend** | Fast below slow (downtrend) | -0.5 |
| **RSI** (14-period) | RSI < 30 (oversold) | +1.5 |
| **RSI** (14-period) | RSI > 70 (overbought) | -1.5 |
| **MACD Histogram** | Crosses above zero | +1.0 |
| **MACD Histogram** | Crosses below zero | -1.0 |
| **MACD Histogram** | Persistently positive (both bars > 0) | +0.5 |
| **MACD Histogram** | Persistently negative (both bars < 0) | -0.5 |

#### Mean Reversion

| Indicator | Condition | Score |
|-----------|-----------|-------|
| **Bollinger Band** (20-period, 2σ) | Price at/below lower band | +1.5 |
| **Bollinger Band** (20-period, 2σ) | Price at/above upper band | -1.5 |

#### Volume Confirmation

| Condition | Score |
|-----------|-------|
| Volume > 1.5× 20-day average, existing score > 0 | +0.5 |
| Volume > 1.5× 20-day average, existing score < 0 | -0.5 |

### Stage 2: Sentiment Adjustment (`services/sentiment.py`)

Three sources, all fail silently to 0. Maximum contribution: **±2.0**.

#### Analyst Consensus (per-ticker, cached 4h)

Fetches recommendation counts from yfinance. Weighted score:
```
weighted = strongBuy×2 + buy×1 + hold×0 + sell×(-1) + strongSell×(-2)
score = weighted / (2 × total_analysts)
```
Range: **-1.0 to +1.0**. For CDR symbols (`.NE`), uses the US counterpart ticker.

#### CNN Fear & Greed Index (market-wide, cached 1h)

Contrarian modifier via the `fear-greed` library:

| Value | Label | Score |
|-------|-------|-------|
| < 20 | Extreme Fear | +0.5 (contrarian buy) |
| 20–39 | Fear | +0.25 |
| 40–60 | Neutral | 0.0 |
| 61–80 | Greed | -0.25 |
| > 80 | Extreme Greed | -0.5 (contrarian sell) |

#### News Headline Sentiment (per-ticker, cached 30min)

Scores 10 most recent yfinance headlines via keyword matching (32 positive, 37 negative words). Range: **-0.5 to +0.5**.

### Stage 3: Commodity Correlation (`services/commodity.py`)

Live commodity/crypto futures trade nearly 24/7. Their moves are used to boost/dampen signals for correlated Canadian-listed assets.

#### Tracked Commodities

| Ticker | Name | Key Correlated Assets |
|--------|------|----------------------|
| GC=F | Gold (COMEX) | Gold miners (AEM, ABX, FNV, K), gold ETFs (ZGLD, CGL, KILO, HUG) |
| CL=F | Crude Oil (WTI) | Oil producers (SU, CNQ, CVE, IMO), energy ETFs (XEG), pipelines |
| NG=F | Natural Gas | Gas producers (TOU, PEY, CR, BIR), natgas ETFs (HUN) |
| SI=F | Silver (COMEX) | Silver miners (PAAS), silver ETFs (HUZ, VALT) |
| BTC-USD | Bitcoin | Bitcoin ETFs (BTCC-B, BTCX-B, FBTC, IBIT), crypto-adjacent (HUT, COIN) |
| ETH-USD | Ethereum | Ether ETFs (ETHX-B, ETHH) |
| SOL-USD | Solana | Solana ETFs (SOLQ, SOLX, SOLA) |

#### Correlation Weights

Two levels of mapping:
1. **Per-symbol overrides** (64 symbols) — tight correlations: gold miners 0.80–0.95, oil producers 0.70–0.90, crypto ETFs 0.90–0.95
2. **Sector-level defaults** — broader correlations: energy↔oil 0.8, materials↔gold 0.7

**Inverse ETFs** use negative weights (e.g., HBD.TO = -0.95 for gold), naturally flipping the signal.

#### Score Calculation

```
raw_adjustment = commodity_pct_change × weight × 15.0
```

| Caps | Normal Moves | Extreme Moves (≥5%) |
|------|-------------|---------------------|
| Per commodity | ±0.5 | ±1.0 |
| Total across all | ±1.0 | ±1.0 |

Moves below 0.5% are ignored. Prices cached 5 minutes.

The 5% threshold for extreme moves was chosen because moves that large are almost always driven by real catalysts (geopolitical events, supply shocks) that hold through to market open.

### Stage 4: Score → Signal Conversion

```
total_score = technical_score + sentiment_score + commodity_score
strength = min(|total_score| / 9.0, 1.0)
```

| Score Range | Signal |
|-------------|--------|
| ≥ +2.0 | **BUY** |
| ≤ -2.0 | **SELL** |
| -2.0 to +2.0 | **HOLD** |

#### Filtering Thresholds

| Signal Type | Minimum Strength | Context |
|-------------|-----------------|---------|
| BUY (universe scan) | 35% (score ≥ ~2.8) | Recommendations and scheduled scans |
| SELL (universe scan) | 30% (score ≤ ~-2.4) | Held → sell signals, non-held → watchlist alerts |
| BUY/SELL (single check) | None | On-demand symbol lookup |

#### Score Display

Every signal shows its total score (e.g. `-2.5/9`, max ±9). Each factor shows its contribution (`[+1.5]`, `[-0.5]`) color-coded green/red in all clients (web, iOS, Discord).

#### Why Sells Are Less Frequent Than Buys

The indicator set is oriented toward catching **overbought reversals** (RSI > 70 + BB upper + bearish EMA) rather than scoring sustained downtrends. A stock already in a downtrend will show: EMA downtrend (−0.5) + MACD persistently negative (−0.5) + possibly BB lower (+1.5 mean-reversion!) = net near zero. This is intentional — the system avoids selling into oversold dips. Strong sell signals require multiple overbought indicators agreeing simultaneously.

---

## Recommendation Engine (`services/strategy.py`)

### Universe Scan

Runs every 15 minutes during market hours and on-demand when a user requests recommendations:
1. Scans all ~333 symbols (20 concurrent via asyncio semaphore)
2. Filters to BUY ≥ 35% and SELL ≥ 30% strength
3. Sorts by strength descending

### Sector Resolution

`get_sector()` resolves a symbol's sector by trying alternate exchange suffixes. If `MSFT.TO` isn't in the universe, it checks `MSFT.NE` and bare `MSFT`. This means holdings on any exchange (TSX `.TO`, CBOE Canada `.NE`, US bare) map to the correct sector without duplicating config entries.

### Top Recommendations

Adds portfolio context:
1. **Sector penalty** — Symbols in over-concentrated sectors (>40%) get strength halved — **except** same-sector swaps (which don't increase exposure)
2. **Sell signals** — Held positions shown as sells; non-held shown as "Watchlist Alerts"
3. **Sell-to-fund** — When cash < $50, suggests which holding to sell to fund each buy

#### Sell-to-Fund Ranking

Each held position gets a sell desirability score:

| Factor | Score |
|--------|-------|
| Active SELL signal | `strength × 2.0` |
| Over-concentrated sector | +0.5 |
| Exceeded max hold time | +0.3 |
| HOLD signal (neutral) | +0.2 (0.1 × 2.0) |

Same-sector swaps are preferred to maintain diversification.

#### Caching

`get_top_recommendations()` caches results. `get_holding_advice()` cross-references the cache so the holdings view shows the same SWAP suggestions as the recommendations view. Refreshed every 15 min (scheduled scan) and on-demand when recommendations are requested.

### Per-Holding Advice

For each held position:
1. Run full signal + sentiment analysis
2. Find alternatives (up to 15 sector peers + universe symbols)
3. Determine action:

| Action | Condition |
|--------|-----------|
| **SELL** | Sell signal ≥ 30%, no better alternative |
| **SWAP** | Sell signal + better alternative, OR cached sell-to-fund match |
| **HOLD+** | Buy signal on current holding |
| **HOLD** | No strong signal |

### Exit Alerts

Checked every 15 minutes for held positions only (priority order):
1. **Stop loss hit** — price below trailing/hard stop (high severity, urgent)
2. **Take profit** — gain ≥ 8% from entry (high severity, urgent) — lock in winners
3. **Max hold time** — held 7+ days (medium severity)
4. **Sell signal** — technical SELL (≥ 30% strength) for a held position (medium severity)
5. **Momentum lost** — signal weakened to HOLD while position is at a loss (low severity)

Exit alerts use 60 days of price history (same as universe scan) to ensure all indicators have enough data.

### Action Plan

The system generates a prioritized, position-sized action plan that tells you exactly what trades to execute:

1. **Sells first** — stop losses, profit-taking, time exits (urgent actions)
2. **Swaps** — replace weak holdings with stronger opportunities
3. **Buys** — new positions only if under max position count and have cash

Every action includes exact share count, price, and dollar amount. New buys are limited by `max_positions` (5) — the system won't recommend accumulating positions indefinitely.

---

## Position Sizing (ATR-Based)

```
risk_per_trade = portfolio_value × 2%
shares = risk_per_trade / (2 × ATR)
```

Constrained by max position size (50% of portfolio) and minimum 1 share.

**Example**: $10,000 portfolio, stock at $50, ATR = $1.50 → risk = $200 → 66 shares ($3,300, 33%)

---

## Risk Management

### Per-Position Stops

| Stop Type | Threshold | Behavior |
|-----------|-----------|----------|
| **Hard stop** | 5% below entry | Set on entry, never moves down |
| **Trailing stop** | 3% below peak | Ratchets up, never moves down |
| **Tightened trail** | 1.5% below peak (when gain ≥ 5%) | Automatically tightens to protect profits |
| **Take profit** | 8% above entry | Full sell — lock in gains |

### Portfolio Circuit Breakers

| Rule | Threshold | Effect |
|------|-----------|--------|
| Daily drawdown | 8% from day's open | Halt recommendations |
| Total drawdown | 20% from peak | Halt until manual reset |

### Position Limits

| Limit | Value |
|-------|-------|
| Max simultaneous positions | 5 |
| Max % in one position | 30% |
| Max % in one sector | 40% |
| Holding period | 2–7 days (alerts after 7) |

---

## Symbol Universe

~333 securities across 21 sectors configured in `config/settings.yaml`:

| Sector | Count | Examples |
|--------|-------|---------|
| Technology | 41 | NVDA.NE, SHOP.TO, PLTR.NE, UBER.NE |
| Financials | 28 | RY.TO, TD.TO, V.NE, BRK.NE |
| Broad Market ETFs | 27 | XSP.TO, ZQQ.TO, VFV.TO, XIU.TO |
| Consumer | 25 | ATD.TO, DOL.TO, COST.NE, LULU.NE |
| Energy | 24 | SU.TO, CNQ.TO, TOU.TO, XEG.TO |
| Materials | 21 | AEM.TO, ABX.TO, WPM.TO, CCO.TO |
| Real Estate | 19 | BAM.TO, REI-UN.TO, GRT-UN.TO |
| Industrials | 18 | CNR.TO, CP.TO, WSP.TO, GE.NE |
| Crypto | 15 | BTCC-B.TO, ETHX-B.TO, SOLQ.TO, HUT.TO |
| Utilities | 14 | FTS.TO, H.TO, EMA.TO, NEE.NE |
| Healthcare | 14 | JNJ.NE, LLY.NE, AMGN.NE, WELL.TO |
| Leveraged/Inverse ETFs | 14 | HQU.TO, HQD.TO, HSU.TO |
| Covered Call ETFs | 12 | ZWC.TO, ZWB.TO, HDIV.TO |
| Dividend ETFs | 10 | XDV.TO, VDY.TO, CDZ.TO |
| Gold/Commodities ETFs | 10 | ZGLD.TO, CGL.TO, HUC.TO |
| Thematic ETFs | 10 | HCLN.TO, ZEB.TO, XMV.TO |
| All-in-One ETFs | 9 | VEQT.TO, XEQT.TO, VGRO.TO |
| Bond ETFs | 8 | ZAG.TO, XBB.TO, VAB.TO |
| Cannabis | 6 | WEED.TO, TLRY.TO, ACB.TO |
| Aerospace & Defense | 4 | LMT.NE, BA.NE, RTX.NE, CAE.TO |
| Telecom | 4 | T.TO, BCE.TO, RCI-B.TO |

Symbols ending in `.TO` are TSX-listed; `.NE` are CDRs on CBOE Canada. CDR data falls back to US counterpart via yfinance when `.NE` data is unavailable.

### Market Data

- **Source:** yfinance (free, ~15 min delay)
- `.TO` symbols work directly; `.NE` CDRs fall back to US ticker
- Pre-market data from US tickers for CDR counterparts (8:00 AM ET)
- Batch price fetching via `yfinance.download()` for portfolio display

### Symbol Resolution

Bare tickers are resolved in order: `.TO` → `.NE` → US exchange.
