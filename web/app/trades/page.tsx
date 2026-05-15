"use client";

import { Suspense, useMemo, useRef, useState, useCallback, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeftRight,
  BarChart3,
  Check,
  Clock,
  Download,
  Loader2,
  PenLine,
  Plus,
  RefreshCw,
  Trash2,
  TrendingUp,
  Upload,
  X,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { HoldingAdvice, TradeOut, TradeUpdateInput } from "@/lib/api";
import {
  useHoldings,
  useTradeHistory,
  useRecordBuy,
  useRecordSell,
  useUpdateTrade,
  useDeleteTrade,
  queryKeys,
} from "@/lib/hooks";
import { formatCurrency, formatPercent, pnlColor, cn } from "@/lib/utils";
import { usePrivacy } from "@/lib/privacy";
import { TradesTableSkeleton } from "@/components/ui/loading";
import { useToast } from "@/components/ui/toast";
import { downloadCsv } from "@/lib/csv";

type TradeFilter = "all" | "buys" | "sells" | "manual" | "screenshot" | "discord";

function formatTradeDateTime(timestamp: string | null): string {
  if (!timestamp) return "--";
  const d = new Date(timestamp);
  if (Number.isNaN(d.getTime())) return "--";

  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd} ${hh}:${min}`;
}

function impliedFee(trade: TradeOut): number {
  const gross = trade.quantity * trade.price;
  return Math.max(0, Math.abs(gross - trade.total));
}

function pnlTone(value: number | null | undefined): "pos" | "neg" | "mut" {
  if (value == null || value === 0) return "mut";
  return value > 0 ? "pos" : "neg";
}

function TradeForm({
  onComplete,
  initialAction,
  initialSymbol,
  initialPrice,
  holdings,
}: {
  onComplete: () => void;
  initialAction?: "buy" | "sell";
  initialSymbol?: string;
  initialPrice?: number | null;
  holdings: HoldingAdvice[];
}) {
  const { toast } = useToast();
  const { mask } = usePrivacy();
  const recordBuy = useRecordBuy();
  const recordSell = useRecordSell();

  const [action, setAction] = useState<"buy" | "sell">(initialAction ?? "buy");
  const [symbol, setSymbol] = useState(initialSymbol ?? "");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState(
    typeof initialPrice === "number" && Number.isFinite(initialPrice)
      ? initialPrice.toFixed(2)
      : ""
  );
  const [marketPrice, setMarketPrice] = useState<number | null>(null);
  const [fetchingPrice, setFetchingPrice] = useState(false);

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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
        setPrice((prev) => (prev ? prev : result.price!.toFixed(2)));
      }
    } catch {
      // User can input manually.
    } finally {
      setFetchingPrice(false);
    }
  }, []);

  useEffect(() => {
    setAction(initialAction ?? "buy");
    setSymbol(initialSymbol ?? "");
    if (typeof initialPrice === "number" && Number.isFinite(initialPrice)) {
      setPrice(initialPrice.toFixed(2));
    } else {
      setPrice("");
    }
    setQuantity("");
    setMarketPrice(null);

    if (initialSymbol && !(typeof initialPrice === "number" && Number.isFinite(initialPrice))) {
      void fetchMarketPrice(initialSymbol);
    }
  }, [fetchMarketPrice, initialAction, initialPrice, initialSymbol]);

  function onSymbolChange(next: string) {
    setSymbol(next);
    setMarketPrice(null);
    if (timerRef.current) clearTimeout(timerRef.current);
    if (next.trim().length >= 2) {
      timerRef.current = setTimeout(() => void fetchMarketPrice(next), 600);
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!symbol || !quantity || !price) return;

    const qty = parseFloat(quantity);
    const px = parseFloat(price);
    const mutation = action === "buy" ? recordBuy : recordSell;

    try {
      await mutation.mutateAsync({
        symbol: symbol.toUpperCase(),
        quantity: qty,
        price: px,
      });
      toast(
        `${action === "buy" ? "Bought" : "Sold"} ${quantity} ${symbol.toUpperCase()} @ ${formatCurrency(px)}`,
        "success"
      );
      setSymbol("");
      setQuantity("");
      setPrice("");
      setMarketPrice(null);
      onComplete();
    } catch (err) {
      toast(err instanceof Error ? err.message : "Trade failed", "error");
    }
  }

  const submitting = recordBuy.isPending || recordSell.isPending;
  const qty = parseFloat(quantity);
  const px = parseFloat(price);
  const total = Number.isFinite(qty) && Number.isFinite(px) ? qty * px : null;
  const selectedHolding = holdings.find((holding) => (
    holding.symbol.toUpperCase() === symbol.trim().toUpperCase()
  ));
  const sellPnl = action === "sell" && selectedHolding && Number.isFinite(qty) && Number.isFinite(px)
    ? (px - selectedHolding.avg_cost) * qty
    : null;
  const sellPnlPct = sellPnl != null && selectedHolding && selectedHolding.avg_cost > 0
    ? ((px - selectedHolding.avg_cost) / selectedHolding.avg_cost) * 100
    : null;
  const sellExceedsHolding = action === "sell" && selectedHolding && Number.isFinite(qty)
    ? qty > selectedHolding.quantity
    : false;

  return (
    <div className="card">
      <div className="head">
        <h3>Record trade</h3>
        <span className="sub">manual entry</span>
      </div>
      <form onSubmit={onSubmit} className="body space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => setAction("buy")}
            className={cn(
              "rounded-lg border px-3 py-2 text-sm font-medium transition-colors",
              action === "buy"
                ? "border-brand-500/30 bg-brand-500/20 text-brand-300"
                : "border-white/10 bg-white/5 text-slate-400 hover:bg-white/10"
            )}
          >
            Buy
          </button>
          <button
            type="button"
            onClick={() => setAction("sell")}
            className={cn(
              "rounded-lg border px-3 py-2 text-sm font-medium transition-colors",
              action === "sell"
                ? "border-red-500/30 bg-red-500/20 text-red-300"
                : "border-white/10 bg-white/5 text-slate-400 hover:bg-white/10"
            )}
          >
            Sell
          </button>
        </div>

        <div>
          <label className="mb-1 block text-xs text-slate-500">Symbol</label>
          <div className="relative">
            <input
              type="text"
              value={symbol}
              onChange={(e) => onSymbolChange(e.target.value)}
              placeholder="e.g. SHOP.TO"
              className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder-slate-500 outline-none focus:border-brand-500/50"
              required
            />
            {fetchingPrice && <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-slate-500" />}
          </div>
          {marketPrice != null && <p className="mt-1 text-xs text-slate-500">Market price: {formatCurrency(marketPrice)}</p>}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-xs text-slate-500">Quantity</label>
            <input
              type="number"
              step="any"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
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
              className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder-slate-500 outline-none focus:border-brand-500/50"
              placeholder={marketPrice != null ? marketPrice.toFixed(2) : "0.00"}
              required
            />
          </div>
        </div>

        {symbol && total != null && (
          <div className="space-y-1 text-xs text-slate-500">
            <p>Total: {mask(formatCurrency(total))}</p>
            {action === "sell" && selectedHolding && sellPnl != null && sellPnlPct != null && (
              <p className={cn("font-medium", pnlColor(sellPnl))}>
                Est. realized P&amp;L: {mask(formatCurrency(sellPnl))} ({mask(formatPercent(sellPnlPct))})
                <span className="text-slate-500"> · avg cost {mask(formatCurrency(selectedHolding.avg_cost))}</span>
              </p>
            )}
            {sellExceedsHolding && selectedHolding && (
              <p className="text-amber-300">
                Quantity exceeds current holding of {mask(selectedHolding.quantity.toFixed(4))} shares.
              </p>
            )}
            {action === "sell" && !selectedHolding && symbol.trim() && (
              <p className="text-amber-300">No current holding found for this symbol.</p>
            )}
          </div>
        )}

        <button
          type="submit"
          disabled={submitting}
          className={cn(
            "w-full rounded-lg py-2.5 text-sm font-medium transition-colors disabled:opacity-50",
            action === "buy" ? "bg-brand-600 text-white hover:bg-brand-500" : "bg-red-600 text-white hover:bg-red-500"
          )}
        >
          {submitting ? "Submitting..." : `Record ${action === "buy" ? "buy" : "sell"}`}
        </button>
      </form>
    </div>
  );
}

function EditTradePanel({
  trade,
  onSave,
  onDelete,
  onClose,
}: {
  trade: TradeOut;
  onSave: (id: number, trade: TradeUpdateInput) => Promise<void>;
  onDelete: (trade: TradeOut) => Promise<void>;
  onClose: () => void;
}) {
  const { toast } = useToast();
  const { mask } = usePrivacy();
  const [action, setAction] = useState<"BUY" | "SELL">(
    trade.action === "SELL" ? "SELL" : "BUY"
  );
  const [symbol, setSymbol] = useState(trade.symbol);
  const [quantity, setQuantity] = useState(trade.quantity.toString());
  const [price, setPrice] = useState(trade.price.toString());
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    setAction(trade.action === "SELL" ? "SELL" : "BUY");
    setSymbol(trade.symbol);
    setQuantity(trade.quantity.toString());
    setPrice(trade.price.toString());
  }, [trade]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (trade.id == null) {
      toast("This trade cannot be edited because it has no ID", "error");
      return;
    }

    const qty = parseFloat(quantity);
    const px = parseFloat(price);
    const cleaned = symbol.trim().toUpperCase();
    if (!cleaned || !Number.isFinite(qty) || !Number.isFinite(px) || qty <= 0 || px <= 0) {
      toast("Enter a valid symbol, quantity, and price", "error");
      return;
    }

    setSaving(true);
    try {
      await onSave(trade.id, {
        action,
        symbol: cleaned,
        quantity: qty,
        price: px,
      });
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!confirm(`Delete ${trade.action} ${trade.symbol} from trade history?`)) return;
    setDeleting(true);
    try {
      await onDelete(trade);
    } finally {
      setDeleting(false);
    }
  }

  const qty = parseFloat(quantity);
  const px = parseFloat(price);
  const total = Number.isFinite(qty) && Number.isFinite(px) ? qty * px : 0;

  return (
    <div className="card">
      <div className="head">
        <h3 className="flex items-center gap-2">
          <PenLine className="h-4 w-4 text-brand-300" />
          Edit trade
        </h3>
        <button
          onClick={onClose}
          className="text-slate-500 transition-colors hover:text-white"
          aria-label="Close trade editor"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <form onSubmit={handleSubmit} className="body space-y-4">
        <div className="grid gap-3 md:grid-cols-[160px_1fr_1fr_1fr]">
          <div>
            <label className="mb-1 block text-xs text-slate-500">Action</label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setAction("BUY")}
                className={cn(
                  "rounded-lg border px-3 py-2 text-sm font-medium transition-colors",
                  action === "BUY"
                    ? "border-brand-500/30 bg-brand-500/20 text-brand-300"
                    : "border-white/10 bg-white/5 text-slate-400 hover:bg-white/10"
                )}
              >
                Buy
              </button>
              <button
                type="button"
                onClick={() => setAction("SELL")}
                className={cn(
                  "rounded-lg border px-3 py-2 text-sm font-medium transition-colors",
                  action === "SELL"
                    ? "border-red-500/30 bg-red-500/20 text-red-300"
                    : "border-white/10 bg-white/5 text-slate-400 hover:bg-white/10"
                )}
              >
                Sell
              </button>
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs text-slate-500">Symbol</label>
            <input
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-brand-500/50"
              required
            />
          </div>

          <div>
            <label className="mb-1 block text-xs text-slate-500">Quantity</label>
            <input
              type="number"
              step="any"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-brand-500/50"
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
              className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-brand-500/50"
              required
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-slate-500">
            {formatTradeDateTime(trade.timestamp)} · total {mask(formatCurrency(total))}
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-500 disabled:opacity-60"
            >
              <Check className="h-4 w-4" />
              {saving ? "Saving..." : "Save changes"}
            </button>
            <button
              type="button"
              onClick={handleDelete}
              disabled={deleting}
              className="inline-flex items-center gap-2 rounded-lg border border-red-500/25 bg-red-500/15 px-4 py-2 text-sm font-medium text-red-300 transition-colors hover:bg-red-500/25 disabled:opacity-60"
            >
              <Trash2 className="h-4 w-4" />
              {deleting ? "Deleting..." : "Delete"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}

export default function TradesPage() {
  return (
    <Suspense>
      <TradesContent />
    </Suspense>
  );
}

function TradesContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const qc = useQueryClient();
  const { mask } = usePrivacy();
  const { toast } = useToast();
  const { data: trades = [], isLoading, isFetching } = useTradeHistory(100);
  const { data: portfolio } = useHoldings();
  const updateTrade = useUpdateTrade();
  const deleteTrade = useDeleteTrade();

  const requestedAction = searchParams.get("action");
  const intentAction: "buy" | "sell" | undefined = requestedAction === "sell"
    ? "sell"
    : requestedAction === "buy"
      ? "buy"
      : undefined;
  const intentSymbol = searchParams.get("symbol")?.trim().toUpperCase() ?? "";
  const rawIntentPrice = searchParams.get("price");
  const intentPrice = rawIntentPrice != null && Number.isFinite(Number(rawIntentPrice))
    ? Number(rawIntentPrice)
    : undefined;
  const intentOpen = searchParams.get("open") === "1" || !!intentAction || !!intentSymbol || rawIntentPrice != null;

  const [showForm, setShowForm] = useState(intentOpen);
  const [filter, setFilter] = useState<TradeFilter>("all");
  const [editingTrade, setEditingTrade] = useState<TradeOut | null>(null);

  useEffect(() => {
    if (intentOpen) setShowForm(true);
  }, [intentOpen]);

  const sorted = useMemo(
    () =>
      [...trades].sort((a, b) => {
        const ta = a.timestamp ? new Date(a.timestamp).getTime() : 0;
        const tb = b.timestamp ? new Date(b.timestamp).getTime() : 0;
        return tb - ta;
      }),
    [trades]
  );

  const buys = sorted.filter((trade) => trade.action === "BUY").length;
  const sells = sorted.filter((trade) => trade.action === "SELL").length;
  const volume = sorted.reduce((sum, trade) => sum + trade.total, 0);
  const realizedPnl = sorted.reduce((sum, trade) => sum + (trade.pnl ?? 0), 0);
  const closedPnlPct = volume > 0 ? (realizedPnl / volume) * 100 : 0;

  const filterCounts = {
    all: sorted.length,
    buys,
    sells,
    manual: sorted.length,
    screenshot: 0,
    discord: 0,
  } satisfies Record<TradeFilter, number>;

  const filtered = useMemo(() => {
    if (filter === "all") return sorted;
    if (filter === "buys") return sorted.filter((trade) => trade.action === "BUY");
    if (filter === "sells") return sorted.filter((trade) => trade.action === "SELL");
    if (filter === "manual") return sorted;
    return [];
  }, [filter, sorted]);

  function refresh() {
    qc.invalidateQueries({ queryKey: queryKeys.tradeHistory(100) });
  }

  async function handleSaveTrade(id: number, trade: TradeUpdateInput) {
    try {
      const updated = await updateTrade.mutateAsync({ id, trade });
      toast(`Updated ${updated.action} ${updated.symbol}`, "success");
      setEditingTrade(null);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Trade update failed", "error");
    }
  }

  async function handleDeleteTrade(trade: TradeOut) {
    if (trade.id == null) {
      toast("This trade cannot be deleted because it has no ID", "error");
      return;
    }
    try {
      await deleteTrade.mutateAsync(trade.id);
      toast(`Deleted ${trade.action} ${trade.symbol}`, "success");
      if (editingTrade?.id === trade.id) setEditingTrade(null);
    } catch (err) {
      toast(err instanceof Error ? err.message : "Trade delete failed", "error");
    }
  }

  function exportCsv() {
    const today = new Date().toISOString().slice(0, 10);
    const rows = sorted.map((trade) => [
      formatTradeDateTime(trade.timestamp),
      trade.action,
      trade.symbol,
      trade.quantity.toFixed(4),
      trade.price.toFixed(4),
      impliedFee(trade).toFixed(4),
      trade.total.toFixed(4),
      trade.pnl == null ? "" : trade.pnl.toFixed(4),
      trade.pnl_pct == null ? "" : trade.pnl_pct.toFixed(4),
    ]);

    downloadCsv(
      `trades-${today}.csv`,
      ["timestamp", "action", "symbol", "quantity", "price", "fee", "total", "pnl", "pnl_pct"],
      rows
    );
  }

  return (
    <div className="space-y-6">
      <div className="ph">
        <div>
          <h1>Trades</h1>
          <p className="sub">
            {sorted.length} trades
            <span className="divider">·</span>
            last 30 days
            <span className="divider">·</span>
            <span className="text-emerald-400">{buys} buys</span>
            <span className="divider">·</span>
            <span className="text-red-400">{sells} sells</span>
          </p>
        </div>

        <div className="actions">
          <button
            onClick={exportCsv}
            className="flex items-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.08]"
          >
            <Download className="h-4 w-4" />
            Export CSV
          </button>
          <button
            onClick={() => router.push("/upload")}
            className="flex items-center gap-2 rounded-lg border border-brand-500/20 bg-brand-500/15 px-3 py-2 text-sm text-brand-200 transition-colors hover:bg-brand-500/25"
          >
            <Upload className="h-4 w-4" />
            Upload screenshot
          </button>
          <button
            onClick={() => setShowForm((prev) => !prev)}
            className="flex items-center gap-2 rounded-lg bg-brand-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-500"
          >
            <Plus className="h-4 w-4" />
            {showForm ? "Hide form" : "Record trade"}
          </button>
        </div>
      </div>

      <div className="grid-4">
        <div className="stat2">
          <div className="lbl">
            <span>Trades / 30d</span>
            <span className="ico"><ArrowLeftRight className="h-4 w-4" /></span>
          </div>
          <div className="val">{sorted.length}</div>
          <div className="chg neu">{buys} buys · {sells} sells</div>
        </div>

        <div className="stat2">
          <div className="lbl">
            <span>Volume / 30d</span>
            <span className="ico"><BarChart3 className="h-4 w-4" /></span>
          </div>
          <div className="val">{mask(formatCurrency(volume))}</div>
          <div className="chg neu">avg {sorted.length > 0 ? mask(formatCurrency(volume / sorted.length)) : "--"} / trade</div>
        </div>

        <div className="stat2">
          <div className="lbl">
            <span>Realized P&amp;L</span>
            <span className="ico"><TrendingUp className="h-4 w-4" /></span>
          </div>
          <div className={cn("val", realizedPnl >= 0 ? "text-emerald-400" : "text-red-400")}>{mask(formatCurrency(realizedPnl))}</div>
          <div className={cn("chg", realizedPnl >= 0 ? "pos" : "neg")}>{closedPnlPct >= 0 ? "+" : ""}{closedPnlPct.toFixed(2)}% on closed</div>
        </div>

        <div className="stat2">
          <div className="lbl">
            <span>Avg holding</span>
            <span className="ico"><Clock className="h-4 w-4" /></span>
          </div>
          <div className="val">--</div>
          <div className="chg neu">not in API feed</div>
        </div>
      </div>

      {showForm && (
        <TradeForm
          key={`${intentAction ?? "buy"}:${intentSymbol}:${intentPrice ?? ""}`}
          onComplete={refresh}
          initialAction={intentAction}
          initialSymbol={intentSymbol}
          initialPrice={intentPrice}
          holdings={portfolio?.holdings ?? []}
        />
      )}

      {editingTrade && (
        <EditTradePanel
          trade={editingTrade}
          onSave={handleSaveTrade}
          onDelete={handleDeleteTrade}
          onClose={() => setEditingTrade(null)}
        />
      )}

      <div className="page-tabs">
        <button className={cn(filter === "all" && "on")} onClick={() => setFilter("all")}>All <span className="c">{filterCounts.all}</span></button>
        <button className={cn(filter === "buys" && "on")} onClick={() => setFilter("buys")}>Buys <span className="c">{filterCounts.buys}</span></button>
        <button className={cn(filter === "sells" && "on")} onClick={() => setFilter("sells")}>Sells <span className="c">{filterCounts.sells}</span></button>
        <button className={cn(filter === "manual" && "on")} onClick={() => setFilter("manual")}>Manual <span className="c">{filterCounts.manual}</span></button>
        <button className={cn(filter === "screenshot" && "on")} onClick={() => setFilter("screenshot")}>Screenshot <span className="c">{filterCounts.screenshot}</span></button>
        <button className={cn(filter === "discord" && "on")} onClick={() => setFilter("discord")}>Discord <span className="c">{filterCounts.discord}</span></button>
      </div>

      <div className="card">
        <div className="head">
          <h3>Trade log</h3>
          <div className="flex items-center gap-3">
            <span className="sub">newest first</span>
            <button
              onClick={refresh}
              disabled={isFetching}
              className="inline-flex items-center gap-1 rounded-lg border border-white/[0.08] bg-white/[0.03] px-2.5 py-1.5 text-xs text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.08] disabled:opacity-60"
            >
              <RefreshCw className={cn("h-3.5 w-3.5", isFetching && "animate-spin")} />
              Refresh
            </button>
          </div>
        </div>

        {isLoading ? (
          <div className="p-4">
            <TradesTableSkeleton rows={6} />
          </div>
        ) : (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Date / time</th>
                  <th>Action</th>
                  <th>Symbol</th>
                  <th className="r">Qty</th>
                  <th className="r">Price</th>
                  <th className="r">P&amp;L</th>
                  <th className="r">Total</th>
                  <th>Source</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((trade, index) => (
                  <tr key={`${trade.id ?? "trade"}-${trade.timestamp ?? index}`}>
                    <td className="mono mut">{formatTradeDateTime(trade.timestamp)}</td>
                    <td>
                      <span className={cn("pill-badge", trade.action === "BUY" ? "pb-buy" : "pb-sell")}>{trade.action}</span>
                    </td>
                    <td className="font-semibold text-slate-100">{trade.symbol}</td>
                    <td className="r mono">{mask(trade.quantity.toFixed(2))}</td>
                    <td className="r mono">{mask(formatCurrency(trade.price))}</td>
                    <td className={cn("r mono", pnlTone(trade.pnl))}>
                      {trade.pnl == null || trade.pnl_pct == null ? (
                        "--"
                      ) : (
                        <>
                          {mask(formatCurrency(trade.pnl))}
                          <div className={cn("sub", pnlTone(trade.pnl))}>
                            {mask(formatPercent(trade.pnl_pct))}
                          </div>
                        </>
                      )}
                    </td>
                    <td className="r mono">{mask(formatCurrency(trade.total))}</td>
                    <td>
                      <span className="inline-flex items-center gap-1.5 text-xs text-slate-400">
                        <PenLine className="h-3.5 w-3.5" />
                        manual
                      </span>
                    </td>
                    <td>
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={() => setEditingTrade(trade)}
                          className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03] text-slate-400 transition-colors hover:border-white/[0.16] hover:text-slate-200"
                          aria-label={`Edit ${trade.symbol} trade`}
                          title="Edit trade"
                        >
                          <PenLine className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => {
                            if (confirm(`Delete ${trade.action} ${trade.symbol} from trade history?`)) {
                              void handleDeleteTrade(trade);
                            }
                          }}
                          disabled={deleteTrade.isPending}
                          className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-red-500/20 bg-red-500/10 text-red-300 transition-colors hover:border-red-500/35 hover:bg-red-500/20 disabled:opacity-60"
                          aria-label={`Delete ${trade.symbol} trade`}
                          title="Delete trade"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}

                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={9} className="py-10 text-center text-sm text-slate-500">
                      {filter === "screenshot" || filter === "discord"
                        ? "This source is not available from the current trade history API."
                        : "No trades match this filter."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-4 py-3 text-xs text-slate-500">
        Trade source and average holding duration are not currently returned by the API. Source tabs are shown for design parity and remain empty until backend fields are added.
      </div>
    </div>
  );
}
