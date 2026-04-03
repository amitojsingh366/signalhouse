"use client";

import { useCallback } from "react";
import { Sunrise, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { usePremarketMovers, queryKeys } from "@/lib/hooks";
import { formatCurrency, cn } from "@/lib/utils";
import { usePrivacy } from "@/lib/privacy";
import { Skeleton } from "@/components/ui/loading";

function MoverCard({ mover }: { mover: { cdr_symbol: string; us_symbol: string; premarket_price: number; change_pct: number } }) {
  const { mask } = usePrivacy();
  const isPositive = mover.change_pct >= 0;
  const pctDisplay = mask(`${isPositive ? "+" : ""}${(mover.change_pct * 100).toFixed(1)}%`);

  return (
    <Link
      href={`/signals?check=${encodeURIComponent(mover.cdr_symbol)}`}
      className="glass-card flex items-center justify-between p-4 transition-colors hover:bg-white/[0.05]"
    >
      <div className="flex items-center gap-3">
        <span className={cn("h-2.5 w-2.5 rounded-full", isPositive ? "bg-emerald-400" : "bg-red-400")} />
        <div>
          <div className="flex items-center gap-2">
            <span className="text-base font-semibold">{mover.cdr_symbol}</span>
            <span className="text-xs text-slate-500">({mover.us_symbol})</span>
          </div>
          <p className="text-sm text-slate-400">
            Premarket: {mask(formatCurrency(mover.premarket_price))}
          </p>
        </div>
      </div>

      <span
        className={cn(
          "rounded-full px-3 py-1 text-sm font-semibold tabular-nums",
          isPositive
            ? "bg-emerald-500/15 text-emerald-400"
            : "bg-red-500/15 text-red-400"
        )}
      >
        {pctDisplay}
      </span>
    </Link>
  );
}

function MoverSkeleton() {
  return (
    <div className="glass-card flex items-center justify-between p-4">
      <div className="flex items-center gap-3">
        <Skeleton className="h-2.5 w-2.5 rounded-full" />
        <div className="space-y-2">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-3 w-20" />
        </div>
      </div>
      <Skeleton className="h-7 w-16 rounded-full" />
    </div>
  );
}

export default function PreMarketPage() {
  const qc = useQueryClient();
  const { data, isLoading, isFetching } = usePremarketMovers();

  const refresh = useCallback(() => {
    qc.invalidateQueries({ queryKey: queryKeys.premarket });
  }, [qc]);

  const movers = data?.movers
    ?.slice()
    .sort((a, b) => Math.abs(b.change_pct) - Math.abs(a.change_pct)) ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Sunrise className="h-6 w-6 text-brand-400" />
          <h1 className="text-2xl font-bold">Pre-Market Movers</h1>
        </div>
        <button
          onClick={refresh}
          disabled={isFetching}
          className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-300 transition-colors hover:bg-white/10"
        >
          <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
          Refresh
        </button>
      </div>

      <p className="text-sm text-slate-500">
        US premarket moves for CDR-tracked stocks. Click any mover to check its signal.
      </p>

      {isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <MoverSkeleton key={i} />
          ))}
        </div>
      ) : movers.length === 0 ? (
        <div className="glass-card flex flex-col items-center gap-3 py-16">
          <Sunrise className="h-10 w-10 text-slate-600" />
          <p className="text-sm text-slate-500">No pre-market data available</p>
          <p className="text-xs text-slate-600">
            Movers appear weekdays around 8 AM ET when US premarket data is available.
          </p>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {movers.map((m) => (
            <MoverCard key={m.cdr_symbol} mover={m} />
          ))}
        </div>
      )}
    </div>
  );
}
