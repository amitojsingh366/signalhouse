const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

// --- localStorage cache layer ---

const CACHE_PREFIX = "trader_cache_";
const CACHE_DURATIONS: Record<string, number> = {
  "/api/portfolio/holdings": 2 * 60 * 1000,   // 2 min
  "/api/portfolio/pnl": 2 * 60 * 1000,
  "/api/portfolio/snapshots": 5 * 60 * 1000,  // 5 min
  "/api/signals/recommend": 10 * 60 * 1000,   // 10 min
  "/api/signals/insights": 10 * 60 * 1000,
  "/api/status": 60 * 1000,                   // 1 min
  "/api/symbols": 30 * 60 * 1000,             // 30 min
  "/api/trades/history": 2 * 60 * 1000,
};

function getCacheKey(path: string): string {
  return CACHE_PREFIX + path;
}

function getCache<T>(path: string): T | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(getCacheKey(path));
    if (!raw) return null;
    const { data, ts } = JSON.parse(raw);
    const maxAge = CACHE_DURATIONS[path.split("?")[0]];
    if (!maxAge || Date.now() - ts > maxAge) return null;
    return data as T;
  } catch {
    return null;
  }
}

function setCache<T>(path: string, data: T): void {
  if (typeof window === "undefined") return;
  try {
    const key = getCacheKey(path);
    localStorage.setItem(key, JSON.stringify({ data, ts: Date.now() }));
  } catch {
    // quota exceeded — silently ignore
  }
}

async function fetchAPI<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body}`);
  }
  const data: T = await res.json();
  // Cache GET responses
  if (!init?.method || init.method === "GET") {
    setCache(path, data);
  }
  return data;
}

/** Fetch with cache-first strategy: returns cached data immediately via onCached, then fetches fresh data */
function fetchWithCache<T>(
  path: string,
  onCached: (data: T) => void,
  onFresh: (data: T) => void,
  onError?: (err: Error) => void,
): void {
  const cached = getCache<T>(path);
  if (cached) onCached(cached);
  fetchAPI<T>(path)
    .then(onFresh)
    .catch((err) => {
      if (!cached && onError) onError(err);
    });
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
  reasons: string[];
  price: number | null;
  sector: string | null;
}

export interface RecommendationOut {
  buys: SignalOut[];
  sells: SignalOut[];
  funding: Record<string, unknown>[];
  sector_exposure: Record<string, number>;
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

export interface SymbolInfo {
  symbol: string;
  name: string;
  sector: string;
}

// --- API functions ---

export { fetchWithCache, getCache };

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
  getRecommendations: (n = 5) =>
    fetchAPI<RecommendationOut>(`/api/signals/recommend?n=${n}`),
  getInsights: () => fetchAPI<InsightsOut>("/api/signals/insights"),

  // Status
  getStatus: () => fetchAPI<StatusOut>("/api/status"),

  // Upload
  parseScreenshot: async (file: File): Promise<UploadHolding[]> => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_BASE}/api/upload/parse`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
    return res.json();
  },
  confirmUpload: (holdings: UploadHolding[]) =>
    fetchAPI<{ status: string; count: number }>("/api/upload/confirm", {
      method: "POST",
      body: JSON.stringify({ holdings }),
    }),

  // Symbols
  getSymbols: () => fetchAPI<SymbolInfo[]>("/api/symbols"),
};
