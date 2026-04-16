"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Shield,
  Key,
  Plus,
  Trash2,
  RefreshCw,
  CheckCircle,
  AlertTriangle,
} from "lucide-react";
import { startRegistration, startAuthentication } from "@simplewebauthn/browser";
import { api, setAuthToken, getAuthToken } from "@/lib/api";
import { cn } from "@/lib/utils";
import { SearchTrigger } from "@/components/ui/search-trigger";

interface CredentialInfo {
  id: number;
  name: string;
  created_at: string | null;
}

export default function SettingsPage() {
  const [registered, setRegistered] = useState(false);
  const [credentials, setCredentials] = useState<CredentialInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [hybridLoading, setHybridLoading] = useState(true);
  const [hybridSaving, setHybridSaving] = useState(false);
  const [hybridTakeProfitEnabled, setHybridTakeProfitEnabled] = useState(false);
  const [hybridMinBuyStrength, setHybridMinBuyStrength] = useState(0.5);
  const [registering, setRegistering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [hasToken, setHasToken] = useState(false);

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
      const settings = await api.getProfitTakingSettings();
      setHybridTakeProfitEnabled(settings.hybrid_take_profit_enabled);
      setHybridMinBuyStrength(settings.hybrid_take_profit_min_buy_strength);
    } catch {
      // Keep local defaults if settings endpoint is unavailable.
    } finally {
      setHybridLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  async function handleRegister() {
    setRegistering(true);
    setError(null);
    setSuccess(null);

    try {
      // 1. Get registration options from server
      const options = await api.getRegisterOptions();

      // 2. Create credential via browser WebAuthn API
      const credential = await startRegistration({ optionsJSON: options as any });

      // 3. Send credential to server for verification
      const result = await api.verifyRegistration(credential as any);

      // 4. Store the token
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

  async function handleHybridTakeProfitChange(enabled: boolean) {
    setHybridSaving(true);
    setError(null);
    const previous = hybridTakeProfitEnabled;
    setHybridTakeProfitEnabled(enabled);
    try {
      const updated = await api.updateProfitTakingSettings(enabled);
      setHybridTakeProfitEnabled(updated.hybrid_take_profit_enabled);
      setHybridMinBuyStrength(updated.hybrid_take_profit_min_buy_strength);
      setSuccess(
        updated.hybrid_take_profit_enabled
          ? "Hybrid profit taking enabled"
          : "Hybrid profit taking disabled"
      );
    } catch (e: any) {
      setHybridTakeProfitEnabled(previous);
      setError(e.message || "Failed to update hybrid profit taking");
    } finally {
      setHybridSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Settings</h1>
        <div className="glass-card animate-pulse p-8">
          <div className="h-6 w-48 rounded bg-white/10" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Settings</h1>
        <SearchTrigger />
      </div>

      <div className="glass-card p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold">Profit Taking</h2>
            <p className="mt-1 text-sm text-slate-400">
              Hybrid mode can hold winners after the take-profit threshold when momentum
              is still strong.
            </p>
          </div>
          <label className="inline-flex items-center gap-2 text-sm text-slate-300">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-white/20 bg-white/5"
              checked={hybridTakeProfitEnabled}
              disabled={hybridLoading || hybridSaving}
              onChange={(e) => handleHybridTakeProfitChange(e.target.checked)}
            />
            {hybridSaving ? "Saving..." : "Enable"}
          </label>
        </div>
        <p className="mt-3 text-xs text-slate-500">
          When enabled, take-profit sells at the configured threshold are deferred if
          the symbol still has a BUY signal of at least{" "}
          {(hybridMinBuyStrength * 100).toFixed(0)}% strength. Trailing stops, stop
          losses, and other exits still apply.
        </p>
      </div>

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

      {/* Passkey management */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-brand-500/20 p-3">
              <Shield className="h-5 w-5 text-brand-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold">Passkeys</h2>
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

        {/* Credential list */}
        {credentials.length > 0 ? (
          <div className="mt-6 space-y-3">
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
          <div className="mt-6 rounded-lg border border-dashed border-white/10 p-8 text-center">
            <Key className="mx-auto h-8 w-8 text-slate-600" />
            <p className="mt-2 text-sm text-slate-500">
              No passkeys registered
            </p>
          </div>
        )}
      </div>

      {/* Login section — shown only when passkeys are registered */}
      {registered && (
        <div className="glass-card p-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">Session</h2>
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
    </div>
  );
}
