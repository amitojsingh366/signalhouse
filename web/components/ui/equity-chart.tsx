"use client";

import { useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SnapshotOut } from "@/lib/api";
import { cn, formatCurrency } from "@/lib/utils";

const RANGES = [
  { label: "1D", days: 1 },
  { label: "3D", days: 3 },
  { label: "7D", days: 7 },
  { label: "1M", days: 30 },
  { label: "3M", days: 90 },
  { label: "1Y", days: 365 },
  { label: "ALL", days: Infinity },
] as const;

interface EquityChartProps {
  snapshots: SnapshotOut[];
  className?: string;
}

export function EquityChart({ snapshots, className }: EquityChartProps) {
  const [range, setRange] = useState(3); // default 1M

  const selected = RANGES[range];
  const cutoff =
    selected.days === Infinity
      ? snapshots
      : snapshots.slice(-selected.days);

  const data = cutoff.map((s) => ({
    date: s.date,
    value: s.portfolio_value,
  }));

  const isPositive =
    data.length >= 2 && data[data.length - 1].value >= data[0].value;

  return (
    <div className={cn("glass-card p-5", className)}>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-medium text-slate-400">Equity Curve</h3>
        <div className="flex gap-1">
          {RANGES.map((r, i) => (
            <button
              key={r.label}
              onClick={() => setRange(i)}
              className={cn(
                "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                i === range
                  ? "bg-brand-600 text-white"
                  : "text-slate-400 hover:text-white hover:bg-white/10"
              )}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {data.length === 0 ? (
        <div className="flex h-48 items-center justify-center text-slate-500">
          No snapshot data yet
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={data}>
            <defs>
              <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="5%"
                  stopColor={isPositive ? "#22c55e" : "#ef4444"}
                  stopOpacity={0.3}
                />
                <stop
                  offset="95%"
                  stopColor={isPositive ? "#22c55e" : "#ef4444"}
                  stopOpacity={0}
                />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis
              dataKey="date"
              stroke="#64748b"
              fontSize={11}
              tickLine={false}
            />
            <YAxis
              stroke="#64748b"
              fontSize={11}
              tickLine={false}
              tickFormatter={(v) => `$${v}`}
              domain={["dataMin - 20", "dataMax + 20"]}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#1e293b",
                border: "1px solid #334155",
                borderRadius: "8px",
                fontSize: "12px",
              }}
              formatter={(value: number) => [formatCurrency(value), "Value"]}
              labelStyle={{ color: "#94a3b8" }}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke={isPositive ? "#22c55e" : "#ef4444"}
              strokeWidth={2}
              fill="url(#colorValue)"
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
