"use client";

import { cn } from "@/lib/utils";

const SCORE_SUFFIX_RE = /\[([+-][\d.]+)\]$/;

function parseScoreTag(text: string): { label: string; raw: string; value: number } | null {
  const match = text.match(SCORE_SUFFIX_RE);
  if (!match) return null;
  const value = parseFloat(match[1]);
  if (Number.isNaN(value)) return null;
  const label = text.slice(0, text.lastIndexOf("[")).trim();
  return { label, raw: match[1], value };
}

function scoreColor(value: number): string {
  if (value > 0) return "text-emerald-400";
  if (value < 0) return "text-red-400";
  return "text-slate-500";
}

export function ScoreTag({ text }: { text: string }) {
  const parsed = parseScoreTag(text);
  if (!parsed) return <span>{text}</span>;

  return (
    <span className="flex items-center justify-between gap-2">
      <span>{parsed.label}</span>
      <span className={cn("font-mono text-[10px] tabular-nums", scoreColor(parsed.value))}>
        {parsed.raw}
      </span>
    </span>
  );
}

export function ScoreBreakdown({
  technical,
  sentiment,
  commodity,
}: {
  technical?: number;
  sentiment?: number;
  commodity?: number;
}) {
  const rows = [
    { label: "Technical", value: technical ?? 0 },
    { label: "Sentiment", value: sentiment ?? 0 },
    { label: "Commodity", value: commodity ?? 0 },
  ];

  return (
    <div className="mt-2 rounded-lg border border-white/10 bg-white/[0.02] p-2">
      <p className="mb-1 text-[10px] uppercase tracking-wide text-slate-500">Score Mix</p>
      <div className="space-y-1">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center justify-between text-xs">
            <span className="text-slate-400">{row.label}</span>
            <span className={cn("font-mono", scoreColor(row.value))}>
              {row.value > 0 ? "+" : ""}
              {row.value.toFixed(2)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
