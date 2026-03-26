"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Search, Command } from "lucide-react";
import { api } from "@/lib/api";
import type { SymbolInfo } from "@/lib/api";
import { cn } from "@/lib/utils";

export function CommandSearch() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [symbols, setSymbols] = useState<SymbolInfo[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Load symbols when modal opens
  useEffect(() => {
    if (open) {
      api.getSymbols().then(setSymbols).catch(() => {});
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  // Cmd+K / Ctrl+K listener
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
      if (e.key === "Escape") {
        setOpen(false);
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  const filtered = query.length > 0
    ? symbols.filter(
        (s) =>
          s.symbol.toLowerCase().includes(query.toLowerCase()) ||
          s.name.toLowerCase().includes(query.toLowerCase())
      ).slice(0, 8)
    : [];

  const selectSymbol = useCallback((symbol: string) => {
    setOpen(false);
    setQuery("");
    router.push(`/signals?check=${encodeURIComponent(symbol)}`);
  }, [router]);

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && filtered.length > 0) {
      e.preventDefault();
      selectSymbol(filtered[selectedIndex].symbol);
    }
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center pt-[20vh]"
      onClick={() => setOpen(false)}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      {/* Modal */}
      <div
        className="relative w-full max-w-lg rounded-xl border border-white/10 bg-surface-900 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 border-b border-white/10 px-4 py-3">
          <Search className="h-5 w-5 text-slate-500" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setSelectedIndex(0); }}
            onKeyDown={handleKeyDown}
            placeholder="Search symbol to check signal..."
            className="flex-1 bg-transparent text-sm text-white placeholder-slate-500 outline-none"
          />
          <kbd className="hidden rounded border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] text-slate-500 sm:inline-block">
            ESC
          </kbd>
        </div>

        {/* Results */}
        {filtered.length > 0 && (
          <div className="max-h-64 overflow-y-auto py-2">
            {filtered.map((s, i) => (
              <button
                key={s.symbol}
                onClick={() => selectSymbol(s.symbol)}
                className={cn(
                  "flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors",
                  i === selectedIndex ? "bg-white/10" : "hover:bg-white/5"
                )}
              >
                <span className="font-medium text-white">{s.symbol}</span>
                <span className="truncate text-slate-500">{s.name}</span>
                <span className="ml-auto text-xs text-slate-600">{s.sector}</span>
              </button>
            ))}
          </div>
        )}

        {/* Empty state */}
        {query.length > 0 && filtered.length === 0 && (
          <div className="px-4 py-8 text-center text-sm text-slate-500">
            No symbols matching &ldquo;{query}&rdquo;
          </div>
        )}

        {/* Hint when empty */}
        {query.length === 0 && (
          <div className="px-4 py-8 text-center text-sm text-slate-500">
            Type a symbol or name to check its signal
          </div>
        )}
      </div>
    </div>
  );
}
