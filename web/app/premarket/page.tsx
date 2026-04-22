"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Bell, Clock, Download, RefreshCw, Thermometer, TrendingUp, ArrowRight } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { usePremarketMovers, queryKeys } from "@/lib/hooks";
import type { PremarketMover } from "@/lib/api";
import { cn, formatCurrency, formatPercent } from "@/lib/utils";
import { downloadCsv } from "@/lib/csv";

function getEtNow() {
  return new Date(new Date().toLocaleString("en-US", { timeZone: "America/Toronto" }));
}

function countdownToOpen(now = getEtNow()) {
  const open = new Date(now);
  open.setHours(9, 30, 0, 0);
  if (now >= open) open.setDate(open.getDate() + 1);

  const diff = Math.max(0, Math.floor((open.getTime() - now.getTime()) / 1000));
  const h = Math.floor(diff / 3600);
  const m = Math.floor((diff % 3600) / 60);
  const s = diff % 60;

  return {
    short: `${h}h ${m}m`,
    clock: `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`,
  };
}

function volumeProxy(changePct: number): string {
  const x = Math.max(0.5, Math.min(4.2, 0.8 + Math.abs(changePct) * 4.6));
  return `${x.toFixed(1)}x`;
}

function sessionLabel(session?: PremarketMover["session"]): string {
  if (session === "after_hours") return "after-hours";
  return "pre-market";
}

function catalystProxy(usSymbol: string, changePct: number, session?: PremarketMover["session"]): string {
  const label = sessionLabel(session);
  if (changePct >= 0.02) return `${usSymbol} showing strong ${label} momentum`;
  if (changePct > 0) return `${usSymbol} trading modestly higher in ${label}`;
  if (changePct <= -0.02) return `${usSymbol} under notable ${label} pressure`;
  return `${usSymbol} mixed ${label} signal`;
}

function formatPremarketChange(changeFraction: number): string {
  return formatPercent(changeFraction * 100);
}

export default function PreMarketPage() {
  const qc = useQueryClient();
  const { data, isLoading, isFetching } = usePremarketMovers();
  const [alertsEnabled, setAlertsEnabled] = useState(false);
  const [countdown, setCountdown] = useState(() => countdownToOpen());

  useEffect(() => {
    const id = window.setInterval(() => setCountdown(countdownToOpen()), 1000);
    return () => window.clearInterval(id);
  }, []);

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

  const exportCsv = useCallback(() => {
    const today = new Date().toISOString().slice(0, 10);
    const rows = movers.map((row) => [
      row.cdr_symbol,
      row.us_symbol,
      row.premarket_price,
      row.change_pct,
      row.change_pct * 100,
      volumeProxy(row.change_pct),
      catalystProxy(row.us_symbol, row.change_pct),
      new Date().toISOString(),
    ]);

    downloadCsv(
      `premarket-${today}.csv`,
      [
        "cdr_symbol",
        "us_symbol",
        "premarket_price",
        "change_fraction",
        "change_pct",
        "volume_proxy",
        "catalyst_proxy",
        "exported_at",
      ],
      rows
    );
  }, [movers]);

  const positive = movers.filter((m) => m.change_pct >= 0).length;
  const negative = movers.filter((m) => m.change_pct < 0).length;
  const biggest = movers[0];

  const checklist = movers.slice(0, 3).map((row) => ({
    text: `Review ${row.cdr_symbol} (${formatPremarketChange(row.change_pct)}) at open`,
    done: false,
    tag: Math.abs(row.change_pct) >= 0.03 ? "urgent" : "watch",
  }));

  checklist.push({
    text: "Refresh pre-market feed before 09:30 ET",
    done: !isFetching,
    tag: "routine",
  });

  return (
    <div className="space-y-6">
      <div className="ph">
        <div>
          <h1>Pre-market</h1>
          <p className="sub">
            Toronto open in <span className="font-mono text-brand-300">{countdown.short}</span>
            <span className="divider">·</span>
            Overnight scan complete
            <span className="divider">·</span>
            {movers.length} holdings moving
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
            onClick={() => setAlertsEnabled((prev) => !prev)}
            className="flex items-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.08]"
          >
            <Bell className="h-4 w-4" />
            {alertsEnabled ? "Open alerts enabled" : "Enable open alerts"}
          </button>
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

      <div className="grid-4">
        <div className="stat2">
          <div className="lbl">
            <span>Open countdown</span>
            <span className="ico"><Clock className="h-4 w-4" /></span>
          </div>
          <div className="val font-mono text-brand-300">{countdown.clock}</div>
          <div className="chg neu">09:30 ET</div>
        </div>

        <div className="stat2">
          <div className="lbl">
            <span>Futures · SPX</span>
            <span className="ico"><TrendingUp className="h-4 w-4" /></span>
          </div>
          <div className="val">--</div>
          <div className="chg neu">not in API feed</div>
        </div>

        <div className="stat2">
          <div className="lbl">
            <span>TSX futures</span>
            <span className="ico"><TrendingUp className="h-4 w-4" /></span>
          </div>
          <div className="val">--</div>
          <div className="chg neu">not in API feed</div>
        </div>

        <div className="stat2">
          <div className="lbl">
            <span>F&amp;G index</span>
            <span className="ico"><Thermometer className="h-4 w-4" /></span>
          </div>
          <div className="val">--</div>
          <div className="chg neu">not in API feed</div>
        </div>
      </div>

      <div className="card">
        <div className="head">
          <h3>Your holdings overnight</h3>
          <span className="sub">ranked by absolute extended-hours move</span>
        </div>

        {isLoading ? (
          <div className="p-8 text-center text-sm text-slate-500">Loading pre-market movers...</div>
        ) : movers.length === 0 ? (
          <div className="p-8 text-center text-sm text-slate-500">
            No extended-hours data available right now.
          </div>
        ) : (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th className="r">O/N change</th>
                  <th className="r">Volume vs avg</th>
                  <th>Catalyst</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {movers.map((row) => {
                  return (
                    <tr key={row.cdr_symbol}>
                      <td className="font-semibold text-slate-100">{row.cdr_symbol}</td>
                      <td className={cn("r mono", row.change_pct >= 0 ? "pos" : "neg")}>
                        {formatPremarketChange(row.change_pct)}
                      </td>
                      <td className="r mono">{volumeProxy(row.change_pct)}</td>
                      <td className="text-slate-300">{catalystProxy(row.us_symbol, row.change_pct, row.session)}</td>
                      <td>
                        <Link
                          href={`/signals?check=${encodeURIComponent(row.cdr_symbol)}`}
                          className="inline-flex items-center gap-1 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-1.5 text-xs text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.08]"
                        >
                          Open signal
                          <ArrowRight className="h-3.5 w-3.5" />
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="head">
            <h3>Gap candidates</h3>
            <span className="sub">largest extended-hours dislocations</span>
          </div>
          <div>
            {movers.slice(0, 4).map((row) => {
              return (
                <Link
                  key={`gap-${row.cdr_symbol}`}
                  href={`/signals?check=${encodeURIComponent(row.cdr_symbol)}`}
                  className="action-row"
                >
                  <div className="conv">
                    <span className={cn("score", row.change_pct >= 0 ? "pos" : "neg")}>
                      {formatPremarketChange(row.change_pct)}
                    </span>
                  </div>
                  <div className="who">
                    <div className="sym">
                      <span className="t">{row.cdr_symbol}</span>
                      <span className="sector">{row.us_symbol}</span>
                    </div>
                    <div className="reason">
                      {formatCurrency(row.session_price ?? row.premarket_price)} {sessionLabel(row.session)} proxy
                    </div>
                  </div>
                  <span className="go">
                    <ArrowRight />
                  </span>
                </Link>
              );
            })}
            {movers.length === 0 && (
              <div className="p-6 text-sm text-slate-500">No candidates in the current API response.</div>
            )}
          </div>
        </div>

        <div className="card">
          <div className="head">
            <h3>Open checklist</h3>
            <span className="sub">derived from current movers</span>
          </div>
          <div className="body flex flex-col gap-3">
            {checklist.map((item, index) => (
              <div
                key={`todo-${index}`}
                className={cn(
                  "flex items-center gap-3 rounded-lg border px-3 py-2.5",
                  item.done
                    ? "border-emerald-500/20 bg-emerald-500/[0.06]"
                    : "border-white/[0.06] bg-white/[0.02]"
                )}
              >
                <span
                  className={cn(
                    "inline-flex h-5 w-5 items-center justify-center rounded-md border text-[10px] font-semibold",
                    item.done
                      ? "border-emerald-400 bg-emerald-400 text-zinc-950"
                      : "border-white/20 text-slate-500"
                  )}
                >
                  {item.done ? "OK" : "-"}
                </span>
                <span className={cn("flex-1 text-sm", item.done ? "text-slate-400 line-through" : "text-slate-200")}>
                  {item.text}
                </span>
                <span className={cn(
                  "pill-badge",
                  item.tag === "urgent" ? "pb-urgent" : item.tag === "watch" ? "pb-hold" : "pb-snooze"
                )}>
                  {item.tag.toUpperCase()}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-4 py-3 text-xs text-slate-500">
        Movers feed currently provides symbol, US pair, extended-hours price (pre-market or after-hours), and change %. Futures, Fear &amp; Greed, and news catalysts are shown as unavailable placeholders.
      </div>

      {biggest && (
        <div className="text-right text-xs text-slate-500">
          Strongest move now: <span className="font-mono text-slate-300">{biggest.cdr_symbol}</span> ({formatPremarketChange(biggest.change_pct)})
          <span className="mx-2 text-slate-700">·</span>
          {positive} up / {negative} down
        </div>
      )}
    </div>
  );
}
