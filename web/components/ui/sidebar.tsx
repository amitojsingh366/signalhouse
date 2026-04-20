"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  ArrowLeftRight,
  Briefcase,
  Bug,
  LayoutDashboard,
  Menu,
  Settings,
  Sunrise,
  Upload,
  X,
  Zap,
} from "lucide-react";
import { useEffect, useMemo, useState, type ComponentType } from "react";
import { useActionPlan } from "@/lib/hooks";
import { cn } from "@/lib/utils";

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

type NavItem = {
  href: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  count?: string;
};

type NavGroup = {
  label: string;
  items: NavItem[];
};

export function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [footerTaps, setFooterTaps] = useState(0);
  const [debugUnlocked, setDebugUnlocked] = useState(false);
  const { data: plan } = useActionPlan();

  useEffect(() => {
    if (isDebugRecent()) setDebugUnlocked(true);
  }, []);

  useEffect(() => {
    if (pathname.startsWith("/debug")) touchDebugVisit();
  }, [pathname]);

  function handleFooterClick() {
    const next = footerTaps + 1;
    if (next >= 10) {
      touchDebugVisit();
      setDebugUnlocked(true);
      setFooterTaps(0);
      return;
    }
    setFooterTaps(next);
  }

  const signalCount = plan?.actions?.length ?? 0;

  const groups = useMemo<NavGroup[]>(() => {
    const list: NavGroup[] = [
      {
        label: "Core",
        items: [
          { href: "/", label: "Dashboard", icon: LayoutDashboard },
          { href: "/signals", label: "Signals", icon: Zap, count: signalCount > 0 ? String(signalCount) : undefined },
          { href: "/portfolio", label: "Portfolio", icon: Briefcase },
        ],
      },
      {
        label: "Scan",
        items: [
          { href: "/premarket", label: "Pre-market", icon: Sunrise },
          { href: "/trades", label: "Trades", icon: ArrowLeftRight },
          { href: "/upload", label: "Upload", icon: Upload },
        ],
      },
      {
        label: "System",
        items: [
          { href: "/status", label: "Status", icon: Activity },
          { href: "/settings", label: "Settings", icon: Settings },
        ],
      },
    ];

    if (debugUnlocked) {
      list[2].items.push({ href: "/debug", label: "Debug", icon: Bug });
    }
    return list;
  }, [debugUnlocked, signalCount]);

  return (
    <>
      <button
        onClick={() => setOpen((prev) => !prev)}
        className="sb-toggle"
        aria-label={open ? "Close navigation" : "Open navigation"}
      >
        {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </button>

      {open && (
        <div
          className="sb-overlay"
          onClick={() => setOpen(false)}
          aria-hidden
        />
      )}

      <aside className={cn("sb", open && "is-open")}>
        <div className="brand">
          <img src="/logo.svg" alt="signalhouse logo" />
          <span className="wm">signalhouse</span>
          <span className="env">TFSA</span>
        </div>

        {groups.map((group) => (
          <div key={group.label}>
            <div className="group-label">{group.label}</div>
            <nav>
              {group.items.map((item) => {
                const active =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname.startsWith(item.href);

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setOpen(false)}
                    className={cn(active && "on")}
                  >
                    <span className="ico">
                      <item.icon />
                    </span>
                    <span className="lbl">{item.label}</span>
                    {item.count ? <span className="count">{item.count}</span> : null}
                  </Link>
                );
              })}
            </nav>
          </div>
        ))}

        <div
          className="sb-foot"
          onClick={handleFooterClick}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              handleFooterClick();
            }
          }}
          role="button"
          tabIndex={0}
        >
          <div className="scan-chip">
            <span className="dot" />
            <div className="txt">
              <span className="a">Live scan</span>
              <span className="b">333 symbols · every 15 min</span>
            </div>
          </div>
          {footerTaps > 0 && !debugUnlocked && (
            <p className="tap-hint">{footerTaps}/10</p>
          )}
        </div>
      </aside>
    </>
  );
}
