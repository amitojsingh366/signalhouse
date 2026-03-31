"use client";

import { useEffect, useState, useCallback } from "react";
import { Key, Shield } from "lucide-react";
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
        // Can't reach API — let it pass through, queries will show errors
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
      <div className="flex min-h-screen items-center justify-center bg-surface-950">
        <div className="glass-card mx-4 w-full max-w-md p-8 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-500/20">
            <Shield className="h-8 w-8 text-brand-400" />
          </div>
          <h1 className="text-xl font-bold">Authentication Required</h1>
          <p className="mt-2 text-sm text-slate-400">
            Sign in with your passkey to access the trading dashboard.
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
            {authenticating ? "Authenticating..." : "Sign In with Passkey"}
          </button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
