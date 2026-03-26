"use client";

import { use, useEffect, useState } from "react";
import { Briefcase, RefreshCw, Pencil, Trash2, X, Check, DollarSign } from "lucide-react";
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

function EditHoldingPanel({
  holding,
  onSave,
  onDelete,
  onClose,
}: {
  holding: HoldingAdvice;
  onSave: (symbol: string, quantity: number, avg_cost: number) => Promise<void>;
  onDelete: (symbol: string) => Promise<void>;
  onClose: () => void;
}) {
  const [qty, setQty] = useState(holding.quantity.toString());
  const [cost, setCost] = useState(holding.avg_cost.toString());
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      await onSave(holding.symbol, parseFloat(qty), parseFloat(cost));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!confirm(`Delete ${holding.symbol} from your holdings?`)) return;
    setDeleting(true);
    try {
      await onDelete(holding.symbol);
    } finally {
      setDeleting(false);
    }
  }

  useEffect(() => {
    setQty(holding.quantity.toString());
    setCost(holding.avg_cost.toString());
  }, [holding]);

  return (
    <div className="glass-card p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Pencil className="h-4 w-4 text-accent" />
          Edit {holding.symbol}
        </h3>
        <button onClick={onClose} className="text-slate-500 hover:text-white">
          <X className="h-5 w-5" />
        </button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 mb-4">
        <div>
          <label className="mb-1 block text-xs text-slate-400">Quantity</label>
          <input
            type="number"
            step="any"
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-accent/50"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-400">Avg Cost per Share</label>
          <input
            type="number"
            step="any"
            value={cost}
            onChange={(e) => setCost(e.target.value)}
            className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-accent/50"
          />
        </div>
      </div>

      {/* Current info */}
      <div className="mb-4 grid grid-cols-3 gap-3 rounded-lg border border-white/5 bg-white/5 p-3">
        <div>
          <p className="text-xs text-slate-500">Current Price</p>
          <p className="text-sm font-medium">{formatCurrency(holding.current_price)}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Market Value</p>
          <p className="text-sm font-medium">{formatCurrency(holding.market_value)}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">P&L</p>
          <p className={cn("text-sm font-medium", pnlColor(holding.pnl))}>
            {formatCurrency(holding.pnl)} ({formatPercent(holding.pnl_pct)})
          </p>
        </div>
      </div>

      {/* Signal & advice */}
      <div className="mb-4 space-y-2">
        <div className="flex items-center gap-2">
          <SignalBadge signal={holding.signal} strength={holding.strength} />
          <span className="text-sm text-slate-400">{holding.action}</span>
        </div>
        <p className="text-xs text-slate-500">{holding.action_detail}</p>
        {holding.reasons.length > 0 && (
          <ul className="list-inside list-disc space-y-0.5 text-xs text-slate-400">
            {holding.reasons.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        )}
        {holding.alternative && (
          <div className="rounded-lg border border-accent/20 bg-accent/5 p-3">
            <p className="text-xs text-accent">
              Swap suggestion: Consider{" "}
              <span className="font-medium">
                {String(holding.alternative.symbol ?? "")}
              </span>
              {holding.alternative.reason
                ? ` — ${String(holding.alternative.reason)}`
                : null}
            </p>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 rounded-lg bg-accent/20 px-4 py-2 text-sm font-medium text-accent transition-colors hover:bg-accent/30 disabled:opacity-50"
        >
          <Check className="h-4 w-4" />
          {saving ? "Saving..." : "Save Changes"}
        </button>
        <button
          onClick={handleDelete}
          disabled={deleting}
          className="flex items-center gap-2 rounded-lg bg-red-500/20 px-4 py-2 text-sm font-medium text-red-400 transition-colors hover:bg-red-500/30 disabled:opacity-50"
        >
          <Trash2 className="h-4 w-4" />
          {deleting ? "Deleting..." : "Delete"}
        </button>
      </div>
    </div>
  );
}

function EditCashPanel({
  currentCash,
  onSave,
  onClose,
}: {
  currentCash: number;
  onSave: (cash: number) => Promise<void>;
  onClose: () => void;
}) {
  const [cash, setCash] = useState(currentCash.toFixed(2));
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      await onSave(parseFloat(cash));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="glass-card p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <DollarSign className="h-4 w-4 text-accent" />
          Edit Cash Balance
        </h3>
        <button onClick={onClose} className="text-slate-500 hover:text-white">
          <X className="h-5 w-5" />
        </button>
      </div>
      <div className="mb-4">
        <label className="mb-1 block text-xs text-slate-400">Cash (CAD)</label>
        <input
          type="number"
          step="0.01"
          value={cash}
          onChange={(e) => setCash(e.target.value)}
          className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-accent/50"
        />
      </div>
      <button
        onClick={handleSave}
        disabled={saving}
        className="flex items-center gap-2 rounded-lg bg-accent/20 px-4 py-2 text-sm font-medium text-accent transition-colors hover:bg-accent/30 disabled:opacity-50"
      >
        <Check className="h-4 w-4" />
        {saving ? "Saving..." : "Save"}
      </button>
    </div>
  );
}

export default function PortfolioPage() {
  const [data, setData] = useState<PortfolioSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<HoldingAdvice | null>(null);
  const [editingCash, setEditingCash] = useState(false);

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

  async function handleSaveHolding(symbol: string, quantity: number, avg_cost: number) {
    await api.updateHolding(symbol, quantity, avg_cost);
    setSelected(null);
    await load();
  }

  async function handleDeleteHolding(symbol: string) {
    await api.deleteHolding(symbol);
    setSelected(null);
    await load();
  }

  async function handleSaveCash(cash: number) {
    await api.updateCash(cash);
    setEditingCash(false);
    await load();
  }

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
      header: "",
      render: (h: HoldingAdvice) => (
        <Pencil className="h-3.5 w-3.5 text-slate-600 transition-colors group-hover:text-accent" />
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
          <button onClick={() => { setEditingCash(true); setSelected(null); }} className="text-left">
            <StatCard
              title="Cash (click to edit)"
              value={data.cash}
              format="currency"
              icon={DollarSign}
              className="h-full"
            />
          </button>
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

      {/* Cash edit panel */}
      {editingCash && data && (
        <EditCashPanel
          currentCash={data.cash}
          onSave={handleSaveCash}
          onClose={() => setEditingCash(false)}
        />
      )}

      {/* Holdings table */}
      {loading ? (
        <TableSkeleton rows={4} />
      ) : (
        <DataTable
          columns={columns}
          data={data?.holdings ?? []}
          keyFn={(h) => h.symbol}
          emptyMessage="No holdings — record a trade or upload a screenshot"
          onRowClick={(h) => {
            setSelected(selected?.symbol === h.symbol ? null : h);
            setEditingCash(false);
          }}
        />
      )}

      {/* Edit panel for selected holding */}
      {selected && (
        <EditHoldingPanel
          holding={selected}
          onSave={handleSaveHolding}
          onDelete={handleDeleteHolding}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
