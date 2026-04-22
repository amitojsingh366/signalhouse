"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import {
  Shield,
  ChevronDown,
  ChevronUp,
  Key,
  Plus,
  Trash2,
  RefreshCw,
  CheckCircle,
  AlertTriangle,
  TrendingUp,
  Bell,
  Link2,
  Database,
  Palette,
  LineChart,
  Download,
  ImageIcon,
  MessageCircle,
  Smartphone,
} from "lucide-react";
import { startRegistration, startAuthentication } from "@simplewebauthn/browser";
import { useQueryClient } from "@tanstack/react-query";
import {
  api,
  setAuthToken,
  getAuthToken,
  type SettingGroup,
  type SettingItem,
} from "@/lib/api";
import { queryKeys } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import { SearchTrigger } from "@/components/ui/search-trigger";

interface CredentialInfo {
  id: number;
  name: string;
  created_at: string | null;
}

const ADVANCED_MODE_STORAGE_KEY = "trader_settings_advanced_mode";
const BASIC_TRADING_TOGGLE_KEYS = new Set([
  "strategy.oversold_fastlane.enabled",
  "risk.hybrid_take_profit_enabled",
]);

export default function SettingsPage() {
  const [registered, setRegistered] = useState(false);
  const [credentials, setCredentials] = useState<CredentialInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [tradingLoading, setTradingLoading] = useState(true);
  const [groups, setGroups] = useState<SettingGroup[]>([]);
  const [savingKeys, setSavingKeys] = useState<Set<string>>(new Set());
  const [registering, setRegistering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [hasToken, setHasToken] = useState(false);
  const [advancedMode, setAdvancedMode] = useState(false);
  const [tab, setTab] = useState<"Trading" | "Auth" | "Notifications" | "Connections" | "Data" | "Appearance">("Trading");
  const refreshTimerRef = useRef<number | null>(null);
  const qc = useQueryClient();

  const scheduleStrategyRefresh = useCallback(() => {
    if (refreshTimerRef.current != null) {
      window.clearTimeout(refreshTimerRef.current);
    }
    refreshTimerRef.current = window.setTimeout(() => {
      qc.invalidateQueries({ queryKey: queryKeys.actionPlan });
      qc.invalidateQueries({ queryKey: queryKeys.recommendations });
      qc.invalidateQueries({ queryKey: ["signal"] });
      refreshTimerRef.current = null;
    }, 600);
  }, [qc]);

  const loadStatus = useCallback(async () => {
    try {
      const status = await api.getAuthStatus();
      setRegistered(status.registered);
      setCredentials(status.credentials);
      setHasToken(!!getAuthToken());
    } catch {
      // Auth status endpoint should always work
    } finally {
      setLoading(false);
    }

    try {
      const cfg = await api.getSettingsConfig();
      setGroups(cfg.groups);
    } catch {
      // Keep empty on error
    } finally {
      setTradingLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const persisted = window.localStorage.getItem(ADVANCED_MODE_STORAGE_KEY);
    setAdvancedMode(persisted === "1");
  }, []);

  useEffect(() => {
    return () => {
      if (refreshTimerRef.current != null) {
        window.clearTimeout(refreshTimerRef.current);
      }
    };
  }, []);

  async function handleRegister() {
    setRegistering(true);
    setError(null);
    setSuccess(null);

    try {
      const options = await api.getRegisterOptions();
      const credential = await startRegistration({ optionsJSON: options as any });
      const result = await api.verifyRegistration(credential as any);

      setAuthToken(result.token);
      setHasToken(true);
      setSuccess("Passkey registered successfully");
      await loadStatus();
    } catch (e: any) {
      if (e.name === "NotAllowedError") {
        setError("Registration was cancelled");
      } else {
        setError(e.message || "Registration failed");
      }
    } finally {
      setRegistering(false);
    }
  }

  async function handleLogin() {
    setError(null);
    setSuccess(null);

    try {
      const options = await api.getLoginOptions();
      const credential = await startAuthentication({ optionsJSON: options as any });
      const result = await api.verifyLogin(credential as any);

      setAuthToken(result.token);
      setHasToken(true);
      setSuccess("Authenticated successfully");
    } catch (e: any) {
      if (e.name === "NotAllowedError") {
        setError("Authentication was cancelled");
      } else {
        setError(e.message || "Authentication failed");
      }
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Delete this passkey? If it's the last one, authentication will be disabled.")) {
      return;
    }
    try {
      await api.deleteCredential(id);
      setSuccess("Passkey deleted");
      await loadStatus();
    } catch (e: any) {
      setError(e.message || "Failed to delete passkey");
    }
  }

  const markSaving = useCallback((key: string, on: boolean) => {
    setSavingKeys((prev) => {
      const next = new Set(prev);
      if (on) next.add(key);
      else next.delete(key);
      return next;
    });
  }, []);

  const toggleAdvancedMode = useCallback(() => {
    setAdvancedMode((previous) => {
      const next = !previous;
      if (typeof window !== "undefined") {
        window.localStorage.setItem(ADVANCED_MODE_STORAGE_KEY, next ? "1" : "0");
      }
      return next;
    });
  }, []);

  const visibleTradingGroups = groups
    .map((group) => ({
      ...group,
      items: advancedMode
        ? group.items
        : group.items.filter((item) => BASIC_TRADING_TOGGLE_KEYS.has(item.key)),
    }))
    .filter((group) => group.items.length > 0);

  async function saveSetting(key: string, value: number | boolean) {
    const previous = groups;
    setGroups((gs) =>
      gs.map((g) => ({
        ...g,
        items: g.items.map((it) => (it.key === key ? { ...it, value } : it)),
      }))
    );
    markSaving(key, true);
    setError(null);
    try {
      const updated = await api.updateSettingsConfig({ [key]: value });
      setGroups(updated.groups);
      scheduleStrategyRefresh();
    } catch (e: any) {
      setGroups(previous);
      setError(e.message || "Failed to update setting");
    } finally {
      markSaving(key, false);
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="ph">
          <div>
            <h1>Settings</h1>
          </div>
        </div>
        <div className="glass-card animate-pulse p-8">
          <div className="h-6 w-48 rounded bg-white/10" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="ph">
        <div>
          <h1>Settings</h1>
          <p className="sub">
            TFSA
            <span className="divider">·</span>
            Changes apply immediately
            <span className="divider">·</span>
            <span className="font-mono text-surface-500">settings.yaml</span>
          </p>
        </div>
        <div className="actions">
          <SearchTrigger />
        </div>
      </div>

      <div className="grid items-start gap-5 xl:grid-cols-[240px_minmax(0,1fr)]">
        <div className="glass-card p-3 xl:sticky xl:top-24">
          <div className="space-y-1">
            {[
              { id: "Trading", icon: LineChart },
              { id: "Auth", icon: Shield },
              { id: "Notifications", icon: Bell },
              { id: "Connections", icon: Link2 },
              { id: "Data", icon: Database },
              { id: "Appearance", icon: Palette },
            ].map(({ id, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setTab(id as typeof tab)}
                className={cn(
                  "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-medium transition-colors",
                  tab === id
                    ? "bg-brand-600/20 text-brand-300"
                    : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
                )}
              >
                <Icon className="h-4 w-4" />
                {id}
              </button>
            ))}
          </div>
          <div className="mt-4 rounded-lg border border-emerald-500/25 bg-emerald-500/10 p-3 text-xs text-emerald-300">
            All systems nominal · last sync just now
          </div>
        </div>

        <div className="space-y-5">
          {/* Alerts */}
          {error && (
            <div className="glass-card border-red-500/30 bg-red-500/5 p-4">
              <p className="text-sm text-red-400">{error}</p>
            </div>
          )}
          {success && (
            <div className="glass-card border-emerald-500/30 bg-emerald-500/5 p-4">
              <p className="text-sm text-emerald-400">{success}</p>
            </div>
          )}

          {tab === "Auth" && (
            <>
              {/* Auth status banner */}
              <div
                className={cn(
                  "glass-card p-5",
                  registered
                    ? "border-emerald-500/30 bg-emerald-500/5"
                    : "border-amber-500/30 bg-amber-500/5"
                )}
              >
                <div className="flex items-center gap-3">
                  {registered ? (
                    <CheckCircle className="h-5 w-5 text-emerald-400" />
                  ) : (
                    <AlertTriangle className="h-5 w-5 text-amber-400" />
                  )}
                  <div>
                    <p
                      className={cn(
                        "font-medium",
                        registered ? "text-emerald-400" : "text-amber-400"
                      )}
                    >
                      {registered ? "API Authentication Active" : "API Authentication Disabled"}
                    </p>
                    <p className="mt-1 text-sm text-slate-400">
                      {registered
                        ? "All API requests require a valid token. Register additional passkeys or authenticate below."
                        : "No passkeys registered. The API is currently open. Register a passkey to enable authentication."}
                    </p>
                  </div>
                </div>
              </div>

              {/* Passkey management */}
              <div className="card">
                <div className="head">
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-brand-500/20 p-3">
                      <Shield className="h-5 w-5 text-brand-400" />
                    </div>
                    <div>
                      <h3 className="text-base font-semibold">Passkeys</h3>
                      <p className="text-sm text-slate-400">
                        Manage your registered passkeys for authentication
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={handleRegister}
                    disabled={registering}
                    className="flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-500 disabled:opacity-50"
                  >
                    {registering ? (
                      <RefreshCw className="h-4 w-4 animate-spin" />
                    ) : (
                      <Plus className="h-4 w-4" />
                    )}
                    Register Passkey
                  </button>
                </div>

                {credentials.length > 0 ? (
                  <div className="space-y-3 p-5">
                    {credentials.map((cred) => (
                      <div
                        key={cred.id}
                        className="flex items-center justify-between rounded-lg border border-white/10 bg-white/[0.02] px-4 py-3"
                      >
                        <div className="flex items-center gap-3">
                          <Key className="h-4 w-4 text-slate-400" />
                          <div>
                            <p className="text-sm font-medium">{cred.name}</p>
                            {cred.created_at && (
                              <p className="text-xs text-slate-500">
                                Registered{" "}
                                {new Date(cred.created_at).toLocaleDateString()}
                              </p>
                            )}
                          </div>
                        </div>
                        <button
                          onClick={() => handleDelete(cred.id)}
                          className="rounded-lg p-2 text-slate-500 transition-colors hover:bg-red-500/10 hover:text-red-400"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-5">
                    <div className="rounded-lg border border-dashed border-white/10 p-8 text-center">
                      <Key className="mx-auto h-8 w-8 text-slate-600" />
                      <p className="mt-2 text-sm text-slate-500">
                        No passkeys registered
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {registered && (
                <div className="card">
                  <div className="head">
                    <div>
                      <h3 className="text-base font-semibold">Session</h3>
                      <p className="text-sm text-slate-400">
                        {hasToken
                          ? "You have an active session token."
                          : "Authenticate with your passkey to access the API."}
                      </p>
                    </div>
                    <button
                      onClick={handleLogin}
                      className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-300 transition-colors hover:bg-white/10"
                    >
                      <Key className="h-4 w-4" />
                      {hasToken ? "Re-authenticate" : "Sign In"}
                    </button>
                  </div>
                </div>
              )}
            </>
          )}

          {tab === "Trading" && (
            <div className="card p-6">
              <div className="mb-4 flex items-start justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="rounded-lg bg-brand-500/20 p-3">
                    <TrendingUp className="h-5 w-5 text-brand-400" />
                  </div>
                  <div>
                    <h2 className="text-lg font-semibold">Trading</h2>
                    <p className="text-sm text-slate-400">
                      Strategy, risk, and notification parameters from{" "}
                      <code className="rounded bg-white/5 px-1 py-0.5 text-xs">settings.yaml</code>.
                      Changes apply immediately and persist across restarts.
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={toggleAdvancedMode}
                  className="pt-1 text-sm font-medium text-brand-300 transition-colors hover:text-brand-200"
                >
                  {advancedMode ? "disable advanced mode" : "advanced mode"}
                </button>
              </div>

              {tradingLoading ? (
                <div className="mt-6 space-y-3">
                  <div className="h-5 w-32 animate-pulse rounded bg-white/10" />
                  <div className="h-12 animate-pulse rounded bg-white/5" />
                  <div className="h-12 animate-pulse rounded bg-white/5" />
                </div>
              ) : (
                <div className="mt-6 space-y-8">
                  {!advancedMode && (
                    <p className="text-xs text-slate-500">
                      Showing core toggles only. Enable advanced mode to edit numeric strategy parameters.
                    </p>
                  )}
                  {visibleTradingGroups.map((group) => (
                    <section key={group.id} className="space-y-4">
                      <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-300">
                        {group.label}
                      </h3>
                      <div className="space-y-3">
                        {group.items.map((item) => (
                          <SettingRow
                            key={item.key}
                            item={item}
                            saving={savingKeys.has(item.key)}
                            onSave={(value) => saveSetting(item.key, value)}
                          />
                        ))}
                      </div>
                    </section>
                  ))}
                </div>
              )}
            </div>
          )}

          {tab === "Notifications" && (
            <>
              <div className="card">
                <div className="head">
                  <h3>Delivery Rules</h3>
                  <span className="sub">iOS VoIP push + Discord</span>
                </div>
                <div className="body space-y-1">
                  <StaticToggleRow
                    title="URGENT exits and drawdown halts"
                    description="Immediate VoIP push and Discord notification for stop losses and risk halts."
                    initialOn
                  />
                  <StaticToggleRow
                    title="BUY >= 50% conviction"
                    description="iOS push and Discord DM for top-tier opportunities."
                    initialOn
                  />
                  <StaticToggleRow
                    title="BUY 35-50% conviction"
                    description="iOS push only for lower-conviction candidates."
                    initialOn
                  />
                  <StaticToggleRow
                    title="SWAP recommendations"
                    description="Notify when a stronger replacement is available for an existing holding."
                    initialOn={false}
                  />
                  <StaticToggleRow
                    title="Daily morning brief"
                    description="Scheduled summary at 8:30 ET."
                    initialOn
                  />
                  <StaticToggleRow
                    title="Weekly performance digest"
                    description="Sunday digest with PnL and hit-rate recap."
                    initialOn={false}
                    isLast
                  />
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="card">
                  <div className="head">
                    <h3>Channels</h3>
                    <span className="sub">linked</span>
                  </div>
                  <div className="body space-y-3">
                    <div className="flex items-center justify-between rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2">
                      <div className="flex items-center gap-2 text-sm text-slate-300">
                        <Smartphone className="h-4 w-4 text-brand-300" />
                        iOS push + VoIP
                      </div>
                      <span className="pill-badge pb-buy">ACTIVE</span>
                    </div>
                    <div className="flex items-center justify-between rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2">
                      <div className="flex items-center gap-2 text-sm text-slate-300">
                        <MessageCircle className="h-4 w-4 text-brand-300" />
                        Discord DM
                      </div>
                      <span className="pill-badge pb-buy">ACTIVE</span>
                    </div>
                  </div>
                </div>

                <div className="card">
                  <div className="head">
                    <h3>Alert Timing</h3>
                    <span className="sub">tradeoffs</span>
                  </div>
                  <div className="body space-y-3 text-sm">
                    <div className="flex items-center justify-between rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2">
                      <span className="text-slate-400">Cooldown</span>
                      <span className="font-mono text-slate-200">60 min</span>
                    </div>
                    <div className="flex items-center justify-between rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2">
                      <span className="text-slate-400">Retry delay</span>
                      <span className="font-mono text-slate-200">30 sec</span>
                    </div>
                    <div className="flex items-center justify-between rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2">
                      <span className="text-slate-400">Max retries</span>
                      <span className="font-mono text-slate-200">1</span>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}

          {tab === "Connections" && (
            <div className="card">
              <div className="head">
                <h3>Connections</h3>
                <span className="sub">integrations</span>
              </div>
              <div className="space-y-3 p-5">
                <div className="flex items-center gap-3 rounded-lg border border-white/10 bg-white/[0.02] px-4 py-3">
                  <div className="rounded-lg border border-white/10 bg-white/5 p-2">
                    <ImageIcon className="h-4 w-4 text-slate-300" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">Brokerage screenshots</p>
                    <p className="text-xs text-slate-500">OCR uploads enabled for Wealthsimple and Questrade formats.</p>
                  </div>
                  <button className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-300 transition-colors hover:bg-white/10">
                    Manage
                  </button>
                </div>

                <div className="flex items-center gap-3 rounded-lg border border-white/10 bg-white/[0.02] px-4 py-3">
                  <div className="rounded-lg border border-white/10 bg-white/5 p-2">
                    <MessageCircle className="h-4 w-4 text-slate-300" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">Discord</p>
                    <p className="text-xs text-slate-500">Slash commands and real-time recommendations are active.</p>
                  </div>
                  <button className="rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-300 transition-colors hover:bg-white/10">
                    Reconnect
                  </button>
                </div>

                <div className="flex items-center gap-3 rounded-lg border border-white/10 bg-white/[0.02] px-4 py-3">
                  <div className="rounded-lg border border-white/10 bg-white/5 p-2">
                    <Smartphone className="h-4 w-4 text-slate-300" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium">iOS app</p>
                    <p className="text-xs text-slate-500">Push delivery active on iPhone 15 Pro with VoIP priority.</p>
                  </div>
                  <span className="pill-badge pb-buy">ACTIVE</span>
                </div>
              </div>
            </div>
          )}

          {tab === "Data" && (
            <>
              <div className="card">
                <div className="head">
                  <h3>Price Feed</h3>
                  <span className="sub">primary + fallback</span>
                </div>
                <div className="grid gap-4 p-5 md:grid-cols-2">
                  <div className="space-y-1">
                    <label className="text-xs uppercase tracking-wide text-slate-500">Primary feed</label>
                    <select className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 outline-none">
                      <option>Yahoo Finance (15 min)</option>
                      <option>Alpha Vantage</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs uppercase tracking-wide text-slate-500">Fallback feed</label>
                    <select className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 outline-none">
                      <option>Questrade API</option>
                      <option>IEX Cloud</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs uppercase tracking-wide text-slate-500">Scan interval</label>
                    <input
                      defaultValue="15 minutes (09:30-16:00 ET)"
                      className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 outline-none"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs uppercase tracking-wide text-slate-500">Symbol universe</label>
                    <input
                      defaultValue="TSX + CBOE CDR + CAD-hedged ETFs"
                      className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 outline-none"
                    />
                  </div>
                </div>
              </div>

              <div className="card">
                <div className="head">
                  <h3>News & Sentiment Inputs</h3>
                  <span className="sub">source health</span>
                </div>
                <div className="body space-y-1">
                  <StaticToggleRow
                    title="Reuters finance feed"
                    description="Currently degraded, backup feed active."
                    initialOn
                  />
                  <StaticToggleRow
                    title="Yahoo headlines"
                    description="Primary headline stream for catalyst extraction."
                    initialOn
                  />
                  <StaticToggleRow
                    title="Analyst rating aggregation"
                    description="Consensus and revisions for sentiment scoring."
                    initialOn
                  />
                  <StaticToggleRow
                    title="Social sentiment stream"
                    description="Optional source for additional context."
                    initialOn={false}
                    isLast
                  />
                </div>
              </div>

              <div className="card">
                <div className="head">
                  <h3>Backups</h3>
                  <span className="sub">automatic</span>
                </div>
                <div className="flex flex-wrap items-center gap-3 p-5 text-sm">
                  <span className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-slate-300">
                    Daily snapshot at 00:00 ET
                  </span>
                  <span className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-slate-300">
                    30-day retention
                  </span>
                  <button className="ml-auto inline-flex items-center gap-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300 transition-colors hover:bg-white/10">
                    <Download className="h-3.5 w-3.5" />
                    Download latest
                  </button>
                </div>
              </div>
            </>
          )}

          {tab === "Appearance" && (
            <>
              <div className="card">
                <div className="head">
                  <h3>Appearance</h3>
                  <span className="sub">personal</span>
                </div>
                <div className="grid gap-4 p-5 md:grid-cols-2">
                  <div className="space-y-1">
                    <label className="text-xs uppercase tracking-wide text-slate-500">Theme</label>
                    <select className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 outline-none">
                      <option>Dark (default)</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs uppercase tracking-wide text-slate-500">Density</label>
                    <select className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 outline-none">
                      <option>Comfortable</option>
                      <option>Dense</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs uppercase tracking-wide text-slate-500">Monospace font</label>
                    <select className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 outline-none">
                      <option>JetBrains Mono</option>
                      <option>IBM Plex Mono</option>
                      <option>SF Mono</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs uppercase tracking-wide text-slate-500">Number format</label>
                    <select className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 outline-none">
                      <option>1,234.56</option>
                      <option>1 234,56</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="card">
                <div className="head">
                  <h3>Accessibility & Layout</h3>
                  <span className="sub">client-side</span>
                </div>
                <div className="body space-y-1">
                  <StaticToggleRow
                    title="Reduce motion"
                    description="Disable sparkline animation and smooth transitions."
                    initialOn={false}
                  />
                  <StaticToggleRow
                    title="Show pre-market tab"
                    description="Display scan-specific navigation during 04:00-09:30 ET."
                    initialOn
                  />
                  <StaticToggleRow
                    title="Compact numeric chips"
                    description="Use denser badges and tighter number blocks on cards."
                    initialOn={false}
                    isLast
                  />
                </div>
              </div>

              <div className="rounded-lg border border-brand-500/25 bg-brand-500/10 p-4 text-sm text-brand-200">
                Appearance changes preview locally in this web client. Core trading behavior is unaffected.
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function PreviewToggle({ initialOn = false }: { initialOn?: boolean }) {
  const [on, setOn] = useState(initialOn);
  return (
    <button
      type="button"
      onClick={() => setOn((v) => !v)}
      className={cn(
        "relative inline-flex h-6 w-11 items-center rounded-full transition-colors",
        on ? "bg-brand-500" : "bg-white/10"
      )}
      aria-pressed={on}
    >
      <span
        className={cn(
          "h-5 w-5 rounded-full bg-white transition-transform",
          on ? "translate-x-5" : "translate-x-0.5"
        )}
      />
    </button>
  );
}

function StaticToggleRow({
  title,
  description,
  initialOn,
  isLast = false,
}: {
  title: string;
  description: string;
  initialOn: boolean;
  isLast?: boolean;
}) {
  return (
    <div className={cn("flex items-center gap-4 py-3", !isLast && "border-b border-white/5")}>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-white">{title}</p>
        <p className="mt-1 text-xs text-slate-500">{description}</p>
      </div>
      <PreviewToggle initialOn={initialOn} />
    </div>
  );
}

function SettingRow({
  item,
  saving,
  onSave,
}: {
  item: SettingItem;
  saving: boolean;
  onSave: (value: number | boolean) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-lg border border-white/5 bg-white/[0.02] p-4">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="text-sm font-medium text-white">{item.label}</p>
          {saving && (
            <span className="text-xs text-slate-500">Saving…</span>
          )}
        </div>
        <p className="mt-1 text-xs text-slate-500">{item.description}</p>
      </div>
      <div className="shrink-0">
        {item.type === "bool" ? (
          <BoolControl
            value={item.value as boolean | null}
            disabled={saving}
            onChange={(v) => onSave(v)}
          />
        ) : (
          <NumberControl
            value={item.value as number | null}
            type={item.type}
            min={item.min}
            max={item.max}
            step={item.step}
            disabled={saving}
            onCommit={(v) => onSave(v)}
          />
        )}
      </div>
    </div>
  );
}

function BoolControl({
  value,
  disabled,
  onChange,
}: {
  value: boolean | null;
  disabled: boolean;
  onChange: (v: boolean) => void;
}) {
  const checked = !!value;
  return (
    <label
      className={cn(
        "relative inline-flex items-center",
        disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer"
      )}
    >
      <input
        type="checkbox"
        className="peer sr-only"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="h-6 w-11 rounded-full bg-white/10 transition-colors duration-200 peer-checked:bg-brand-500 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-brand-500/50 peer-disabled:bg-white/5 after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:bg-white after:transition-transform after:duration-200 peer-checked:after:translate-x-5" />
    </label>
  );
}

function NumberControl({
  value,
  type,
  min,
  max,
  step,
  disabled,
  onCommit,
}: {
  value: number | null;
  type: "int" | "float";
  min: number | null;
  max: number | null;
  step: number | null;
  disabled: boolean;
  onCommit: (v: number) => void;
}) {
  const [draft, setDraft] = useState<string>(value == null ? "" : String(value));
  const skipNextBlurCommitRef = useRef(false);

  useEffect(() => {
    setDraft(value == null ? "" : String(value));
  }, [value]);

  const effectiveStep = step ?? (type === "int" ? 1 : 0.01);
  const stepPrecision = useMemo(() => {
    if (type !== "float") return 0;
    const serialized = String(effectiveStep);
    if (serialized.includes("e-")) {
      const [base, exp] = serialized.split("e-");
      const exponent = Number.parseInt(exp ?? "0", 10);
      const decimals = (base.split(".")[1] ?? "").length;
      return exponent + decimals;
    }
    return (serialized.split(".")[1] ?? "").length;
  }, [effectiveStep, type]);

  const roundToStepPrecision = useCallback(
    (input: number): number => {
      if (type !== "float" || stepPrecision <= 0) return input;
      return Number(input.toFixed(stepPrecision));
    },
    [stepPrecision, type]
  );

  const clampValue = useCallback(
    (input: number): number => {
      let next = input;
      if (min != null) next = Math.max(min, next);
      if (max != null) next = Math.min(max, next);
      if (type === "int") next = Math.round(next);
      return next;
    },
    [max, min, type]
  );

  const parseDraft = useCallback((): number | null => {
    if (draft.trim() === "") return null;
    const parsed = type === "int" ? parseInt(draft, 10) : parseFloat(draft);
    if (!Number.isFinite(parsed)) return null;
    return parsed;
  }, [draft, type]);

  const commit = useCallback(
    (nextValue?: number) => {
      const parsed = nextValue ?? parseDraft();
      if (parsed == null) {
        setDraft(value == null ? "" : String(value));
        return;
      }

      const normalized = clampValue(parsed);
      setDraft(String(normalized));
      if (value == null || normalized !== value) {
        onCommit(normalized);
      }
    },
    [clampValue, onCommit, parseDraft, value]
  );

  const stepBy = useCallback(
    (direction: 1 | -1) => {
      const parsed = parseDraft();
      const base = parsed ?? value ?? 0;
      const stepped = base + direction * effectiveStep;
      const next = clampValue(roundToStepPrecision(stepped));
      commit(next);
    },
    [clampValue, commit, effectiveStep, parseDraft, roundToStepPrecision, value]
  );

  return (
    <div className={cn("inline-flex overflow-hidden rounded-lg border border-white/10 bg-[#11141d]", disabled && "opacity-60")}>
      <input
        type="number"
        className="w-24 bg-transparent px-3 py-2 text-right text-sm text-white outline-none transition-colors focus:bg-white/[0.03]"
        value={draft}
        disabled={disabled}
        min={min ?? undefined}
        max={max ?? undefined}
        step={effectiveStep}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => {
          if (skipNextBlurCommitRef.current) {
            skipNextBlurCommitRef.current = false;
            return;
          }
          commit();
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            commit();
            skipNextBlurCommitRef.current = true;
            (e.target as HTMLInputElement).blur();
            return;
          }
          if (e.key === "Escape") {
            setDraft(value == null ? "" : String(value));
            (e.target as HTMLInputElement).blur();
            return;
          }
          if (e.key === "ArrowUp") {
            e.preventDefault();
            stepBy(1);
            return;
          }
          if (e.key === "ArrowDown") {
            e.preventDefault();
            stepBy(-1);
          }
        }}
      />
      <div className="flex w-6 flex-col border-l border-white/10 bg-black/20">
        <button
          type="button"
          disabled={disabled}
          onMouseDown={(e) => {
            // Keep focus on the input so stepper clicks don't fire an extra blur-commit first.
            skipNextBlurCommitRef.current = true;
            e.preventDefault();
          }}
          onClick={() => {
            skipNextBlurCommitRef.current = false;
            stepBy(1);
          }}
          className="flex h-1/2 items-center justify-center text-slate-400 transition-colors hover:bg-white/5 hover:text-slate-200 disabled:cursor-not-allowed"
          aria-label="Increase value"
        >
          <ChevronUp className="h-3 w-3" />
        </button>
        <button
          type="button"
          disabled={disabled}
          onMouseDown={(e) => {
            // Keep focus on the input so stepper clicks don't fire an extra blur-commit first.
            skipNextBlurCommitRef.current = true;
            e.preventDefault();
          }}
          onClick={() => {
            skipNextBlurCommitRef.current = false;
            stepBy(-1);
          }}
          className="flex h-1/2 items-center justify-center border-t border-white/10 text-slate-400 transition-colors hover:bg-white/5 hover:text-slate-200 disabled:cursor-not-allowed"
          aria-label="Decrease value"
        >
          <ChevronDown className="h-3 w-3" />
        </button>
      </div>
    </div>
  );
}
