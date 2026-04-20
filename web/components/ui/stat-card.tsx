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
    <div className={cn("stat2", className)}>
      <div className="lbl">
        <span>{title}</span>
        {Icon && (
          <span className="ico">
            <Icon className="h-4 w-4" />
          </span>
        )}
      </div>
      <p className="val">{formatted}</p>
      {change !== undefined && (
        <p className={cn("chg", pnlColor(change))}>
          {mask(formatPercent(change))}
          {changeLabel && (
            <span className="ml-1 text-slate-500">{changeLabel}</span>
          )}
        </p>
      )}
    </div>
  );
}
