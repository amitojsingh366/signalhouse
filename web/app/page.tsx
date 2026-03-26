"use client";

import Link from "next/link";
import {
  DollarSign,
  TrendingUp,
  Wallet,
  Zap,
  ArrowLeftRight,
  Briefcase,
  Upload,
  RefreshCw,
  AlertTriangle,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useHoldings, usePnl, useSnapshots, useRecommendations, queryKeys } from "@/lib/hooks";
import { formatCurrency, cn } from "@/lib/utils";
import { StatCard } from "@/components/ui/stat-card";
import { EquityChart } from "@/components/ui/equity-chart";
import { SignalBadge } from "@/components/ui/signal-badge";
import { SectorChart } from "@/components/ui/sector-chart";
import { CardSkeleton, ChartSkeleton, SectorChartSkeleton, SignalsSkeleton } from "@/components/ui/loading";
import { SearchTrigger } from "@/components/ui/search-trigger";

export default function DashboardPage() {
  const qc = useQueryClient();
  const { data: portfolio, isLoading: portfolioLoading } = useHoldings();
  const { data: pnl, isLoading: pnlLoading } = usePnl();
  const { data: snapshots, isLoading: snapshotsLoading } = useSnapshots();
  const { data: signals, isLoading: signalsLoading, isFetching: refreshing } = useRecommendations(3);

  const statsLoading = portfolioLoading && pnlLoading;
  const chartsLoading = snapshotsLoading || signalsLoading;
  const hasStats = portfolio || pnl;

  function refresh() {
    qc.invalidateQueries({ queryKey: queryKeys.holdings });
    qc.invalidateQueries({ queryKey: queryKeys.pnl });
    qc.invalidateQueries({ queryKey: queryKeys.snapshots });
    qc.invalidateQueries({ queryKey: queryKeys.recommendations(3) });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <div className="flex items-center gap-2">
          <SearchTrigger />
          <button
            onClick={refresh}
            disabled={refreshing}
            className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-300 transition-colors hover:bg-white/10 disabled:opacity-50"
          >
            <RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} />
            Refresh
          </button>
        </div>
      </div>

      {/* Quick actions */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Link href="/trades" className="glass-card-hover flex items-center gap-3 p-4">
          <div className="rounded-lg bg-brand-500/20 p-2">
            <ArrowLeftRight className="h-5 w-5 text-brand-400" />
          </div>
          <div>
            <p className="text-sm font-medium">Record Trade</p>
            <p className="text-xs text-slate-500">Buy or sell</p>
          </div>
        </Link>
        <Link href="/signals" className="glass-card-hover flex items-center gap-3 p-4">
          <div className="rounded-lg bg-brand-500/20 p-2">
            <Zap className="h-5 w-5 text-brand-400" />
          </div>
          <div>
            <p className="text-sm font-medium">View Signals</p>
            <p className="text-xs text-slate-500">Latest recommendations</p>
          </div>
        </Link>
        <Link href="/portfolio" className="glass-card-hover flex items-center gap-3 p-4">
          <div className="rounded-lg bg-brand-500/20 p-2">
            <Briefcase className="h-5 w-5 text-brand-400" />
          </div>
          <div>
            <p className="text-sm font-medium">Portfolio</p>
            <p className="text-xs text-slate-500">Holdings & advice</p>
          </div>
        </Link>
        <Link href="/upload" className="glass-card-hover flex items-center gap-3 p-4">
          <div className="rounded-lg bg-brand-500/20 p-2">
            <Upload className="h-5 w-5 text-brand-400" />
          </div>
          <div>
            <p className="text-sm font-medium">Upload Screenshot</p>
            <p className="text-xs text-slate-500">Sync holdings</p>
          </div>
        </Link>
      </div>

       {/* Stat cards */}
      {statsLoading && !hasStats ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            title="Portfolio Value"
            value={portfolio?.total_value ?? 0}
            format="currency"
            change={pnl?.total_pnl_pct}
            changeLabel="total"
            icon={DollarSign}
          />
          <StatCard
            title="Daily P&L"
            value={pnl?.daily_pnl ?? 0}
            format="currency"
            change={pnl?.daily_pnl_pct}
            changeLabel="today"
            icon={TrendingUp}
          />
          <StatCard
            title="Cash Available"
            value={portfolio?.cash ?? 0}
            format="currency"
            icon={Wallet}
          />
          <StatCard
            title="Holdings"
            value={portfolio?.holdings.length ?? 0}
            format="number"
            icon={Briefcase}
          />
        </div>
      )}

      {/* Latest signals preview */}
      {signals && (signals.buys.length > 0 || signals.sells.length > 0 || (signals.exit_alerts && signals.exit_alerts.length > 0) || (signals.watchlist_sells && signals.watchlist_sells.length > 0)) ? (
        <div className="glass-card p-5">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-medium text-slate-400">Latest Signals</h3>
            <Link
              href="/signals"
              className="text-xs text-brand-400 hover:underline"
            >
              View all
            </Link>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {/* Exit alerts first */}
            {signals.exit_alerts?.map((a) => (
              <Link
                key={`exit-${a.symbol}`}
                href={`/signals?check=${encodeURIComponent(a.symbol)}`}
                className={cn(
                  "flex items-center justify-between rounded-lg border px-4 py-3 transition-colors hover:bg-white/[0.08]",
                  a.severity === "high"
                    ? "border-red-500/30 bg-red-500/[0.05]"
                    : "border-amber-500/20 bg-amber-500/[0.03]"
                )}
              >
                <div className="flex items-center gap-2">
                  <AlertTriangle className={cn("h-4 w-4", a.severity === "high" ? "text-red-400" : "text-amber-400")} />
                  <div>
                    <p className="font-medium">{a.symbol}</p>
                    <p className="text-xs text-slate-500">{a.reason}</p>
                  </div>
                </div>
                <span className={cn(
                  "text-sm font-medium",
                  a.pnl_pct >= 0 ? "text-emerald-400" : "text-red-400"
                )}>
                  {a.pnl_pct >= 0 ? "+" : ""}{a.pnl_pct.toFixed(1)}%
                </span>
              </Link>
            ))}
            {/* Buy/sell/watchlist signals */}
            {[...signals.buys, ...signals.sells, ...(signals.watchlist_sells ?? [])].slice(0, 6).map((s) => (
              <Link
                key={s.symbol}
                href={`/signals?check=${encodeURIComponent(s.symbol)}`}
                className="flex items-center justify-between rounded-lg border border-white/5 bg-white/5 px-4 py-3 transition-colors hover:bg-white/[0.08]"
              >
                <div>
                  <p className="font-medium">{s.symbol}</p>
                  <p className="text-xs text-slate-500">
                    {s.sector}
                    {s.price && ` \u00B7 ${formatCurrency(s.price)}`}
                  </p>
                </div>
                <SignalBadge signal={s.signal} strength={s.strength} />
              </Link>
            ))}
          </div>
        </div>
      ) : chartsLoading ? (
        <SignalsSkeleton />
      ) : (
        <div className="glass-card flex flex-col items-center gap-2 py-12">
          <Zap className="h-8 w-8 text-slate-600" />
          <p className="text-sm text-slate-500">No active signals right now</p>
          <p className="text-xs text-slate-600">Try checking a specific symbol on the signals page</p>
        </div>
      )}

      {/* Equity curve */}
      {snapshots && snapshots.length > 0 ? (
        <EquityChart snapshots={snapshots} />
      ) : chartsLoading ? (
        <ChartSkeleton />
      ) : (
        <div className="glass-card flex flex-col items-center gap-2 py-12">
          <TrendingUp className="h-8 w-8 text-slate-600" />
          <p className="text-sm text-slate-500">No equity data yet</p>
          <p className="text-xs text-slate-600">Your portfolio chart will appear after the first daily snapshot</p>
        </div>
      )}

      {/* Sector exposure chart */}
      {signals && Object.keys(signals.sector_exposure).length > 0 ? (
        <SectorChart exposure={signals.sector_exposure} />
      ) : chartsLoading ? (
        <SectorChartSkeleton />
      ) : (
        <div className="glass-card flex flex-col items-center gap-2 py-12">
          <Briefcase className="h-8 w-8 text-slate-600" />
          <p className="text-sm text-slate-500">No sector data available</p>
          <p className="text-xs text-slate-600">Sector exposure will show once you have holdings</p>
        </div>
      )}
    </div>
  );
}
