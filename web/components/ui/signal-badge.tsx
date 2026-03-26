"use client";

import { cn, signalBadgeClass } from "@/lib/utils";

interface SignalBadgeProps {
  signal: string;
  strength?: number;
  className?: string;
}

function getTooltip(signal: string, strength?: number): string {
  const pct = strength !== undefined ? Math.round(strength * 100) : 0;
  switch (signal.toUpperCase()) {
    case "BUY":
      return `Bullish — ${pct}% conviction. More indicators agree on upward momentum. Score ≥ +2 of ±8.`;
    case "SELL":
      return `Bearish — ${pct}% conviction. More indicators agree on downward pressure. Score ≤ -2 of ±8.`;
    case "HOLD":
      return `Neutral — ${pct}% measures slight lean. Indicators are mixed, no strong direction.`;
    default:
      return "";
  }
}

export function SignalBadge({ signal, strength, className }: SignalBadgeProps) {
  return (
    <span
      className={cn(signalBadgeClass(signal), "signal-tooltip", className)}
      data-tooltip={getTooltip(signal, strength)}
    >
      {signal.toUpperCase()}
      {strength !== undefined && (
        <span className="ml-1 opacity-75">{Math.round(strength * 100)}%</span>
      )}
    </span>
  );
}
