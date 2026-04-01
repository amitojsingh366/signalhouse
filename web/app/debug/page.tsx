"use client";

import { useState, useEffect } from "react";
import { Phone, Bell, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import type { DebugDevice, SignalOut } from "@/lib/api";
import { cn } from "@/lib/utils";
import { CardSkeleton } from "@/components/ui/loading";

export default function DebugPage() {
  const [devices, setDevices] = useState<DebugDevice[]>([]);
  const [topSignal, setTopSignal] = useState<SignalOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [signalLoading, setSignalLoading] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState<string>("all");
  const [sending, setSending] = useState<"call" | "notification" | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function pickTopSignal(recs: Awaited<ReturnType<typeof api.getRecommendations>>): SignalOut | null {
    const all = [...recs.buys, ...recs.sells];
    if (!all.length) return null;
    return all.reduce((best, s) => (s.strength > best.strength ? s : best));
  }

  async function loadData() {
    setLoading(true);
    try {
      const [devs, recs] = await Promise.all([
        api.getDebugDevices(),
        api.getRecommendations(5),
      ]);
      setDevices(devs);
      setTopSignal(pickTopSignal(recs));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }

  async function refreshSignal() {
    setSignalLoading(true);
    try {
      const recs = await api.getRecommendations(5);
      setTopSignal(pickTopSignal(recs));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to refresh signal");
    } finally {
      setSignalLoading(false);
    }
  }

  async function sendPush(type: "call" | "notification") {
    if (!topSignal) return;
    setSending(type);
    setResult(null);
    setError(null);
    try {
      const deviceToken = selectedDevice === "all" ? undefined : selectedDevice;
      const res = await api.testPush(
        type,
        { symbol: topSignal.symbol, signal: topSignal.signal, strength: topSignal.strength, score: topSignal.score },
        deviceToken,
      );
      setResult(
        `Sent ${type} to ${res.sent_to} device${res.sent_to !== 1 ? "s" : ""}: ${res.signal} ${res.symbol} (${Math.round(res.strength * 100)}%)`
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to send");
    } finally {
      setSending(null);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Debug</h1>
        <div className="grid gap-4 sm:grid-cols-2">
          <CardSkeleton />
          <CardSkeleton />
        </div>
      </div>
    );
  }

  const strengthPct = topSignal ? Math.round(topSignal.strength * 100) : 0;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Debug</h1>

      {/* Top Signal Card */}
      <div className="glass-card p-5 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-200">Top Signal</h2>
          <button
            onClick={refreshSignal}
            disabled={signalLoading}
            className="flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:bg-white/10"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", signalLoading && "animate-spin")} />
            Refresh
          </button>
        </div>

        {topSignal ? (
          <div className="flex items-center gap-4">
            <span
              className={cn(
                "rounded-md px-3 py-1 text-sm font-bold",
                topSignal.signal === "BUY"
                  ? "bg-emerald-500/20 text-emerald-400"
                  : "bg-red-500/20 text-red-400"
              )}
            >
              {topSignal.signal}
            </span>
            <span className="text-xl font-bold">{topSignal.symbol}</span>
            <span className="text-slate-400">Score: {topSignal.score}/9</span>
            <span className="text-slate-400">Strength: {strengthPct}%</span>
            {topSignal.price != null && (
              <span className="text-slate-400">${topSignal.price.toFixed(2)}</span>
            )}
          </div>
        ) : (
          <p className="text-slate-500">No signals available right now.</p>
        )}

        {topSignal?.reasons && topSignal.reasons.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {topSignal.reasons.map((r, i) => (
              <span
                key={i}
                className="rounded-full bg-white/5 px-2.5 py-0.5 text-xs text-slate-400"
              >
                {r}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Send Controls */}
      <div className="glass-card p-5 space-y-4">
        <h2 className="text-lg font-semibold text-slate-200">Send Test Push</h2>

        {/* Device Selector */}
        <div className="space-y-1.5">
          <label className="text-sm text-slate-400">Target Device</label>
          <select
            value={selectedDevice}
            onChange={(e) => setSelectedDevice(e.target.value)}
            className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-200 outline-none focus:border-brand-500"
          >
            <option value="all">All Devices ({devices.length})</option>
            {devices.map((d) => (
              <option key={d.device_token} value={d.device_token}>
                {d.platform} &mdash; {d.device_token.slice(0, 12)}...
                {d.device_token.slice(-4)}
                {!d.enabled ? " (disabled)" : ""}
              </option>
            ))}
          </select>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-3">
          <button
            onClick={() => sendPush("notification")}
            disabled={sending !== null || !topSignal}
            className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-brand-500 disabled:opacity-50"
          >
            {sending === "notification" ? (
              <RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <Bell className="h-4 w-4" />
            )}
            Send Notification
          </button>
          <button
            onClick={() => sendPush("call")}
            disabled={sending !== null || !topSignal}
            className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:opacity-50"
          >
            {sending === "call" ? (
              <RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <Phone className="h-4 w-4" />
            )}
            Send Call
          </button>
        </div>

        {/* Result / Error */}
        {result && (
          <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/20 px-4 py-3 text-sm text-emerald-400">
            {result}
          </div>
        )}
        {error && (
          <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}
      </div>

      {/* Devices List */}
      <div className="glass-card p-5 space-y-3">
        <h2 className="text-lg font-semibold text-slate-200">
          Registered Devices ({devices.length})
        </h2>
        {devices.length === 0 ? (
          <p className="text-slate-500">No devices registered.</p>
        ) : (
          <div className="space-y-2">
            {devices.map((d) => (
              <div
                key={d.device_token}
                className="flex items-center justify-between rounded-lg bg-white/[0.03] px-4 py-3"
              >
                <div className="space-y-0.5">
                  <p className="text-sm font-medium text-slate-200">{d.platform}</p>
                  <p className="font-mono text-xs text-slate-500">
                    {d.device_token.slice(0, 16)}...{d.device_token.slice(-8)}
                  </p>
                </div>
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 text-xs font-medium",
                    d.enabled
                      ? "bg-emerald-500/20 text-emerald-400"
                      : "bg-red-500/20 text-red-400"
                  )}
                >
                  {d.enabled ? "Enabled" : "Disabled"}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
