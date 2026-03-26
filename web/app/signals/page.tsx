"use client";

import { Suspense, useEffect, useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { Zap, RefreshCw, Search } from "lucide-react";
import { api, getCache, fetchWithCache } from "@/lib/api";
import type { RecommendationOut, SignalOut, SymbolInfo } from "@/lib/api";
import { formatCurrency, formatPercent, cn, pnlColor } from "@/lib/utils";
import { SignalBadge } from "@/components/ui/signal-badge";
import { SearchBar } from "@/components/ui/search-bar";
import { Skeleton, SignalCardsSkeleton, CardSkeleton } from "@/components/ui/loading";
import { PriceChart } from "@/components/ui/price-chart";

function SignalCard({ signal, expanded, onToggle }: { signal: SignalOut; expanded: boolean; onToggle: () => void }) {
  return (
    <div className="glass-card p-4 cursor-pointer transition-colors hover:bg-white/[0.05]" onClick={onToggle}>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-lg font-semibold">{signal.symbol}</span>
        <SignalBadge signal={signal.signal} strength={signal.strength} />
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
            {r}
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

export default function SignalsPage() {
  return (
    <Suspense>
      <SignalsContent />
    </Suspense>
  );
}

function SignalsContent() {
  const searchParams = useSearchParams();

  // Symbols load independently for the search bar (lightweight)
  const [symbols, setSymbols] = useState<SymbolInfo[]>(
    () => getCache<SymbolInfo[]>("/api/symbols") ?? []
  );

  // Recommendations load async with cache
  const [recs, setRecs] = useState<RecommendationOut | null>(
    () => getCache<RecommendationOut>("/api/signals/recommend?n=5")
  );
  const [recsLoading, setRecsLoading] = useState(!recs);
  const [refreshing, setRefreshing] = useState(false);

  // Symbol check state
  const [checked, setChecked] = useState<SignalOut | null>(null);
  const [checkLoading, setCheckLoading] = useState(false);

  // Expanded signal card (shows price chart)
  const [expandedSymbol, setExpandedSymbol] = useState<string | null>(null);

  // Load symbols (for search bar) immediately
  useEffect(() => {
    fetchWithCache<SymbolInfo[]>(
      "/api/symbols",
      (cached) => setSymbols(cached),
      (fresh) => setSymbols(fresh),
    );
  }, []);

  // Load recommendations with cache-first
  useEffect(() => {
    fetchWithCache<RecommendationOut>(
      "/api/signals/recommend?n=5",
      (cached) => { setRecs(cached); setRecsLoading(false); },
      (fresh) => { setRecs(fresh); setRecsLoading(false); },
      () => setRecsLoading(false),
    );
  }, []);

  // Handle ?check= query parameter from command search
  useEffect(() => {
    const sym = searchParams.get("check");
    if (sym) {
      checkSymbol(sym);
    }
  }, [searchParams]); // eslint-disable-line react-hooks/exhaustive-deps

  // Force refresh (bypasses cache)
  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const r = await api.getRecommendations(5);
      setRecs(r);
    } catch (err) {
      console.error(err);
    } finally {
      setRefreshing(false);
    }
  }, []);

  async function checkSymbol(symbol: string) {
    setCheckLoading(true);
    try {
      const sig = await api.checkSignal(symbol);
      setChecked(sig);
    } catch (err) {
      console.error(err);
    } finally {
      setCheckLoading(false);
    }
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
      {checkLoading && (
        <CardSkeleton />
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
                {r}
              </li>
            ))}
          </ul>
          <button
            onClick={() => setChecked(null)}
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

          {/* No signals message */}
          {recs && recs.buys.length === 0 && recs.sells.length === 0 && (
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
