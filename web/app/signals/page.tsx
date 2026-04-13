"use client";

import { Suspense, useState, useCallback, useRef, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { Zap, RefreshCw, AlertTriangle, ArrowRight, TrendingDown, TrendingUp, BellOff, Bell, ChevronDown, ChevronUp, Clock, ShieldAlert, X, DollarSign } from "lucide-react";
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

function ScoreTag({ text }: { text: string }) {
  const match = text.match(/\[([+-][\d.]+)\]$/);
  if (!match) return <span>{text}</span>;
  const label = text.slice(0, text.lastIndexOf("[")).trim();
  const value = parseFloat(match[1]);
  const color = value > 0 ? "text-emerald-400" : value < 0 ? "text-red-400" : "text-slate-500";
  return (
    <span className="flex items-center justify-between gap-2">
      <span>{label}</span>
      <span className={cn("font-mono text-[10px] tabular-nums", color)}>{match[1]}</span>
    </span>
  );
}

function ScoreBreakdown({
  technical,
  sentiment,
  commodity,
}: {
  technical?: number;
  sentiment?: number;
  commodity?: number;
}) {
  const rows = [
    { label: "Technical", value: technical ?? 0 },
    { label: "Sentiment", value: sentiment ?? 0 },
    { label: "Commodity", value: commodity ?? 0 },
  ];
  return (
    <div className="mt-2 rounded-lg border border-white/10 bg-white/[0.02] p-2">
      <p className="mb-1 text-[10px] uppercase tracking-wide text-slate-500">Score Mix</p>
      <div className="space-y-1">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center justify-between text-xs">
            <span className="text-slate-400">{row.label}</span>
            <span className={cn("font-mono", row.value > 0 ? "text-emerald-400" : row.value < 0 ? "text-red-400" : "text-slate-500")}>
              {row.value > 0 ? "+" : ""}{row.value.toFixed(2)}
            </span>
          </div>
        ))}
      </div>
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
  const isSnoozed = action.snoozed;
  const [showSnoozePopup, setShowSnoozePopup] = useState(false);

  if (action.type === "SELL") {
    const isUrgent = action.urgency === "urgent";
    const isLow = action.urgency === "low";
    return (
      <div className={cn(
        "glass-card border transition-all",
        isSnoozed ? "border-slate-700/30 bg-white/[0.01] opacity-60"
          : isUrgent ? "border-red-500/30 bg-red-500/[0.05]"
          : isLow ? "border-slate-500/20 bg-white/[0.02]"
          : "border-amber-500/20 bg-amber-500/[0.03]"
      )}>
        <button onClick={onToggle} className="w-full p-4 text-left">
          <div className="mb-2 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <TrendingDown className={cn("h-4 w-4", isSnoozed ? "text-slate-500" : isUrgent ? "text-red-400" : isLow ? "text-slate-400" : "text-amber-400")} />
              <span className="text-lg font-semibold">{action.symbol}</span>
            </div>
            <div className="flex items-center gap-2">
              {isSnoozed && (
                <span className="rounded-full px-2 py-0.5 text-xs font-medium bg-slate-500/20 text-slate-400">
                  SNOOZED
                </span>
              )}
              <span className={cn(
                "rounded-full px-2 py-0.5 text-xs font-medium",
                isSnoozed ? "bg-slate-500/20 text-slate-500"
                  : isUrgent ? "bg-red-500/20 text-red-400" : isLow ? "bg-slate-500/20 text-slate-400" : "bg-amber-500/20 text-amber-400"
              )}>
                {isUrgent ? "URGENT" : action.reason}
              </span>
            </div>
          </div>
          <p className="mb-3 text-sm font-medium text-white">{action.detail}</p>
          <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400">
            <span>Shares: {mask(String(action.shares?.toFixed(4) ?? ""))}</span>
            <span>Price: {formatCurrency(action.price ?? 0)}</span>
            <span>Value: {mask(formatCurrency(action.dollar_amount ?? 0))}</span>
            {action.pnl_pct != null && (
              <span className={cn("font-medium", action.pnl_pct >= 0 ? "text-emerald-400" : "text-red-400")}>
                {mask(formatPercent(action.pnl_pct))}
              </span>
            )}
          </div>
        </button>
        {/* Snooze button */}
        <div className="relative flex items-center gap-2 px-4 pb-3">
          {isSnoozed ? (
            <button
              onClick={(e) => { e.stopPropagation(); onUnsnooze?.(sym); }}
              disabled={snoozing}
              className="flex items-center gap-1 rounded-md border border-slate-600/30 px-2 py-1 text-xs text-slate-400 hover:text-white hover:border-white/20 transition-colors"
            >
              <Bell className="h-3 w-3" /> Unsnooze
            </button>
          ) : (
            <>
              <button
                onClick={(e) => { e.stopPropagation(); setShowSnoozePopup(!showSnoozePopup); }}
                disabled={snoozing}
                className="flex items-center gap-1 rounded-md border border-slate-600/30 px-2 py-1 text-xs text-slate-400 hover:text-white hover:border-white/20 transition-colors"
              >
                <BellOff className="h-3 w-3" /> Snooze
              </button>
              {showSnoozePopup && (
                <SnoozePopup
                  symbol={sym}
                  onConfirm={(s, h, ind, pts) => { onSnooze?.(s, h, ind, pts); setShowSnoozePopup(false); }}
                  onClose={() => setShowSnoozePopup(false)}
                />
              )}
            </>
          )}
          <span className="ml-auto text-[10px] text-slate-600">
            {expanded ? "click to hide chart" : "click to view chart"}
          </span>
        </div>
        {expanded && sym && <div className="px-2 pb-3"><PriceChart symbol={sym} /></div>}
      </div>
    );
  }

  if (action.type === "SWAP") {
    const sellSym = action.sell_symbol ?? "";
    return (
      <div className={cn(
        "glass-card border transition-all",
        isSnoozed ? "border-slate-700/30 bg-white/[0.01] opacity-60"
          : "border-brand-500/20 bg-brand-500/[0.03]"
      )}>
        <button onClick={onToggle} className="w-full p-4 text-left">
          <div className="mb-2 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ArrowRight className="h-4 w-4 text-brand-400" />
              <span className="text-lg font-semibold">
                {action.sell_symbol} <span className="text-slate-500 mx-1">&rarr;</span> {action.buy_symbol}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {isSnoozed && (
                <span className="rounded-full px-2 py-0.5 text-xs font-medium bg-slate-500/20 text-slate-400">
                  SNOOZED
                </span>
              )}
              <span className="rounded-full px-2 py-0.5 text-xs font-medium bg-brand-500/20 text-brand-400">
                SWAP
              </span>
            </div>
          </div>
          <p className="mb-3 text-sm font-medium text-white">{action.detail}</p>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="rounded-lg bg-red-500/[0.05] border border-red-500/10 p-2">
              <p className="font-medium text-red-400 mb-1">Sell {action.sell_symbol}</p>
              <p className="text-slate-400">{mask(String(action.sell_shares?.toFixed(4) ?? ""))} shares @ {formatCurrency(action.sell_price ?? 0)}</p>
              <p className="text-slate-400">{mask(formatCurrency(action.sell_amount ?? 0))}
                {action.sell_pnl_pct != null && (
                  <span className={cn("ml-1", action.sell_pnl_pct >= 0 ? "text-emerald-400" : "text-red-400")}>
                    {mask(formatPercent(action.sell_pnl_pct))}
                  </span>
                )}
              </p>
            </div>
            <div className="rounded-lg bg-emerald-500/[0.05] border border-emerald-500/10 p-2">
              <p className="font-medium text-emerald-400 mb-1">Buy {action.buy_symbol}</p>
              <p className="text-slate-400">{action.buy_shares} shares @ ~{formatCurrency(action.buy_price ?? 0)}</p>
              <p className="text-slate-400">{mask(formatCurrency(action.buy_amount ?? 0))}
                {action.buy_strength != null && (
                  <span className="ml-1 text-emerald-400">{(action.buy_strength * 100).toFixed(0)}% signal</span>
                )}
              </p>
            </div>
          </div>
        </button>
        {/* Snooze button */}
        <div className="relative flex items-center gap-2 px-4 pb-3">
          {isSnoozed ? (
            <button
              onClick={(e) => { e.stopPropagation(); onUnsnooze?.(sellSym); }}
              disabled={snoozing}
              className="flex items-center gap-1 rounded-md border border-slate-600/30 px-2 py-1 text-xs text-slate-400 hover:text-white hover:border-white/20 transition-colors"
            >
              <Bell className="h-3 w-3" /> Unsnooze
            </button>
          ) : (
            <>
              <button
                onClick={(e) => { e.stopPropagation(); setShowSnoozePopup(!showSnoozePopup); }}
                disabled={snoozing}
                className="flex items-center gap-1 rounded-md border border-slate-600/30 px-2 py-1 text-xs text-slate-400 hover:text-white hover:border-white/20 transition-colors"
              >
                <BellOff className="h-3 w-3" /> Snooze
              </button>
              {showSnoozePopup && (
                <SnoozePopup
                  symbol={sellSym}
                  onConfirm={(s, h, ind, pts) => { onSnooze?.(s, h, ind, pts); setShowSnoozePopup(false); }}
                  onClose={() => setShowSnoozePopup(false)}
                />
              )}
            </>
          )}
          <span className="ml-auto text-[10px] text-slate-600">
            {expanded ? "click to hide chart" : "click to view chart"}
          </span>
        </div>
        {expanded && sellSym && <div className="px-2 pb-3"><PriceChart symbol={sellSym} /></div>}
      </div>
    );
  }

  // BUY
  const isActionable = action.actionable !== false;
  return (
    <div className={cn(
      "glass-card border",
      isActionable
        ? "border-emerald-500/20 bg-emerald-500/[0.03]"
        : "border-slate-500/20 bg-white/[0.02] opacity-75"
    )}>
      <button onClick={onToggle} className="w-full p-4 text-left">
        <div className="mb-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TrendingUp className={cn("h-4 w-4", isActionable ? "text-emerald-400" : "text-slate-500")} />
            <span className="text-lg font-semibold">{action.symbol}</span>
          </div>
          <div className="flex items-center gap-2">
            {!isActionable && (
              <span className="rounded-full px-2 py-0.5 text-xs font-medium bg-amber-500/20 text-amber-400">
                SIGNAL ONLY
              </span>
            )}
            {action.strength != null && (
              <SignalBadge signal="BUY" strength={action.strength} />
            )}
          </div>
        </div>
        <p className={cn("mb-3 text-sm font-medium", isActionable ? "text-white" : "text-amber-400/90")}>{action.detail}</p>
        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400">
          {isActionable && <span>Shares: {action.shares}</span>}
          <span>Price: ~{formatCurrency(action.price ?? 0)}</span>
          {isActionable && <span>Cost: {mask(formatCurrency(action.dollar_amount ?? 0))}</span>}
          {isActionable && action.pct_of_portfolio != null && (
            <span>{mask(`${action.pct_of_portfolio.toFixed(1)}%`)} of portfolio</span>
          )}
          {action.sector && <span className="text-slate-500">{action.sector}</span>}
        </div>
        {action.reasons && action.reasons.length > 0 && (
          <ul className="mt-2 space-y-0.5">
            {action.reasons.filter(r => !r.startsWith("Price:") && !r.startsWith("ATR:")).slice(0, 4).map((r, i) => (
              <li key={i} className="text-xs text-slate-500">
                <ScoreTag text={r} />
              </li>
            ))}
          </ul>
        )}
        <ScoreBreakdown
          technical={action.technical_score}
          sentiment={action.sentiment_score}
          commodity={action.commodity_score}
        />
      </button>
      <div className="px-4 pb-3">
        <span className="text-[10px] text-slate-600">
          {expanded ? "click to hide chart" : "click to view chart"}
        </span>
      </div>
      {expanded && sym && <div className="px-2 pb-3"><PriceChart symbol={sym} /></div>}
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Action Plan</h1>
        <button
          onClick={refresh}
          disabled={refreshing}
          className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-300 transition-colors hover:bg-white/10"
        >
          <RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} />
          Refresh
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
          {activeSells.length > 0 && (
            <div>
              <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
                <AlertTriangle className="h-4 w-4 text-red-400" />
                Sells
              </h2>
              <p className="mb-3 text-xs text-slate-500">Execute these first — stops, profit-taking, and exit signals</p>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
          {activeSwaps.length > 0 && (
            <div>
              <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
                <ArrowRight className="h-4 w-4 text-brand-400" />
                Swaps
              </h2>
              <p className="mb-3 text-xs text-slate-500">Replace weaker holdings with stronger opportunities</p>
              <div className="grid gap-4 lg:grid-cols-2">
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
          {actionableBuys.length > 0 && (
            <div>
              <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
                <TrendingUp className="h-4 w-4 text-emerald-400" />
                Buys
              </h2>
              <p className="mb-3 text-xs text-slate-500">New positions — you have the cash and slots to execute these</p>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
          {signalOnlyBuys.length > 0 && (
            <div>
              <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
                <DollarSign className="h-4 w-4 text-amber-400" />
                Signals
              </h2>
              <p className="mb-3 text-xs text-slate-500">
                Strong buy signals, but not enough cash to act on — free up funds or add cash to unlock
              </p>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
          {snoozedActions.length > 0 && (
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
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
        </>
      )}
    </div>
  );
}
