"use client";

import { useEffect, useState } from "react";
import { Zap, RefreshCw, Search } from "lucide-react";
import { api } from "@/lib/api";
import type { RecommendationOut, SignalOut, SymbolInfo } from "@/lib/api";
import { formatCurrency, formatPercent, cn, pnlColor } from "@/lib/utils";
import { SignalBadge } from "@/components/ui/signal-badge";
import { SectorChart } from "@/components/ui/sector-chart";
import { SearchBar } from "@/components/ui/search-bar";
import { PageLoader } from "@/components/ui/loading";

function SignalCard({ signal }: { signal: SignalOut }) {
  return (
    <div className="glass-card p-4">
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
    </div>
  );
}

export default function SignalsPage() {
  const [recs, setRecs] = useState<RecommendationOut | null>(null);
  const [symbols, setSymbols] = useState<SymbolInfo[]>([]);
  const [checked, setChecked] = useState<SignalOut | null>(null);
  const [checkLoading, setCheckLoading] = useState(false);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const [r, s] = await Promise.all([
        api.getRecommendations(5),
        api.getSymbols(),
      ]);
      setRecs(r);
      setSymbols(s);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
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

  if (loading) return <PageLoader />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Signals</h1>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-300 transition-colors hover:bg-white/10"
        >
          <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
          Refresh
        </button>
      </div>

      {/* Symbol search */}
      <SearchBar
        symbols={symbols}
        onSelect={checkSymbol}
        placeholder="Search any symbol to check signal..."
      />

      {/* Checked symbol result */}
      {checkLoading && (
        <div className="glass-card flex items-center gap-3 p-4">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
          <span className="text-sm text-slate-400">Analyzing...</span>
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

      {/* Buy signals */}
      {recs && recs.buys.length > 0 && (
        <div>
          <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
            <span className="h-2 w-2 rounded-full bg-green-400" />
            Buy Signals
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {recs.buys.map((s) => (
              <SignalCard key={s.symbol} signal={s} />
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
              <SignalCard key={s.symbol} signal={s} />
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

      {/* Sector exposure */}
      {recs && Object.keys(recs.sector_exposure).length > 0 && (
        <SectorChart exposure={recs.sector_exposure} />
      )}
    </div>
  );
}
