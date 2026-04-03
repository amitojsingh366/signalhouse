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
import { usePriceHistory } from "@/lib/hooks";
import { cn, formatCurrency } from "@/lib/utils";
import { Skeleton } from "@/components/ui/loading";

const RANGES = [
  { label: "5D", period: "5d" },
  { label: "1W", period: "7d" },
  { label: "1M", period: "30d" },
  { label: "2M", period: "60d" },
  { label: "6M", period: "6mo" },
  { label: "1Y", period: "1y" },
  { label: "5Y", period: "5y" },
] as const;

interface PriceChartProps {
  symbol: string;
  className?: string;
}

export function PriceChart({ symbol, className }: PriceChartProps) {
  const [rangeIdx, setRangeIdx] = useState(3); // default 2M
  const { data: priceData, isLoading: loading } = usePriceHistory(symbol, RANGES[rangeIdx].period);

  const data = (priceData?.bars ?? []).map((b) => ({
    date: b.date,
    close: b.close,
  }));

  const isPositive =
    data.length >= 2 && data[data.length - 1].close >= data[0].close;

  const gradientId = `priceGrad-${symbol.replace(/[^a-zA-Z0-9]/g, "")}`;

  return (
    <div className={cn("glass-card p-5", className)}>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-medium text-slate-400">
          {symbol} Price
        </h3>
        <div className="flex gap-1">
          {RANGES.map((r, i) => (
            <button
              key={r.label}
              onClick={() => setRangeIdx(i)}
              className={cn(
                "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                i === rangeIdx
                  ? "bg-brand-600 text-white"
                  : "text-slate-400 hover:text-white hover:bg-white/10"
              )}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <Skeleton className="h-[220px] w-full rounded-lg" />
      ) : data.length === 0 ? (
        <div className="flex h-[220px] items-center justify-center text-slate-500">
          No price data available
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={data}>
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="5%"
                  stopColor={isPositive ? "#a78bfa" : "#ef4444"}
                  stopOpacity={0.3}
                />
                <stop
                  offset="95%"
                  stopColor={isPositive ? "#a78bfa" : "#ef4444"}
                  stopOpacity={0}
                />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
            <XAxis
              dataKey="date"
              stroke="#52525b"
              fontSize={11}
              tickLine={false}
              tickFormatter={(v) => {
                const d = new Date(v + "T00:00:00");
                return d.toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                });
              }}
            />
            <YAxis
              stroke="#52525b"
              fontSize={11}
              tickLine={false}
              tickFormatter={(v) => `$${v}`}
              domain={["dataMin - 1", "dataMax + 1"]}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#18181b",
                border: "1px solid rgba(167, 139, 250, 0.3)",
                borderRadius: "8px",
                fontSize: "12px",
                color: "#e4e4e7",
                boxShadow: "0 4px 12px rgba(0, 0, 0, 0.4)",
              }}
              formatter={(value: number) => [formatCurrency(value), "Close"]}
              labelFormatter={(label) => {
                const d = new Date(label + "T00:00:00");
                return d.toLocaleDateString("en-US", {
                  weekday: "short",
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                });
              }}
              labelStyle={{ color: "#a78bfa", fontWeight: 500 }}
            />
            <Area
              type="monotone"
              dataKey="close"
              stroke={isPositive ? "#a78bfa" : "#ef4444"}
              strokeWidth={2}
              fill={`url(#${gradientId})`}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
