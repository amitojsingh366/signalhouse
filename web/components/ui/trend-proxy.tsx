import { useMemo } from "react";

import { cn } from "@/lib/utils";

interface SparkPoint {
  date: string;
  close: number;
}

interface TrendProxyProps {
  positive?: boolean;
  points?: SparkPoint[];
  className?: string;
}

function buildPath(points: SparkPoint[]): { line: string; area: string; positive: boolean } | null {
  if (points.length < 2) return null;
  const closes = points
    .map((point) => point.close)
    .filter((value) => Number.isFinite(value));
  if (closes.length < 2) return null;

  const first = closes[0];
  const last = closes[closes.length - 1];
  const positive = last >= first;
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const span = max - min || 1;

  const width = 92;
  const xStart = 2;
  const yTop = 4;
  const yBottom = 20;
  const ySpan = yBottom - yTop;
  const step = width / Math.max(1, closes.length - 1);

  const coords = closes.map((value, index) => {
    const x = xStart + step * index;
    const norm = (value - min) / span;
    const y = yBottom - norm * ySpan;
    return `${x.toFixed(2)} ${y.toFixed(2)}`;
  });

  const line = `M${coords[0]} L${coords.slice(1).join(" L")}`;
  const lastX = xStart + width;
  const area = `${line} L${lastX.toFixed(2)} 22 L2 22 Z`;
  return { line, area, positive };
}

export function TrendProxy({ positive = true, points = [], className }: TrendProxyProps) {
  const dynamicPath = useMemo(() => buildPath(points), [points]);
  const effectivePositive = dynamicPath?.positive ?? positive;

  const stroke = effectivePositive ? "#34d399" : "#ef4444";
  const fill = effectivePositive ? "rgba(52, 211, 153, 0.16)" : "rgba(239, 68, 68, 0.14)";
  const fallbackLine = effectivePositive
    ? "M2 18 C20 16, 36 12, 52 10 C66 8, 78 7, 94 6"
    : "M2 6 C20 8, 36 12, 52 14 C66 16, 78 17, 94 18";
  const fallbackArea = `${fallbackLine} L94 22 L2 22 Z`;

  return (
    <svg className={cn("spark-sm", className)} viewBox="0 0 96 24" fill="none" aria-hidden>
      <path d={dynamicPath?.area ?? fallbackArea} fill={fill} />
      <path d={dynamicPath?.line ?? fallbackLine} stroke={stroke} strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}
