"use client";

import { cn, formatCurrency, formatPercent, pnlColor } from "@/lib/utils";
import { usePrivacy } from "@/lib/privacy";
import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  title: string;
  value: string | number;
  change?: number;
  changeLabel?: string;
  icon?: LucideIcon;
  format?: "currency" | "percent" | "number" | "none";
  className?: string;
}

export function StatCard({
  title,
  value,
  change,
  changeLabel,
  icon: Icon,
  format = "none",
  className,
}: StatCardProps) {
  const { mask } = usePrivacy();

  const formatted =
    typeof value === "number"
      ? format === "currency"
        ? mask(formatCurrency(value))
        : format === "percent"
          ? mask(formatPercent(value))
          : value.toLocaleString()
      : value;

  return (
    <div className={cn("glass-card p-5", className)}>
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-400">{title}</p>
        {Icon && <Icon className="h-4 w-4 text-slate-500" />}
      </div>
      <p className="mt-2 text-2xl font-semibold tracking-tight">{formatted}</p>
      {change !== undefined && (
        <p className={cn("mt-1 text-sm", pnlColor(change))}>
          {mask(formatPercent(change))}
          {changeLabel && (
            <span className="ml-1 text-slate-500">{changeLabel}</span>
          )}
        </p>
      )}
    </div>
  );
}
