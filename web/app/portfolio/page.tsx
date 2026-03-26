"use client";

import { useEffect, useState } from "react";
import { Briefcase, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import type { PortfolioSummary, HoldingAdvice } from "@/lib/api";
import {
  formatCurrency,
  formatPercent,
  pnlColor,
  cn,
} from "@/lib/utils";
import { StatCard } from "@/components/ui/stat-card";
import { DataTable } from "@/components/ui/data-table";
import { SignalBadge } from "@/components/ui/signal-badge";
import { CardSkeleton, TableSkeleton } from "@/components/ui/loading";

export default function PortfolioPage() {
  const [data, setData] = useState<PortfolioSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<HoldingAdvice | null>(null);

  async function load() {
    setLoading(true);
    try {
      setData(await api.getHoldings());
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const columns = [
    {
      key: "symbol",
      header: "Symbol",
      render: (h: HoldingAdvice) => (
        <span className="font-medium">{h.symbol}</span>
      ),
    },
    {
      key: "quantity",
      header: "Qty",
      className: "text-right",
      render: (h: HoldingAdvice) => h.quantity.toFixed(2),
    },
    {
      key: "avg_cost",
      header: "Avg Cost",
      className: "text-right",
      render: (h: HoldingAdvice) => formatCurrency(h.avg_cost),
    },
    {
      key: "price",
      header: "Price",
      className: "text-right",
      render: (h: HoldingAdvice) => formatCurrency(h.current_price),
    },
    {
      key: "value",
      header: "Value",
      className: "text-right",
      render: (h: HoldingAdvice) => formatCurrency(h.market_value),
    },
    {
      key: "pnl",
      header: "P&L",
      className: "text-right",
      render: (h: HoldingAdvice) => (
        <span className={pnlColor(h.pnl)}>
          {formatCurrency(h.pnl)} ({formatPercent(h.pnl_pct)})
        </span>
      ),
    },
    {
      key: "signal",
      header: "Signal",
      render: (h: HoldingAdvice) => (
        <SignalBadge signal={h.signal} strength={h.strength} />
      ),
    },
    {
      key: "action",
      header: "Advice",
      render: (h: HoldingAdvice) => (
        <span className="text-xs text-slate-400">{h.action}</span>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Portfolio</h1>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-300 transition-colors hover:bg-white/10 disabled:opacity-50"
        >
          <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
          Refresh
        </button>
      </div>

      {/* Summary stats */}
      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
      ) : data ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard
            title="Total Value"
            value={data.total_value}
            format="currency"
            icon={Briefcase}
          />
          <StatCard
            title="Cash"
            value={data.cash}
            format="currency"
          />
          <StatCard
            title="Total P&L"
            value={data.total_pnl}
            format="currency"
            change={data.total_pnl_pct}
          />
          <StatCard
            title="Positions"
            value={data.holdings.length}
          />
        </div>
      ) : null}

      {/* Holdings table */}
      {loading ? (
        <TableSkeleton rows={4} />
      ) : (
        <DataTable
          columns={columns}
          data={data?.holdings ?? []}
          keyFn={(h) => h.symbol}
          emptyMessage="No holdings — record a trade or upload a screenshot"
          onRowClick={(h) => setSelected(selected?.symbol === h.symbol ? null : h)}
        />
      )}

      {/* Expanded detail for selected holding */}
      {selected && (
        <div className="glass-card p-5">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-lg font-semibold">{selected.symbol}</h3>
            <button
              onClick={() => setSelected(null)}
              className="text-xs text-slate-500 hover:text-white"
            >
              Close
            </button>
          </div>
          <div className="space-y-2 text-sm">
            <p>
              <span className="text-slate-400">Action: </span>
              <span className="font-medium">{selected.action}</span>
            </p>
            <p className="text-slate-400">{selected.action_detail}</p>
            {selected.reasons.length > 0 && (
              <div>
                <p className="mb-1 text-slate-400">Reasons:</p>
                <ul className="list-inside list-disc space-y-0.5 text-slate-300">
                  {selected.reasons.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              </div>
            )}
            {selected.alternative && (
              <div className="mt-3 rounded-lg border border-brand-500/20 bg-brand-500/5 p-3">
                <p className="text-xs text-brand-400">
                  Swap suggestion: Consider{" "}
                  <span className="font-medium">
                    {String(selected.alternative.symbol ?? "")}
                  </span>
                  {selected.alternative.reason
                    ? ` — ${String(selected.alternative.reason)}`
                    : null}
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
