"use client";

import Link from "next/link";
import { Suspense, useState, useCallback, useRef, useEffect, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import {
  Zap,
  RefreshCw,
  AlertTriangle,
  ArrowRight,
  BellOff,
  Bell,
  Clock,
  X,
  Filter,
  Download,
  ArrowLeft,
  Check,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useActionPlan, useSignalCheck, queryKeys } from "@/lib/hooks";
import type { ActionItem, SignalOut } from "@/lib/api";
import { api } from "@/lib/api";
import { formatCurrency, formatPercent, cn } from "@/lib/utils";
import { usePrivacy } from "@/lib/privacy";
import { Skeleton, SignalCardsSkeleton } from "@/components/ui/loading";
import { PriceChart } from "@/components/ui/price-chart";
import { buildTradeIntentHref } from "@/lib/trade-intent";
import { downloadCsv } from "@/lib/csv";

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
    <div
      ref={ref}
      className="absolute right-0 top-full z-50 mt-2 max-h-[min(70vh,420px)] w-64 overflow-y-auto rounded-xl border border-white/10 bg-zinc-900/95 p-4 shadow-2xl backdrop-blur-xl"
    >
      <div className="mb-3 flex items-center justify-between">
        <span className="text-sm font-medium text-white">Snooze {symbol}</span>
        <button onClick={onClose} className="text-slate-500 hover:text-white">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="mb-3">
        <p className="mb-2 text-xs text-slate-500">Duration</p>
        <div className="grid grid-cols-3 gap-1.5">
          {SNOOZE_DURATIONS.map(({ label, hours }) => (
            <button
              key={label}
              onClick={() => {
                setSelectedHours(hours);
                setIndefinite(false);
              }}
              className={cn(
                "rounded-lg border px-2 py-1.5 text-xs font-medium transition-colors",
                !indefinite && selectedHours === hours
                  ? "border-brand-500/30 bg-brand-500/20 text-brand-400"
                  : "border-white/5 bg-white/5 text-slate-400 hover:bg-white/10"
              )}
            >
              {label}
            </button>
          ))}
        </div>
        <button
          onClick={() => setIndefinite(!indefinite)}
          className={cn(
            "mt-1.5 w-full rounded-lg border px-2 py-1.5 text-xs font-medium transition-colors",
            indefinite
              ? "border-amber-500/30 bg-amber-500/20 text-amber-400"
              : "border-white/5 bg-white/5 text-slate-400 hover:bg-white/10"
          )}
        >
          <Clock className="mr-1 inline h-3 w-3" />
          Indefinite
        </button>
      </div>

      <div className="mb-3">
        <button
          onClick={() => setPhantomTrailingStop(!phantomTrailingStop)}
          className="flex w-full items-center gap-2 rounded-lg border border-white/5 bg-white/5 px-3 py-2 text-left transition-colors hover:bg-white/10"
        >
          <div
            className={cn(
              "flex h-4 w-7 items-center rounded-full transition-colors",
              phantomTrailingStop ? "justify-end bg-brand-500" : "justify-start bg-slate-600"
            )}
          >
            <div className="mx-0.5 h-3 w-3 rounded-full bg-white" />
          </div>
          <div>
            <p className="text-xs font-medium text-white">Phantom trailing stop</p>
            <p className="text-[10px] text-slate-500">Auto-unsnooze if loss worsens 3%+</p>
          </div>
        </button>
      </div>

      <button
        onClick={() => onConfirm(symbol, selectedHours, indefinite, phantomTrailingStop)}
        className="w-full rounded-lg border border-brand-500/20 bg-brand-500/20 py-2 text-xs font-medium text-brand-400 transition-colors hover:bg-brand-500/30"
      >
        <BellOff className="mr-1 inline h-3 w-3" />
        Snooze{" "}
        {indefinite
          ? "indefinitely"
          : SNOOZE_DURATIONS.find((d) => d.hours === selectedHours)?.label ?? `${selectedHours}h`}
      </button>
    </div>
  );
}

function actionSymbol(action: ActionItem): string {
  if (action.type === "SWAP") return action.sell_symbol ?? action.buy_symbol ?? "";
  return action.symbol ?? "";
}

function actionKey(action: ActionItem): string {
  return `${action.type}:${action.symbol ?? ""}:${action.sell_symbol ?? ""}:${action.buy_symbol ?? ""}`;
}

function reasonWithoutScore(reason: string): { label: string; value: number | null } {
  const m = reason.match(/\[([+-]?\d+(?:\.\d+)?)\]$/);
  if (!m) return { label: reason, value: null };
  return {
    label: reason.slice(0, reason.lastIndexOf("[")).trim(),
    value: Number.parseFloat(m[1]),
  };
}

function numberField(source: Record<string, number | null> | null | undefined, key: string): number | null {
  const value = source?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function numberFieldAny(
  source: Record<string, number | null> | null | undefined,
  keys: string[]
): number | null {
  for (const key of keys) {
    const value = source?.[key];
    if (typeof value === "number" && Number.isFinite(value)) return value;
  }
  return null;
}

function formatCompact(value: number): string {
  return new Intl.NumberFormat("en-CA", {
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(value);
}

function sectionMeta(action: ActionItem): {
  score: number | null;
  price: number | null;
  delta: number | null;
  symbol: string;
  sector: string | null;
  detail: string;
  badgeClass: string;
  badgeText: string;
  urgent: boolean;
} {
  if (action.reason === "Suppressed") {
    return {
      score: action.score ?? null,
      price: action.price ?? null,
      delta: null,
      symbol: action.symbol ?? "-",
      sector: action.sector ?? null,
      detail: action.detail,
      badgeClass: "pb-hold",
      badgeText: action.type === "SELL" ? "SELL <30%" : "BUY <35%",
      urgent: false,
    };
  }

  const symbol = action.type === "SWAP"
    ? `${action.sell_symbol ?? "-"} -> ${action.buy_symbol ?? "-"}`
    : action.symbol ?? "-";
  const score = action.score ?? (action.type === "BUY" && action.strength != null ? action.strength * 9 : null);
  const price = action.type === "SWAP" ? action.sell_price ?? null : action.price ?? null;
  const delta = action.type === "SWAP"
    ? action.sell_pnl_pct ?? null
    : action.type === "SELL"
      ? action.pnl_pct ?? null
      : null;

  if (action.type === "SELL") {
    return {
      score,
      price,
      delta,
      symbol,
      sector: action.sector ?? null,
      detail: action.detail,
      badgeClass: action.urgency === "urgent" ? "pb-urgent" : "pb-sell",
      badgeText: action.urgency === "urgent" ? "URGENT" : "SELL",
      urgent: action.urgency === "urgent",
    };
  }
  if (action.type === "SWAP") {
    return {
      score,
      price,
      delta,
      symbol,
      sector: action.sector ?? null,
      detail: action.detail,
      badgeClass: "pb-swap",
      badgeText: "SWAP",
      urgent: false,
    };
  }

  const actionable = action.actionable !== false;
  return {
    score,
    price,
    delta,
    symbol,
    sector: action.sector ?? null,
    detail: action.detail,
    badgeClass: actionable ? "pb-buy" : "pb-hold",
    badgeText: actionable
      ? action.strength != null
        ? `BUY ${(action.strength * 100).toFixed(0)}%`
        : "BUY"
      : "HOLD",
    urgent: false,
  };
}

function SignalRow({ action, onOpen }: { action: ActionItem; onOpen: (symbol: string) => void }) {
  const { mask } = usePrivacy();
  const meta = sectionMeta(action);
  const symbol = actionSymbol(action);

  return (
    <button
      type="button"
      onClick={() => symbol && onOpen(symbol)}
      className={cn("action-row w-full text-left", meta.urgent && "urgent")}
    >
      <div className="conv">
        <span className={cn("score", meta.score != null && (meta.score >= 0 ? "pos" : "neg"))}>
          {meta.score == null ? "-" : `${meta.score >= 0 ? "+" : ""}${meta.score.toFixed(1)}`}
        </span>
        <span className="of">/ 9</span>
      </div>

      <div className="who">
        <div className="sym">
          <span className="t">{meta.symbol}</span>
          {meta.sector && <span className="sector">{meta.sector}</span>}
          <span className={cn("pill-badge", meta.badgeClass)}>{meta.badgeText}</span>
          {action.snoozed && <span className="pill-badge pb-snooze">SNOOZED</span>}
        </div>
        <div className="reason">{meta.detail}</div>
      </div>

      <div className="px">
        <span className="p">{meta.price == null ? "-" : formatCurrency(meta.price)}</span>
        {meta.delta != null ? (
          <span className={cn("d", meta.delta >= 0 ? "pos" : "neg")}>{mask(formatPercent(meta.delta))}</span>
        ) : (
          <span className="d" style={{ color: "var(--surface-500)" }}>{action.reason}</span>
        )}
      </div>

      <span className="go">
        <ArrowRight />
      </span>
    </button>
  );
}

function SignalSection({
  title,
  subtitle,
  tone,
  actions,
  onOpen,
}: {
  title: string;
  subtitle: string;
  tone: "danger" | "brand" | "neutral";
  actions: ActionItem[];
  onOpen: (symbol: string) => void;
}) {
  const titleClass = tone === "danger" ? "text-red-300" : tone === "brand" ? "text-brand-300" : "text-slate-300";
  const Icon = tone === "danger" ? AlertTriangle : Zap;

  if (actions.length === 0) return null;

  return (
    <div className="card signal-list-card">
      <div className="head">
        <h3 className={cn("flex items-center gap-2", titleClass)}>
          <Icon className="h-3.5 w-3.5" />
          {title}
        </h3>
        <span className="sub">{subtitle}</span>
      </div>
      <div>
        {actions.map((action) => (
          <SignalRow key={actionKey(action)} action={action} onOpen={onOpen} />
        ))}
      </div>
    </div>
  );
}

function suppressedReason(signal: SignalOut): string {
  return (
    signal.reasons.find((reason) => reason.startsWith("Suppressed:")) ??
    "Suppressed: below scan threshold"
  );
}

function suppressedToAction(signal: SignalOut): ActionItem {
  return {
    type: signal.signal === "SELL" ? "SELL" : "BUY",
    urgency: "low",
    symbol: signal.symbol,
    price: signal.price ?? undefined,
    strength: signal.strength,
    score: signal.score,
    technical_score: signal.technical_score,
    sentiment_score: signal.sentiment_score,
    commodity_score: signal.commodity_score,
    sector: signal.sector ?? undefined,
    reasons: signal.reasons,
    reason: "Suppressed",
    detail: suppressedReason(signal),
    actionable: false,
  };
}

function SignalDetailSkeleton() {
  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-6 w-72" />
      </div>
      <Skeleton className="h-[360px] w-full rounded-xl" />
      <div className="grid gap-4 lg:grid-cols-[1.5fr_0.9fr]">
        <Skeleton className="h-[320px] w-full rounded-xl" />
        <Skeleton className="h-[320px] w-full rounded-xl" />
      </div>
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
  const { mask } = usePrivacy();

  const [detailSymbol, setDetailSymbol] = useState<string | null>(() => searchParams.get("check"));
  const [viewFilter, setViewFilter] = useState<"all" | "exit" | "buy" | "swap" | "hold" | "suppressed">("all");
  const [snoozing, setSnoozing] = useState(false);
  const [showSnoozePopup, setShowSnoozePopup] = useState(false);

  const { data: plan, isLoading: planLoading, isFetching: refreshing } = useActionPlan();
  const { data: checked, isLoading: checkLoading } = useSignalCheck(detailSymbol);

  const refresh = useCallback(() => {
    qc.invalidateQueries({ queryKey: queryKeys.actionPlan });
    if (detailSymbol) qc.invalidateQueries({ queryKey: queryKeys.signal(detailSymbol) });
  }, [qc, detailSymbol]);

  const openDetail = useCallback(
    (symbol: string) => {
      setShowSnoozePopup(false);
      setDetailSymbol(symbol);
      qc.invalidateQueries({ queryKey: queryKeys.signal(symbol) });
    },
    [qc]
  );

  const closeDetail = useCallback(() => {
    setShowSnoozePopup(false);
    setDetailSymbol(null);
  }, []);

  const handleSnooze = useCallback(
    async (symbol: string, hours: number, indefinite: boolean, phantomTrailingStop: boolean) => {
      setSnoozing(true);
      try {
        await api.snoozeSignal(symbol, hours, indefinite, phantomTrailingStop);
        qc.invalidateQueries({ queryKey: queryKeys.actionPlan });
      } finally {
        setSnoozing(false);
      }
    },
    [qc]
  );

  const handleUnsnooze = useCallback(
    async (symbol: string) => {
      setSnoozing(true);
      try {
        await api.unsnoozeSignal(symbol);
        qc.invalidateQueries({ queryKey: queryKeys.actionPlan });
      } finally {
        setSnoozing(false);
      }
    },
    [qc]
  );

  const exportCsv = useCallback(() => {
    const today = new Date().toISOString().slice(0, 10);
    const rows = (plan?.actions ?? []).map((action) => [
      action.type,
      action.urgency,
      action.symbol ?? "",
      action.sell_symbol ?? "",
      action.buy_symbol ?? "",
      action.actionable ?? "",
      action.snoozed ?? false,
      action.score ?? "",
      action.strength ?? "",
      action.price ?? action.sell_price ?? action.buy_price ?? "",
      action.shares ?? action.sell_shares ?? action.buy_shares ?? "",
      action.pnl_pct ?? action.sell_pnl_pct ?? "",
      action.pnl ?? "",
      action.sector ?? "",
      action.reason,
      action.detail,
      (action.reasons ?? []).join(" | "),
    ]);

    downloadCsv(
      `signals-${today}.csv`,
      [
        "action_type",
        "urgency",
        "symbol",
        "sell_symbol",
        "buy_symbol",
        "actionable",
        "snoozed",
        "score",
        "strength",
        "price",
        "shares",
        "pnl_pct",
        "pnl",
        "sector",
        "reason",
        "detail",
        "reasons",
      ],
      rows
    );
  }, [plan?.actions]);

  const allActions = plan?.actions ?? [];
  const suppressedActions = useMemo(
    () => (plan?.suppressed_signals ?? []).map(suppressedToAction),
    [plan?.suppressed_signals]
  );
  const activeSells = allActions.filter((a) => a.type === "SELL" && !a.snoozed);
  const activeSwaps = allActions.filter((a) => a.type === "SWAP" && !a.snoozed);
  const actionableBuys = allActions.filter((a) => a.type === "BUY" && a.actionable !== false && !a.snoozed);
  const signalOnlyBuys = allActions.filter((a) => a.type === "BUY" && a.actionable === false && !a.snoozed);
  const snoozedActions = allActions.filter((a) => a.snoozed);

  const holdSignals = useMemo(() => {
    const map = new Map<string, ActionItem>();
    [...signalOnlyBuys, ...snoozedActions].forEach((action) => {
      map.set(actionKey(action), action);
    });
    return Array.from(map.values());
  }, [signalOnlyBuys, snoozedActions]);

  const actionableCount = activeSells.length + activeSwaps.length + actionableBuys.length;

  const selectedAction = useMemo(() => {
    if (!detailSymbol) return null;
    const detailActions = [...allActions, ...suppressedActions];
    return (
      detailActions.find((a) => a.symbol === detailSymbol) ??
      detailActions.find((a) => a.sell_symbol === detailSymbol) ??
      detailActions.find((a) => a.buy_symbol === detailSymbol) ??
      null
    );
  }, [allActions, suppressedActions, detailSymbol]);

  const filteredSections = {
    exit: viewFilter === "all" || viewFilter === "exit",
    buy: viewFilter === "all" || viewFilter === "buy",
    swap: viewFilter === "all" || viewFilter === "swap",
    hold: viewFilter === "all" || viewFilter === "hold",
    suppressed: viewFilter === "all" || viewFilter === "suppressed",
  };

  if (detailSymbol) {
    const detailMeta = selectedAction ? sectionMeta(selectedAction) : null;
    const canSnoozeSelected =
      selectedAction != null && selectedAction.reason !== "Suppressed" && selectedAction.type !== "BUY";
    const parsedReasons = (checked?.reasons ?? []).map(reasonWithoutScore);
    const atrHint = (checked?.reasons ?? []).find((r) => r.toLowerCase().startsWith("atr:"));
    const volHint = (checked?.reasons ?? []).find((r) => r.toLowerCase().includes("volume"));
    const tradePlan = checked?.trade_plan;
    const fundamentals = checked?.fundamentals;

    const planEntryLow = numberField(tradePlan, "entry_low");
    const planEntryHigh = numberField(tradePlan, "entry_high");
    const planStopLoss = numberField(tradePlan, "stop_loss");
    const planTakeProfit1 = numberField(tradePlan, "take_profit_1");
    const planTakeProfit2 = numberField(tradePlan, "take_profit_2");
    const planRiskReward = numberFieldAny(tradePlan, ["risk_reward_ratio", "riskRewardRatio"]);
    const planRiskRewardTp1 = numberFieldAny(tradePlan, ["risk_reward_tp1", "riskRewardTp1"]);
    const planRiskRewardTp2 = numberFieldAny(tradePlan, ["risk_reward_tp2", "riskRewardTp2"]);
    const planAtr = numberField(tradePlan, "atr");

    const marketCap = numberFieldAny(fundamentals, ["market_cap", "marketCap"]);
    const peRatio = numberFieldAny(fundamentals, ["pe_ratio", "trailingPE", "forwardPE"]);
    const dividendYield = numberFieldAny(fundamentals, ["dividend_yield", "dividendYield"]);
    const week52Low = numberFieldAny(fundamentals, ["week_52_low", "year_low", "fiftyTwoWeekLow"]);
    const week52High = numberFieldAny(fundamentals, ["week_52_high", "year_high", "fiftyTwoWeekHigh"]);
    const avgVolume = numberFieldAny(fundamentals, ["avg_volume", "averageVolume", "threeMonthAverageVolume"]);
    const referenceEntry =
      (planEntryLow != null && planEntryHigh != null)
        ? (planEntryLow + planEntryHigh) / 2
        : (
          (typeof checked?.price === "number" ? checked.price : null)
          ?? (typeof selectedAction?.price === "number" ? selectedAction.price : null)
          ?? (typeof selectedAction?.buy_price === "number" ? selectedAction.buy_price : null)
        );
    const fallbackRiskReward =
      referenceEntry != null
      && planStopLoss != null
      && planTakeProfit1 != null
      && referenceEntry > planStopLoss
      && planTakeProfit1 > referenceEntry
        ? (planTakeProfit1 - referenceEntry) / (referenceEntry - planStopLoss)
        : null;
    const displayedRiskReward = planRiskReward ?? fallbackRiskReward;
    const recordBuyHref = buildTradeIntentHref({
      open: true,
      action: "buy",
      symbol: checked?.symbol ?? detailSymbol,
      price:
        (typeof checked?.price === "number" ? checked.price : null) ??
        (typeof selectedAction?.price === "number" ? selectedAction.price : null) ??
        (typeof selectedAction?.buy_price === "number" ? selectedAction.buy_price : null),
    });

    return (
      <div className="space-y-5">
        {checkLoading && <SignalDetailSkeleton />}

        {!checkLoading && checked && (
          <>
            <div className="ph">
              <div>
                <div className="mb-2 flex items-center gap-3">
                  <button
                    onClick={closeDetail}
                    className="inline-flex items-center gap-1 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:bg-white/10"
                  >
                    <ArrowLeft className="h-4 w-4" />
                    Signals
                  </button>
                </div>
                <h1>
                  {checked.symbol}
                  {checked.sector && (
                    <span className="ml-3 font-mono text-[22px] font-normal text-slate-500">{checked.sector}</span>
                  )}
                </h1>
                <p className="sub flex flex-wrap items-center gap-2">
                  <span className="font-mono text-[38px] font-semibold leading-none text-slate-100">
                    {checked.price != null ? formatCurrency(checked.price) : "-"}
                  </span>
                  {detailMeta?.delta != null && (
                    <span className={cn("font-mono text-xl", detailMeta.delta >= 0 ? "text-emerald-400" : "text-red-400")}>{mask(formatPercent(detailMeta.delta))}</span>
                  )}
                  <span className="divider">|</span>
                  <span>{atrHint ? atrHint.replace(/^ATR:\s*/i, "ATR ") : "ATR n/a"}</span>
                  <span>|</span>
                  <span>{volHint ?? "Vol n/a"}</span>
                </p>
              </div>

              <div className="actions">
                {detailMeta && <span className={cn("pill-badge", detailMeta.badgeClass)}>{detailMeta.badgeText}</span>}

                {canSnoozeSelected && (
                  <div className="relative">
                    {selectedAction.snoozed ? (
                      <button
                        onClick={() => detailSymbol && handleUnsnooze(detailSymbol)}
                        disabled={snoozing}
                        className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200 transition-colors hover:bg-white/10 disabled:opacity-50"
                      >
                        <Bell className="h-4 w-4" />
                        Unsnooze
                      </button>
                    ) : (
                      <button
                        onClick={() => setShowSnoozePopup((v) => !v)}
                        disabled={snoozing}
                        className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200 transition-colors hover:bg-white/10 disabled:opacity-50"
                      >
                        <BellOff className="h-4 w-4" />
                        Snooze
                      </button>
                    )}
                    {showSnoozePopup && detailSymbol && (
                      <SnoozePopup
                        symbol={detailSymbol}
                        onConfirm={(s, h, ind, pts) => {
                          handleSnooze(s, h, ind, pts);
                          setShowSnoozePopup(false);
                        }}
                        onClose={() => setShowSnoozePopup(false)}
                      />
                    )}
                  </div>
                )}

                <Link href={recordBuyHref} className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-500">
                  <Check className="h-4 w-4" />
                  Record buy
                </Link>
              </div>
            </div>

            <div className="card">
              <div className="head">
                <h3>{checked.symbol} price</h3>
              </div>
              <div className="body" style={{ padding: "8px 10px" }}>
                <PriceChart symbol={checked.symbol} embedded height={360} className="p-0" />
              </div>
            </div>

            <div className="signal-detail-grid">
              <div className="card">
                <div className="head">
                  <h3>Score breakdown</h3>
                  <span className="sub">{parsedReasons.length || 0} indicators | weighted</span>
                </div>
                <div className="body">
                  <div className="reasons">
                    <div className="total">
                      <span className="text-lg text-slate-100">Net score</span>
                      <span className={cn("big", (checked.score ?? 0) >= 0 ? "text-emerald-400" : "text-red-400")}>
                        {(checked.score ?? 0) >= 0 ? "+" : ""}
                        {(checked.score ?? 0).toFixed(1)}
                        <span className="ml-1 text-base font-normal text-slate-500">/ 9</span>
                      </span>
                    </div>

                    {parsedReasons.map((row, idx) => (
                      <div key={`${row.label}-${idx}`} className="row">
                        <span className="lbl">{row.label}</span>
                        <span
                          className={cn(
                            "val",
                            row.value == null ? "mut" : row.value > 0 ? "pos" : row.value < 0 ? "neg" : "mut"
                          )}
                        >
                          {row.value == null ? "--" : `${row.value > 0 ? "+" : ""}${row.value.toFixed(1)}`}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="rail">
                <div className="card">
                  <div className="head">
                    <h3>Trade plan</h3>
                    <span className="sub">suggested</span>
                  </div>
                  <div className="body">
                    <div className="kv">
                      <span className="k">Entry window</span>
                      <span className="v">
                        {planEntryLow != null && planEntryHigh != null
                          ? `${formatCurrency(planEntryLow)} - ${formatCurrency(planEntryHigh)}`
                          : "-"}
                      </span>
                    </div>
                    <div className="kv">
                      <span className="k">Stop loss</span>
                      <span className="v text-red-400">{planStopLoss != null ? formatCurrency(planStopLoss) : "-"}</span>
                    </div>
                    <div className="kv">
                      <span className="k">Take profit 1</span>
                      <span className="v text-emerald-400">{planTakeProfit1 != null ? formatCurrency(planTakeProfit1) : "-"}</span>
                    </div>
                    <div className="kv">
                      <span className="k">Take profit 2</span>
                      <span className="v text-emerald-400">{planTakeProfit2 != null ? formatCurrency(planTakeProfit2) : "-"}</span>
                    </div>
                    <div className="kv">
                      <span className="k">Position size</span>
                      <span className="v">
                        {selectedAction?.shares != null
                          ? `${selectedAction.shares.toFixed(0)} shares${selectedAction.pct_of_portfolio != null ? ` | ${selectedAction.pct_of_portfolio.toFixed(1)}%` : ""}`
                          : "Model suggestion"}
                      </span>
                    </div>
                    <div className="kv">
                      <span className="k">Risk / reward</span>
                      <span className="v">
                        {displayedRiskReward != null ? `1 : ${displayedRiskReward.toFixed(2)}` : "-"}
                        {planRiskRewardTp1 != null && planRiskRewardTp2 != null
                          ? ` (TP1 ${planRiskRewardTp1.toFixed(2)} · TP2 ${planRiskRewardTp2.toFixed(2)})`
                          : ""}
                      </span>
                    </div>
                    <div className="kv">
                      <span className="k">ATR</span>
                      <span className="v">
                        {planAtr != null
                          ? formatCurrency(planAtr)
                          : (atrHint ? atrHint.replace(/^ATR:\s*/i, "") : "n/a")}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="head">
                    <h3>Fundamentals</h3>
                    <span className="sub">trailing</span>
                  </div>
                  <div className="body">
                    <div className="kv">
                      <span className="k">Market cap</span>
                      <span className="v">{marketCap != null ? `$${formatCompact(marketCap)}` : "-"}</span>
                    </div>
                    <div className="kv">
                      <span className="k">P/E</span>
                      <span className="v">{peRatio != null ? peRatio.toFixed(2) : "-"}</span>
                    </div>
                    <div className="kv">
                      <span className="k">Dividend yield</span>
                      <span className="v">{dividendYield != null ? `${(dividendYield * 100).toFixed(2)}%` : "-"}</span>
                    </div>
                    <div className="kv">
                      <span className="k">52w range</span>
                      <span className="v">
                        {week52Low != null && week52High != null
                          ? `${formatCurrency(week52Low)} - ${formatCurrency(week52High)}`
                          : "-"}
                      </span>
                    </div>
                    <div className="kv">
                      <span className="k">Avg volume</span>
                      <span className="v">{avgVolume != null ? formatCompact(avgVolume) : "-"}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </>
        )}

        {!checkLoading && !checked && (
          <div className="glass-card p-8 text-center">
            <p className="text-sm text-slate-400">Could not load signal details for {detailSymbol}.</p>
            <button
              onClick={closeDetail}
              className="mt-3 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300 hover:bg-white/10"
            >
              Back to signals
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="ph">
        <div>
          <h1>Signals</h1>
          <p className="sub">
            Updated now | 333 symbols scanned
            <span className="divider">|</span>
            <span className="text-emerald-400">{actionableCount} actionable</span>
            <span className="divider">|</span>
            <span className="text-slate-500">{holdSignals.length} hold</span>
            <span className="divider">|</span>
            <span className="text-slate-500">{suppressedActions.length} suppressed</span>
          </p>
        </div>
        <div className="actions">
          <button className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-300 transition-colors hover:bg-white/10">
            <Filter className="h-4 w-4" />
            Filters
          </button>
          <button
            onClick={exportCsv}
            className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-300 transition-colors hover:bg-white/10"
          >
            <Download className="h-4 w-4" />
            Export CSV
          </button>
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
        <button className={viewFilter === "all" ? "on" : ""} onClick={() => setViewFilter("all")}>All<span className="c">{allActions.length + suppressedActions.length}</span></button>
        <button className={viewFilter === "exit" ? "on" : ""} onClick={() => setViewFilter("exit")}>Exit alerts<span className="c">{activeSells.length}</span></button>
        <button className={viewFilter === "buy" ? "on" : ""} onClick={() => setViewFilter("buy")}>Buy signals<span className="c">{actionableBuys.length}</span></button>
        <button className={viewFilter === "swap" ? "on" : ""} onClick={() => setViewFilter("swap")}>Swaps<span className="c">{activeSwaps.length}</span></button>
        <button className={viewFilter === "hold" ? "on" : ""} onClick={() => setViewFilter("hold")}>Holds<span className="c">{holdSignals.length}</span></button>
        <button className={viewFilter === "suppressed" ? "on" : ""} onClick={() => setViewFilter("suppressed")}>Suppressed<span className="c">{suppressedActions.length}</span></button>
      </div>

      {planLoading ? (
        <div className="space-y-4">
          <SignalCardsSkeleton count={3} />
        </div>
      ) : (
        <>
          {filteredSections.exit && (
            <SignalSection
              title="Exit alerts"
              subtitle="Act on these before open"
              tone="danger"
              actions={activeSells}
              onOpen={openDetail}
            />
          )}

          {filteredSections.buy && (
            <SignalSection
              title="Buy signals"
              subtitle={`${actionableBuys.length} actionable | sorted by conviction`}
              tone="brand"
              actions={actionableBuys}
              onOpen={openDetail}
            />
          )}

          {filteredSections.swap && (
            <SignalSection
              title="Swap signals"
              subtitle="Replace weaker holdings with stronger setups"
              tone="brand"
              actions={activeSwaps}
              onOpen={openDetail}
            />
          )}

          {filteredSections.hold && (
            <SignalSection
              title="Holds"
              subtitle="Not actionable yet or currently snoozed"
              tone="neutral"
              actions={holdSignals}
              onOpen={openDetail}
            />
          )}

          {filteredSections.suppressed && (
            <SignalSection
              title="Suppressed"
              subtitle="BUY/SELL signals below scan thresholds"
              tone="neutral"
              actions={suppressedActions}
              onOpen={openDetail}
            />
          )}

          {allActions.length === 0 && suppressedActions.length === 0 && (
            <div className="glass-card flex flex-col items-center gap-2 py-12">
              <Zap className="h-8 w-8 text-slate-600" />
              <p className="text-sm text-slate-500">No trades needed right now</p>
              <p className="text-xs text-slate-600">Portfolio is on track. Check back later.</p>
            </div>
          )}

          {(allActions.length > 0 || suppressedActions.length > 0) &&
            ((viewFilter === "exit" && activeSells.length === 0) ||
              (viewFilter === "buy" && actionableBuys.length === 0) ||
              (viewFilter === "swap" && activeSwaps.length === 0) ||
              (viewFilter === "hold" && holdSignals.length === 0) ||
              (viewFilter === "suppressed" && suppressedActions.length === 0)) && (
              <div className="glass-card py-10 text-center text-sm text-slate-500">No signals in this filter.</div>
            )}
        </>
      )}
    </div>
  );
}
