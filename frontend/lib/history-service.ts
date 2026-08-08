import {
  API_BASE_URL,
  ApiError,
  getAccessToken,
} from "@/lib/api";

export type TradeHistoryRecord = {
  id: string;
  symbol: string;
  timeframe: string;
  direction: "BUY" | "SELL";
  entry: number | string | null;
  stopLoss: number | string | null;
  takeProfit1: number | string | null;
  takeProfit2: number | string | null;
  confidence: number;
  confirmations: number;
  riskReward: number | string | null;
  status: string;
  createdAt: string | null;
  closedAt: string | null;
  result: string | null;
  raw: unknown;
};

export type TradeHistoryResponse = {
  records: TradeHistoryRecord[];
  total: number;
  tpHit: number;
  slHit: number;
  open: number;
};

type UnknownRecord = Record<string, unknown>;

const HISTORY_ENDPOINT =
  process.env.NEXT_PUBLIC_HISTORY_ENDPOINT?.trim() ||
  "/history/list";

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
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    const text = String(value).trim();

    return text || null;
  }

  return null;
}

function toNumber(
  value: unknown,
): number {
  if (
    typeof value === "number" &&
    Number.isFinite(value)
  ) {
    return value;
  }

  if (typeof value === "string") {
    const parsed = Number.parseFloat(
      value.replace("%", "").trim(),
    );

    return Number.isFinite(parsed)
      ? parsed
      : 0;
  }

  return 0;
}

function toDirection(
  value: unknown,
): "BUY" | "SELL" | null {
  const normalized =
    toText(value)?.toUpperCase() || "";

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

function getItems(
  payload: unknown,
): unknown[] {
  if (Array.isArray(payload)) {
    return payload;
  }

  if (!isRecord(payload)) {
    return [];
  }

  const nested = firstDefined(
    payload,
    [
      "history",
      "records",
      "signals",
      "trades",
      "results",
      "items",
      "data",
    ],
  );

  if (Array.isArray(nested)) {
    return nested;
  }

  if (isRecord(nested)) {
    const nestedItems = firstDefined(
      nested,
      [
        "history",
        "records",
        "signals",
        "trades",
        "results",
        "items",
      ],
    );

    return Array.isArray(nestedItems)
      ? nestedItems
      : [];
  }

  return [];
}

function normalizeRecord(
  value: unknown,
  index: number,
): TradeHistoryRecord | null {
  if (!isRecord(value)) {
    return null;
  }

  const direction = toDirection(
    firstDefined(value, [
      "direction",
      "signal",
      "side",
      "trade_direction",
      "bias",
    ]),
  );

  const symbol =
    toText(
      firstDefined(value, [
        "symbol",
        "pair",
        "market",
        "instrument",
      ]),
    )?.toUpperCase() || "";

  const timeframe =
    toText(
      firstDefined(value, [
        "timeframe",
        "interval",
        "tf",
      ]),
    )?.toUpperCase() || "";

  if (!direction || !symbol || !timeframe) {
    return null;
  }

  const id =
    toText(
      firstDefined(value, [
        "id",
        "signal_id",
        "signal_uid",
        "trade_id",
        "trade_uid",
        "uuid",
        "uid",
      ]),
    ) ||
    `${symbol}-${timeframe}-${direction}-${index}`;

  const status =
    toText(
      firstDefined(value, [
        "status",
        "signal_status",
        "trade_status",
        "state",
        "outcome",
        "result_status",
      ]),
    )?.toUpperCase() || "OPEN";

  return {
    id,
    symbol,
    timeframe,
    direction,
    entry: toText(
      firstDefined(value, [
        "entry",
        "entry_price",
        "entry_level",
      ]),
    ),
    stopLoss: toText(
      firstDefined(value, [
        "stop_loss",
        "stopLoss",
        "sl",
      ]),
    ),
    takeProfit1: toText(
      firstDefined(value, [
        "take_profit_1",
        "takeProfit1",
        "tp1",
        "take_profit",
      ]),
    ),
    takeProfit2: toText(
      firstDefined(value, [
        "take_profit_2",
        "takeProfit2",
        "tp2",
      ]),
    ),
    confidence: Math.min(
      Math.max(
        toNumber(
          firstDefined(value, [
            "confidence",
            "confidence_score",
            "confidence_level",
            "final_confidence",
          ]),
        ),
        0,
      ),
      100,
    ),
    confirmations: Math.max(
      Math.trunc(
        toNumber(
          firstDefined(value, [
            "confirmations",
            "confirmation_count",
            "confirmations_count",
            "total_confirmations",
          ]),
        ),
      ),
      0,
    ),
    riskReward: toText(
      firstDefined(value, [
        "risk_reward",
        "riskReward",
        "rr",
        "rr_ratio",
        "risk_reward_ratio",
      ]),
    ),
    status,
    createdAt: toText(
      firstDefined(value, [
        "created_at",
        "createdAt",
        "published_at",
        "generated_at",
        "opened_at",
        "timestamp",
      ]),
    ),
    closedAt: toText(
      firstDefined(value, [
        "closed_at",
        "closedAt",
        "completed_at",
        "resolved_at",
        "finished_at",
      ]),
    ),
    result: toText(
      firstDefined(value, [
        "result",
        "outcome",
        "final_result",
        "trade_result",
      ]),
    ),
    raw: value,
  };
}

export async function getTradeHistory(
  market: string,
  direction: string,
  status: string,
  period: string,
  signal?: AbortSignal,
): Promise<TradeHistoryResponse> {
  const accessToken = getAccessToken();

  if (!accessToken) {
    throw new ApiError(
      "Authentication is required to load trade history.",
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

  if (direction !== "All Directions") {
    query.set(
      "direction",
      direction.trim().toUpperCase(),
    );
  }

  if (status !== "All Statuses") {
    query.set(
      "status",
      status.trim().toUpperCase(),
    );
  }

  const response = await fetch(
    `${API_BASE_URL}${HISTORY_ENDPOINT}?${query.toString()}`,
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
        `Trade history request failed with status ${response.status}`,
      ),
      response.status,
      payload,
    );
  }

  const records = getItems(payload)
    .map(normalizeRecord)
    .filter(
      (
        record,
      ): record is TradeHistoryRecord =>
        record !== null,
    )
    .sort((first, second) => {
      const firstTime = first.createdAt
        ? Date.parse(first.createdAt)
        : 0;

      const secondTime = second.createdAt
        ? Date.parse(second.createdAt)
        : 0;

      return secondTime - firstTime;
    });

  const tpHit = records.filter((record) =>
    [
      "TP HIT",
      "TP_HIT",
      "TAKE PROFIT HIT",
      "TAKE_PROFIT_HIT",
      "WIN",
      "WON",
      "PROFIT",
    ].includes(record.status),
  ).length;

  const slHit = records.filter((record) =>
    [
      "SL HIT",
      "SL_HIT",
      "STOP LOSS HIT",
      "STOP_LOSS_HIT",
      "LOSS",
      "LOST",
    ].includes(record.status),
  ).length;

  const open = records.filter((record) =>
    [
      "OPEN",
      "ACTIVE",
      "PENDING",
      "PUBLISHED",
    ].includes(record.status),
  ).length;

  return {
    records,
    total: records.length,
    tpHit,
    slHit,
    open,
  };
}