import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type {
  PortfolioSummary,
  PnlSummary,
  SnapshotOut,
  RecommendationOut,
  ActionPlanOut,
  StatusOut,
  TradeOut,
  SignalOut,
  SymbolInfo,
  PriceHistory,
  UploadHolding,
  PremarketResponse,
} from "./api";

// --- Query key factory ---

export const queryKeys = {
  holdings: ["holdings"] as const,
  pnl: ["pnl"] as const,
  snapshots: ["snapshots"] as const,
  recommendations: ["recommendations"] as const,
  actionPlan: ["actionPlan"] as const,
  status: ["status"] as const,
  tradeHistory: (limit: number) => ["tradeHistory", limit] as const,
  symbols: ["symbols"] as const,
  signal: (symbol: string) => ["signal", symbol] as const,
  price: (symbol: string) => ["price", symbol] as const,
  priceHistory: (symbol: string, period: string) => ["priceHistory", symbol, period] as const,
  insights: ["insights"] as const,
  premarket: ["premarket"] as const,
};

// --- Query hooks ---

export function useHoldings() {
  return useQuery<PortfolioSummary>({
    queryKey: queryKeys.holdings,
    queryFn: () => api.getHoldings(),
    staleTime: 2 * 60 * 1000,
  });
}

export function usePnl() {
  return useQuery<PnlSummary>({
    queryKey: queryKeys.pnl,
    queryFn: () => api.getPnl(),
    staleTime: 2 * 60 * 1000,
  });
}

export function useSnapshots() {
  return useQuery<SnapshotOut[]>({
    queryKey: queryKeys.snapshots,
    queryFn: () => api.getSnapshots(),
    staleTime: 5 * 60 * 1000,
  });
}

export function useRecommendations() {
  return useQuery<RecommendationOut>({
    queryKey: queryKeys.recommendations,
    queryFn: () => api.getRecommendations(5),
    staleTime: 10 * 60 * 1000,
  });
}

export function useActionPlan() {
  return useQuery<ActionPlanOut>({
    queryKey: queryKeys.actionPlan,
    queryFn: () => api.getActionPlan(),
    staleTime: 10 * 60 * 1000,
  });
}

export function useStatus() {
  return useQuery<StatusOut>({
    queryKey: queryKeys.status,
    queryFn: () => api.getStatus(),
    staleTime: 60 * 1000,
  });
}

export function useTradeHistory(limit = 50) {
  return useQuery<TradeOut[]>({
    queryKey: queryKeys.tradeHistory(limit),
    queryFn: () => api.getTradeHistory(limit),
    staleTime: 2 * 60 * 1000,
  });
}

export function useSymbols() {
  return useQuery<SymbolInfo[]>({
    queryKey: queryKeys.symbols,
    queryFn: () => api.getSymbols(),
    staleTime: 30 * 60 * 1000,
  });
}

export function useSignalCheck(symbol: string | null) {
  return useQuery<SignalOut>({
    queryKey: queryKeys.signal(symbol!),
    queryFn: () => api.checkSignal(symbol!),
    enabled: !!symbol,
    staleTime: 5 * 60 * 1000,
  });
}

export function usePremarketMovers() {
  return useQuery<PremarketResponse>({
    queryKey: queryKeys.premarket,
    queryFn: () => api.getPremarketMovers(),
    staleTime: 5 * 60 * 1000,
  });
}

export function usePriceHistory(symbol: string, period = "60d") {
  return useQuery<PriceHistory>({
    queryKey: queryKeys.priceHistory(symbol, period),
    queryFn: () => api.getPriceHistory(symbol, period),
    staleTime: 5 * 60 * 1000,
  });
}

// --- Mutation hooks ---

export function useRecordBuy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ symbol, quantity, price }: { symbol: string; quantity: number; price: number }) =>
      api.recordBuy(symbol, quantity, price),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.holdings });
      qc.invalidateQueries({ queryKey: queryKeys.pnl });
      qc.invalidateQueries({ queryKey: ["tradeHistory"] });
      qc.invalidateQueries({ queryKey: queryKeys.snapshots });
    },
  });
}

export function useRecordSell() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ symbol, quantity, price }: { symbol: string; quantity: number; price: number }) =>
      api.recordSell(symbol, quantity, price),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.holdings });
      qc.invalidateQueries({ queryKey: queryKeys.pnl });
      qc.invalidateQueries({ queryKey: ["tradeHistory"] });
      qc.invalidateQueries({ queryKey: queryKeys.snapshots });
    },
  });
}

export function useUpdateHolding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ symbol, quantity, avg_cost }: { symbol: string; quantity?: number; avg_cost?: number }) =>
      api.updateHolding(symbol, quantity, avg_cost),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.holdings });
      qc.invalidateQueries({ queryKey: queryKeys.pnl });
    },
  });
}

export function useDeleteHolding() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (symbol: string) => api.deleteHolding(symbol),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.holdings });
      qc.invalidateQueries({ queryKey: queryKeys.pnl });
    },
  });
}

export function useUpdateCash() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (cash: number) => api.updateCash(cash),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.holdings });
      qc.invalidateQueries({ queryKey: queryKeys.pnl });
    },
  });
}

export function useParseScreenshot() {
  return useMutation({
    mutationFn: (file: File) => api.parseScreenshot(file),
  });
}

export function useConfirmUpload() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (holdings: UploadHolding[]) => api.confirmUpload(holdings),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.holdings });
      qc.invalidateQueries({ queryKey: queryKeys.pnl });
    },
  });
}
