"use client";

import { cn, signalBadgeClass } from "@/lib/utils";

interface SignalBadgeProps {
  signal: string;
  strength?: number;
  className?: string;
}

export function SignalBadge({ signal, strength, className }: SignalBadgeProps) {
  return (
    <span className={cn(signalBadgeClass(signal), className)}>
      {signal.toUpperCase()}
      {strength !== undefined && (
        <span className="ml-1 opacity-75">{Math.round(strength * 100)}%</span>
      )}
    </span>
  );
}
