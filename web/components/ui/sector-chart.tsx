"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { cn } from "@/lib/utils";

interface SectorExposureValue {
  value: number;
  pct: number;
  symbols: string[];
}

interface SectorChartProps {
  exposure: Record<string, number | SectorExposureValue>;
  className?: string;
}

const COLORS = [
  "#2e91ff", "#22c55e", "#f59e0b", "#ef4444", "#a855f7",
  "#06b6d4", "#ec4899", "#f97316", "#14b8a6", "#8b5cf6",
  "#64748b", "#e11d48",
];

export function SectorChart({ exposure, className }: SectorChartProps) {
  const data = Object.entries(exposure)
    .map(([sector, val], i) => {
      const pct = typeof val === "object" && val !== null ? (val as SectorExposureValue).pct : (val as number);
      return {
        sector,
        exposure: Math.round((pct ?? 0) * 10000) / 100,
        fill: COLORS[i % COLORS.length],
      };
    })
    .sort((a, b) => b.exposure - a.exposure);

  if (data.length === 0) {
    return (
      <div className={cn("glass-card p-5", className)}>
        <h3 className="mb-4 text-sm font-medium text-slate-400">
          Sector Exposure
        </h3>
        <div className="flex h-40 items-center justify-center text-slate-500">
          No sector data
        </div>
      </div>
    );
  }

  return (
    <div className={cn("glass-card p-5", className)}>
      <h3 className="mb-4 text-sm font-medium text-slate-400">
        Sector Exposure
      </h3>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} layout="vertical">
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" horizontal={false} />
          <XAxis
            type="number"
            stroke="#64748b"
            fontSize={11}
            tickFormatter={(v) => `${v}%`}
          />
          <YAxis
            type="category"
            dataKey="sector"
            stroke="#64748b"
            fontSize={11}
            width={90}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#1e293b",
              border: "1px solid #334155",
              borderRadius: "8px",
              fontSize: "12px",
            }}
            formatter={(value: number) => [`${value}%`, "Exposure"]}
            labelStyle={{ color: "#94a3b8" }}
          />
          <Bar dataKey="exposure" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
