const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Auth token persistence
const TOKEN_KEY = "trader_auth_token";

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setAuthToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearAuthToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// Global 401 handler — set by AuthGate component
let _onUnauthorized: (() => void) | null = null;
export function setOnUnauthorized(fn: (() => void) | null): void {
  _onUnauthorized = fn;
}

async function fetchAPI<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAuthToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });
  if (res.status === 401) {
    clearAuthToken();
    _onUnauthorized?.();
    throw new Error("Authentication required");
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json();
}

// --- Types (mirroring API schemas) ---

export interface HoldingAdvice {
  symbol: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  market_value: number;
  pnl: number;
  pnl_pct: number;
  signal: string;
  strength: number;
  technical_score: number;
  sentiment_score: number;
  commodity_score: number;
  action: string;
  action_detail: string;
  reasons: string[];
  alternative: Record<string, unknown> | null;
}

export interface PortfolioSummary {
  holdings: HoldingAdvice[];
  total_value: number;
  cash: number;
  total_cost: number;
  total_pnl: number;
  total_pnl_pct: number;
}

export interface PnlSummary {
  current_value: number;
  initial_capital: number;
  cash: number;
  daily_pnl: number;
  daily_pnl_pct: number;
  total_pnl: number;
  total_pnl_pct: number;
  recent_trades: TradeOut[];
}

export interface TradeOut {
  id: number | null;
  symbol: string;
  action: string;
  quantity: number;
  price: number;
  total: number;
  pnl: number | null;
  pnl_pct: number | null;
  timestamp: string | null;
}

export interface SignalOut {
  symbol: string;
  signal: string;
  strength: number;
  score: number;
  technical_score: number;
  sentiment_score: number;
  commodity_score: number;
  reasons: string[];
  price: number | null;
  sector: string | null;
}

export interface ExitAlert {
  symbol: string;
  reason: string;
  detail: string;
  severity: string;
  current_price: number;
  entry_price: number;
  pnl_pct: number;
  quantity: number | null;
  action: string | null;
  action_detail: string | null;
}

export interface RecommendationOut {
  exit_alerts: ExitAlert[];
  buys: SignalOut[];
  sells: SignalOut[];
  watchlist_sells: SignalOut[];
  funding: Record<string, unknown>[];
  sector_exposure: Record<string, number>;
}

export interface ActionItem {
  type: "BUY" | "SELL" | "SWAP";
  urgency: "urgent" | "normal" | "low";
  symbol?: string;
  shares?: number;
  price?: number;
  dollar_amount?: number;
  pct_of_portfolio?: number;
  pnl_pct?: number;
  entry_price?: number;
  strength?: number;
  score?: number;
  technical_score?: number;
  sentiment_score?: number;
  commodity_score?: number;
  reason: string;
  detail: string;
  sector?: string;
  reasons?: string[];
  // SWAP fields
  sell_symbol?: string;
  sell_shares?: number;
  sell_price?: number;
  sell_amount?: number;
  sell_pnl_pct?: number;
  buy_symbol?: string;
  buy_shares?: number;
  buy_price?: number;
  buy_amount?: number;
  buy_strength?: number;
  actionable?: boolean;
  snoozed?: boolean;
}

export interface ActionPlanOut {
  actions: ActionItem[];
  portfolio_value: number;
  cash: number;
  num_positions: number;
  max_positions: number;
  sells_count: number;
  buys_count: number;
  swaps_count: number;
  sector_exposure: Record<string, unknown>;
}

export interface SnoozeOut {
  symbol: string;
  snoozed_at: string;
  expires_at: string;
  pnl_pct_at_snooze: number;
  indefinite: boolean;
  phantom_trailing_stop: boolean;
}

export interface SnapshotOut {
  date: string;
  portfolio_value: number;
  cash: number;
  positions_value: number;
}

export interface StatusOut {
  symbols_tracked: number;
  holdings_count: number;
  market_open: boolean;
  uptime_seconds: number | null;
  scan_interval_minutes: number;
  risk_halted: boolean;
  risk_halt_reason: string;
}

export interface UploadHolding {
  symbol: string;
  quantity: number;
  market_value_cad: number;
}

export interface InsightsOut {
  holdings: Record<string, unknown>[];
  premarket: Record<string, unknown>[];
  top_movers: Record<string, unknown>[];
  sector_exposure: Record<string, number>;
  portfolio_value: number;
  daily_pnl: number;
  daily_pnl_pct: number;
  total_pnl: number;
  total_pnl_pct: number;
  cash: number;
}

export interface PriceBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface PriceHistory {
  symbol: string;
  bars: PriceBar[];
}

export interface SymbolInfo {
  symbol: string;
  name: string;
  sector: string;
}

export interface PremarketMover {
  cdr_symbol: string;
  us_symbol: string;
  premarket_price: number;
  change_pct: number;
}

export interface PremarketResponse {
  movers: PremarketMover[];
}

export interface DebugDevice {
  device_token: string;
  push_token: string | null;
  platform: string;
  enabled: boolean;
}

export interface TestPushResult {
  sent_to: number;
  symbol: string;
  signal: string;
  strength: number;
  score: number;
}

// --- API functions ---

export const api = {
  // Portfolio
  getHoldings: () => fetchAPI<PortfolioSummary>("/api/portfolio/holdings"),
  getPnl: () => fetchAPI<PnlSummary>("/api/portfolio/pnl"),
  getSnapshots: () => fetchAPI<SnapshotOut[]>("/api/portfolio/snapshots"),
  updateHolding: (symbol: string, quantity?: number, avg_cost?: number) =>
    fetchAPI<{ symbol: string; quantity: number; avg_cost: number }>("/api/portfolio/holding", {
      method: "PUT",
      body: JSON.stringify({ symbol, quantity, avg_cost }),
    }),
  deleteHolding: (symbol: string) =>
    fetchAPI<{ status: string; symbol: string }>(`/api/portfolio/holding/${encodeURIComponent(symbol)}`, {
      method: "DELETE",
    }),
  updateCash: (cash: number) =>
    fetchAPI<{ cash: number }>("/api/portfolio/cash", {
      method: "PUT",
      body: JSON.stringify({ cash }),
    }),

  // Trades
  recordBuy: (symbol: string, quantity: number, price: number) =>
    fetchAPI<TradeOut>("/api/trades/buy", {
      method: "POST",
      body: JSON.stringify({ symbol, quantity, price }),
    }),
  recordSell: (symbol: string, quantity: number, price: number) =>
    fetchAPI<TradeOut>("/api/trades/sell", {
      method: "POST",
      body: JSON.stringify({ symbol, quantity, price }),
    }),
  getTradeHistory: (limit = 50) =>
    fetchAPI<TradeOut[]>(`/api/trades/history?limit=${limit}`),

  // Signals
  checkSignal: (symbol: string) =>
    fetchAPI<SignalOut>(`/api/signals/check/${encodeURIComponent(symbol)}`),
  getPrice: (symbol: string) =>
    fetchAPI<{ symbol: string; price: number | null }>(`/api/signals/price/${encodeURIComponent(symbol)}`),
  getRecommendations: (n = 5) =>
    fetchAPI<RecommendationOut>(`/api/signals/recommend?n=${n}`),
  getActionPlan: () =>
    fetchAPI<ActionPlanOut>("/api/signals/actions"),
  snoozeSignal: (symbol: string, hours = 4, indefinite = false, phantomTrailingStop = true) =>
    fetchAPI<SnoozeOut>("/api/signals/snooze", {
      method: "POST",
      body: JSON.stringify({ symbol, hours, indefinite, phantom_trailing_stop: phantomTrailingStop }),
    }),
  unsnoozeSignal: (symbol: string) =>
    fetchAPI<{ status: string; symbol: string }>(`/api/signals/snooze/${encodeURIComponent(symbol)}`, {
      method: "DELETE",
    }),
  getSnoozed: () =>
    fetchAPI<SnoozeOut[]>("/api/signals/snoozed"),
  getPriceHistory: (symbol: string, period = "60d") =>
    fetchAPI<PriceHistory>(`/api/signals/history/${encodeURIComponent(symbol)}?period=${period}`),
  getInsights: () => fetchAPI<InsightsOut>("/api/signals/insights"),
  getPremarketMovers: () => fetchAPI<PremarketResponse>("/api/signals/premarket"),

  // Status
  getStatus: () => fetchAPI<StatusOut>("/api/status"),

  // Upload
  parseScreenshot: async (file: File): Promise<UploadHolding[]> => {
    const form = new FormData();
    form.append("file", file);
    const token = getAuthToken();
    const res = await fetch(`${API_BASE}/api/upload/parse`, {
      method: "POST",
      body: form,
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (res.status === 401) {
      clearAuthToken();
      _onUnauthorized?.();
      throw new Error("Authentication required");
    }
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new Error(body?.detail || `Upload failed: ${res.status}`);
    }
    return res.json();
  },
  confirmUpload: (holdings: UploadHolding[]) =>
    fetchAPI<{ status: string; count: number }>("/api/upload/confirm", {
      method: "POST",
      body: JSON.stringify({ holdings }),
    }),

  // Symbols
  getSymbols: () => fetchAPI<SymbolInfo[]>("/api/symbols"),

  // Auth
  getAuthStatus: () =>
    fetchAPI<{
      registered: boolean;
      credentials: { id: number; name: string; created_at: string | null }[];
    }>("/api/auth/status"),
  getRegisterOptions: () =>
    fetchAPI<Record<string, unknown>>("/api/auth/register/options", { method: "POST" }),
  verifyRegistration: (credential: Record<string, unknown>) =>
    fetchAPI<{ status: string; token: string }>("/api/auth/register/verify", {
      method: "POST",
      body: JSON.stringify(credential),
    }),
  getLoginOptions: () =>
    fetchAPI<Record<string, unknown>>("/api/auth/login/options", { method: "POST" }),
  verifyLogin: (credential: Record<string, unknown>) =>
    fetchAPI<{ status: string; token: string }>("/api/auth/login/verify", {
      method: "POST",
      body: JSON.stringify(credential),
    }),
  deleteCredential: (id: number) =>
    fetchAPI<{ status: string }>(`/api/auth/credentials/${id}`, { method: "DELETE" }),

  // Debug
  getDebugDevices: () => fetchAPI<DebugDevice[]>("/api/debug/devices"),
  testPush: (
    push_type: "call" | "notification",
    signal: { symbol: string; signal: string; strength: number; score: number },
    device_token?: string,
  ) =>
    fetchAPI<TestPushResult>("/api/debug/test-push", {
      method: "POST",
      body: JSON.stringify({ push_type, device_token: device_token || null, ...signal }),
    }),
};
