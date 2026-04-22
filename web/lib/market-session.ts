export type MarketSession = "premarket" | "regular" | "postmarket";

const MARKET_OPEN_MINUTES = 9 * 60 + 30;
const MARKET_CLOSE_MINUTES = 16 * 60;

function getEasternMinutes(now: Date): number {
  const parts = new Intl.DateTimeFormat("en-CA", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "America/Toronto",
  }).formatToParts(now);

  const hour = Number(parts.find((part) => part.type === "hour")?.value ?? "0");
  const minute = Number(parts.find((part) => part.type === "minute")?.value ?? "0");
  return hour * 60 + minute;
}

export function getMarketSession(now = new Date()): MarketSession {
  const minutes = getEasternMinutes(now);
  if (minutes >= MARKET_OPEN_MINUTES && minutes < MARKET_CLOSE_MINUTES) {
    return "regular";
  }
  if (minutes < MARKET_OPEN_MINUTES) {
    return "premarket";
  }
  return "postmarket";
}

export function getExtendedSessionLabel(now = new Date(), regularLabel = "Pre-market"): string {
  const session = getMarketSession(now);
  if (session === "premarket") return "Pre-market";
  if (session === "postmarket") return "Post-market";
  return regularLabel;
}
