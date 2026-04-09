"use client";

import Link from "next/link";
import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  Wallet,
  Zap,
  ArrowLeftRight,
  ArrowRight,
  Briefcase,
  Upload,
  RefreshCw,
  AlertTriangle,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useHoldings, usePnl, useSnapshots, useActionPlan, queryKeys } from "@/lib/hooks";
import { formatCurrency, cn } from "@/lib/utils";
import { usePrivacy } from "@/lib/privacy";
import { StatCard } from "@/components/ui/stat-card";
import { EquityChart } from "@/components/ui/equity-chart";
import { SectorChart } from "@/components/ui/sector-chart";
import { CardSkeleton, ChartSkeleton, SectorChartSkeleton, SignalsSkeleton } from "@/components/ui/loading";
import { SearchTrigger } from "@/components/ui/search-trigger";

export default function DashboardPage() {
  const qc = useQueryClient();
  const { data: portfolio, isLoading: portfolioLoading } = useHoldings();
  const { data: pnl, isLoading: pnlLoading } = usePnl();
  const { data: snapshots, isLoading: snapshotsLoading } = useSnapshots();
  const { data: plan, isLoading: planLoading, isFetching: refreshing } = useActionPlan();

  const { mask } = usePrivacy();
  const statsLoading = portfolioLoading && pnlLoading;
  const chartsLoading = snapshotsLoading || planLoading;
  const hasStats = portfolio || pnl;

  function refresh() {
    qc.invalidateQueries({ queryKey: queryKeys.holdings });
    qc.invalidateQueries({ queryKey: queryKeys.pnl });
    qc.invalidateQueries({ queryKey: queryKeys.snapshots });
    qc.invalidateQueries({ queryKey: queryKeys.actionPlan });
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

      {/* Action plan preview */}
      {plan && plan.actions.length > 0 ? (
        <div className="glass-card p-5">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-medium text-slate-400">Action Plan</h3>
            <Link
              href="/signals"
              className="text-xs text-brand-400 hover:underline"
            >
              View full plan
            </Link>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {plan.actions.slice(0, 3).map((a, i) => {
              if (a.type === "SELL") {
                const isUrgent = a.urgency === "urgent";
                return (
                  <Link
                    key={`action-${i}`}
                    href="/signals"
                    className={cn(
                      "flex items-center justify-between rounded-lg border px-4 py-3 transition-colors hover:bg-white/[0.08]",
                      isUrgent
                        ? "border-red-500/30 bg-red-500/[0.05]"
                        : "border-amber-500/20 bg-amber-500/[0.03]"
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <TrendingDown className={cn("h-4 w-4", isUrgent ? "text-red-400" : "text-amber-400")} />
                      <div>
                        <p className="font-medium">SELL {a.symbol}</p>
                        <p className="text-xs text-slate-500">{a.reason}</p>
                      </div>
                    </div>
                    {a.pnl_pct != null && (
                      <span className={cn(
                        "text-sm font-medium",
                        a.pnl_pct >= 0 ? "text-emerald-400" : "text-red-400"
                      )}>
                        {mask(`${a.pnl_pct >= 0 ? "+" : ""}${a.pnl_pct.toFixed(1)}%`)}
                      </span>
                    )}
                  </Link>
                );
              }
              if (a.type === "SWAP") {
                return (
                  <Link
                    key={`action-${i}`}
                    href="/signals"
                    className="flex items-center justify-between rounded-lg border border-brand-500/20 bg-brand-500/[0.03] px-4 py-3 transition-colors hover:bg-white/[0.08]"
                  >
                    <div className="flex items-center gap-2">
                      <ArrowRight className="h-4 w-4 text-brand-400" />
                      <div>
                        <p className="font-medium">{a.sell_symbol} &rarr; {a.buy_symbol}</p>
                        <p className="text-xs text-slate-500">Swap</p>
                      </div>
                    </div>
                  </Link>
                );
              }
              // BUY
              return (
                <Link
                  key={`action-${i}`}
                  href="/signals"
                  className="flex items-center justify-between rounded-lg border border-emerald-500/20 bg-emerald-500/[0.03] px-4 py-3 transition-colors hover:bg-white/[0.08]"
                >
                  <div className="flex items-center gap-2">
                    <TrendingUp className="h-4 w-4 text-emerald-400" />
                    <div>
                      <p className="font-medium">BUY {a.symbol}</p>
                      <p className="text-xs text-slate-500">{a.shares} sh @ ~{formatCurrency(a.price ?? 0)}</p>
                    </div>
                  </div>
                  {a.strength != null && (
                    <span className="text-sm font-medium text-emerald-400">
                      {(a.strength * 100).toFixed(0)}%
                    </span>
                  )}
                </Link>
              );
            })}
          </div>
        </div>
      ) : chartsLoading ? (
        <SignalsSkeleton />
      ) : (
        <div className="glass-card flex flex-col items-center gap-2 py-12">
          <Zap className="h-8 w-8 text-slate-600" />
          <p className="text-sm text-slate-500">No trades needed right now</p>
          <p className="text-xs text-slate-600">Portfolio is on track</p>
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
      {plan && Object.keys(plan.sector_exposure).length > 0 ? (
        <SectorChart exposure={plan.sector_exposure as Record<string, number>} />
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
