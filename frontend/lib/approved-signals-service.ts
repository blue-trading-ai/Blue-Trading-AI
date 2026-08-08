import type { TradingSignal } from "@/components/signals/signal-card";
import { apiRequest } from "@/lib/api";
import { normalizeTradingSignals } from "@/lib/signal-normalizer";

const SIGNALS_ENDPOINT =
  process.env
    .NEXT_PUBLIC_SIGNALS_ENDPOINT
    ?.trim() ||
  "/signals/list";

const MINIMUM_CONFIDENCE = 80;
const MINIMUM_CONFIRMATIONS = 3;
const MAXIMUM_VISIBLE_SIGNALS = 10;

export type ApprovedSignalsResponse = {
  signals: TradingSignal[];
  total: number;
};

function normalizeEndpoint(
  endpoint: string,
): string {
  const normalized =
    endpoint.trim();

  if (!normalized) {
    return "/signals/list";
  }

  return normalized.startsWith("/")
    ? normalized
    : `/${normalized}`;
}

function toFiniteNumber(
  value: unknown,
): number | null {
  if (
    typeof value === "number" &&
    Number.isFinite(value)
  ) {
    return value;
  }

  if (
    typeof value === "string" &&
    value.trim()
  ) {
    const parsed =
      Number.parseFloat(
        value
          .replace(/,/g, "")
          .replace(/^1\s*:\s*/, "")
          .replace("%", "")
          .trim(),
      );

    return Number.isFinite(parsed)
      ? parsed
      : null;
  }

  return null;
}

function normalizeDirection(
  value: unknown,
): "BUY" | "SELL" | null {
  const normalized =
    String(value ?? "")
      .trim()
      .toUpperCase();

  if (
    normalized === "BUY" ||
    normalized === "LONG" ||
    normalized === "BULLISH"
  ) {
    return "BUY";
  }

  if (
    normalized === "SELL" ||
    normalized === "SHORT" ||
    normalized === "BEARISH"
  ) {
    return "SELL";
  }

  return null;
}

function getRiskReward(
  signal: TradingSignal,
): number | null {
  return toFiniteNumber(
    signal.riskReward,
  );
}

function hasValidQuality(
  signal: TradingSignal,
): boolean {
  return (
    Number.isFinite(
      signal.confidence,
    ) &&
    signal.confidence >=
      MINIMUM_CONFIDENCE &&
    Number.isFinite(
      signal.confirmations,
    ) &&
    signal.confirmations >=
      MINIMUM_CONFIRMATIONS
  );
}

function hasValidIdentity(
  signal: TradingSignal,
): boolean {
  return (
    typeof signal.symbol ===
      "string" &&
    signal.symbol.trim().length > 0 &&
    typeof signal.timeframe ===
      "string" &&
    signal.timeframe.trim().length >
      0 &&
    normalizeDirection(
      signal.direction,
    ) !== null
  );
}

function hasValidTradeLevels(
  signal: TradingSignal,
): boolean {
  const direction =
    normalizeDirection(
      signal.direction,
    );

  const entry =
    toFiniteNumber(signal.entry);

  const stopLoss =
    toFiniteNumber(
      signal.stopLoss,
    );

  const takeProfit1 =
    toFiniteNumber(
      signal.takeProfit1,
    );

  const takeProfit2 =
    toFiniteNumber(
      signal.takeProfit2,
    );

  if (
    !direction ||
    entry === null ||
    stopLoss === null ||
    takeProfit1 === null ||
    takeProfit2 === null ||
    entry <= 0 ||
    stopLoss <= 0 ||
    takeProfit1 <= 0 ||
    takeProfit2 <= 0
  ) {
    return false;
  }

  if (direction === "BUY") {
    return (
      stopLoss < entry &&
      takeProfit1 > entry &&
      takeProfit2 >
        takeProfit1
    );
  }

  return (
    stopLoss > entry &&
    takeProfit1 < entry &&
    takeProfit2 <
      takeProfit1
  );
}

function hasValidRiskReward(
  signal: TradingSignal,
): boolean {
  const riskReward =
    getRiskReward(signal);

  if (riskReward === null) {
    return true;
  }

  return riskReward > 0;
}

function isApprovedSignal(
  signal: TradingSignal,
): boolean {
  return (
    hasValidIdentity(signal) &&
    hasValidQuality(signal) &&
    hasValidTradeLevels(signal) &&
    hasValidRiskReward(signal)
  );
}

function getSignalTimestamp(
  signal: TradingSignal,
): number {
  if (!signal.createdAt) {
    return 0;
  }

  const timestamp =
    Date.parse(signal.createdAt);

  return Number.isFinite(timestamp)
    ? timestamp
    : 0;
}

function getSignalIdentity(
  signal: TradingSignal,
): string {
  return [
    signal.symbol,
    signal.timeframe,
    signal.direction,
    signal.entry,
    signal.stopLoss,
    signal.takeProfit1,
    signal.takeProfit2,
    signal.createdAt ?? "",
  ]
    .map((value) =>
      String(value ?? "")
        .trim()
        .toUpperCase(),
    )
    .join("|");
}

function removeDuplicateSignals(
  signals: readonly TradingSignal[],
): TradingSignal[] {
  const seen =
    new Set<string>();

  return signals.filter(
    (signal) => {
      const identity =
        getSignalIdentity(signal);

      if (
        !identity ||
        seen.has(identity)
      ) {
        return false;
      }

      seen.add(identity);
      return true;
    },
  );
}

export async function getApprovedSignals(
  signal?: AbortSignal,
): Promise<ApprovedSignalsResponse> {
  const query =
    new URLSearchParams({
      limit: String(
        MAXIMUM_VISIBLE_SIGNALS,
      ),
    });

  const endpoint =
    `${normalizeEndpoint(
      SIGNALS_ENDPOINT,
    )}?${query.toString()}`;

  const payload =
    await apiRequest<unknown>(
      endpoint,
      {
        method: "GET",
        signal,
      },
    );

  const signals =
    removeDuplicateSignals(
      normalizeTradingSignals(
        payload,
      )
        .filter(isApprovedSignal)
        .sort(
          (first, second) =>
            getSignalTimestamp(
              second,
            ) -
            getSignalTimestamp(
              first,
            ),
        ),
    ).slice(
      0,
      MAXIMUM_VISIBLE_SIGNALS,
    );

  return {
    signals,
    total: signals.length,
  };
}