"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Bug,
  Home,
  ArrowLeftRight,
  Briefcase,
  Zap,
  Sunrise,
  Upload,
  Activity,
  Settings,
  Menu,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useState, useEffect } from "react";

const DEBUG_LS_KEY = "debug_last_visited";
const DEBUG_TTL_MS = 24 * 60 * 60 * 1000;

function isDebugRecent(): boolean {
  if (typeof window === "undefined") return false;
  const raw = localStorage.getItem(DEBUG_LS_KEY);
  if (!raw) return false;
  return Date.now() - parseInt(raw, 10) < DEBUG_TTL_MS;
}

function touchDebugVisit() {
  if (typeof window !== "undefined") {
    localStorage.setItem(DEBUG_LS_KEY, String(Date.now()));
  }
}

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: Home },
  { href: "/portfolio", label: "Portfolio", icon: Briefcase },
  { href: "/signals", label: "Signals", icon: Zap },
  { href: "/premarket", label: "Pre-Market", icon: Sunrise },
  { href: "/trades", label: "Trades", icon: ArrowLeftRight },
  { href: "/upload", label: "Upload", icon: Upload },
  { href: "/status", label: "Status", icon: Activity },
  { href: "/settings", label: "Settings", icon: Settings },
];

const DEBUG_ITEM = { href: "/debug", label: "Debug", icon: Bug };

export function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [footerTaps, setFooterTaps] = useState(0);
  const [debugUnlocked, setDebugUnlocked] = useState(false);

  // Restore from localStorage on mount
  useEffect(() => {
    if (isDebugRecent()) setDebugUnlocked(true);
  }, []);

  // Refresh the TTL whenever /debug is active
  useEffect(() => {
    if (pathname.startsWith("/debug")) touchDebugVisit();
  }, [pathname]);

  function handleFooterClick() {
    const next = footerTaps + 1;
    if (next >= 10) {
      touchDebugVisit();
      setDebugUnlocked(true);
      setFooterTaps(0);
    } else {
      setFooterTaps(next);
    }
  }

  const navItems = debugUnlocked ? [...NAV_ITEMS, DEBUG_ITEM] : NAV_ITEMS;

  return (
    <>
      {/* Mobile toggle */}
      <button
        onClick={() => setOpen(!open)}
        className="fixed left-4 top-4 z-50 rounded-lg bg-surface-800 p-2 text-slate-400 lg:hidden"
      >
        {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </button>

      {/* Overlay */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed left-0 top-0 z-40 flex h-full w-64 flex-col border-r border-white/10 bg-surface-900/95 backdrop-blur-xl transition-transform lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Brand */}
        <div className="flex h-16 items-center gap-3 border-b border-white/10 px-6">
          <BarChart3 className="h-6 w-6 text-brand-500" />
          <span className="text-lg font-bold tracking-tight">Trader</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 space-y-1 p-4">
          {navItems.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  active
                    ? "bg-brand-600/20 text-brand-400"
                    : "text-slate-400 hover:bg-white/5 hover:text-white"
                )}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="border-t border-white/10 p-4">
          <p
            onClick={handleFooterClick}
            className="cursor-default select-none text-xs text-slate-600"
          >
            TFSA Trading Bot
            {footerTaps > 0 && !debugUnlocked && (
              <span className="ml-1 text-slate-700">
                {footerTaps}/10
              </span>
            )}
          </p>
        </div>
      </aside>
    </>
  );
}
