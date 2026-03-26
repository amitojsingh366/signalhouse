"use client";

import {
  Activity,
  Clock,
  BarChart3,
  Briefcase,
  AlertTriangle,
  CheckCircle,
  RefreshCw,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useStatus, queryKeys } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import { CardSkeleton } from "@/components/ui/loading";
import { SearchTrigger } from "@/components/ui/search-trigger";

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function StatusItem({
  icon: Icon,
  label,
  value,
  status: itemStatus,
}: {
  icon: typeof Activity;
  label: string;
  value: string | number;
  status?: "ok" | "warning" | "error";
}) {
  const statusColors = {
    ok: "text-emerald-400",
    warning: "text-yellow-400",
    error: "text-red-400",
  };

  return (
    <div className="glass-card flex items-center gap-4 p-5">
      <div
        className={cn(
          "rounded-lg p-3",
          itemStatus === "ok"
            ? "bg-emerald-500/20"
            : itemStatus === "error"
              ? "bg-red-500/20"
              : itemStatus === "warning"
                ? "bg-yellow-500/20"
                : "bg-white/10"
        )}
      >
        <Icon
          className={cn(
            "h-5 w-5",
            itemStatus ? statusColors[itemStatus] : "text-slate-400"
          )}
        />
      </div>
      <div>
        <p className="text-sm text-slate-400">{label}</p>
        <p className="text-lg font-semibold">{value}</p>
      </div>
    </div>
  );
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
        <h1 className="text-2xl font-bold">Status</h1>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Status</h1>
        <div className="glass-card p-8 text-center text-slate-500">
          Failed to load status. Is the API running?
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Status</h1>
        <div className="flex items-center gap-2">
          <SearchTrigger />
          <button
            onClick={refresh}
            disabled={isFetching}
            className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-300 transition-colors hover:bg-white/10"
          >
            <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
            Refresh
          </button>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatusItem
          icon={status.market_open ? CheckCircle : Clock}
          label="Market Status"
          value={status.market_open ? "Open" : "Closed"}
          status={status.market_open ? "ok" : undefined}
        />
        <StatusItem
          icon={Activity}
          label="Uptime"
          value={
            status.uptime_seconds
              ? formatUptime(status.uptime_seconds)
              : "Unknown"
          }
          status="ok"
        />
        <StatusItem
          icon={BarChart3}
          label="Symbols Tracked"
          value={status.symbols_tracked}
        />
        <StatusItem
          icon={Briefcase}
          label="Holdings"
          value={status.holdings_count}
        />
        <StatusItem
          icon={Clock}
          label="Scan Interval"
          value={`${status.scan_interval_minutes} min`}
        />
        <StatusItem
          icon={status.risk_halted ? AlertTriangle : CheckCircle}
          label="Risk Status"
          value={status.risk_halted ? "HALTED" : "Active"}
          status={status.risk_halted ? "error" : "ok"}
        />
      </div>

      {status.risk_halted && status.risk_halt_reason && (
        <div className="glass-card border-red-500/30 bg-red-500/5 p-5">
          <div className="flex items-center gap-3">
            <AlertTriangle className="h-5 w-5 text-red-400" />
            <div>
              <p className="font-medium text-red-400">
                Risk Manager — Recommendations Halted
              </p>
              <p className="mt-1 text-sm text-slate-400">
                {status.risk_halt_reason}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
