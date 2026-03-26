"use client";

import { useEffect, useState } from "react";
import { ArrowLeftRight } from "lucide-react";
import { api } from "@/lib/api";
import type { TradeOut, SymbolInfo } from "@/lib/api";
import { formatCurrency, formatPercent, pnlColor, cn } from "@/lib/utils";
import { DataTable } from "@/components/ui/data-table";
import { TableSkeleton } from "@/components/ui/loading";
import { useToast } from "@/components/ui/toast";

function TradeForm({
  symbols,
  onComplete,
}: {
  symbols: SymbolInfo[];
  onComplete: () => void;
}) {
  const { toast } = useToast();
  const [action, setAction] = useState<"buy" | "sell">("buy");
  const [symbol, setSymbol] = useState("");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!symbol || !quantity || !price) return;

    setSubmitting(true);
    try {
      const fn = action === "buy" ? api.recordBuy : api.recordSell;
      await fn(symbol.toUpperCase(), parseFloat(quantity), parseFloat(price));
      toast(
        `${action === "buy" ? "Bought" : "Sold"} ${quantity} ${symbol.toUpperCase()} @ ${formatCurrency(parseFloat(price))}`,
        "success"
      );
      setSymbol("");
      setQuantity("");
      setPrice("");
      onComplete();
    } catch (err) {
      toast(
        err instanceof Error ? err.message : "Trade failed",
        "error"
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="glass-card p-5">
      <h3 className="mb-4 text-sm font-medium text-slate-400">Record Trade</h3>

      {/* Action toggle */}
      <div className="mb-4 flex gap-2">
        <button
          type="button"
          onClick={() => setAction("buy")}
          className={cn(
            "flex-1 rounded-lg py-2 text-sm font-medium transition-colors",
            action === "buy"
              ? "bg-green-500/20 text-green-400 border border-green-500/30"
              : "bg-white/5 text-slate-400 border border-white/10 hover:bg-white/10"
          )}
        >
          Buy
        </button>
        <button
          type="button"
          onClick={() => setAction("sell")}
          className={cn(
            "flex-1 rounded-lg py-2 text-sm font-medium transition-colors",
            action === "sell"
              ? "bg-red-500/20 text-red-400 border border-red-500/30"
              : "bg-white/5 text-slate-400 border border-white/10 hover:bg-white/10"
          )}
        >
          Sell
        </button>
      </div>

      <div className="space-y-3">
        <div>
          <label className="mb-1 block text-xs text-slate-500">Symbol</label>
          <input
            type="text"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            placeholder="e.g. SHOP.TO"
            className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder-slate-500 outline-none focus:border-brand-500/50"
            required
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-xs text-slate-500">Quantity</label>
            <input
              type="number"
              step="any"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              placeholder="0.00"
              className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder-slate-500 outline-none focus:border-brand-500/50"
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-500">Price (CAD)</label>
            <input
              type="number"
              step="any"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder="0.00"
              className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder-slate-500 outline-none focus:border-brand-500/50"
              required
            />
          </div>
        </div>

        {symbol && quantity && price && (
          <p className="text-xs text-slate-500">
            Total: {formatCurrency(parseFloat(quantity) * parseFloat(price))}
          </p>
        )}

        <button
          type="submit"
          disabled={submitting}
          className={cn(
            "w-full rounded-lg py-2.5 text-sm font-medium transition-colors disabled:opacity-50",
            action === "buy"
              ? "bg-green-600 text-white hover:bg-green-500"
              : "bg-red-600 text-white hover:bg-red-500"
          )}
        >
          {submitting
            ? "Submitting..."
            : `Record ${action === "buy" ? "Buy" : "Sell"}`}
        </button>
      </div>
    </form>
  );
}

export default function TradesPage() {
  const [trades, setTrades] = useState<TradeOut[]>([]);
  const [symbols, setSymbols] = useState<SymbolInfo[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const [t, s] = await Promise.all([
        api.getTradeHistory(50),
        api.getSymbols(),
      ]);
      setTrades(t);
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

  const columns = [
    {
      key: "timestamp",
      header: "Date",
      render: (t: TradeOut) =>
        t.timestamp
          ? new Date(t.timestamp).toLocaleDateString("en-CA")
          : "—",
    },
    {
      key: "action",
      header: "Action",
      render: (t: TradeOut) => (
        <span
          className={cn(
            "badge",
            t.action === "BUY" ? "badge-buy" : "badge-sell"
          )}
        >
          {t.action}
        </span>
      ),
    },
    {
      key: "symbol",
      header: "Symbol",
      render: (t: TradeOut) => (
        <span className="font-medium">{t.symbol}</span>
      ),
    },
    {
      key: "quantity",
      header: "Qty",
      className: "text-right",
      render: (t: TradeOut) => t.quantity.toFixed(2),
    },
    {
      key: "price",
      header: "Price",
      className: "text-right",
      render: (t: TradeOut) => formatCurrency(t.price),
    },
    {
      key: "total",
      header: "Total",
      className: "text-right",
      render: (t: TradeOut) => formatCurrency(t.total),
    },
    {
      key: "pnl",
      header: "P&L",
      className: "text-right",
      render: (t: TradeOut) =>
        t.pnl != null ? (
          <span className={pnlColor(t.pnl)}>
            {formatCurrency(t.pnl)}
          </span>
        ) : (
          <span className="text-slate-600">—</span>
        ),
    },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Trades</h1>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Trade form */}
        <div className="lg:col-span-1">
          <TradeForm symbols={symbols} onComplete={load} />
        </div>

        {/* Trade history */}
        <div className="lg:col-span-2">
          <h2 className="mb-3 text-sm font-medium text-slate-400">
            Trade History
          </h2>
          {loading ? (
            <TableSkeleton rows={6} />
          ) : (
            <DataTable
              columns={columns}
              data={trades}
              keyFn={(t) => `${t.id ?? t.timestamp}`}
              emptyMessage="No trades recorded yet"
            />
          )}
        </div>
      </div>
    </div>
  );
}
