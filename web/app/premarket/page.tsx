"use client";

import { useCallback, useMemo } from "react";
import { Clock, RefreshCw, Sunrise, Thermometer } from "lucide-react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { usePremarketMovers, queryKeys } from "@/lib/hooks";
import { cn, formatCurrency } from "@/lib/utils";

function nextOpenCountdown(): string {
  const now = new Date();
  const etNow = new Date(
    now.toLocaleString("en-US", { timeZone: "America/Toronto" })
  );
  const open = new Date(etNow);
  open.setHours(9, 30, 0, 0);
  if (etNow >= open) {
    open.setDate(open.getDate() + 1);
  }
  const diffMs = open.getTime() - etNow.getTime();
  const totalMins = Math.max(0, Math.floor(diffMs / 60_000));
  const hours = Math.floor(totalMins / 60);
  const mins = totalMins % 60;
  return `${hours}h ${mins}m`;
}

export default function PreMarketPage() {
  const qc = useQueryClient();
  const { data, isLoading, isFetching } = usePremarketMovers();

  const refresh = useCallback(() => {
    qc.invalidateQueries({ queryKey: queryKeys.premarket });
  }, [qc]);

  const movers = useMemo(
    () =>
      data?.movers
        ?.slice()
        .sort((a, b) => Math.abs(b.change_pct) - Math.abs(a.change_pct)) ?? [],
    [data]
  );

  const positive = movers.filter((m) => m.change_pct >= 0).length;
  const negative = movers.filter((m) => m.change_pct < 0).length;
  const avgAbsMove =
    movers.length > 0
      ? movers.reduce((sum, m) => sum + Math.abs(m.change_pct * 100), 0) / movers.length
      : 0;

  return (
    <div className="space-y-6">
      <div className="ph">
        <div>
          <h1>Pre-market</h1>
          <p className="sub">
            Toronto open in <span className="font-mono text-brand-300">{nextOpenCountdown()}</span>
            <span className="divider">·</span>
            {movers.length} movers tracked
            <span className="divider">·</span>
            <span className="text-slate-400">US session proxy for CDRs</span>
          </p>
        </div>
        <div className="actions">
          <button
            onClick={refresh}
            disabled={isFetching}
            className="flex items-center gap-2 rounded-lg bg-brand-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-500 disabled:opacity-70"
          >
            <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
            Refresh
          </button>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div className="stat2">
          <div className="lbl">
            <span>Open countdown</span>
            <span className="ico">
              <Clock />
            </span>
          </div>
          <div className="val font-mono text-brand-300">{nextOpenCountdown()}</div>
          <div className="chg neu">09:30 ET</div>
        </div>

        <div className="stat2">
          <div className="lbl">
            <span>Movers</span>
            <span className="ico">
              <Sunrise />
            </span>
          </div>
          <div className="val">{movers.length}</div>
          <div className="chg neu">{positive} up · {negative} down</div>
        </div>

        <div className="stat2">
          <div className="lbl">
            <span>Avg abs move</span>
            <span className="ico">
              <Thermometer />
            </span>
          </div>
          <div className="val">{avgAbsMove.toFixed(2)}%</div>
          <div className="chg neu">across tracked CDRs</div>
        </div>

        <div className="stat2">
          <div className="lbl">
            <span>Data cadence</span>
            <span className="ico">
              <RefreshCw />
            </span>
          </div>
          <div className="val">{isFetching ? "Refreshing" : "Live"}</div>
          <div className={cn("chg", isFetching ? "neu" : "pos")}>
            {isFetching ? "updating now" : "ready"}
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="glass-card p-8 text-center text-sm text-slate-500">
          Loading pre-market movers...
        </div>
      ) : movers.length === 0 ? (
        <div className="glass-card p-8 text-center text-sm text-slate-500">
          No pre-market data available right now.
        </div>
      ) : (
        <>
          <div className="card">
            <div className="head">
              <h3>Your holdings overnight proxy</h3>
              <span className="sub">sorted by absolute move</span>
            </div>
            <table className="w-full text-sm">
              <thead className="border-b border-white/10">
                <tr>
                  <th className="px-4 py-3 text-left font-mono text-[11px] uppercase tracking-[0.08em] text-slate-500">
                    Symbol
                  </th>
                  <th className="px-4 py-3 text-right font-mono text-[11px] uppercase tracking-[0.08em] text-slate-500">
                    Premarket
                  </th>
                  <th className="px-4 py-3 text-right font-mono text-[11px] uppercase tracking-[0.08em] text-slate-500">
                    O/N change
                  </th>
                  <th className="px-4 py-3 text-left font-mono text-[11px] uppercase tracking-[0.08em] text-slate-500">
                    US pair
                  </th>
                  <th className="px-4 py-3 text-right font-mono text-[11px] uppercase tracking-[0.08em] text-slate-500">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {movers.map((m) => {
                  const pct = m.change_pct * 100;
                  return (
                    <tr key={m.cdr_symbol} className="hover:bg-white/[0.02]">
                      <td className="px-4 py-3 font-medium text-slate-200">{m.cdr_symbol}</td>
                      <td className="px-4 py-3 text-right font-mono text-slate-300">
                        {formatCurrency(m.premarket_price)}
                      </td>
                      <td className={cn(
                        "px-4 py-3 text-right font-mono",
                        pct >= 0 ? "text-emerald-400" : "text-red-400"
                      )}>
                        {pct >= 0 ? "+" : ""}
                        {pct.toFixed(2)}%
                      </td>
                      <td className="px-4 py-3 text-slate-500">{m.us_symbol}</td>
                      <td className="px-4 py-3 text-right">
                        <Link
                          href={`/signals?check=${encodeURIComponent(m.cdr_symbol)}`}
                          className="rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-1.5 text-xs text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.08]"
                        >
                          Open signal
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="card">
            <div className="head">
              <h3>Gap candidates</h3>
              <span className="sub">largest pre-market dislocations</span>
            </div>
            <div className="divide-y divide-white/5">
              {movers.slice(0, 5).map((m) => {
                const pct = m.change_pct * 100;
                return (
                  <Link
                    key={`gap-${m.cdr_symbol}`}
                    href={`/signals?check=${encodeURIComponent(m.cdr_symbol)}`}
                    className="flex items-center gap-4 px-4 py-3 transition-colors hover:bg-white/[0.02]"
                  >
                    <div className={cn(
                      "w-16 text-right font-mono text-sm",
                      pct >= 0 ? "text-emerald-400" : "text-red-400"
                    )}>
                      {pct >= 0 ? "+" : ""}
                      {pct.toFixed(2)}%
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="font-semibold text-slate-100">{m.cdr_symbol}</p>
                      <p className="truncate text-xs text-slate-500">
                        {m.us_symbol} · {formatCurrency(m.premarket_price)}
                      </p>
                    </div>
                    <span className="badge badge-hold">PRE</span>
                  </Link>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
