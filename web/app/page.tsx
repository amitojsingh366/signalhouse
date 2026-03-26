"use client";

import { useEffect, useState, useCallback } from "react";
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
} from "lucide-react";
import { api, getCache, fetchWithCache } from "@/lib/api";
import type {
  PortfolioSummary,
  PnlSummary,
  SnapshotOut,
  RecommendationOut,
} from "@/lib/api";
import { formatCurrency, formatPercent, pnlColor, cn } from "@/lib/utils";
import { StatCard } from "@/components/ui/stat-card";
import { EquityChart } from "@/components/ui/equity-chart";
import { SignalBadge } from "@/components/ui/signal-badge";
import { SectorChart } from "@/components/ui/sector-chart";
import { CardSkeleton, ChartSkeleton, SectorChartSkeleton, SignalsSkeleton } from "@/components/ui/loading";
import { SearchTrigger } from "@/components/ui/search-trigger";

export default function DashboardPage() {
  // Phase 1: stat cards (instant from cache)
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(
    () => getCache<PortfolioSummary>("/api/portfolio/holdings")
  );
  const [pnl, setPnl] = useState<PnlSummary | null>(
    () => getCache<PnlSummary>("/api/portfolio/pnl")
  );
  const [statsLoading, setStatsLoading] = useState(!portfolio && !pnl);

  // Phase 2: charts & signals (load async)
  const [snapshots, setSnapshots] = useState<SnapshotOut[]>(
    () => getCache<SnapshotOut[]>("/api/portfolio/snapshots") ?? []
  );
  const [signals, setSignals] = useState<RecommendationOut | null>(
    () => getCache<RecommendationOut>("/api/signals/recommend?n=3")
  );
  const [chartsLoading, setChartsLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(() => {
    // Phase 1: fetch portfolio + pnl
    let statsResolved = 0;
    const markStatsDone = () => {
      statsResolved++;
      if (statsResolved >= 2) setStatsLoading(false);
    };

    fetchWithCache<PortfolioSummary>(
      "/api/portfolio/holdings",
      (cached) => { setPortfolio(cached); setStatsLoading(false); },
      (fresh) => { setPortfolio(fresh); markStatsDone(); },
      () => markStatsDone(),
    );
    fetchWithCache<PnlSummary>(
      "/api/portfolio/pnl",
      (cached) => { setPnl(cached); setStatsLoading(false); },
      (fresh) => { setPnl(fresh); markStatsDone(); },
      () => markStatsDone(),
    );

    // Phase 2: fetch charts + signals in parallel
    let chartsResolved = 0;
    const markChartsDone = () => {
      chartsResolved++;
      if (chartsResolved >= 2) setChartsLoading(false);
    };

    fetchWithCache<SnapshotOut[]>(
      "/api/portfolio/snapshots",
      (cached) => setSnapshots(cached),
      (fresh) => { setSnapshots(fresh); markChartsDone(); },
      () => markChartsDone(),
    );
    fetchWithCache<RecommendationOut>(
      "/api/signals/recommend?n=3",
      (cached) => setSignals(cached),
      (fresh) => { setSignals(fresh); markChartsDone(); },
      () => markChartsDone(),
    );
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const [p, pnlData, snaps, recs] = await Promise.all([
        api.getHoldings(),
        api.getPnl(),
        api.getSnapshots(),
        api.getRecommendations(3),
      ]);
      setPortfolio(p);
      setPnl(pnlData);
      setSnapshots(snaps);
      setSignals(recs);
    } catch (err) {
      console.error(err);
    } finally {
      setRefreshing(false);
    }
  }, []);

  const hasStats = portfolio || pnl;

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

       {/* Stat cards — render immediately from cache or show skeleton */}
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
      {signals && (signals.buys.length > 0 || signals.sells.length > 0) ? (
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
            {[...signals.buys, ...signals.sells].slice(0, 6).map((s) => (
              <div
                key={s.symbol}
                className="flex items-center justify-between rounded-lg border border-white/5 bg-white/5 px-4 py-3"
              >
                <div>
                  <p className="font-medium">{s.symbol}</p>
                  <p className="text-xs text-slate-500">
                    {s.sector}
                    {s.price && ` \u00B7 ${formatCurrency(s.price)}`}
                  </p>
                </div>
                <SignalBadge signal={s.signal} strength={s.strength} />
              </div>
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
      {snapshots.length > 0 ? (
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
