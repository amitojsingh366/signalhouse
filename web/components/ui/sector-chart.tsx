"use client";

import { useState, useCallback } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
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

// Purple gradient from bright to dim
function getPurpleShade(index: number, total: number, activeIndex: number | null): string {
  // Base opacity: highest bar is brightest, lowest is dimmest
  const baseOpacity = 1 - (index / Math.max(total - 1, 1)) * 0.6;
  // When hovering, dim all except the active one
  if (activeIndex !== null) {
    return index === activeIndex
      ? `rgba(167, 139, 250, ${Math.min(baseOpacity + 0.15, 1)})`
      : `rgba(167, 139, 250, ${baseOpacity * 0.35})`;
  }
  return `rgba(167, 139, 250, ${baseOpacity})`;
}

export function SectorChart({ exposure, className }: SectorChartProps) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  const data = Object.entries(exposure)
    .map(([sector, val]) => {
      const pct = typeof val === "object" && val !== null ? (val as SectorExposureValue).pct : (val as number);
      return {
        sector,
        exposure: Math.round((pct ?? 0) * 10000) / 100,
      };
    })
    .sort((a, b) => b.exposure - a.exposure);

  const handleMouseEnter = useCallback((_: unknown, index: number) => {
    setActiveIndex(index);
  }, []);

  const handleMouseLeave = useCallback(() => {
    setActiveIndex(null);
  }, []);

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
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" horizontal={false} />
          <XAxis
            type="number"
            stroke="#52525b"
            fontSize={11}
            tickFormatter={(v) => `${v}%`}
          />
          <YAxis
            type="category"
            dataKey="sector"
            stroke="#52525b"
            fontSize={11}
            width={90}
            tickLine={false}
          />
          <Tooltip
            cursor={false}
            contentStyle={{
              backgroundColor: "#18181b",
              border: "1px solid rgba(167, 139, 250, 0.3)",
              borderRadius: "8px",
              fontSize: "12px",
              color: "#e4e4e7",
              boxShadow: "0 4px 12px rgba(0, 0, 0, 0.4)",
            }}
            formatter={(value: number) => [`${value}%`, "Exposure"]}
            labelStyle={{ color: "#a78bfa", fontWeight: 500 }}
            itemStyle={{ color: "#e4e4e7" }}
          />
          <Bar
            dataKey="exposure"
            radius={[0, 4, 4, 0]}
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
          >
            {data.map((_, index) => (
              <Cell
                key={`cell-${index}`}
                fill={getPurpleShade(index, data.length, activeIndex)}
                style={{ transition: "fill 0.2s ease" }}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
