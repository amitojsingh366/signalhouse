"use client";

import { Suspense, useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { Zap, RefreshCw, AlertTriangle } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useRecommendations, useSymbols, useSignalCheck, queryKeys } from "@/lib/hooks";
import type { ExitAlert, SignalOut } from "@/lib/api";
import { formatCurrency, formatPercent, cn, pnlColor } from "@/lib/utils";
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

function SignalCard({ signal, expanded, onToggle }: { signal: SignalOut; expanded: boolean; onToggle: () => void }) {
  const { mask } = usePrivacy();
  return (
    <div className="glass-card p-4 cursor-pointer transition-colors hover:bg-white/[0.05]" onClick={onToggle}>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-lg font-semibold">{signal.symbol}</span>
        <div className="flex items-center gap-2">
          {signal.score !== undefined && signal.score !== 0 && (
            <span className="text-xs font-mono text-slate-500">
              {signal.score > 0 ? "+" : ""}{signal.score}/9
            </span>
          )}
          <SignalBadge signal={signal.signal} strength={signal.strength} />
        </div>
      </div>
      {signal.price && (
        <p className="mb-2 text-sm text-slate-400">
          Price: {formatCurrency(signal.price)}
        </p>
      )}
      {signal.sector && (
        <p className="mb-2 text-xs text-slate-500">{signal.sector}</p>
      )}
      <ul className="space-y-1">
        {signal.reasons.map((r, i) => (
          <li key={i} className="text-xs text-slate-400">
            <ScoreTag text={r} />
          </li>
        ))}
      </ul>
      {expanded && (
        <div className="mt-4" onClick={(e) => e.stopPropagation()}>
          <PriceChart symbol={signal.symbol} />
        </div>
      )}
    </div>
  );
}

function ExitAlertCard({ alert, onClick }: { alert: ExitAlert; onClick: () => void }) {
  const { mask } = usePrivacy();
  const isHigh = alert.severity === "high";
  return (
    <div
      className={cn(
        "glass-card p-4 border cursor-pointer transition-colors hover:bg-white/[0.05]",
        isHigh ? "border-red-500/30 bg-red-500/[0.05]" : "border-amber-500/20 bg-amber-500/[0.03]"
      )}
      onClick={onClick}
    >
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertTriangle className={cn("h-4 w-4", isHigh ? "text-red-400" : "text-amber-400")} />
          <span className="text-lg font-semibold">{alert.symbol}</span>
        </div>
        <span className={cn(
          "rounded-full px-2 py-0.5 text-xs font-medium",
          isHigh ? "bg-red-500/20 text-red-400" : "bg-amber-500/20 text-amber-400"
        )}>
          {alert.reason}
        </span>
      </div>
      <p className="mb-2 text-sm text-slate-400">{alert.detail}</p>
      <div className="flex items-center gap-4 text-xs text-slate-500">
        <span>Entry: {mask(formatCurrency(alert.entry_price))}</span>
        <span>Current: {formatCurrency(alert.current_price)}</span>
        <span className={cn("font-medium", alert.pnl_pct >= 0 ? "text-emerald-400" : "text-red-400")}>
          {mask(formatPercent(alert.pnl_pct))}
        </span>
      </div>
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

  // Checked symbol state — driven by search bar or ?check= param
  const [checkedSymbol, setCheckedSymbol] = useState<string | null>(
    () => searchParams.get("check")
  );
  const [expandedSymbol, setExpandedSymbol] = useState<string | null>(null);

  const { mask } = usePrivacy();
  const { data: symbols = [] } = useSymbols();
  const { data: recs, isLoading: recsLoading, isFetching: refreshing } = useRecommendations();
  const { data: checked, isLoading: checkLoading } = useSignalCheck(checkedSymbol);

  const refresh = useCallback(() => {
    qc.invalidateQueries({ queryKey: queryKeys.recommendations });
  }, [qc]);

  function checkSymbol(symbol: string) {
    setCheckedSymbol(symbol);
    // Invalidate so it refetches even if we checked this symbol before
    qc.invalidateQueries({ queryKey: queryKeys.signal(symbol) });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Signals</h1>
        <button
          onClick={refresh}
          disabled={refreshing}
          className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-300 transition-colors hover:bg-white/10"
        >
          <RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} />
          Refresh
        </button>
      </div>

      {/* Symbol search — always visible immediately */}
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
            <div className="flex items-center justify-between">
              <Skeleton className="h-3.5 w-[44%]" />
              <Skeleton className="h-3 w-8" />
            </div>
            <div className="flex items-center justify-between">
              <Skeleton className="h-3.5 w-[36%]" />
              <Skeleton className="h-3 w-8" />
            </div>
            <div className="flex items-center justify-between">
              <Skeleton className="h-3.5 w-[40%]" />
              <Skeleton className="h-3 w-8" />
            </div>
            <div className="flex items-center justify-between">
              <Skeleton className="h-3.5 w-[32%]" />
              <Skeleton className="h-3 w-8" />
            </div>
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

      {/* Price chart for checked symbol */}
      {checked && !checkLoading && (
        <PriceChart symbol={checked.symbol} />
      )}

      {/* Signal cards — show cached data or loading state */}
      {recsLoading ? (
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
          {/* Exit alerts — shown first (stop losses, max hold, sell signals for holdings) */}
          {recs && recs.exit_alerts && recs.exit_alerts.length > 0 && (
            <div>
              <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
                <AlertTriangle className="h-4 w-4 text-red-400" />
                Exit Alerts
              </h2>
              <p className="mb-3 text-xs text-slate-500">Stop losses, time exits, and sell signals for your holdings — act on these first</p>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {recs.exit_alerts.map((a) => (
                  <ExitAlertCard key={a.symbol} alert={a} onClick={() => checkSymbol(a.symbol)} />
                ))}
              </div>
            </div>
          )}

          {/* Buy signals */}
          {recs && recs.buys.length > 0 && (
            <div>
              <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
                <span className="h-2 w-2 rounded-full bg-brand-400" />
                Buy Signals
              </h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {recs.buys.map((s) => (
                  <SignalCard
                    key={s.symbol}
                    signal={s}
                    expanded={expandedSymbol === s.symbol}
                    onToggle={() => setExpandedSymbol(expandedSymbol === s.symbol ? null : s.symbol)}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Sell signals */}
          {recs && recs.sells.length > 0 && (
            <div>
              <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
                <span className="h-2 w-2 rounded-full bg-red-400" />
                Sell Signals
              </h2>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {recs.sells.map((s) => (
                  <SignalCard
                    key={s.symbol}
                    signal={s}
                    expanded={expandedSymbol === s.symbol}
                    onToggle={() => setExpandedSymbol(expandedSymbol === s.symbol ? null : s.symbol)}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Funding suggestions */}
          {recs && recs.funding.length > 0 && (
            <div className="glass-card p-5">
              <h3 className="mb-3 text-sm font-medium text-slate-400">
                Sell-to-Fund Suggestions
              </h3>
              <div className="space-y-2">
                {recs.funding.map((f, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between rounded-lg border border-white/5 bg-white/5 px-4 py-2 text-sm"
                  >
                    <span>
                      Sell{" "}
                      <span className="font-medium">{String(f.sell ?? "")}</span> to
                      buy{" "}
                      <span className="font-medium">{String(f.buy ?? "")}</span>
                    </span>
                    {f.reason ? (
                      <span className="text-xs text-slate-500">
                        {String(f.reason)}
                      </span>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Watchlist sell signals (not held) */}
          {recs && recs.watchlist_sells && recs.watchlist_sells.length > 0 && (
            <div>
              <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
                <span className="h-2 w-2 rounded-full bg-amber-400" />
                Watchlist Alerts
              </h2>
              <p className="mb-3 text-xs text-slate-500">Sell signals for symbols you don&apos;t hold — avoid buying these</p>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {recs.watchlist_sells.map((s) => (
                  <SignalCard
                    key={s.symbol}
                    signal={s}
                    expanded={expandedSymbol === s.symbol}
                    onToggle={() => setExpandedSymbol(expandedSymbol === s.symbol ? null : s.symbol)}
                  />
                ))}
              </div>
            </div>
          )}

          {/* No signals message */}
          {recs && recs.buys.length === 0 && recs.sells.length === 0 && (!recs.exit_alerts || recs.exit_alerts.length === 0) && (!recs.watchlist_sells || recs.watchlist_sells.length === 0) && (
            <div className="glass-card flex flex-col items-center gap-2 py-12">
              <Zap className="h-8 w-8 text-slate-600" />
              <p className="text-sm text-slate-500">No active signals right now</p>
              <p className="text-xs text-slate-600">Try refreshing or check a specific symbol above</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
