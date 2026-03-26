"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  DollarSign,
  TrendingUp,
  Wallet,
  Zap,
  ArrowLeftRight,
  Briefcase,
  Upload,
} from "lucide-react";
import { api } from "@/lib/api";
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
import { CardSkeleton, PageLoader } from "@/components/ui/loading";

export default function DashboardPage() {
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const [pnl, setPnl] = useState<PnlSummary | null>(null);
  const [snapshots, setSnapshots] = useState<SnapshotOut[]>([]);
  const [signals, setSignals] = useState<RecommendationOut | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [p, pnlData, snaps, sigs] = await Promise.all([
          api.getHoldings(),
          api.getPnl(),
          api.getSnapshots(),
          api.getRecommendations(3),
        ]);
        setPortfolio(p);
        setPnl(pnlData);
        setSnapshots(snaps);
        setSignals(sigs);
      } catch (err) {
        console.error("Failed to load dashboard:", err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
        <PageLoader />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      {/* Stat cards */}
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

      {/* Equity curve */}
      <EquityChart snapshots={snapshots} />

      {/* CTAs */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Link href="/trades" className="glass-card-hover flex items-center gap-3 p-4">
          <div className="rounded-lg bg-green-500/20 p-2">
            <ArrowLeftRight className="h-5 w-5 text-green-400" />
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
          <div className="rounded-lg bg-purple-500/20 p-2">
            <Briefcase className="h-5 w-5 text-purple-400" />
          </div>
          <div>
            <p className="text-sm font-medium">Portfolio</p>
            <p className="text-xs text-slate-500">Holdings & advice</p>
          </div>
        </Link>
        <Link href="/upload" className="glass-card-hover flex items-center gap-3 p-4">
          <div className="rounded-lg bg-yellow-500/20 p-2">
            <Upload className="h-5 w-5 text-yellow-400" />
          </div>
          <div>
            <p className="text-sm font-medium">Upload Screenshot</p>
            <p className="text-xs text-slate-500">Sync holdings</p>
          </div>
        </Link>
      </div>

      {/* Latest signals preview */}
      {signals && (signals.buys.length > 0 || signals.sells.length > 0) && (
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
      )}
    </div>
  );
}
