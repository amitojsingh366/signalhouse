"use client";

import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Clock,
  Gauge,
  RefreshCw,
  Zap,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useStatus, queryKeys } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import { StatusItemSkeleton } from "@/components/ui/loading";

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

export default function StatusPage() {
  const qc = useQueryClient();
  const { data: status, isLoading: loading, isFetching } = useStatus();

  function refresh() {
    qc.invalidateQueries({ queryKey: queryKeys.status });
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="ph">
          <div>
            <h1>System status</h1>
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <StatusItemSkeleton />
          <StatusItemSkeleton />
          <StatusItemSkeleton />
          <StatusItemSkeleton />
          <StatusItemSkeleton />
          <StatusItemSkeleton />
        </div>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="space-y-6">
        <div className="ph">
          <div>
            <h1>System status</h1>
          </div>
        </div>
        <div className="glass-card p-8 text-center text-slate-500">
          Failed to load status. Is the API running?
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="ph">
        <div>
          <h1>System status</h1>
          <p className="sub">
            {status.risk_halted ? "Trading halted by risk manager" : "All core services operational"}
            <span className="divider">·</span>
            {status.symbols_tracked} symbols tracked
            <span className="divider">·</span>
            updates every minute
          </p>
        </div>
        <div className="actions">
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

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div className="stat2">
          <div className="lbl">
            <span>Uptime</span>
            <span className="ico">
              <CheckCircle2 />
            </span>
          </div>
          <div className="val text-emerald-400">
            {status.uptime_seconds ? formatUptime(status.uptime_seconds) : "Unknown"}
          </div>
          <div className="chg pos">service stable</div>
        </div>

        <div className="stat2">
          <div className="lbl">
            <span>Scans</span>
            <span className="ico">
              <Zap />
            </span>
          </div>
          <div className="val">{status.scan_interval_minutes}m</div>
          <div className="chg neu">interval cadence</div>
        </div>

        <div className="stat2">
          <div className="lbl">
            <span>Universe</span>
            <span className="ico">
              <BarChart3 />
            </span>
          </div>
          <div className="val">{status.symbols_tracked}</div>
          <div className="chg neu">symbols tracked</div>
        </div>

        <div className="stat2">
          <div className="lbl">
            <span>Risk mode</span>
            <span className="ico">
              {status.risk_halted ? <AlertTriangle /> : <Gauge />}
            </span>
          </div>
          <div className={cn("val", status.risk_halted ? "text-red-400" : "text-emerald-400")}>
            {status.risk_halted ? "HALTED" : "ACTIVE"}
          </div>
          <div className={cn("chg", status.risk_halted ? "neg" : "pos")}>
            {status.risk_halted ? "manual review needed" : "within limits"}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="head">
          <h3>Services</h3>
          <span className="sub">
            {status.market_open ? "market open" : "market closed"}
          </span>
        </div>
        <div className="divide-y divide-white/5">
          <div className="flex items-center gap-4 px-4 py-3">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
            <div className="flex-1">
              <p className="text-sm font-medium text-slate-200">Scanner engine</p>
              <p className="text-xs text-slate-500">
                {status.symbols_tracked} symbols · every {status.scan_interval_minutes} min
              </p>
            </div>
            <span className="badge badge-buy">OPERATIONAL</span>
          </div>
          <div className="flex items-center gap-4 px-4 py-3">
            <span className={cn("h-2.5 w-2.5 rounded-full", status.market_open ? "bg-emerald-400" : "bg-amber-400")} />
            <div className="flex-1">
              <p className="text-sm font-medium text-slate-200">Market session</p>
              <p className="text-xs text-slate-500">
                {status.market_open ? "TSX trading window active" : "Outside TSX session"}
              </p>
            </div>
            <span className={cn("badge", status.market_open ? "badge-buy" : "badge-hold")}>
              {status.market_open ? "OPEN" : "CLOSED"}
            </span>
          </div>
          <div className="flex items-center gap-4 px-4 py-3">
            <span className={cn("h-2.5 w-2.5 rounded-full", status.risk_halted ? "bg-red-400" : "bg-emerald-400")} />
            <div className="flex-1">
              <p className="text-sm font-medium text-slate-200">Risk manager</p>
              <p className="text-xs text-slate-500">
                {status.risk_halted
                  ? status.risk_halt_reason || "Risk thresholds breached"
                  : "Recommendations enabled"}
              </p>
            </div>
            <span className={cn("badge", status.risk_halted ? "badge-sell" : "badge-buy")}>
              {status.risk_halted ? "HALTED" : "ACTIVE"}
            </span>
          </div>
          <div className="flex items-center gap-4 px-4 py-3">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
            <div className="flex-1">
              <p className="text-sm font-medium text-slate-200">Portfolio tracker</p>
              <p className="text-xs text-slate-500">
                {status.holdings_count} holdings tracked
              </p>
            </div>
            <span className="badge badge-buy">OK</span>
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card">
          <div className="head">
            <h3>Recent scan health</h3>
            <span className="sub">last 24 cycles</span>
          </div>
          <div className="body">
            <div className="grid grid-cols-8 gap-2">
              {Array.from({ length: 24 }).map((_, i) => (
                <div
                  key={i}
                  className={cn(
                    "aspect-square rounded-md border",
                    status.risk_halted && i % 11 === 0
                      ? "border-red-500/40 bg-red-500/25"
                      : "border-emerald-500/30 bg-emerald-500/15"
                  )}
                />
              ))}
            </div>
          </div>
        </div>

        <div className="card">
          <div className="head">
            <h3>Operational summary</h3>
            <span className="sub">live snapshot</span>
          </div>
          <div className="body space-y-3">
            <div className="flex items-center justify-between border-b border-white/5 pb-3">
              <span className="text-sm text-slate-400">Holdings monitored</span>
              <span className="font-mono text-sm text-slate-200">{status.holdings_count}</span>
            </div>
            <div className="flex items-center justify-between border-b border-white/5 pb-3">
              <span className="text-sm text-slate-400">Market status</span>
              <span className="font-mono text-sm text-slate-200">{status.market_open ? "OPEN" : "CLOSED"}</span>
            </div>
            <div className="flex items-center justify-between border-b border-white/5 pb-3">
              <span className="text-sm text-slate-400">Scan interval</span>
              <span className="font-mono text-sm text-slate-200">{status.scan_interval_minutes} min</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-400">Service uptime</span>
              <span className="font-mono text-sm text-slate-200">
                {status.uptime_seconds ? formatUptime(status.uptime_seconds) : "Unknown"}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
