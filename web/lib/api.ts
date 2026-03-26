const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

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

export const api = {
  // Portfolio
  getHoldings: () => fetchAPI<PortfolioSummary>("/api/portfolio/holdings"),
  getPnl: () => fetchAPI<PnlSummary>("/api/portfolio/pnl"),
  getSnapshots: () => fetchAPI<SnapshotOut[]>("/api/portfolio/snapshots"),

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
