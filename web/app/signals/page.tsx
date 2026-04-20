"use client";

import { Suspense, useState, useCallback, useRef, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { Zap, RefreshCw, AlertTriangle, ArrowRight, TrendingUp, BellOff, Bell, ChevronDown, ChevronUp, Clock, X, DollarSign } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useActionPlan, useSymbols, useSignalCheck, queryKeys } from "@/lib/hooks";
import type { ActionItem } from "@/lib/api";
import { api } from "@/lib/api";
import { formatCurrency, formatPercent, cn } from "@/lib/utils";
import { usePrivacy } from "@/lib/privacy";
import { SignalBadge } from "@/components/ui/signal-badge";
import { SearchBar } from "@/components/ui/search-bar";
import { Skeleton, SignalCardsSkeleton } from "@/components/ui/loading";
import { PriceChart } from "@/components/ui/price-chart";
import { ScoreBreakdown, ScoreTag } from "@/components/ui/score-breakdown";

const SNOOZE_DURATIONS = [
  { label: "1h", hours: 1 },
  { label: "4h", hours: 4 },
  { label: "8h", hours: 8 },
  { label: "24h", hours: 24 },
  { label: "3d", hours: 72 },
  { label: "7d", hours: 168 },
] as const;

function SnoozePopup({
  symbol,
  onConfirm,
  onClose,
}: {
  symbol: string;
  onConfirm: (symbol: string, hours: number, indefinite: boolean, phantomTrailingStop: boolean) => void;
  onClose: () => void;
}) {
  const [selectedHours, setSelectedHours] = useState(4);
  const [indefinite, setIndefinite] = useState(false);
  const [phantomTrailingStop, setPhantomTrailingStop] = useState(true);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [onClose]);

  return (
    <div ref={ref} className="absolute bottom-full left-0 mb-2 z-50 w-64 rounded-xl border border-white/10 bg-zinc-900/95 backdrop-blur-xl p-4 shadow-2xl animate-in fade-in slide-in-from-bottom-2 duration-150">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-sm font-medium text-white">Snooze {symbol}</span>
        <button onClick={onClose} className="text-slate-500 hover:text-white">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Duration picker */}
      <div className="mb-3">
        <p className="mb-2 text-xs text-slate-500">Duration</p>
        <div className="grid grid-cols-3 gap-1.5">
          {SNOOZE_DURATIONS.map(({ label, hours }) => (
            <button
              key={label}
              onClick={() => { setSelectedHours(hours); setIndefinite(false); }}
              className={cn(
                "rounded-lg px-2 py-1.5 text-xs font-medium transition-colors",
                !indefinite && selectedHours === hours
                  ? "bg-brand-500/20 text-brand-400 border border-brand-500/30"
                  : "bg-white/5 text-slate-400 border border-white/5 hover:bg-white/10"
              )}
            >
              {label}
            </button>
          ))}
        </div>
        <button
          onClick={() => setIndefinite(!indefinite)}
          className={cn(
            "mt-1.5 w-full rounded-lg px-2 py-1.5 text-xs font-medium transition-colors",
            indefinite
              ? "bg-amber-500/20 text-amber-400 border border-amber-500/30"
              : "bg-white/5 text-slate-400 border border-white/5 hover:bg-white/10"
          )}
        >
          <Clock className="mr-1 inline h-3 w-3" />
          Indefinite
        </button>
      </div>

      {/* Phantom trailing stop toggle */}
      <div className="mb-3">
        <button
          onClick={() => setPhantomTrailingStop(!phantomTrailingStop)}
          className="flex w-full items-center gap-2 rounded-lg border border-white/5 bg-white/5 px-3 py-2 text-left transition-colors hover:bg-white/10"
        >
          <div className={cn(
            "flex h-4 w-7 items-center rounded-full transition-colors",
            phantomTrailingStop ? "bg-brand-500 justify-end" : "bg-slate-600 justify-start"
          )}>
            <div className="mx-0.5 h-3 w-3 rounded-full bg-white" />
          </div>
          <div>
            <p className="text-xs font-medium text-white">Phantom trailing stop</p>
            <p className="text-[10px] text-slate-500">Auto-unsnooze if loss worsens 3%+</p>
          </div>
        </button>
      </div>

      {/* Confirm */}
      <button
        onClick={() => onConfirm(symbol, selectedHours, indefinite, phantomTrailingStop)}
        className="w-full rounded-lg bg-brand-500/20 py-2 text-xs font-medium text-brand-400 transition-colors hover:bg-brand-500/30 border border-brand-500/20"
      >
        <BellOff className="mr-1 inline h-3 w-3" />
        Snooze {indefinite ? "indefinitely" : SNOOZE_DURATIONS.find(d => d.hours === selectedHours)?.label ?? `${selectedHours}h`}
      </button>
    </div>
  );
}

/** Get the primary symbol for an action (for chart display). */
function actionSymbol(action: ActionItem): string {
  if (action.type === "SWAP") return action.sell_symbol ?? action.buy_symbol ?? "";
  return action.symbol ?? "";
}

function ActionCard({
  action,
  expanded,
  onToggle,
  onSnooze,
  onUnsnooze,
  snoozing,
}: {
  action: ActionItem;
  expanded: boolean;
  onToggle: () => void;
  onSnooze?: (symbol: string, hours: number, indefinite: boolean, phantomTrailingStop: boolean) => void;
  onUnsnooze?: (symbol: string) => void;
  snoozing?: boolean;
}) {
  const { mask } = usePrivacy();
  const sym = actionSymbol(action);
  const isSnoozed = !!action.snoozed;
  const [showSnoozePopup, setShowSnoozePopup] = useState(false);
  const isSell = action.type === "SELL";
  const isSwap = action.type === "SWAP";
  const isBuy = action.type === "BUY";
  const isUrgent = action.urgency === "urgent";
  const isActionable = action.actionable !== false;

  const score = action.score ?? (isBuy && action.strength != null ? action.strength * 9 : undefined);
  const scoreText = score == null ? "—" : `${score >= 0 ? "+" : ""}${score.toFixed(1)}`;
  const scoreClass = score == null ? "" : score >= 0 ? "pos" : "neg";

  const labelSymbol = isSwap
    ? `${action.sell_symbol ?? "—"} → ${action.buy_symbol ?? "—"}`
    : (action.symbol ?? "—");
  const priceValue = isSwap ? action.sell_price : action.price;
  const deltaPct = isSwap ? action.sell_pnl_pct : action.pnl_pct;
  const reasonTags = (action.reasons ?? [])
    .filter((r) => !r.startsWith("Price:") && !r.startsWith("ATR:"))
    .slice(0, 4);

  const metaItems: string[] = [];
  if (isSell) {
    if (action.shares != null) metaItems.push(`Shares ${mask(action.shares.toFixed(4))}`);
    if (action.price != null) metaItems.push(`Price ${formatCurrency(action.price)}`);
    if (action.dollar_amount != null) metaItems.push(`Value ${mask(formatCurrency(action.dollar_amount))}`);
    if (action.entry_price != null) metaItems.push(`Entry ${formatCurrency(action.entry_price)}`);
  } else if (isSwap) {
    if (action.sell_shares != null) metaItems.push(`Sell ${mask(action.sell_shares.toFixed(4))} ${action.sell_symbol ?? ""}`.trim());
    if (action.buy_shares != null) metaItems.push(`Buy ${action.buy_shares.toFixed(4)} ${action.buy_symbol ?? ""}`.trim());
    if (action.sell_amount != null) metaItems.push(`From ${mask(formatCurrency(action.sell_amount))}`);
    if (action.buy_amount != null) metaItems.push(`To ~${mask(formatCurrency(action.buy_amount))}`);
    if (action.buy_strength != null) metaItems.push(`Conviction ${(action.buy_strength * 100).toFixed(0)}%`);
  } else {
    if (isActionable && action.shares != null) metaItems.push(`Shares ${action.shares.toFixed(4)}`);
    if (action.price != null) metaItems.push(`Price ~${formatCurrency(action.price)}`);
    if (isActionable && action.dollar_amount != null) metaItems.push(`Cost ${mask(formatCurrency(action.dollar_amount))}`);
    if (isActionable && action.pct_of_portfolio != null) {
      metaItems.push(`${mask(action.pct_of_portfolio.toFixed(1))}% of portfolio`);
    }
    if (!isActionable) metaItems.push("Not actionable: insufficient cash or max positions reached");
  }

  return (
    <div
      className={cn(
        "signal-action-card",
        isUrgent && "urgent",
        isSwap && "swap",
        isBuy && isActionable && "buy",
        isBuy && !isActionable && "signal-only",
        isSnoozed && "snoozed"
      )}
    >
      <button onClick={onToggle} className="w-full text-left">
        <div className="signal-action-head">
          <div className="signal-action-score">
            <div className={cn("v", scoreClass)}>{scoreText}</div>
            <div className="of">/ 9</div>
          </div>
          <div className="signal-action-who">
            <div className="sym">
              <span className="t">{labelSymbol}</span>
              {action.sector && <span className="sector">{action.sector}</span>}
              {isSell && (
                <span className={cn("pill-badge", isUrgent ? "pb-urgent" : "pb-sell")}>
                  {isUrgent ? "URGENT" : "SELL"}
                </span>
              )}
              {isSwap && <span className="pill-badge pb-swap">SWAP</span>}
              {isBuy && (
                <span className={cn("pill-badge", isActionable ? "pb-buy" : "pb-so")}>
                  {isActionable
                    ? action.strength != null
                      ? `BUY ${(action.strength * 100).toFixed(0)}%`
                      : "BUY"
                    : "SIGNAL ONLY"}
                </span>
              )}
              {isSnoozed && <span className="pill-badge pb-snooze">SNOOZED</span>}
            </div>
            <div className="reason">{action.detail}</div>
          </div>
          <div className="signal-action-price">
            <div className="p">{priceValue != null ? (isBuy ? `~${formatCurrency(priceValue)}` : formatCurrency(priceValue)) : "—"}</div>
            {deltaPct != null ? (
              <div className={cn("d", deltaPct >= 0 ? "text-emerald-400" : "text-red-400")}>
                {mask(formatPercent(deltaPct))}
              </div>
            ) : (
              <div className="d">{action.reason}</div>
            )}
          </div>
        </div>

        {metaItems.length > 0 && (
          <div className="signal-action-meta">
            {metaItems.map((item) => (
              <span key={item}>{item}</span>
            ))}
          </div>
        )}

        {reasonTags.length > 0 && (
          <div className="signal-action-reasons">
            {reasonTags.map((reason) => (
              <span key={reason} className="tag">
                <ScoreTag text={reason} />
              </span>
            ))}
          </div>
        )}

        {isBuy && (
          <div className="px-4 pb-2">
            <ScoreBreakdown
              total={action.score}
              technical={action.technical_score}
              sentiment={action.sentiment_score}
              commodity={action.commodity_score}
            />
          </div>
        )}
      </button>

      <div className="signal-action-foot">
        <div className="relative flex items-center gap-2">
          {isSnoozed && onUnsnooze && sym && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onUnsnooze(sym);
              }}
              disabled={snoozing}
              className="flex items-center gap-1 rounded-md border border-slate-600/30 px-2 py-1 text-xs text-slate-400 transition-colors hover:border-white/20 hover:text-white"
            >
              <Bell className="h-3 w-3" />
              Unsnooze
            </button>
          )}
          {!isSnoozed && onSnooze && sym && (
            <>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setShowSnoozePopup(!showSnoozePopup);
                }}
                disabled={snoozing}
                className="flex items-center gap-1 rounded-md border border-slate-600/30 px-2 py-1 text-xs text-slate-400 transition-colors hover:border-white/20 hover:text-white"
              >
                <BellOff className="h-3 w-3" />
                Snooze
              </button>
              {showSnoozePopup && (
                <SnoozePopup
                  symbol={sym}
                  onConfirm={(s, h, ind, pts) => {
                    onSnooze(s, h, ind, pts);
                    setShowSnoozePopup(false);
                  }}
                  onClose={() => setShowSnoozePopup(false)}
                />
              )}
            </>
          )}
        </div>
        <button onClick={onToggle} className="toggle">
          {expanded ? "Hide chart" : "View chart"}
        </button>
      </div>

      {expanded && sym && (
        <div className="px-2 pb-3">
          <PriceChart symbol={sym} />
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
  const qc = useQueryClient();

  const [checkedSymbol, setCheckedSymbol] = useState<string | null>(
    () => searchParams.get("check")
  );
  const [expandedCard, setExpandedCard] = useState<string | null>(null);
  const [snoozing, setSnoozing] = useState(false);
  const [showSnoozed, setShowSnoozed] = useState(false);
  const [viewFilter, setViewFilter] = useState<
    "all" | "exit" | "swap" | "buy" | "signal" | "snoozed"
  >("all");

  const { mask } = usePrivacy();
  const { data: symbols = [] } = useSymbols();
  const { data: plan, isLoading: planLoading, isFetching: refreshing } = useActionPlan();
  const { data: checked, isLoading: checkLoading } = useSignalCheck(checkedSymbol);

  const refresh = useCallback(() => {
    qc.invalidateQueries({ queryKey: queryKeys.actionPlan });
  }, [qc]);

  function checkSymbol(symbol: string) {
    setCheckedSymbol(symbol);
    qc.invalidateQueries({ queryKey: queryKeys.signal(symbol) });
  }

  const toggleCard = useCallback((key: string) => {
    setExpandedCard(prev => prev === key ? null : key);
  }, []);

  const handleSnooze = useCallback(async (symbol: string, hours: number, indefinite: boolean, phantomTrailingStop: boolean) => {
    setSnoozing(true);
    try {
      await api.snoozeSignal(symbol, hours, indefinite, phantomTrailingStop);
      qc.invalidateQueries({ queryKey: queryKeys.actionPlan });
    } finally {
      setSnoozing(false);
    }
  }, [qc]);

  const handleUnsnooze = useCallback(async (symbol: string) => {
    setSnoozing(true);
    try {
      await api.unsnoozeSignal(symbol);
      qc.invalidateQueries({ queryKey: queryKeys.actionPlan });
    } finally {
      setSnoozing(false);
    }
  }, [qc]);

  const allActions = plan?.actions ?? [];
  const activeSells = allActions.filter(a => a.type === "SELL" && !a.snoozed);
  const activeSwaps = allActions.filter(a => a.type === "SWAP" && !a.snoozed);
  const actionableBuys = allActions.filter(a => a.type === "BUY" && a.actionable !== false);
  const signalOnlyBuys = allActions.filter(a => a.type === "BUY" && a.actionable === false);
  const snoozedActions = allActions.filter(a => a.snoozed);
  const hasActions = activeSells.length > 0 || activeSwaps.length > 0 || actionableBuys.length > 0 || signalOnlyBuys.length > 0;
  const showExit = viewFilter === "all" || viewFilter === "exit";
  const showSwap = viewFilter === "all" || viewFilter === "swap";
  const showBuy = viewFilter === "all" || viewFilter === "buy";
  const showSignalOnly = viewFilter === "all" || viewFilter === "signal";
  const showSnoozedSection = viewFilter === "all" || viewFilter === "snoozed";

  return (
    <div className="space-y-6">
      <div className="ph">
        <div>
          <h1>Signals</h1>
          <p className="sub">
            Updated now
            <span className="divider">·</span>
            333 symbols scanned
            <span className="divider">·</span>
            <span className="text-emerald-400">{actionableBuys.length + activeSwaps.length + activeSells.length} actionable</span>
          </p>
        </div>
        <div className="actions">
          <button
            onClick={refresh}
            disabled={refreshing}
            className="flex items-center gap-2 rounded-lg bg-brand-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-500 disabled:opacity-70"
          >
            <RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} />
            Refresh
          </button>
        </div>
      </div>

      <div className="page-tabs">
        <button className={viewFilter === "all" ? "on" : ""} onClick={() => setViewFilter("all")}>
          All<span className="c">{allActions.length}</span>
        </button>
        <button className={viewFilter === "exit" ? "on" : ""} onClick={() => setViewFilter("exit")}>
          Exit alerts<span className="c">{activeSells.length}</span>
        </button>
        <button className={viewFilter === "buy" ? "on" : ""} onClick={() => setViewFilter("buy")}>
          Buys<span className="c">{actionableBuys.length}</span>
        </button>
        <button className={viewFilter === "swap" ? "on" : ""} onClick={() => setViewFilter("swap")}>
          Swaps<span className="c">{activeSwaps.length}</span>
        </button>
        <button className={viewFilter === "signal" ? "on" : ""} onClick={() => setViewFilter("signal")}>
          Signal only<span className="c">{signalOnlyBuys.length}</span>
        </button>
        <button className={viewFilter === "snoozed" ? "on" : ""} onClick={() => setViewFilter("snoozed")}>
          Snoozed<span className="c">{snoozedActions.length}</span>
        </button>
      </div>

      {/* Portfolio summary bar */}
      {plan && (
        <div className="glass-card flex flex-wrap items-center gap-4 px-5 py-3 text-sm">
          <div>
            <span className="text-slate-500 mr-1">Portfolio:</span>
            <span className="font-medium">{mask(formatCurrency(plan.portfolio_value))}</span>
          </div>
          <div>
            <span className="text-slate-500 mr-1">Cash:</span>
            <span className="font-medium">{mask(formatCurrency(plan.cash))}</span>
          </div>
          <div>
            <span className="text-slate-500 mr-1">Positions:</span>
            <span className="font-medium">{plan.num_positions}/{plan.max_positions}</span>
          </div>
          {hasActions && (
            <div className="ml-auto flex items-center gap-2">
              {activeSells.length > 0 && (
                <span className="rounded-full bg-red-500/20 px-2 py-0.5 text-xs text-red-400">
                  {activeSells.length} sell{activeSells.length > 1 ? "s" : ""}
                </span>
              )}
              {activeSwaps.length > 0 && (
                <span className="rounded-full bg-brand-500/20 px-2 py-0.5 text-xs text-brand-400">
                  {activeSwaps.length} swap{activeSwaps.length > 1 ? "s" : ""}
                </span>
              )}
              {actionableBuys.length > 0 && (
                <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-xs text-emerald-400">
                  {actionableBuys.length} buy{actionableBuys.length > 1 ? "s" : ""}
                </span>
              )}
              {signalOnlyBuys.length > 0 && (
                <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-xs text-amber-400">
                  {signalOnlyBuys.length} signal{signalOnlyBuys.length > 1 ? "s" : ""}
                </span>
              )}
              {snoozedActions.length > 0 && (
                <span className="rounded-full bg-slate-500/20 px-2 py-0.5 text-xs text-slate-400">
                  {snoozedActions.length} snoozed
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Symbol search */}
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
            {[44, 36, 40, 32].map((w, i) => (
              <div key={i} className="flex items-center justify-between">
                <Skeleton className={`h-3.5 w-[${w}%]`} />
                <Skeleton className="h-3 w-8" />
              </div>
            ))}
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
          <ScoreBreakdown
            total={checked.score}
            technical={checked.technical_score}
            sentiment={checked.sentiment_score}
            commodity={checked.commodity_score}
          />
          <button
            onClick={() => setCheckedSymbol(null)}
            className="mt-3 text-xs text-slate-500 hover:text-white"
          >
            Dismiss
          </button>
        </div>
      )}
      {checked && !checkLoading && (
        <PriceChart symbol={checked.symbol} />
      )}

      {/* Action plan */}
      {planLoading ? (
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
          {/* Sells */}
          {showExit && activeSells.length > 0 && (
            <div>
              <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
                <AlertTriangle className="h-4 w-4 text-red-400" />
                Sells
              </h2>
              <p className="mb-3 text-xs text-slate-500">Execute these first — stops, profit-taking, and exit signals</p>
              <div className="signal-action-grid">
                {activeSells.map((a, i) => {
                  const key = `sell-${a.symbol}-${i}`;
                  return (
                    <ActionCard
                      key={key}
                      action={a}
                      expanded={expandedCard === key}
                      onToggle={() => toggleCard(key)}
                      onSnooze={handleSnooze}
                      onUnsnooze={handleUnsnooze}
                      snoozing={snoozing}
                    />
                  );
                })}
              </div>
            </div>
          )}

          {/* Swaps */}
          {showSwap && activeSwaps.length > 0 && (
            <div>
              <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
                <ArrowRight className="h-4 w-4 text-brand-400" />
                Swaps
              </h2>
              <p className="mb-3 text-xs text-slate-500">Replace weaker holdings with stronger opportunities</p>
              <div className="signal-action-grid">
                {activeSwaps.map((a, i) => {
                  const key = `swap-${a.sell_symbol}-${i}`;
                  return (
                    <ActionCard
                      key={key}
                      action={a}
                      expanded={expandedCard === key}
                      onToggle={() => toggleCard(key)}
                      onSnooze={handleSnooze}
                      onUnsnooze={handleUnsnooze}
                      snoozing={snoozing}
                    />
                  );
                })}
              </div>
            </div>
          )}

          {/* Actionable Buys */}
          {showBuy && actionableBuys.length > 0 && (
            <div>
              <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
                <TrendingUp className="h-4 w-4 text-emerald-400" />
                Buys
              </h2>
              <p className="mb-3 text-xs text-slate-500">New positions — you have the cash and slots to execute these</p>
              <div className="signal-action-grid">
                {actionableBuys.map((a, i) => {
                  const key = `buy-${a.symbol}-${i}`;
                  return (
                    <ActionCard
                      key={key}
                      action={a}
                      expanded={expandedCard === key}
                      onToggle={() => toggleCard(key)}
                    />
                  );
                })}
              </div>
            </div>
          )}

          {/* Signal-only Buys (not enough cash) */}
          {showSignalOnly && signalOnlyBuys.length > 0 && (
            <div>
              <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
                <DollarSign className="h-4 w-4 text-amber-400" />
                Signals
              </h2>
              <p className="mb-3 text-xs text-slate-500">
                Strong buy signals, but not enough cash to act on — free up funds or add cash to unlock
              </p>
              <div className="signal-action-grid">
                {signalOnlyBuys.map((a, i) => {
                  const key = `signal-${a.symbol}-${i}`;
                  return (
                    <ActionCard
                      key={key}
                      action={a}
                      expanded={expandedCard === key}
                      onToggle={() => toggleCard(key)}
                    />
                  );
                })}
              </div>
            </div>
          )}

          {/* Snoozed actions */}
          {showSnoozedSection && snoozedActions.length > 0 && (
            <div>
              <button
                onClick={() => setShowSnoozed(!showSnoozed)}
                className="mb-3 flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-300 transition-colors"
              >
                <BellOff className="h-4 w-4" />
                {snoozedActions.length} snoozed signal{snoozedActions.length > 1 ? "s" : ""}
                {showSnoozed ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              </button>
              {showSnoozed && (
                <div className="signal-action-grid">
                  {snoozedActions.map((a, i) => {
                    const sym = a.symbol || a.sell_symbol || "";
                    const key = `snoozed-${sym}-${i}`;
                    return (
                      <ActionCard
                        key={key}
                        action={a}
                        expanded={expandedCard === key}
                        onToggle={() => toggleCard(key)}
                        onSnooze={handleSnooze}
                        onUnsnooze={handleUnsnooze}
                        snoozing={snoozing}
                      />
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* No actions */}
          {!hasActions && snoozedActions.length === 0 && (
            <div className="glass-card flex flex-col items-center gap-2 py-12">
              <Zap className="h-8 w-8 text-slate-600" />
              <p className="text-sm text-slate-500">No trades needed right now</p>
              <p className="text-xs text-slate-600">Portfolio is on track. Check back later or search a symbol above.</p>
            </div>
          )}
          {(hasActions || snoozedActions.length > 0) &&
            (viewFilter === "exit" && activeSells.length === 0 ||
              viewFilter === "swap" && activeSwaps.length === 0 ||
              viewFilter === "buy" && actionableBuys.length === 0 ||
              viewFilter === "signal" && signalOnlyBuys.length === 0 ||
              viewFilter === "snoozed" && snoozedActions.length === 0) && (
              <div className="glass-card py-10 text-center text-sm text-slate-500">
                No signals in this filter.
              </div>
            )}
        </>
      )}
    </div>
  );
}
