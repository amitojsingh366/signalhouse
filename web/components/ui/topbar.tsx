"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import {
  Bell,
  ChevronRight,
  Eye,
  EyeOff,
  Home,
  RefreshCw,
  Search,
} from "lucide-react";
import { useStatus } from "@/lib/hooks";
import { usePrivacy } from "@/lib/privacy";
import { cn } from "@/lib/utils";

function pageLabel(pathname: string): string {
  if (pathname === "/") return "Dashboard";
  if (pathname.startsWith("/signals")) return "Signals";
  if (pathname.startsWith("/portfolio")) return "Portfolio";
  if (pathname.startsWith("/premarket")) return "Pre-market";
  if (pathname.startsWith("/trades")) return "Trades";
  if (pathname.startsWith("/upload")) return "Upload";
  if (pathname.startsWith("/status")) return "Status";
  if (pathname.startsWith("/settings")) return "Settings";
  if (pathname.startsWith("/debug")) return "Debug";
  return "Dashboard";
}

function formatEasternNow(): string {
  return new Intl.DateTimeFormat("en-CA", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "America/Toronto",
  }).format(new Date());
}

export function TopBar() {
  const pathname = usePathname();
  const qc = useQueryClient();
  const { data: status, isFetching } = useStatus();
  const { hidden, toggle: togglePrivacy } = usePrivacy();
  const [timeEt, setTimeEt] = useState(() => formatEasternNow());

  const page = useMemo(() => pageLabel(pathname), [pathname]);

  useEffect(() => {
    const id = window.setInterval(() => setTimeEt(formatEasternNow()), 60_000);
    return () => window.clearInterval(id);
  }, []);

  function openSearch() {
    document.dispatchEvent(
      new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true })
    );
  }

  function refreshAll() {
    qc.invalidateQueries();
  }

  return (
    <header className="topbar">
      <div className="crumb">
        <span className="home">
          <Home />
        </span>
        <span className="chev">
          <ChevronRight />
        </span>
        <span className="page">{page}</span>
      </div>

      <span className="sep" />

      <div className={cn("mkt", status && !status.market_open && "closed")}>
        <span className="dot" />
        <span>{status?.market_open ? "TSX OPEN" : "TSX CLOSED"}</span>
        <span style={{ color: "var(--surface-600)" }}>·</span>
        <span>{timeEt} ET</span>
      </div>

      <button className="search-k" onClick={openSearch}>
        <Search />
        <span>Search any symbol…</span>
        <span className="k-hint">⌘K</span>
      </button>

      <button className="icon-btn" title="Notifications">
        <Bell />
        <span className="bump" />
      </button>

      <button
        className="icon-btn"
        title={hidden ? "Show numbers" : "Hide numbers"}
        onClick={togglePrivacy}
      >
        {hidden ? <EyeOff /> : <Eye />}
      </button>

      <button
        className="icon-btn"
        title="Refresh"
        onClick={refreshAll}
        disabled={isFetching}
      >
        <RefreshCw className={cn(isFetching && "animate-spin")} />
      </button>

      <div className="avatar">AS</div>
    </header>
  );
}
