"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowLeftRight,
  ArrowRight,
  BellOff,
  Briefcase,
  Check,
  Download,
  TrendingDown,
  Upload,
  Wallet,
  Zap,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import {
  queryKeys,
  useActionPlan,
  useHoldings,
  useHoldingsSpark,
  usePnl,
  useRunScanNow,
  useSnapshots,
  useStatus,
  useTickerStrip,
} from "@/lib/hooks";
import type { ActionItem, HoldingAdvice, TickerStripItem } from "@/lib/api";
import { cn, formatCurrency, formatPercent } from "@/lib/utils";
import { usePrivacy } from "@/lib/privacy";
import { EquityChart } from "@/components/ui/equity-chart";
import { ChartSkeleton, SignalsSkeleton } from "@/components/ui/loading";
import { TrendProxy } from "@/components/ui/trend-proxy";
import { buildTradeIntentHref } from "@/lib/trade-intent";

const RANGES = ["1D", "7D", "1M", "3M", "1Y", "ALL"] as const;

interface SectorRow {
  name: string;
  pct: number;
  value: number;
}

function tickerTimeEt(): string {
  return new Intl.DateTimeFormat("en-CA", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "America/Toronto",
  }).format(new Date());
}

function formatLastScanLabel(lastScanAt: string | null | undefined): string {
  if (!lastScanAt) return "awaiting first scan";
  const parsed = Date.parse(lastScanAt);
  if (Number.isNaN(parsed)) return "recently";

  const diffMs = Date.now() - parsed;
  if (diffMs <= 60_000) return "just now";

  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 60) return `${minutes} min ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;

  return new Intl.DateTimeFormat("en-CA", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(parsed));
}

function actionScore(action: ActionItem): number {
  if (typeof action.score === "number") return action.score;
  if (action.type === "BUY" && typeof action.strength === "number") return action.strength * 9;
  return 0;
}

function actionSymbol(action: ActionItem): string {
  if (action.type === "SWAP") return `${action.sell_symbol ?? "-"} -> ${action.buy_symbol ?? "-"}`;
  return action.symbol ?? "-";
}

function actionPrice(action: ActionItem): number | null {
  if (action.type === "SWAP") return action.sell_price ?? null;
  return action.price ?? null;
}

function actionDelta(action: ActionItem): number | null {
  if (action.type === "SELL") return action.pnl_pct ?? null;
  if (action.type === "SWAP") return action.sell_pnl_pct ?? null;
  return null;
}

function signalBadgeForAction(action: ActionItem): { cls: string; text: string } {
  if (action.type === "SELL") {
    if (action.urgency === "urgent") return { cls: "pb-urgent", text: "URGENT" };
    return { cls: "pb-sell", text: "SELL" };
  }
  if (action.type === "SWAP") return { cls: "pb-swap", text: "SWAP" };

  const actionable = action.actionable !== false;
  if (!actionable) return { cls: "pb-hold", text: "HOLD" };
  if (typeof action.strength === "number") {
    return { cls: "pb-buy", text: `BUY ${(action.strength * 100).toFixed(0)}%` };
  }
  return { cls: "pb-buy", text: "BUY" };
}

function signalBadgeForHolding(holding: HoldingAdvice): { cls: string; text: string } {
  const sig = holding.signal.toUpperCase();
  if (sig === "BUY") return { cls: "pb-buy", text: `BUY ${(holding.strength * 100).toFixed(0)}%` };
  if (sig === "SELL") {
    if (holding.action.toUpperCase().includes("URGENT")) return { cls: "pb-urgent", text: "URGENT" };
    return { cls: "pb-sell", text: "SELL" };
  }
  return { cls: "pb-hold", text: "HOLD" };
}

function parseReason(reason: string): { label: string; score: number | null } {
  const match = reason.match(/\[([+-]?\d+(?:\.\d+)?)\]$/);
  if (!match) return { label: reason, score: null };
  return {
    label: reason.slice(0, reason.lastIndexOf("[")).trim(),
    score: Number.parseFloat(match[1]),
  };
}

function HeroSpark() {
  return (
    <svg className="spark" viewBox="0 0 620 70" fill="none" preserveAspectRatio="none" aria-hidden>
      <defs>
        <linearGradient id="heroSparkFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#a78bfa" stopOpacity="0.30" />
          <stop offset="100%" stopColor="#a78bfa" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path
        d="M0 62 C35 61, 72 57, 108 58 C140 59, 172 47, 206 46 C241 45, 274 49, 310 40 C348 31, 386 30, 420 24 C455 18, 490 20, 524 13 C558 6, 589 4, 620 2 L620 70 L0 70 Z"
        fill="url(#heroSparkFill)"
      />
      <path
        d="M0 62 C35 61, 72 57, 108 58 C140 59, 172 47, 206 46 C241 45, 274 49, 310 40 C348 31, 386 30, 420 24 C455 18, 490 20, 524 13 C558 6, 589 4, 620 2"
        stroke="#a78bfa"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}

function TickerStrip({ items }: { items: TickerStripItem[] }) {
  const doubled = [...items, ...items];
  return (
    <div className="ticker">
      <div className="track">
        {doubled.map((item, i) => (
          <span key={`${item.symbol}-${i}`} className="t-item">
            <span className="s">{item.label}</span>
            <span className="p">{item.display_price}</span>
            <span
              className={cn(
                "d",
                item.change_pct == null ? "" : item.change_pct >= 0 ? "pos" : "neg"
              )}
            >
              {item.change_label ?? (item.change_pct == null ? "--" : formatPercent(item.change_pct))}
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}

function toSectorRows(
  sectorExposure: Record<string, unknown> | undefined,
  investedValue: number
): SectorRow[] {
  if (!sectorExposure) return [];

  const rows: SectorRow[] = [];
  for (const [name, raw] of Object.entries(sectorExposure)) {
    if (typeof raw === "number") {
      if (raw <= 1) {
        rows.push({ name, pct: raw * 100, value: investedValue * raw });
      } else if (raw <= 100) {
        rows.push({ name, pct: raw, value: investedValue * (raw / 100) });
      } else {
        const pct = investedValue > 0 ? (raw / investedValue) * 100 : 0;
        rows.push({ name, pct, value: raw });
      }
      continue;
    }

    if (raw && typeof raw === "object") {
      const obj = raw as Record<string, unknown>;
      const pctRaw = typeof obj.pct === "number" ? obj.pct : typeof obj.percent === "number" ? obj.percent : null;
      const valRaw = typeof obj.value === "number" ? obj.value : typeof obj.amount === "number" ? obj.amount : null;

      let pct = pctRaw ?? 0;
      if (pct <= 1) pct *= 100;
      const value = valRaw ?? investedValue * (pct / 100);

      rows.push({ name, pct, value });
    }
  }

  return rows
    .filter((row) => Number.isFinite(row.pct) && row.pct > 0)
    .sort((a, b) => b.pct - a.pct);
}

export default function DashboardPage() {
  const qc = useQueryClient();
  const { data: portfolio, isLoading: portfolioLoading } = useHoldings();
  const { data: pnl, isLoading: pnlLoading } = usePnl();
  const { data: snapshots, isLoading: snapshotsLoading } = useSnapshots();
  const { data: status } = useStatus();
  const { data: plan, isLoading: planLoading, isFetching: refreshing } = useActionPlan();
  const { data: tickerItems } = useTickerStrip();
  const { data: sparkData } = useHoldingsSpark(7);
  const { mutateAsync: runScanNowMutateAsync, isPending: scanNowPending } = useRunScanNow();
  const { mask } = usePrivacy();

  const [range, setRange] = useState<(typeof RANGES)[number]>("1M");
  const [updatedEt, setUpdatedEt] = useState("--:--");
  const [snoozing, setSnoozing] = useState(false);

  const chartsLoading = snapshotsLoading || planLoading;
  const portfolioValue = portfolio?.total_value ?? 0;
  const dailyPnl = pnl?.daily_pnl ?? 0;
  const dailyPnlPct = pnl?.daily_pnl_pct ?? 0;
  const lifetimePnl = pnl?.total_pnl ?? portfolio?.total_pnl ?? 0;
  const lifetimePct = pnl?.total_pnl_pct ?? portfolio?.total_pnl_pct ?? 0;
  const actionCount = plan?.actions.length ?? 0;
  const lastScanLabel = useMemo(() => formatLastScanLabel(status?.last_scan_at), [status?.last_scan_at]);

  const maxPositions = plan?.max_positions ?? status?.max_positions ?? 12;
  const numPositions = plan?.num_positions ?? portfolio?.holdings.length ?? 0;
  const openSlots = Math.max(0, maxPositions - numPositions);

  const invested = Math.max(0, (portfolio?.total_value ?? 0) - (portfolio?.cash ?? 0));
  const sectorRows = useMemo(
    () => toSectorRows((plan?.sector_exposure ?? undefined) as Record<string, unknown> | undefined, invested),
    [plan?.sector_exposure, invested]
  );

  const urgentSell = useMemo(
    () => plan?.actions.find((action) => action.type === "SELL" && action.urgency === "urgent") ?? null,
    [plan]
  );

  const topConviction = useMemo(() => {
    if (!plan?.actions?.length) return null;
    const buys = plan.actions.filter((action) => action.type === "BUY");
    if (buys.length === 0) return null;
    return [...buys].sort((a, b) => actionScore(b) - actionScore(a))[0];
  }, [plan]);

  const latestSignals = useMemo(() => plan?.actions.slice(0, 5) ?? [], [plan]);
  const urgentSellHref = useMemo(
    () =>
      buildTradeIntentHref({
        open: true,
        action: "sell",
        symbol: urgentSell?.symbol ?? null,
        price:
          (typeof urgentSell?.current_price === "number" ? urgentSell.current_price : null) ??
          (typeof urgentSell?.price === "number" ? urgentSell.price : null),
      }),
    [urgentSell?.current_price, urgentSell?.price, urgentSell?.symbol]
  );
  const topConvictionHref = useMemo(
    () =>
      buildTradeIntentHref({
        open: true,
        action: "buy",
        symbol: topConviction?.symbol ?? null,
        price: typeof topConviction?.price === "number" ? topConviction.price : null,
      }),
    [topConviction?.price, topConviction?.symbol]
  );

  const holdingsRows = useMemo(
    () => [...(portfolio?.holdings ?? [])].sort((a, b) => b.market_value - a.market_value).slice(0, 6),
    [portfolio?.holdings]
  );
  const sparklineBySymbol = useMemo(() => {
    const map = new Map<string, { date: string; close: number }[]>();
    for (const entry of sparkData?.series ?? []) {
      map.set(entry.symbol, entry.points ?? []);
    }
    return map;
  }, [sparkData?.series]);

  useEffect(() => {
    setUpdatedEt(tickerTimeEt());
    const id = window.setInterval(() => setUpdatedEt(tickerTimeEt()), 60_000);
    return () => window.clearInterval(id);
  }, []);

  const handleRunScanNow = useCallback(async () => {
    await runScanNowMutateAsync();
  }, [runScanNowMutateAsync]);

  const snoozeUrgent = useCallback(async () => {
    if (!urgentSell?.symbol) return;
    setSnoozing(true);
    try {
      await api.snoozeSignal(urgentSell.symbol, 2, false, true);
      qc.invalidateQueries({ queryKey: queryKeys.actionPlan });
    } finally {
      setSnoozing(false);
    }
  }, [qc, urgentSell?.symbol]);

  return (
    <div className="space-y-6">
      <div className="ph">
        <div>
          <h1>Dashboard</h1>
          <p className="sub">
            Last scan {(refreshing || scanNowPending) ? "running now" : lastScanLabel}
            <span className="divider">·</span>
            {actionCount} signals across {status?.symbols_tracked ?? "--"} symbols
            <span className="divider">·</span>
            <span className="text-emerald-400">Execute these first</span>
          </p>
        </div>

        <div className="actions">
          <div className="seg">
            {RANGES.map((value) => (
              <button key={value} className={cn(range === value && "on")} onClick={() => setRange(value)}>
                {value}
              </button>
            ))}
          </div>
          <button className="flex items-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06]">
            <Download className="h-4 w-4" />
            Export
          </button>
          <button
            onClick={() => void handleRunScanNow()}
            disabled={refreshing || scanNowPending}
            className="flex items-center gap-2 rounded-lg bg-brand-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-500 disabled:opacity-70"
          >
            <Zap className="h-4 w-4" />
            {scanNowPending ? "Scanning..." : "Run scan now"}
          </button>
        </div>
      </div>

      <TickerStrip items={tickerItems ?? []} />

      <div className="hero-strip">
        <div className="big">
          <span className="glyph" />
          <div className="lbl">
            <span className="dot" />
            Total portfolio value
          </div>
          <div className="val">{mask(formatCurrency(portfolioValue))}</div>
          <div className="chg">
            <span className={lifetimePnl >= 0 ? "pos" : "neg"}>{mask(formatCurrency(lifetimePnl))}</span>
            <span style={{ color: "var(--surface-500)" }}>{mask(formatPercent(lifetimePct))} lifetime</span>
            <span
              style={{
                marginLeft: "auto",
                fontSize: 11,
                color: "var(--surface-500)",
                fontFamily: "var(--font-mono)",
              }}
            >
              Updated {updatedEt} ET
            </span>
          </div>
          <div className="spark">
            <HeroSpark />
          </div>
        </div>

        <div className="stat2">
          <div className="lbl">
            <span>Daily P&amp;L</span>
            <span className="ico">
              <TrendingDown className="h-4 w-4" />
            </span>
          </div>
          <div className={cn("val", dailyPnl >= 0 ? "text-emerald-400" : "text-red-400")}>{mask(formatCurrency(dailyPnl))}</div>
          <div className={cn("chg", dailyPnl >= 0 ? "pos" : "neg")}>{mask(formatPercent(dailyPnlPct))} today</div>
        </div>

        <div className="stat2">
          <div className="lbl">
            <span>Cash available</span>
            <span className="ico">
              <Wallet className="h-4 w-4" />
            </span>
          </div>
          <div className="val">{mask(formatCurrency(portfolio?.cash ?? 0))}</div>
          <div className="chg neu">
            {portfolio && portfolio.total_value > 0
              ? `${((portfolio.cash / portfolio.total_value) * 100).toFixed(1)}% of book`
              : "--"}
          </div>
        </div>

        <div className="stat2">
          <div className="lbl">
            <span>Open positions</span>
            <span className="ico">
              <Briefcase className="h-4 w-4" />
            </span>
          </div>
          <div className="val">
            {numPositions}
            <span style={{ fontSize: 13, color: "var(--surface-500)", fontFamily: "var(--font-mono)", fontWeight: 400, marginLeft: 6 }}>
              / {maxPositions} slots
            </span>
          </div>
          <div className="chg neu">{openSlots} slots open</div>
        </div>
      </div>

      {urgentSell && (
        <div className="exit-banner">
          <div className="icon">
            <AlertTriangle className="h-4 w-4" />
          </div>
          <div className="body">
            <div className="t">
              <span className="sym">{urgentSell.symbol}</span>
              {` — ${urgentSell.detail || urgentSell.reason}`}
            </div>
            <div className="s">
              {typeof urgentSell.shares === "number" ? `${urgentSell.shares.toFixed(2)} shares` : "Position at risk"}
              {typeof urgentSell.days_held === "number" ? ` · held ${urgentSell.days_held.toFixed(1)}d` : ""}
              {typeof urgentSell.pnl_pct === "number" ? ` · ${formatPercent(urgentSell.pnl_pct)}` : ""}
              {typeof urgentSell.pnl === "number" ? ` · ${formatCurrency(urgentSell.pnl)}` : ""}
              {typeof urgentSell.entry_price === "number" ? ` · entry ${formatCurrency(urgentSell.entry_price)}` : ""}
            </div>
          </div>
          <Link
            href={urgentSellHref}
            className="rounded-lg bg-red-500 px-3.5 py-2 text-sm font-medium text-white transition-colors hover:bg-red-600"
          >
            Record sell
          </Link>
          <button
            onClick={() => void snoozeUrgent()}
            disabled={snoozing}
            className="inline-flex items-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.08] disabled:opacity-60"
          >
            <BellOff className="h-4 w-4" />
            {snoozing ? "Snoozing..." : "Snooze 2h"}
          </button>
        </div>
      )}

      <div className="qa-grid">
        <Link href={buildTradeIntentHref({ open: true })} className="qa">
          <span className="icn">
            <ArrowLeftRight />
          </span>
          <div className="t">
            <div className="a">Record trade</div>
            <div className="b">Buy or sell</div>
          </div>
        </Link>

        <Link href="/signals" className="qa">
          <span className="icn">
            <Zap />
          </span>
          <div className="t">
            <div className="a">View signals</div>
            <div className="b">{actionCount} new today</div>
          </div>
        </Link>

        <Link href="/upload" className="qa">
          <span className="icn">
            <Upload />
          </span>
          <div className="t">
            <div className="a">Upload screenshot</div>
            <div className="b">Sync holdings</div>
          </div>
        </Link>

        <Link href="/portfolio" className="qa">
          <span className="icn">
            <Briefcase />
          </span>
          <div className="t">
            <div className="a">Portfolio</div>
            <div className="b">{portfolio?.holdings.length ?? 0} holdings</div>
          </div>
        </Link>
      </div>

      <div className="grid-2">
        {snapshots && snapshots.length > 0 ? (
          <EquityChart snapshots={snapshots} />
        ) : chartsLoading ? (
          <ChartSkeleton />
        ) : (
          <div className="card">
            <div className="head">
              <h3>Equity curve</h3>
              <span className="sub">no snapshot history</span>
            </div>
            <div className="body text-sm text-slate-500">Your equity curve will appear after daily snapshots are recorded.</div>
          </div>
        )}

        <div className="card">
          <div className="head">
            <h3>Sector exposure</h3>
            <span className="sub">
              {(portfolio?.holdings.length ?? 0)} holdings · {portfolio && portfolio.total_value > 0 ? `${((invested / portfolio.total_value) * 100).toFixed(1)}% invested` : "--"}
            </span>
          </div>
          <div className="body">
            {sectorRows.length > 0 ? (
              sectorRows.slice(0, 6).map((row) => (
                <div className="sector-row" key={row.name}>
                  <span className="name">{row.name}</span>
                  <span className="bar">
                    <span style={{ width: `${Math.max(6, Math.min(100, row.pct))}%` }} />
                  </span>
                  <span className="val">
                    <span>{mask(formatCurrency(row.value))}</span>
                    <span className="m">{row.pct.toFixed(0)}%</span>
                  </span>
                </div>
              ))
            ) : (
              <div className="py-8 text-sm text-slate-500">Sector exposure is not available yet.</div>
            )}
          </div>
        </div>
      </div>

      {latestSignals.length > 0 ? (
        <>
          <div className="section-label">
            Latest signals <span className="c">{latestSignals.length} today</span>
          </div>
          <div className="card">
            <div>
              {latestSignals.map((action, index) => {
                const badge = signalBadgeForAction(action);
                const score = actionScore(action);
                const price = actionPrice(action);
                const delta = actionDelta(action);

                return (
                  <Link
                    key={`${action.type}-${action.symbol ?? ""}-${action.sell_symbol ?? ""}-${index}`}
                    href={action.symbol ? `/signals?check=${encodeURIComponent(action.symbol)}` : "/signals"}
                    className={cn("action-row", action.type === "SELL" && action.urgency === "urgent" && "urgent")}
                  >
                    <div className="conv">
                      <span className={cn("score", score >= 0 ? "pos" : "neg")}>
                        {score >= 0 ? "+" : ""}
                        {score.toFixed(1)}
                      </span>
                      <span className="of">/ 9</span>
                    </div>
                    <div className="who">
                      <div className="sym">
                        <span className="t">{actionSymbol(action)}</span>
                        {action.sector && <span className="sector">{action.sector}</span>}
                        <span className={cn("pill-badge", badge.cls)}>{badge.text}</span>
                      </div>
                      <div className="reason">{action.detail || action.reason}</div>
                    </div>
                    <div className="px">
                      <span className="p">{price != null ? mask(formatCurrency(price)) : "--"}</span>
                      {delta != null ? (
                        <span className={cn("d", delta >= 0 ? "pos" : "neg")}>{mask(formatPercent(delta))}</span>
                      ) : (
                        <span className="d" style={{ color: "var(--surface-500)" }}>signal</span>
                      )}
                    </div>
                    <span className="go">
                      <ArrowRight />
                    </span>
                  </Link>
                );
              })}
            </div>
          </div>
        </>
      ) : planLoading ? (
        <SignalsSkeleton />
      ) : (
        <div className="card">
          <div className="body text-sm text-slate-500">No signal actions right now.</div>
        </div>
      )}

      <div className="grid-2">
        <div className="card">
          <div className="head">
            <h3>Holdings</h3>
            <span className="sub">{portfolio?.holdings.length ?? 0} positions · {mask(formatCurrency(invested))} invested</span>
          </div>
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th className="r">Qty</th>
                  <th className="r">Price</th>
                  <th className="r">P&amp;L</th>
                  <th>7d</th>
                  <th>Signal</th>
                </tr>
              </thead>
              <tbody>
                {holdingsRows.map((holding) => {
                  const badge = signalBadgeForHolding(holding);
                  return (
                    <tr key={holding.symbol}>
                      <td className="font-semibold text-slate-100">{holding.symbol}</td>
                      <td className="r mono">{mask(holding.quantity.toFixed(2))}</td>
                      <td className="r mono">{mask(formatCurrency(holding.current_price))}</td>
                      <td className={cn("r mono", holding.pnl >= 0 ? "pos" : "neg")}>
                        {mask(formatCurrency(holding.pnl))}
                        <span style={{ opacity: 0.7, fontSize: 11 }}> ({mask(formatPercent(holding.pnl_pct))})</span>
                      </td>
                      <td>
                        <TrendProxy
                          positive={holding.pnl >= 0}
                          points={sparklineBySymbol.get(holding.symbol)}
                        />
                      </td>
                      <td>
                        <span className={cn("pill-badge", badge.cls)}>{badge.text}</span>
                      </td>
                    </tr>
                  );
                })}
                {holdingsRows.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-sm text-slate-500">No holdings yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card">
          <div className="head">
            <h3>Top conviction · {topConviction?.symbol ?? "--"}</h3>
            {topConviction ? (
              <span className={cn("pill-badge", signalBadgeForAction(topConviction).cls)}>
                {signalBadgeForAction(topConviction).text}
              </span>
            ) : (
              <span className="sub">no buy setup</span>
            )}
          </div>

          {topConviction ? (
            <div className="body">
              <div className="reasons">
                <div className="total">
                  <span>Score</span>
                  <span className="big">
                    {actionScore(topConviction) >= 0 ? "+" : ""}
                    {actionScore(topConviction).toFixed(2)}
                    <span style={{ color: "var(--surface-500)", fontWeight: 400, fontSize: 13 }}> / 9</span>
                  </span>
                </div>

                {(topConviction.reasons ?? []).slice(0, 7).map((reason, index) => {
                  const parsed = parseReason(reason);
                  return (
                    <div className="row" key={`top-reason-${index}`}>
                      <span className="lbl">{parsed.label}</span>
                      <span className={cn("val", parsed.score == null ? "mut" : parsed.score >= 0 ? "pos" : "neg")}>
                        {parsed.score == null ? "--" : `${parsed.score >= 0 ? "+" : ""}${parsed.score.toFixed(1)}`}
                      </span>
                    </div>
                  );
                })}
              </div>

              <div className="mt-4 flex gap-2">
                <Link href={topConvictionHref} className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-500">
                  <Check className="h-4 w-4" />
                  Record buy
                </Link>
                {topConviction.symbol && (
                  <Link
                    href={`/signals?check=${encodeURIComponent(topConviction.symbol)}`}
                    className="inline-flex items-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.08]"
                  >
                    Full detail
                  </Link>
                )}
              </div>
            </div>
          ) : (
            <div className="body text-sm text-slate-500">No actionable buy conviction in the current scan.</div>
          )}
        </div>
      </div>

      {(portfolioLoading || pnlLoading) && <div className="text-xs text-slate-500">Loading dashboard data…</div>}
    </div>
  );
}
