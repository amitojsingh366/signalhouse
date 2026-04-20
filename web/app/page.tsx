"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeftRight,
  ArrowRight,
  Briefcase,
  Download,
  RefreshCw,
  TrendingDown,
  TrendingUp,
  Upload,
  Wallet,
  Zap,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useActionPlan, useHoldings, usePnl, useSnapshots, queryKeys } from "@/lib/hooks";
import type { ActionItem } from "@/lib/api";
import { cn, formatCurrency } from "@/lib/utils";
import { usePrivacy } from "@/lib/privacy";
import { EquityChart } from "@/components/ui/equity-chart";
import { SectorChart } from "@/components/ui/sector-chart";
import {
  ChartSkeleton,
  SectorChartSkeleton,
  SignalsSkeleton,
} from "@/components/ui/loading";

const TICKER_ITEMS = [
  { s: "TSX", p: "22,418.12", d: "+0.18%", up: true },
  { s: "CAD/USD", p: "0.7342", d: "-0.12%", up: false },
  { s: "OIL", p: "$82.14", d: "-1.8%", up: false },
  { s: "GOLD", p: "$2,384", d: "+0.4%", up: true },
  { s: "BTC", p: "$71,248", d: "+2.1%", up: true },
  { s: "F&G", p: "15", d: "Extreme Fear", up: false },
  { s: "SHOP.TO", p: "$133.98", d: "+2.8%", up: true },
  { s: "CSU.TO", p: "$4,218", d: "+1.7%", up: true },
];

const RANGES = ["1D", "7D", "1M", "3M", "1Y", "ALL"] as const;

function signedCurrency(value: number): string {
  const abs = formatCurrency(Math.abs(value));
  if (value > 0) return `+${abs}`;
  if (value < 0) return `-${abs}`;
  return abs;
}

function actionHeadline(action: ActionItem): string {
  if (action.type === "SWAP") {
    return `${action.sell_symbol ?? "SELL"} → ${action.buy_symbol ?? "BUY"}`;
  }
  if (action.type === "BUY") return `BUY ${action.symbol ?? ""}`.trim();
  return `SELL ${action.symbol ?? ""}`.trim();
}

function actionBadgeClass(action: ActionItem): string {
  if (action.type === "BUY") return "badge-buy";
  if (action.urgency === "urgent") return "badge-sell";
  if (action.type === "SWAP") return "badge-buy";
  return "badge-hold";
}

function tickerTimeEt(): string {
  return new Intl.DateTimeFormat("en-CA", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "America/Toronto",
  }).format(new Date());
}

function TickerStrip() {
  const doubled = [...TICKER_ITEMS, ...TICKER_ITEMS];
  return (
    <div className="ticker">
      <div className="track">
        {doubled.map((item, i) => (
          <span key={`${item.s}-${i}`} className="t-item">
            <span className="s">{item.s}</span>
            <span className="p">{item.p}</span>
            <span className={cn("d", item.up ? "pos" : "neg")}>{item.d}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const qc = useQueryClient();
  const { data: portfolio, isLoading: portfolioLoading } = useHoldings();
  const { data: pnl, isLoading: pnlLoading } = usePnl();
  const { data: snapshots, isLoading: snapshotsLoading } = useSnapshots();
  const { data: plan, isLoading: planLoading, isFetching: refreshing } = useActionPlan();
  const { mask } = usePrivacy();
  const [range, setRange] = useState<(typeof RANGES)[number]>("1M");
  const [updatedEt, setUpdatedEt] = useState("--:--");

  const chartsLoading = snapshotsLoading || planLoading;
  const portfolioValue = portfolio?.total_value ?? 0;
  const dailyPnl = pnl?.daily_pnl ?? 0;
  const lifetimePnl = pnl?.total_pnl ?? portfolio?.total_pnl ?? 0;
  const lifetimePct = pnl?.total_pnl_pct ?? portfolio?.total_pnl_pct ?? 0;
  const actionCount = plan?.actions.length ?? 0;
  const openSlots = Math.max(0, (plan?.max_positions ?? 0) - (plan?.num_positions ?? 0));
  const urgentSell = useMemo(
    () => plan?.actions.find((a) => a.type === "SELL" && a.urgency === "urgent"),
    [plan]
  );

  useEffect(() => {
    setUpdatedEt(tickerTimeEt());
    const id = window.setInterval(() => setUpdatedEt(tickerTimeEt()), 60_000);
    return () => window.clearInterval(id);
  }, []);

  function refresh() {
    qc.invalidateQueries({ queryKey: queryKeys.holdings });
    qc.invalidateQueries({ queryKey: queryKeys.pnl });
    qc.invalidateQueries({ queryKey: queryKeys.snapshots });
    qc.invalidateQueries({ queryKey: queryKeys.actionPlan });
  }

  return (
    <div className="space-y-6">
      <div className="ph">
        <div>
          <h1>Dashboard</h1>
          <p className="sub">
            Last scan {refreshing ? "running now" : "a moment ago"}
            <span className="divider">·</span>
            {actionCount} actions across 333 symbols
            <span className="divider">·</span>
            <span className="text-emerald-400">Execute these first</span>
          </p>
        </div>
        <div className="actions">
          <div className="seg">
            {RANGES.map((value) => (
              <button
                key={value}
                className={cn(range === value && "on")}
                onClick={() => setRange(value)}
              >
                {value}
              </button>
            ))}
          </div>
          <button className="flex items-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06]">
            <Download className="h-4 w-4" />
            Export
          </button>
          <button
            onClick={refresh}
            disabled={refreshing}
            className="flex items-center gap-2 rounded-lg bg-brand-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-500 disabled:opacity-70"
          >
            <RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} />
            Run scan now
          </button>
        </div>
      </div>

      <TickerStrip />

      <div className="hero-strip">
        <div className="big">
          <span className="glyph" />
          <div className="lbl">
            <span className="dot" />
            Total portfolio value
          </div>
          <div className="val">{mask(formatCurrency(portfolioValue))}</div>
          <div className="chg">
            <span className={lifetimePnl >= 0 ? "pos" : "neg"}>
              {mask(signedCurrency(lifetimePnl))}
            </span>
            <span className="text-surface-500">
              {lifetimePct >= 0 ? "+" : ""}
              {lifetimePct.toFixed(2)}% lifetime
            </span>
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
        </div>

        <div className="stat2">
          <div className="lbl">
            <span>Daily P&amp;L</span>
            <span className="ico">
              <TrendingDown />
            </span>
          </div>
          <div className="val">{mask(signedCurrency(dailyPnl))}</div>
          <div className={cn("chg", dailyPnl > 0 ? "pos" : dailyPnl < 0 ? "neg" : "neu")}>
            {pnl ? `${pnl.daily_pnl_pct >= 0 ? "+" : ""}${pnl.daily_pnl_pct.toFixed(2)}% today` : "No data"}
          </div>
        </div>

        <div className="stat2">
          <div className="lbl">
            <span>Cash available</span>
            <span className="ico">
              <Wallet />
            </span>
          </div>
          <div className="val">{mask(formatCurrency(portfolio?.cash ?? 0))}</div>
          <div className="chg neu">
            {portfolio && portfolio.total_value > 0
              ? `${((portfolio.cash / portfolio.total_value) * 100).toFixed(1)}% of book`
              : "Waiting for data"}
          </div>
        </div>

        <div className="stat2">
          <div className="lbl">
            <span>Open positions</span>
            <span className="ico">
              <Briefcase />
            </span>
          </div>
          <div className="val">
            {plan?.num_positions ?? portfolio?.holdings.length ?? 0}
            <span
              style={{
                fontSize: 13,
                color: "var(--surface-500)",
                fontFamily: "var(--font-mono)",
                fontWeight: 400,
                marginLeft: 6,
              }}
            >
              / {plan?.max_positions ?? 12} slots
            </span>
          </div>
          <div className="chg neu">{openSlots} slots open</div>
        </div>
      </div>

      {urgentSell && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/[0.05] p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-red-300">
                {urgentSell.symbol} — urgent exit
              </p>
              <p className="mt-1 text-sm text-slate-300">{urgentSell.detail || urgentSell.reason}</p>
            </div>
            <Link
              href="/trades"
              className="rounded-lg border border-red-500/30 bg-red-500/15 px-3 py-2 text-xs font-medium text-red-300 transition-colors hover:bg-red-500/25"
            >
              Record sell
            </Link>
          </div>
        </div>
      )}

      <div className="qa-grid">
        <Link href="/trades" className="qa">
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
            <div className="b">{actionCount} actions today</div>
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

      {plan && plan.actions.length > 0 ? (
        <>
          <div className="section-label">
            Latest signals <span className="c">{plan.actions.length} today</span>
          </div>
          <div className="glass-card overflow-hidden">
            {plan.actions.slice(0, 6).map((action, i) => (
              <Link
                key={`action-${i}`}
                href="/signals"
                className={cn(
                  "flex items-center gap-4 border-b border-white/[0.04] px-4 py-4 transition-colors hover:bg-white/[0.02]",
                  i === plan.actions.slice(0, 6).length - 1 && "border-b-0"
                )}
              >
                <span className={cn("badge", actionBadgeClass(action))}>
                  {action.type}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-slate-100">
                    {actionHeadline(action)}
                  </p>
                  <p className="truncate text-xs text-slate-400">{action.detail || action.reason}</p>
                </div>
                <div className="text-right">
                  <p className="font-mono text-sm text-slate-100">
                    {action.price != null ? formatCurrency(action.price) : "—"}
                  </p>
                  <p className="text-xs text-slate-500">
                    {action.strength != null
                      ? `${Math.round(action.strength * 100)}%`
                      : action.urgency.toUpperCase()}
                  </p>
                </div>
                <ArrowRight className="h-4 w-4 text-slate-500" />
              </Link>
            ))}
          </div>
        </>
      ) : chartsLoading ? (
        <SignalsSkeleton />
      ) : (
        <div className="glass-card flex flex-col items-center gap-2 py-12">
          <Zap className="h-8 w-8 text-slate-600" />
          <p className="text-sm text-slate-500">No trades needed right now</p>
          <p className="text-xs text-slate-600">Portfolio is on track</p>
        </div>
      )}

      <div className="grid-2">
        {snapshots && snapshots.length > 0 ? (
          <EquityChart snapshots={snapshots} />
        ) : chartsLoading ? (
          <ChartSkeleton />
        ) : (
          <div className="glass-card flex flex-col items-center gap-2 py-12">
            <TrendingUp className="h-8 w-8 text-slate-600" />
            <p className="text-sm text-slate-500">No equity data yet</p>
            <p className="text-xs text-slate-600">
              Your portfolio chart will appear after the first daily snapshot.
            </p>
          </div>
        )}

        {plan && Object.keys(plan.sector_exposure).length > 0 ? (
          <SectorChart exposure={plan.sector_exposure as Record<string, number>} />
        ) : chartsLoading ? (
          <SectorChartSkeleton />
        ) : (
          <div className="glass-card flex flex-col items-center gap-2 py-12">
            <Briefcase className="h-8 w-8 text-slate-600" />
            <p className="text-sm text-slate-500">No sector data available</p>
            <p className="text-xs text-slate-600">
              Sector exposure will show once you have holdings.
            </p>
          </div>
        )}
      </div>

      {(portfolioLoading || pnlLoading) && (
        <div className="text-xs text-slate-500">Loading portfolio snapshots…</div>
      )}
    </div>
  );
}
