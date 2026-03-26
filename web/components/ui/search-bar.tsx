"use client";

import { useState, useEffect, useRef } from "react";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";
import type { SymbolInfo } from "@/lib/api";

interface SearchBarProps {
  symbols: SymbolInfo[];
  onSelect: (symbol: string) => void;
  placeholder?: string;
  className?: string;
}

export function SearchBar({
  symbols,
  onSelect,
  placeholder = "Search symbol...",
  className,
}: SearchBarProps) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const filtered = query.length > 0
    ? symbols.filter(
        (s) =>
          s.symbol.toLowerCase().includes(query.toLowerCase()) ||
          s.name.toLowerCase().includes(query.toLowerCase())
      ).slice(0, 8)
    : [];

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  return (
    <div ref={ref} className={cn("relative", className)}>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          placeholder={placeholder}
          className="w-full rounded-lg border border-white/10 bg-white/5 py-2.5 pl-10 pr-4 text-sm text-white placeholder-slate-500 outline-none transition-colors focus:border-brand-500/50 focus:bg-white/10"
        />
      </div>
      {open && filtered.length > 0 && (
        <div className="absolute left-0 right-0 top-full z-50 mt-1 rounded-lg border border-white/10 bg-surface-800 py-1 shadow-xl">
          {filtered.map((s) => (
            <button
              key={s.symbol}
              onClick={() => {
                onSelect(s.symbol);
                setQuery("");
                setOpen(false);
              }}
              className="flex w-full items-center gap-3 px-4 py-2 text-left text-sm hover:bg-white/5"
            >
              <span className="font-medium text-white">{s.symbol}</span>
              <span className="truncate text-slate-500">{s.name}</span>
              <span className="ml-auto text-xs text-slate-600">{s.sector}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
