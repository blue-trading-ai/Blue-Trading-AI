import {
  API_BASE_URL,
  ApiError,
  getAccessToken,
} from "@/lib/api";

export type MarketAnalysisResult = {
  symbol: string;
  timeframe: string;
  signal: string | null;
  confidence: number;
  confirmations: number;
  entry: number | string | null;
  stopLoss: number | string | null;
  takeProfit1: number | string | null;
  takeProfit2: number | string | null;
  riskReward: number | string | null;
  marketStructure: string | null;
  reasons: string[];
  raw: unknown;
};

type UnknownRecord = Record<string, unknown>;

function isRecord(
  value: unknown,
): value is UnknownRecord {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value)
  );
}

function firstDefined(
  source: UnknownRecord,
  keys: string[],
): unknown {
  for (const key of keys) {
    const value = source[key];

    if (
      value !== undefined &&
      value !== null &&
      value !== ""
    ) {
      return value;
    }
  }

  return undefined;
}

function toText(
  value: unknown,
): string | null {
  if (
    typeof value === "string" ||
    typeof value === "number"
  ) {
    const text = String(value).trim();

    return text || null;
  }

  return null;
}

function toNumber(
  value: unknown,
): number {
  if (typeof value === "number") {
    return Number.isFinite(value)
      ? value
      : 0;
  }

  if (typeof value === "string") {
    const parsed = Number.parseFloat(value);

    return Number.isFinite(parsed)
      ? parsed
      : 0;
  }

  return 0;
}

function toReasons(
  value: unknown,
): string[] {
  if (Array.isArray(value)) {
    return value
      .map((item) => toText(item))
      .filter(
        (item): item is string =>
          item !== null,
      );
  }

  if (typeof value === "string") {
    return value
      .split(/[,|;]/)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  return [];
}

function normalizeTimeframe(
  timeframe: string,
): string {
  const normalized = timeframe
    .trim()
    .toLowerCase();

  const mapping: Record<string, string> = {
    m5: "5m",
    m15: "15m",
    m30: "30m",
    h1: "1h",
    h4: "4h",
    d1: "1d",
    daily: "1d",
  };

  return mapping[normalized] || normalized;
}

function getErrorMessage(
  payload: unknown,
  fallback: string,
): string {
  if (isRecord(payload)) {
    const detail = firstDefined(payload, [
      "detail",
      "message",
      "error",
    ]);

    const text = toText(detail);

    if (text) {
      return text;
    }
  }

  if (
    typeof payload === "string" &&
    payload.trim()
  ) {
    return payload.trim();
  }

  return fallback;
}

export async function runMarketAnalysis(
  symbol: string,
  timeframe: string,
  signal?: AbortSignal,
): Promise<MarketAnalysisResult> {
  const accessToken = getAccessToken();

  if (!accessToken) {
    throw new ApiError(
      "Authentication is required to run market analysis.",
      401,
      null,
    );
  }

  const normalizedSymbol = symbol
    .trim()
    .toUpperCase();

  const normalizedTimeframe =
    normalizeTimeframe(timeframe);

  const endpoint =
    `${API_BASE_URL}/trading/signal/` +
    `${encodeURIComponent(normalizedSymbol)}` +
    `?interval=${encodeURIComponent(normalizedTimeframe)}`;

  const response = await fetch(endpoint, {
    method: "GET",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    cache: "no-store",
    signal,
  });

  const contentType =
    response.headers.get("content-type") || "";

  const payload: unknown =
    contentType.includes("application/json")
      ? await response.json()
      : await response.text();

  if (!response.ok) {
    throw new ApiError(
      getErrorMessage(
        payload,
        `Market analysis failed with status ${response.status}`,
      ),
      response.status,
      payload,
    );
  }

  const source = isRecord(payload)
    ? payload
    : {};

  return {
    symbol:
      toText(
        firstDefined(source, [
          "symbol",
          "pair",
          "market",
        ]),
      ) || normalizedSymbol,
    timeframe:
      toText(
        firstDefined(source, [
          "timeframe",
          "interval",
          "tf",
        ]),
      ) || timeframe.toUpperCase(),
    signal: toText(
      firstDefined(source, [
        "signal",
        "direction",
        "bias",
        "trade_direction",
      ]),
    ),
    confidence: Math.min(
      Math.max(
        toNumber(
          firstDefined(source, [
            "confidence",
            "confidence_score",
            "confidence_level",
            "score",
          ]),
        ),
        0,
      ),
      100,
    ),
    confirmations: Math.max(
      Math.trunc(
        toNumber(
          firstDefined(source, [
            "confirmations",
            "confirmation_count",
            "confirmations_count",
          ]),
        ),
      ),
      0,
    ),
    entry: toText(
      firstDefined(source, [
        "entry",
        "entry_price",
        "entry_level",
      ]),
    ),
    stopLoss: toText(
      firstDefined(source, [
        "stop_loss",
        "stopLoss",
        "sl",
      ]),
    ),
    takeProfit1: toText(
      firstDefined(source, [
        "take_profit_1",
        "takeProfit1",
        "tp1",
        "take_profit",
      ]),
    ),
    takeProfit2: toText(
      firstDefined(source, [
        "take_profit_2",
        "takeProfit2",
        "tp2",
      ]),
    ),
    riskReward: toText(
      firstDefined(source, [
        "risk_reward",
        "riskReward",
        "rr",
        "rr_ratio",
      ]),
    ),
    marketStructure: toText(
      firstDefined(source, [
        "market_structure",
        "marketStructure",
        "structure",
      ]),
    ),
    reasons: toReasons(
      firstDefined(source, [
        "reasons",
        "confirmation_reasons",
        "confirmations_list",
        "analysis_reasons",
      ]),
    ),
    raw: payload,
  };
}