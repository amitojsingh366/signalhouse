"use client";

import { Suspense, useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { Zap, RefreshCw, AlertTriangle, ArrowRight, TrendingDown, TrendingUp } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useActionPlan, useSymbols, useSignalCheck, queryKeys } from "@/lib/hooks";
import type { ActionItem } from "@/lib/api";
import { formatCurrency, formatPercent, cn } from "@/lib/utils";
import { usePrivacy } from "@/lib/privacy";
import { SignalBadge } from "@/components/ui/signal-badge";
import { SearchBar } from "@/components/ui/search-bar";
import { Skeleton, SignalCardsSkeleton } from "@/components/ui/loading";
import { PriceChart } from "@/components/ui/price-chart";

function ScoreTag({ text }: { text: string }) {
  const match = text.match(/\[([+-][\d.]+)\]$/);
  if (!match) return <span>{text}</span>;
  const label = text.slice(0, text.lastIndexOf("[")).trim();
  const value = parseFloat(match[1]);
  const color = value > 0 ? "text-emerald-400" : value < 0 ? "text-red-400" : "text-slate-500";
  return (
    <span className="flex items-center justify-between gap-2">
      <span>{label}</span>
      <span className={cn("font-mono text-[10px] tabular-nums", color)}>{match[1]}</span>
    </span>
  );
}

function ActionCard({ action }: { action: ActionItem }) {
  const { mask } = usePrivacy();

  if (action.type === "SELL") {
    const isUrgent = action.urgency === "urgent";
    const isLow = action.urgency === "low";
    return (
      <div className={cn(
        "glass-card p-4 border",
        isUrgent ? "border-red-500/30 bg-red-500/[0.05]"
          : isLow ? "border-slate-500/20 bg-white/[0.02]"
          : "border-amber-500/20 bg-amber-500/[0.03]"
      )}>
        <div className="mb-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TrendingDown className={cn("h-4 w-4", isUrgent ? "text-red-400" : isLow ? "text-slate-400" : "text-amber-400")} />
            <span className="text-lg font-semibold">{action.symbol}</span>
          </div>
          <span className={cn(
            "rounded-full px-2 py-0.5 text-xs font-medium",
            isUrgent ? "bg-red-500/20 text-red-400" : isLow ? "bg-slate-500/20 text-slate-400" : "bg-amber-500/20 text-amber-400"
          )}>
            {isUrgent ? "URGENT" : action.reason}
          </span>
        </div>
        <p className="mb-3 text-sm font-medium text-white">{action.detail}</p>
        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400">
          <span>Shares: {mask(String(action.shares?.toFixed(4) ?? ""))}</span>
          <span>Price: {formatCurrency(action.price ?? 0)}</span>
          <span>Value: {mask(formatCurrency(action.dollar_amount ?? 0))}</span>
          {action.pnl_pct != null && (
            <span className={cn("font-medium", action.pnl_pct >= 0 ? "text-emerald-400" : "text-red-400")}>
              {mask(formatPercent(action.pnl_pct))}
            </span>
          )}
        </div>
        {action.reason && (
          <p className="mt-2 text-xs text-slate-500">{action.reason}</p>
        )}
      </div>
    );
  }

  if (action.type === "SWAP") {
    return (
      <div className="glass-card p-4 border border-brand-500/20 bg-brand-500/[0.03]">
        <div className="mb-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ArrowRight className="h-4 w-4 text-brand-400" />
            <span className="text-lg font-semibold">
              {action.sell_symbol} <span className="text-slate-500 mx-1">&rarr;</span> {action.buy_symbol}
            </span>
          </div>
          <span className="rounded-full px-2 py-0.5 text-xs font-medium bg-brand-500/20 text-brand-400">
            SWAP
          </span>
        </div>
        <p className="mb-3 text-sm font-medium text-white">{action.detail}</p>
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div className="rounded-lg bg-red-500/[0.05] border border-red-500/10 p-2">
            <p className="font-medium text-red-400 mb-1">Sell {action.sell_symbol}</p>
            <p className="text-slate-400">{mask(String(action.sell_shares?.toFixed(4) ?? ""))} shares @ {formatCurrency(action.sell_price ?? 0)}</p>
            <p className="text-slate-400">{mask(formatCurrency(action.sell_amount ?? 0))}
              {action.sell_pnl_pct != null && (
                <span className={cn("ml-1", action.sell_pnl_pct >= 0 ? "text-emerald-400" : "text-red-400")}>
                  {mask(formatPercent(action.sell_pnl_pct))}
                </span>
              )}
            </p>
          </div>
          <div className="rounded-lg bg-emerald-500/[0.05] border border-emerald-500/10 p-2">
            <p className="font-medium text-emerald-400 mb-1">Buy {action.buy_symbol}</p>
            <p className="text-slate-400">{action.buy_shares} shares @ ~{formatCurrency(action.buy_price ?? 0)}</p>
            <p className="text-slate-400">{mask(formatCurrency(action.buy_amount ?? 0))}
              {action.buy_strength != null && (
                <span className="ml-1 text-emerald-400">{(action.buy_strength * 100).toFixed(0)}% signal</span>
              )}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // BUY
  return (
    <div className="glass-card p-4 border border-emerald-500/20 bg-emerald-500/[0.03]">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-emerald-400" />
          <span className="text-lg font-semibold">{action.symbol}</span>
        </div>
        <div className="flex items-center gap-2">
          {action.strength != null && (
            <SignalBadge signal="BUY" strength={action.strength} />
          )}
        </div>
      </div>
      <p className="mb-3 text-sm font-medium text-white">{action.detail}</p>
      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400">
        <span>Shares: {action.shares}</span>
        <span>Price: ~{formatCurrency(action.price ?? 0)}</span>
        <span>Cost: {mask(formatCurrency(action.dollar_amount ?? 0))}</span>
        {action.pct_of_portfolio != null && (
          <span>{mask(`${action.pct_of_portfolio.toFixed(1)}%`)} of portfolio</span>
        )}
        {action.sector && <span className="text-slate-500">{action.sector}</span>}
      </div>
      {action.reasons && action.reasons.length > 0 && (
        <ul className="mt-2 space-y-0.5">
          {action.reasons.filter(r => !r.startsWith("Price:") && !r.startsWith("ATR:")).slice(0, 4).map((r, i) => (
            <li key={i} className="text-xs text-slate-500">
              <ScoreTag text={r} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function SignalsPage() {
  return (
    <Suspense>
      <SignalsContent />
    </Suspense>
  );
}

function SignalsContent() {
  const searchParams = useSearchParams();
  const qc = useQueryClient();

  const [checkedSymbol, setCheckedSymbol] = useState<string | null>(
    () => searchParams.get("check")
  );

  const { mask } = usePrivacy();
  const { data: symbols = [] } = useSymbols();
  const { data: plan, isLoading: planLoading, isFetching: refreshing } = useActionPlan();
  const { data: checked, isLoading: checkLoading } = useSignalCheck(checkedSymbol);

  const refresh = useCallback(() => {
    qc.invalidateQueries({ queryKey: queryKeys.actionPlan });
  }, [qc]);

  function checkSymbol(symbol: string) {
    setCheckedSymbol(symbol);
    qc.invalidateQueries({ queryKey: queryKeys.signal(symbol) });
  }

  const sells = plan?.actions.filter(a => a.type === "SELL") ?? [];
  const swaps = plan?.actions.filter(a => a.type === "SWAP") ?? [];
  const buys = plan?.actions.filter(a => a.type === "BUY") ?? [];
  const hasActions = sells.length > 0 || swaps.length > 0 || buys.length > 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Action Plan</h1>
        <button
          onClick={refresh}
          disabled={refreshing}
          className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-300 transition-colors hover:bg-white/10"
        >
          <RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} />
          Refresh
        </button>
      </div>

      {/* Portfolio summary bar */}
      {plan && (
        <div className="glass-card flex flex-wrap items-center gap-4 px-5 py-3 text-sm">
          <div>
            <span className="text-slate-500 mr-1">Portfolio:</span>
            <span className="font-medium">{mask(formatCurrency(plan.portfolio_value))}</span>
          </div>
          <div>
            <span className="text-slate-500 mr-1">Cash:</span>
            <span className="font-medium">{mask(formatCurrency(plan.cash))}</span>
          </div>
          <div>
            <span className="text-slate-500 mr-1">Positions:</span>
            <span className="font-medium">{plan.num_positions}/{plan.max_positions}</span>
          </div>
          {hasActions && (
            <div className="ml-auto flex items-center gap-2">
              {sells.length > 0 && (
                <span className="rounded-full bg-red-500/20 px-2 py-0.5 text-xs text-red-400">
                  {sells.length} sell{sells.length > 1 ? "s" : ""}
                </span>
              )}
              {swaps.length > 0 && (
                <span className="rounded-full bg-brand-500/20 px-2 py-0.5 text-xs text-brand-400">
                  {swaps.length} swap{swaps.length > 1 ? "s" : ""}
                </span>
              )}
              {buys.length > 0 && (
                <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-xs text-emerald-400">
                  {buys.length} buy{buys.length > 1 ? "s" : ""}
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Symbol search */}
      <SearchBar
        symbols={symbols}
        onSelect={checkSymbol}
        placeholder="Search any symbol to check signal..."
      />

      {/* Checked symbol result */}
      {checkLoading && checkedSymbol && (
        <div className="glass-card p-5">
          <div className="mb-3 flex items-center justify-between">
            <div className="space-y-2">
              <Skeleton className="h-6 w-28" />
              <Skeleton className="h-3.5 w-20" />
            </div>
            <div className="flex items-center gap-3">
              <Skeleton className="h-3.5 w-12" />
              <Skeleton className="h-6 w-20" />
              <Skeleton className="h-5 w-20 rounded-full" />
            </div>
          </div>
          <div className="space-y-2">
            {[44, 36, 40, 32].map((w, i) => (
              <div key={i} className="flex items-center justify-between">
                <Skeleton className={`h-3.5 w-[${w}%]`} />
                <Skeleton className="h-3 w-8" />
              </div>
            ))}
          </div>
          <Skeleton className="mt-3 h-3 w-14" />
        </div>
      )}
      {checked && !checkLoading && (
        <div className="glass-card p-5">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h3 className="text-xl font-bold">{checked.symbol}</h3>
              {checked.sector && (
                <p className="text-sm text-slate-500">{checked.sector}</p>
              )}
            </div>
            <div className="flex items-center gap-3">
              {checked.score !== undefined && checked.score !== 0 && (
                <span className="text-sm font-mono text-slate-500">
                  {checked.score > 0 ? "+" : ""}{checked.score}/9
                </span>
              )}
              {checked.price && (
                <span className="text-lg font-semibold">
                  {formatCurrency(checked.price)}
                </span>
              )}
              <SignalBadge signal={checked.signal} strength={checked.strength} />
            </div>
          </div>
          <ul className="space-y-1">
            {checked.reasons.map((r, i) => (
              <li key={i} className="text-sm text-slate-400">
                <ScoreTag text={r} />
              </li>
            ))}
          </ul>
          <button
            onClick={() => setCheckedSymbol(null)}
            className="mt-3 text-xs text-slate-500 hover:text-white"
          >
            Dismiss
          </button>
        </div>
      )}
      {checked && !checkLoading && (
        <PriceChart symbol={checked.symbol} />
      )}

      {/* Action plan */}
      {planLoading ? (
        <div className="space-y-6">
          <div>
            <div className="mb-3 flex items-center gap-2">
              <Skeleton className="h-2 w-2 rounded-full" />
              <Skeleton className="h-5 w-24" />
            </div>
            <SignalCardsSkeleton count={3} />
          </div>
        </div>
      ) : (
        <>
          {/* Sells */}
          {sells.length > 0 && (
            <div>
              <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
                <AlertTriangle className="h-4 w-4 text-red-400" />
                Sells
              </h2>
              <p className="mb-3 text-xs text-slate-500">Execute these first — stops, profit-taking, and exit signals</p>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {sells.map((a, i) => <ActionCard key={`sell-${i}`} action={a} />)}
              </div>
            </div>
          )}

          {/* Swaps */}
          {swaps.length > 0 && (
            <div>
              <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
                <ArrowRight className="h-4 w-4 text-brand-400" />
                Swaps
              </h2>
              <p className="mb-3 text-xs text-slate-500">Replace weaker holdings with stronger opportunities</p>
              <div className="grid gap-4 lg:grid-cols-2">
                {swaps.map((a, i) => <ActionCard key={`swap-${i}`} action={a} />)}
              </div>
            </div>
          )}

          {/* Buys */}
          {buys.length > 0 && (
            <div>
              <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
                <TrendingUp className="h-4 w-4 text-emerald-400" />
                Buys
              </h2>
              <p className="mb-3 text-xs text-slate-500">New positions — only if you have available slots and cash</p>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {buys.map((a, i) => <ActionCard key={`buy-${i}`} action={a} />)}
              </div>
            </div>
          )}

          {/* No actions */}
          {!hasActions && (
            <div className="glass-card flex flex-col items-center gap-2 py-12">
              <Zap className="h-8 w-8 text-slate-600" />
              <p className="text-sm text-slate-500">No trades needed right now</p>
              <p className="text-xs text-slate-600">Portfolio is on track. Check back later or search a symbol above.</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
