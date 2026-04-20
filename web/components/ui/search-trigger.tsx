"use client";

import { Search } from "lucide-react";

/** Inline button that opens the Cmd+K command search modal */
export function SearchTrigger({ className }: { className?: string }) {
  function open() {
    // Dispatch Cmd+K to trigger the CommandSearch modal
    document.dispatchEvent(
      new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true })
    );
  }

  return (
    <button
      onClick={open}
      className={`flex items-center gap-2 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-sm text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.08] ${className ?? ""}`}
    >
      <Search className="h-4 w-4" />
      <span className="hidden sm:inline">Search symbol</span>
      <kbd className="hidden rounded border border-white/10 bg-white/5 px-1.5 py-px text-[10px] leading-none text-slate-500 sm:inline-block">
        ⌘K
      </kbd>
    </button>
  );
}
