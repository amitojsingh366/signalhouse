export interface TradeIntentOptions {
  open?: boolean;
  action?: "buy" | "sell";
  symbol?: string | null;
  price?: number | null;
}

export function buildTradeIntentHref(options: TradeIntentOptions = {}): string {
  const { open = false, action, symbol, price } = options;
  const params = new URLSearchParams();

  if (open) params.set("open", "1");
  if (action) params.set("action", action);
  if (symbol && symbol.trim()) params.set("symbol", symbol.trim().toUpperCase());
  if (typeof price === "number" && Number.isFinite(price)) {
    params.set("price", price.toFixed(2));
  }

  const query = params.toString();
  return query ? `/trades?${query}` : "/trades";
}
