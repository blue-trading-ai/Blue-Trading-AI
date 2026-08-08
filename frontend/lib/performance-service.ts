import {
  API_BASE_URL,
  ApiError,
  getAccessToken,
} from "@/lib/api";

export type PerformanceSummary = {
  winRate: number;
  totalSignals: number;
  successfulSignals: number;
  losingSignals: number;
  openSignals: number;
  rejectedSignals: number;
  averageConfidence: number;
  averageRiskReward: number;
  maximumDrawdown: number;
  averageConfirmations: number;
  bestMarket: string | null;
  bestTimeframe: string | null;
  period: string;
  market: string;
  raw: unknown;
};

type UnknownRecord = Record<string, unknown>;

const PERFORMANCE_ENDPOINT =
  process.env.NEXT_PUBLIC_PERFORMANCE_ENDPOINT?.trim() ||
  "/signals/performance/overview";

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

function toNumber(
  value: unknown,
  fallback = 0,
): number {
  if (
    typeof value === "number" &&
    Number.isFinite(value)
  ) {
    return value;
  }

  if (typeof value === "string") {
    const normalized = value
      .trim()
      .replace("%", "");

    const parsed =
      Number.parseFloat(normalized);

    return Number.isFinite(parsed)
      ? parsed
      : fallback;
  }

  return fallback;
}

function toInteger(
  value: unknown,
): number {
  return Math.max(
    Math.trunc(toNumber(value)),
    0,
  );
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

    if (typeof detail === "string" && detail.trim()) {
      return detail.trim();
    }

    if (
      isRecord(detail) &&
      typeof detail.message === "string" &&
      detail.message.trim()
    ) {
      return detail.message.trim();
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

function getSummarySource(
  payload: unknown,
): UnknownRecord {
  if (!isRecord(payload)) {
    return {};
  }

  const nested = firstDefined(
    payload,
    [
      "overview",
      "summary",
      "performance",
      "statistics",
      "stats",
      "data",
    ],
  );

  return isRecord(nested)
    ? nested
    : payload;
}

function normalizePeriod(
  period: string,
): string {
  const mapping: Record<string, string> = {
    "7 Days": "7d",
    "30 Days": "30d",
    "90 Days": "90d",
    "All Time": "all",
  };

  return mapping[period] || period;
}

export async function getPerformanceSummary(
  period: string,
  market: string,
  signal?: AbortSignal,
): Promise<PerformanceSummary> {
  const accessToken = getAccessToken();

  if (!accessToken) {
    throw new ApiError(
      "Authentication is required to load performance data.",
      401,
      null,
    );
  }

  const query = new URLSearchParams({
    period: normalizePeriod(period),
  });

  if (market !== "All Markets") {
    const normalizedMarket =
      market.trim().toUpperCase();

    query.set("market", normalizedMarket);
    query.set("symbol", normalizedMarket);
  }

  const response = await fetch(
    `${API_BASE_URL}${PERFORMANCE_ENDPOINT}?${query.toString()}`,
    {
      method: "GET",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      cache: "no-store",
      signal,
    },
  );

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
        `Performance request failed with status ${response.status}`,
      ),
      response.status,
      payload,
    );
  }

  const source =
    getSummarySource(payload);

  const totalSignals = toInteger(
    firstDefined(source, [
      "total_signals",
      "totalSignals",
      "signal_count",
      "trade_count",
      "total_trades",
      "completed_signals",
      "completed_trades",
    ]),
  );

  const successfulSignals = toInteger(
    firstDefined(source, [
      "successful_signals",
      "successfulSignals",
      "wins",
      "winning_signals",
      "winning_trades",
      "profitable_signals",
    ]),
  );

  const losingSignals = toInteger(
    firstDefined(source, [
      "losing_signals",
      "losingSignals",
      "losses",
      "losing_trades",
      "failed_signals",
    ]),
  );

  const calculatedWinRate =
    totalSignals > 0
      ? (successfulSignals / totalSignals) *
        100
      : 0;

  return {
    winRate: Math.min(
      Math.max(
        toNumber(
          firstDefined(source, [
            "win_rate",
            "winRate",
            "success_rate",
            "accuracy",
            "overall_win_rate",
          ]),
          calculatedWinRate,
        ),
        0,
      ),
      100,
    ),
    totalSignals,
    successfulSignals,
    losingSignals,
    openSignals: toInteger(
      firstDefined(source, [
        "open_signals",
        "openSignals",
        "active_signals",
        "pending_signals",
      ]),
    ),
    rejectedSignals: toInteger(
      firstDefined(source, [
        "rejected_signals",
        "rejectedSignals",
        "no_trade_rejections",
        "blocked_setups",
        "cancelled_signals",
      ]),
    ),
    averageConfidence: Math.min(
      Math.max(
        toNumber(
          firstDefined(source, [
            "average_confidence",
            "averageConfidence",
            "avg_confidence",
          ]),
        ),
        0,
      ),
      100,
    ),
    averageRiskReward: Math.max(
      toNumber(
        firstDefined(source, [
          "average_risk_reward",
          "averageRiskReward",
          "avg_risk_reward",
          "average_rr",
          "avg_rr",
        ]),
      ),
      0,
    ),
    maximumDrawdown: Math.max(
      toNumber(
        firstDefined(source, [
          "maximum_drawdown",
          "maximumDrawdown",
          "max_drawdown",
          "drawdown",
        ]),
      ),
      0,
    ),
    averageConfirmations: Math.max(
      toNumber(
        firstDefined(source, [
          "average_confirmations",
          "averageConfirmations",
          "avg_confirmations",
        ]),
      ),
      0,
    ),
    bestMarket: toText(
      firstDefined(source, [
        "best_market",
        "bestMarket",
        "top_market",
        "best_symbol",
        "top_symbol",
      ]),
    ),
    bestTimeframe: toText(
      firstDefined(source, [
        "best_timeframe",
        "bestTimeframe",
        "top_timeframe",
      ]),
    ),
    period,
    market,
    raw: payload,
  };
}