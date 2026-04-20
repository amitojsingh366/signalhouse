"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Briefcase,
  Check,
  DollarSign,
  Layers,
  MoreHorizontal,
  Pencil,
  RefreshCw,
  Trash2,
  TrendingUp,
  Upload,
  Wallet,
  X,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useHoldings, useUpdateHolding, useDeleteHolding, useUpdateCash, queryKeys } from "@/lib/hooks";
import type { HoldingAdvice } from "@/lib/api";
import { formatCurrency, formatPercent, pnlColor, cn } from "@/lib/utils";
import { usePrivacy } from "@/lib/privacy";
import { ScoreBreakdown, ScoreTag } from "@/components/ui/score-breakdown";
import { CardSkeleton, HoldingsTableSkeleton } from "@/components/ui/loading";

const MAX_POSITIONS = 12;

type HoldingsFilter = "all" | "winners" | "losers";

function TrendProxy({ positive }: { positive: boolean }) {
  const stroke = positive ? "#34d399" : "#ef4444";
  const fill = positive ? "rgba(52, 211, 153, 0.16)" : "rgba(239, 68, 68, 0.14)";
  const path = positive
    ? "M2 18 C20 16, 36 12, 52 10 C66 8, 78 7, 94 6"
    : "M2 6 C20 8, 36 12, 52 14 C66 16, 78 17, 94 18";

  return (
    <svg className="spark-sm" viewBox="0 0 96 24" fill="none" aria-hidden>
      <path d={`${path} L94 22 L2 22 Z`} fill={fill} />
      <path d={path} stroke={stroke} strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}

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
  const { mask } = usePrivacy();
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

  return (
    <div className="card">
      <div className="head">
        <h3 className="flex items-center gap-2">
          <Pencil className="h-4 w-4 text-brand-300" />
          Edit {holding.symbol}
        </h3>
        <button onClick={onClose} className="text-slate-500 transition-colors hover:text-white" aria-label="Close edit panel">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="body space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs text-slate-400">Quantity</label>
            <input
              type="number"
              step="any"
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-brand-500/50"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">Avg Cost per Share</label>
            <input
              type="number"
              step="any"
              value={cost}
              onChange={(e) => setCost(e.target.value)}
              className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-brand-500/50"
            />
          </div>
        </div>

        <div className="grid gap-3 rounded-lg border border-white/5 bg-white/5 p-3 sm:grid-cols-3">
          <div>
            <p className="text-xs text-slate-500">Current Price</p>
            <p className="text-sm font-medium">{formatCurrency(holding.current_price)}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Market Value</p>
            <p className="text-sm font-medium">{mask(formatCurrency(holding.market_value))}</p>
          </div>
          <div>
            <p className="text-xs text-slate-500">P&amp;L</p>
            <p className={cn("text-sm font-medium", pnlColor(holding.pnl))}>
              {mask(formatCurrency(holding.pnl))} ({mask(formatPercent(holding.pnl_pct))})
            </p>
          </div>
        </div>

        <div className="space-y-2">
          <p className="text-sm text-slate-400">{holding.action}</p>
          <p className="text-xs text-slate-500">{holding.action_detail}</p>
          <ScoreBreakdown
            total={holding.technical_score + holding.sentiment_score + holding.commodity_score}
            technical={holding.technical_score}
            sentiment={holding.sentiment_score}
            commodity={holding.commodity_score}
          />
          {holding.reasons.length > 0 && (
            <ul className="space-y-0.5 text-xs text-slate-400">
              {holding.reasons.map((reason, index) => (
                <li key={`${holding.symbol}-reason-${index}`}>
                  <ScoreTag text={reason} />
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-500 disabled:opacity-60"
          >
            <Check className="h-4 w-4" />
            {saving ? "Saving..." : "Save changes"}
          </button>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="inline-flex items-center gap-2 rounded-lg border border-red-500/25 bg-red-500/15 px-4 py-2 text-sm font-medium text-red-300 transition-colors hover:bg-red-500/25 disabled:opacity-60"
          >
            <Trash2 className="h-4 w-4" />
            {deleting ? "Deleting..." : "Delete"}
          </button>
        </div>
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
    <div className="card">
      <div className="head">
        <h3 className="flex items-center gap-2">
          <Wallet className="h-4 w-4 text-brand-300" />
          Edit cash balance
        </h3>
        <button onClick={onClose} className="text-slate-500 transition-colors hover:text-white" aria-label="Close cash editor">
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="body space-y-4">
        <div>
          <label className="mb-1 block text-xs text-slate-400">Cash (CAD)</label>
          <input
            type="number"
            step="0.01"
            value={cash}
            onChange={(e) => setCash(e.target.value)}
            className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-brand-500/50"
          />
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-500 disabled:opacity-60"
        >
          <Check className="h-4 w-4" />
          {saving ? "Saving..." : "Save"}
        </button>
      </div>
    </div>
  );
}

export default function PortfolioPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const { data, isLoading: loading, isFetching } = useHoldings();
  const updateHolding = useUpdateHolding();
  const deleteHolding = useDeleteHolding();
  const updateCash = useUpdateCash();
  const { mask } = usePrivacy();

  const [selected, setSelected] = useState<HoldingAdvice | null>(null);
  const [editingCash, setEditingCash] = useState(false);
  const [filter, setFilter] = useState<HoldingsFilter>("all");

  function refresh() {
    qc.invalidateQueries({ queryKey: queryKeys.holdings });
  }

  async function handleSaveHolding(symbol: string, quantity: number, avg_cost: number) {
    await updateHolding.mutateAsync({ symbol, quantity, avg_cost });
    setSelected(null);
  }

  async function handleDeleteHolding(symbol: string) {
    await deleteHolding.mutateAsync(symbol);
    setSelected(null);
  }

  async function handleSaveCash(cash: number) {
    await updateCash.mutateAsync(cash);
    setEditingCash(false);
  }

  const holdings = data?.holdings ?? [];
  const filteredHoldings = useMemo(() => {
    const base = [...holdings].sort((a, b) => b.market_value - a.market_value);
    if (filter === "winners") return base.filter((row) => row.pnl > 0);
    if (filter === "losers") return base.filter((row) => row.pnl < 0);
    return base;
  }, [holdings, filter]);

  const invested = data?.total_cost ?? 0;
  const allocatedPct = data && data.total_value > 0
    ? ((data.total_value - data.cash) / data.total_value) * 100
    : 0;
  const openSlots = Math.max(0, MAX_POSITIONS - holdings.length);

  return (
    <div className="space-y-6">
      <div className="ph">
        <div>
          <h1>Portfolio</h1>
          <p className="sub">
            {holdings.length} positions
            <span className="divider">·</span>
            {mask(formatCurrency(invested))} invested
            <span className="divider">·</span>
            {mask(formatCurrency(data?.cash ?? 0))} cash
            <span className="divider">·</span>
            <span className="text-amber-300">{allocatedPct.toFixed(1)}% allocated</span>
          </p>
        </div>

        <div className="actions">
          <button
            onClick={() => router.push("/upload")}
            className="flex items-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.08]"
          >
            <Upload className="h-4 w-4" />
            Upload screenshot
          </button>
          <button
            onClick={() => {
              setEditingCash(true);
              setSelected(null);
            }}
            className="flex items-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.08]"
          >
            <Pencil className="h-4 w-4" />
            Edit cash
          </button>
          <button
            onClick={() => router.push("/trades")}
            className="flex items-center gap-2 rounded-lg bg-brand-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-500"
          >
            <TrendingUp className="h-4 w-4" />
            Record trade
          </button>
        </div>
      </div>

      {loading ? (
        <div className="grid-4">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
      ) : (
        <div className="grid-4">
          <div className="stat2">
            <div className="lbl">
              <span>Total value</span>
              <span className="ico"><Briefcase className="h-4 w-4" /></span>
            </div>
            <div className="val">{mask(formatCurrency(data?.total_value ?? 0))}</div>
            <div className={cn("chg", (data?.total_pnl ?? 0) >= 0 ? "pos" : "neg")}>
              {data ? mask(formatPercent(data.total_pnl_pct)) : "--"} lifetime
            </div>
          </div>

          <div className="stat2">
            <div className="lbl">
              <span>Total P&amp;L</span>
              <span className="ico"><TrendingUp className="h-4 w-4" /></span>
            </div>
            <div className={cn("val", pnlColor(data?.total_pnl ?? 0))}>{mask(formatCurrency(data?.total_pnl ?? 0))}</div>
            <div className={cn("chg", (data?.total_pnl ?? 0) >= 0 ? "pos" : "neg")}>
              {data ? mask(formatPercent(data.total_pnl_pct)) : "--"}
            </div>
          </div>

          <button
            onClick={() => {
              setEditingCash(true);
              setSelected(null);
            }}
            className="stat2 text-left"
          >
            <div className="lbl">
              <span>Cash available</span>
              <span className="ico"><DollarSign className="h-4 w-4" /></span>
            </div>
            <div className="val">{mask(formatCurrency(data?.cash ?? 0))}</div>
            <div className="chg neu">click to edit</div>
          </button>

          <div className="stat2">
            <div className="lbl">
              <span>Positions</span>
              <span className="ico"><Layers className="h-4 w-4" /></span>
            </div>
            <div className="val">
              {holdings.length}
              <span className="ml-2 text-[13px] font-normal text-slate-500">/ {MAX_POSITIONS}</span>
            </div>
            <div className="chg neu">{openSlots} slots open</div>
          </div>
        </div>
      )}

      {editingCash && data && (
        <EditCashPanel
          currentCash={data.cash}
          onSave={handleSaveCash}
          onClose={() => setEditingCash(false)}
        />
      )}

      <div className="card">
        <div className="head">
          <h3>Holdings</h3>
          <div className="flex items-center gap-3">
            <span className="sub">sorted by value</span>
            <div className="seg">
              <button className={cn(filter === "all" && "on")} onClick={() => setFilter("all")}>All</button>
              <button className={cn(filter === "winners" && "on")} onClick={() => setFilter("winners")}>Winners</button>
              <button className={cn(filter === "losers" && "on")} onClick={() => setFilter("losers")}>Losers</button>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="p-4">
            <HoldingsTableSkeleton rows={6} />
          </div>
        ) : (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th className="r">Qty</th>
                  <th className="r">Avg cost</th>
                  <th className="r">Current</th>
                  <th className="r">Value</th>
                  <th className="r">P&amp;L</th>
                  <th className="r">7d</th>
                  <th>Signal</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filteredHoldings.map((row) => {
                  const score = row.technical_score + row.sentiment_score + row.commodity_score;
                  const signalLabel = row.signal.toUpperCase() === "BUY"
                    ? `BUY ${(row.strength * 100).toFixed(0)}%`
                    : row.signal.toUpperCase() === "SELL"
                      ? row.action.toUpperCase().includes("URGENT") ? "URGENT" : "SELL"
                      : "HOLD";
                  const signalClass = row.signal.toUpperCase() === "BUY"
                    ? "pb-buy"
                    : row.signal.toUpperCase() === "SELL"
                      ? (row.action.toUpperCase().includes("URGENT") ? "pb-urgent" : "pb-sell")
                      : "pb-hold";

                  return (
                    <tr key={row.symbol}>
                      <td>
                        <button
                          onClick={() => router.push(`/signals?check=${encodeURIComponent(row.symbol)}`)}
                          className="font-semibold text-slate-100 transition-colors hover:text-brand-300"
                        >
                          {row.symbol}
                        </button>
                      </td>
                      <td className="r mono">{mask(row.quantity.toFixed(2))}</td>
                      <td className="r mono">{mask(formatCurrency(row.avg_cost))}</td>
                      <td className="r mono">{mask(formatCurrency(row.current_price))}</td>
                      <td className="r mono">{mask(formatCurrency(row.market_value))}</td>
                      <td className={cn("r mono", row.pnl >= 0 ? "pos" : "neg")}>
                        {mask(formatCurrency(row.pnl))}
                        <div className={cn("sub", row.pnl >= 0 ? "pos" : "neg")}>
                          {mask(formatPercent(row.pnl_pct))}
                        </div>
                      </td>
                      <td className="r">
                        <div className="ml-auto w-fit" title="7d trend proxy from current P&L direction">
                          <TrendProxy positive={row.pnl >= 0} />
                        </div>
                      </td>
                      <td>
                        <div className="flex items-center gap-2">
                          <span className={cn("pill-badge", signalClass)}>{signalLabel}</span>
                          <span className={cn("mono text-[11px]", score >= 0 ? "text-emerald-400" : "text-red-400")}>
                            {score >= 0 ? "+" : ""}{score.toFixed(1)}
                          </span>
                        </div>
                      </td>
                      <td>
                        <button
                          onClick={() => {
                            setSelected(selected?.symbol === row.symbol ? null : row);
                            setEditingCash(false);
                          }}
                          className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03] text-slate-400 transition-colors hover:border-white/[0.18] hover:text-slate-200"
                          aria-label={`Edit ${row.symbol}`}
                        >
                          <MoreHorizontal className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })}

                {filteredHoldings.length === 0 && (
                  <tr>
                    <td colSpan={9} className="py-10 text-center text-sm text-slate-500">
                      No holdings in this filter.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selected && (
        <EditHoldingPanel
          holding={selected}
          onSave={handleSaveHolding}
          onDelete={handleDeleteHolding}
          onClose={() => setSelected(null)}
        />
      )}

      <div className="flex justify-end">
        <button
          onClick={refresh}
          disabled={isFetching}
          className="flex items-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.08] disabled:opacity-60"
        >
          <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
          Refresh
        </button>
      </div>
    </div>
  );
}
