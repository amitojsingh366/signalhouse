"use client";

import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton h-4 w-full", className)} />;
}

/* ── StatCard skeleton (matches stat-card.tsx layout) ── */
export function CardSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("glass-card p-5", className)}>
      {/* Title row with icon */}
      <div className="flex items-center justify-between">
        <Skeleton className="h-3.5 w-24" />
        <Skeleton className="h-4 w-4 rounded" />
      </div>
      {/* Large value */}
      <Skeleton className="mt-2 h-7 w-28" />
      {/* Change % + label */}
      <Skeleton className="mt-1 h-3.5 w-20" />
    </div>
  );
}

/* ── StatusItem skeleton (matches status page StatusItem: icon box + label/value) ── */
export function StatusItemSkeleton() {
  return (
    <div className="glass-card flex items-center gap-4 p-5">
      <Skeleton className="h-11 w-11 shrink-0 rounded-lg" />
      <div className="space-y-2">
        <Skeleton className="h-3.5 w-24" />
        <Skeleton className="h-5 w-16" />
      </div>
    </div>
  );
}

/* ── Holdings table skeleton (matches portfolio DataTable: 8 columns) ── */
export function HoldingsTableSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="glass-card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/10">
              {["Symbol", "Qty", "Avg Cost", "Price", "Value", "P&L", "Signal", ""].map((h) => (
                <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-400">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {Array.from({ length: rows }).map((_, i) => (
              <tr key={i}>
                <td className="px-4 py-3"><Skeleton className="h-4 w-20" /></td>
                <td className="px-4 py-3 text-right"><Skeleton className="ml-auto h-4 w-10" /></td>
                <td className="px-4 py-3 text-right"><Skeleton className="ml-auto h-4 w-14" /></td>
                <td className="px-4 py-3 text-right"><Skeleton className="ml-auto h-4 w-14" /></td>
                <td className="px-4 py-3 text-right"><Skeleton className="ml-auto h-4 w-16" /></td>
                <td className="px-4 py-3 text-right"><Skeleton className="ml-auto h-4 w-24" /></td>
                <td className="px-4 py-3"><Skeleton className="h-5 w-16 rounded-full" /></td>
                <td className="px-4 py-3"><Skeleton className="h-3.5 w-3.5 rounded" /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── Trades table skeleton (matches trades DataTable: 7 columns) ── */
export function TradesTableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="glass-card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/10">
              {["Date", "Action", "Symbol", "Qty", "Price", "Total", "P&L"].map((h) => (
                <th key={h} className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-slate-400">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {Array.from({ length: rows }).map((_, i) => (
              <tr key={i}>
                <td className="px-4 py-3"><Skeleton className="h-4 w-20" /></td>
                <td className="px-4 py-3"><Skeleton className="h-5 w-12 rounded-full" /></td>
                <td className="px-4 py-3"><Skeleton className="h-4 w-20" /></td>
                <td className="px-4 py-3 text-right"><Skeleton className="ml-auto h-4 w-10" /></td>
                <td className="px-4 py-3 text-right"><Skeleton className="ml-auto h-4 w-14" /></td>
                <td className="px-4 py-3 text-right"><Skeleton className="ml-auto h-4 w-16" /></td>
                <td className="px-4 py-3 text-right"><Skeleton className="ml-auto h-4 w-14" /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── Generic table skeleton (fallback) ── */
export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="glass-card overflow-hidden">
      <div className="border-b border-white/10 px-4 py-3">
        <Skeleton className="h-3 w-full" />
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="flex gap-4 border-b border-white/5 px-4 py-3"
        >
          <Skeleton className="h-4 w-16" />
          <Skeleton className="h-4 w-12" />
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-16" />
        </div>
      ))}
    </div>
  );
}

/* ── Equity chart skeleton ── */
export function ChartSkeleton({ height = 280, className }: { height?: number; className?: string }) {
  return (
    <div className={cn("glass-card p-5", className)}>
      <div className="mb-4 flex items-center justify-between">
        <Skeleton className="h-4 w-24" />
        <div className="flex gap-1">
          {Array.from({ length: 7 }).map((_, i) => (
            <Skeleton key={i} className="h-7 w-8 rounded-md" />
          ))}
        </div>
      </div>
      <div style={{ height: height - 60 }} className="relative overflow-hidden">
        {/* Fake chart silhouette */}
        <svg className="absolute inset-0 h-full w-full px-8 pb-6" preserveAspectRatio="none">
          <defs>
            <linearGradient id="skelGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="white" stopOpacity="0.06" />
              <stop offset="100%" stopColor="white" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path
            d="M0,80 Q30,60 60,65 T120,50 T180,55 T240,40 T300,45 T360,30 T420,35 T480,25 T540,30 T600,20 L600,100 L0,100 Z"
            fill="url(#skelGrad)"
            className="animate-pulse"
            vectorEffect="non-scaling-stroke"
          />
          <path
            d="M0,80 Q30,60 60,65 T120,50 T180,55 T240,40 T300,45 T360,30 T420,35 T480,25 T540,30 T600,20"
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth="2"
            className="animate-pulse"
            vectorEffect="non-scaling-stroke"
          />
        </svg>
        {/* Axis lines */}
        <div className="absolute bottom-5 left-8 right-0">
          <Skeleton className="h-px w-full opacity-30" />
        </div>
        <div className="absolute bottom-0 left-8 right-0 flex justify-between">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-3 w-10" />
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── Sector chart skeleton (horizontal bar chart) ── */
export function SectorChartSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("glass-card p-5", className)}>
      <Skeleton className="mb-4 h-4 w-32" />
      {/* Matches BarChart layout="vertical" with YAxis width=90 */}
      <div className="space-y-4" style={{ height: 200 }}>
        {[80, 60, 40, 20].map((w, i) => (
          <div key={i} className="flex items-center gap-3">
            <Skeleton className="h-3.5 w-[90px] shrink-0" />
            <div className="skeleton h-5 rounded" style={{ width: `${w}%` }} />
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Dashboard signals preview skeleton (matches signal card grid) ── */
export function SignalsSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="glass-card p-5">
      <div className="mb-4 flex items-center justify-between">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-3 w-14" />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: count }).map((_, i) => (
          <div
            key={i}
            className="flex items-center justify-between rounded-lg border border-white/5 bg-white/5 px-4 py-3"
          >
            <div className="space-y-1.5">
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-3 w-32" />
            </div>
            <Skeleton className="h-5 w-20 rounded-full" />
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Signal cards skeleton (matches SignalCard: symbol, score, badge, price, sector, reasons) ── */
export function SignalCardsSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="glass-card p-4">
          {/* Header: symbol + score + badge */}
          <div className="mb-2 flex items-center justify-between">
            <Skeleton className="h-5 w-24" />
            <div className="flex items-center gap-2">
              <Skeleton className="h-3 w-10" />
              <Skeleton className="h-5 w-20 rounded-full" />
            </div>
          </div>
          {/* Price */}
          <Skeleton className="mb-2 h-3.5 w-28" />
          {/* Sector */}
          <Skeleton className="mb-2 h-3 w-20" />
          {/* Score breakdown reasons */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Skeleton className="h-3 w-40" />
              <Skeleton className="h-3 w-8" />
            </div>
            <div className="flex items-center justify-between">
              <Skeleton className="h-3 w-32" />
              <Skeleton className="h-3 w-8" />
            </div>
            <div className="flex items-center justify-between">
              <Skeleton className="h-3 w-28" />
              <Skeleton className="h-3 w-8" />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function UploadingSpinner() {
  return (
    <div className="flex flex-col items-center gap-4 py-4">
      <div className="h-10 w-10 animate-spin rounded-full border-[3px] border-brand-500/30 border-t-brand-500" />
      <div className="text-center">
        <p className="text-sm font-medium text-slate-200">Analyzing screenshot&hellip;</p>
        <p className="mt-1 text-xs text-slate-500">This may take up to a minute</p>
      </div>
    </div>
  );
}

export function PageLoader() {
  return (
    <div className="flex h-64 items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
    </div>
  );
}
