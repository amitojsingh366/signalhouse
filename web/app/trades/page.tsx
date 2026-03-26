"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { ArrowLeftRight, Loader2 } from "lucide-react";
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
  const [marketPrice, setMarketPrice] = useState<number | null>(null);
  const [fetchingPrice, setFetchingPrice] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const priceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounced price fetch when symbol changes
  const fetchMarketPrice = useCallback(async (sym: string) => {
    if (!sym.trim()) {
      setMarketPrice(null);
      return;
    }
    setFetchingPrice(true);
    try {
      const result = await api.getPrice(sym);
      if (result.price != null) {
        setMarketPrice(result.price);
        // Only auto-fill if price field is empty or was previously auto-filled
        setPrice((prev) => (!prev ? result.price!.toFixed(2) : prev));
      }
    } catch {
      // silently ignore — user can enter manually
    } finally {
      setFetchingPrice(false);
    }
  }, []);

  function handleSymbolChange(val: string) {
    setSymbol(val);
    setMarketPrice(null);
    if (priceTimerRef.current) clearTimeout(priceTimerRef.current);
    if (val.trim().length >= 2) {
      priceTimerRef.current = setTimeout(() => fetchMarketPrice(val), 600);
    }
  }

  function useMarketPrice() {
    if (marketPrice != null) {
      setPrice(marketPrice.toFixed(2));
    }
  }

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
      setMarketPrice(null);
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
    <form onSubmit={handleSubmit} className="glass-card p-4 sm:p-5">
      <h3 className="mb-4 text-sm font-medium text-slate-400">Record Trade</h3>

      {/* Action toggle */}
      <div className="mb-4 flex gap-2">
        <button
          type="button"
          onClick={() => setAction("buy")}
          className={cn(
            "flex-1 rounded-lg py-2 text-sm font-medium transition-colors",
            action === "buy"
              ? "bg-brand-500/20 text-brand-400 border border-brand-500/30"
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
          <div className="relative">
            <input
              type="text"
              value={symbol}
              onChange={(e) => handleSymbolChange(e.target.value)}
              placeholder="e.g. SHOP.TO"
              className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder-slate-500 outline-none focus:border-brand-500/50"
              required
            />
            {fetchingPrice && (
              <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-slate-500" />
            )}
          </div>
          {marketPrice != null && (
            <p className="mt-1 text-xs text-slate-500">
              Market price: {formatCurrency(marketPrice)}
            </p>
          )}
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
            <label className="mb-1 flex items-center justify-between text-xs text-slate-500">
              <span>Price (CAD)</span>
              {marketPrice != null && price !== marketPrice.toFixed(2) && (
                <button
                  type="button"
                  onClick={useMarketPrice}
                  className="text-brand-400 hover:underline"
                >
                  Use market
                </button>
              )}
            </label>
            <input
              type="number"
              step="any"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              placeholder={marketPrice != null ? marketPrice.toFixed(2) : "0.00"}
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
              ? "bg-brand-600 text-white hover:bg-brand-500"
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
      // most recent should be first. time decending order
      const [t, s] = await Promise.all([
        api.getTradeHistory(50),
        api.getSymbols(),
      ]);
      setTrades(t.sort((a, b) => {
        const timeA = a.timestamp ? new Date(a.timestamp).getTime() : 0;
        const timeB = b.timestamp ? new Date(b.timestamp).getTime() : 0;
        return timeB - timeA;
      }));
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

      {/* Trade form — full width on mobile, sidebar on desktop */}
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-1 min-w-0">
          <TradeForm symbols={symbols} onComplete={load} />
        </div>

        {/* Trade history — scrollable table */}
        <div className="lg:col-span-2 min-w-0">
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
