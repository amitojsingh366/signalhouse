"use client";

import { useEffect, useState, useCallback } from "react";
import { Key, Shield, Mail, Zap } from "lucide-react";
import { startAuthentication } from "@simplewebauthn/browser";
import {
  api,
  setAuthToken,
  getAuthToken,
  setOnUnauthorized,
} from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const [needsAuth, setNeedsAuth] = useState(false);
  const [authenticating, setAuthenticating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(true);
  const qc = useQueryClient();

  // Check on mount: if passkeys are registered and we have no token, prompt login
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const status = await api.getAuthStatus();
        if (mounted && status.registered && !getAuthToken()) {
          setNeedsAuth(true);
        }
      } catch {
        // Can't reach API - let it pass through, queries will show errors
      } finally {
        if (mounted) setChecking(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  // Register global 401 handler
  useEffect(() => {
    setOnUnauthorized(() => setNeedsAuth(true));
    return () => setOnUnauthorized(null);
  }, []);

  const handleLogin = useCallback(async () => {
    setAuthenticating(true);
    setError(null);
    try {
      const options = await api.getLoginOptions();
      const credential = await startAuthentication({ optionsJSON: options as any });
      const result = await api.verifyLogin(credential as any);
      setAuthToken(result.token);
      setNeedsAuth(false);
      // Refetch all queries now that we're authenticated
      qc.invalidateQueries();
    } catch (e: any) {
      if (e.name === "NotAllowedError") {
        setError("Authentication was cancelled");
      } else {
        setError(e.message || "Authentication failed");
      }
    } finally {
      setAuthenticating(false);
    }
  }, [qc]);

  if (checking) {
    return <>{children}</>;
  }

  if (needsAuth) {
    return (
      <div className="auth-wrap">
        <div className="auth-left">
          <div className="brand">
            <img src="/logo.svg" alt="signalhouse logo" />
            <span style={{ fontSize: 16 }}>signalhouse</span>
          </div>

          <div>
            <div
              style={{
                color: "var(--brand-300)",
                fontSize: 12,
                letterSpacing: "0.12em",
                textTransform: "uppercase",
                fontWeight: 600,
                marginBottom: 14,
              }}
            >
              <span
                style={{
                  display: "inline-block",
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: "var(--brand-400)",
                  marginRight: 8,
                  boxShadow: "0 0 0 3px rgba(167,139,250,0.2)",
                }}
              />
              Live | TSX session | TFSA
            </div>
            <h2>
              Signal over <em>noise</em>.
              <br />
              Decisions, not dashboards.
            </h2>
            <p className="blurb">
              Scans TSX stocks, CDRs, and CAD-hedged ETFs during market hours.
              Recommendations are scored, explained, and ready to execute manually.
            </p>
          </div>

          <div className="foot">
            <span>v2.14</span>
            <span>TFSA-native</span>
            <span style={{ marginLeft: "auto" }}>Cmd+K from anywhere</span>
          </div>

          <div className="mini-live">
            <div className="flex items-center justify-between">
              <span className="font-mono text-sm font-semibold text-white">DSG.TO</span>
              <span className="pill-badge pb-buy">BUY 40%</span>
            </div>
            <div className="mt-2 text-xs leading-relaxed text-slate-400">
              EMA bullish crossover + MACD momentum confirm. Analyst revisions are positive this session.
            </div>
            <div className="mt-3 flex gap-4 font-mono text-[11px] text-slate-500">
              <span>
                $99.49 <span className="text-emerald-400">+2.1%</span>
              </span>
              <span>+3.6 / 9</span>
              <span>Vol 3.1x</span>
            </div>
          </div>
        </div>

        <div className="auth-right">
          <div className="auth-card">
            <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-500/20">
              <Shield className="h-7 w-7 text-brand-300" />
            </div>
            <h1 className="text-2xl font-bold">Sign in</h1>
            <p className="mt-2 text-sm text-slate-400">
              Authenticate with your passkey to access the trading dashboard.
            </p>

            {error && (
              <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/5 p-3">
                <p className="text-sm text-red-400">{error}</p>
              </div>
            )}

            <button
              onClick={handleLogin}
              disabled={authenticating}
              className="mt-6 flex w-full items-center justify-center gap-2 rounded-lg bg-brand-600 px-4 py-3 font-medium text-white transition-colors hover:bg-brand-500 disabled:opacity-50"
            >
              <Key className="h-5 w-5" />
              {authenticating ? "Authenticating..." : "Continue with passkey"}
            </button>

            <div className="divider">OR</div>

            <button
              type="button"
              className="flex w-full items-center justify-center gap-2 rounded-lg border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300 transition-colors hover:bg-white/10"
            >
              <Mail className="h-4 w-4" />
              Email magic link
            </button>

            <div className="mt-5 rounded-lg border border-white/5 bg-white/[0.02] p-3 text-xs text-slate-400">
              <p className="flex items-center gap-2 text-slate-300">
                <Zap className="h-3.5 w-3.5 text-brand-300" />
                Security: passkey challenge + short-lived API token
              </p>
            </div>

            <p className="mt-4 text-center text-xs text-slate-500">
              By continuing you agree to terms and privacy policy. Not financial advice.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
