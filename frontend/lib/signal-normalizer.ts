import type { TradingSignal } from "@/components/signals/signal-card";

type UnknownRecord =
  Record<string, unknown>;

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
  keys: readonly string[],
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
  fallback = "",
): string {
  if (
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    const text =
      String(value).trim();

    return text || fallback;
  }

  return fallback;
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
      .replace(/,/g, "")
      .replace("%", "")
      .replace(/^1\s*:\s*/, "");

    const parsed =
      Number.parseFloat(normalized);

    return Number.isFinite(parsed)
      ? parsed
      : fallback;
  }

  return fallback;
}

function toDirection(
  value: unknown,
): "BUY" | "SELL" | null {
  const normalized =
    toText(value).toUpperCase();

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

function isBlockedStatus(
  value: unknown,
): boolean {
  const normalized =
    toText(value).toUpperCase();

  return [
    "BLOCKED",
    "REJECTED",
    "FAILED",
    "NO_TRADE",
    "NO TRADE",
    "HOLD",
    "SKIP",
    "CANCELLED",
    "CANCELED",
  ].includes(normalized);
}

function toStatus(
  value: unknown,
): TradingSignal["status"] {
  const normalized =
    toText(value).toUpperCase();

  if (
    normalized === "PENDING" ||
    normalized === "WAITING" ||
    normalized === "DRAFT" ||
    normalized === "QUEUED"
  ) {
    return "PENDING";
  }

  if (
    normalized === "CLOSED" ||
    normalized === "COMPLETED" ||
    normalized === "EXPIRED" ||
    normalized === "CANCELLED" ||
    normalized === "CANCELED" ||
    normalized === "REJECTED" ||
    normalized === "FAILED" ||
    normalized === "BLOCKED" ||
    normalized === "NO_TRADE" ||
    normalized === "NO TRADE" ||
    normalized === "HOLD" ||
    normalized === "SKIP" ||
    normalized === "TP_HIT" ||
    normalized === "SL_HIT" ||
    normalized === "WIN" ||
    normalized === "LOSS"
  ) {
    return "CLOSED";
  }

  return "ACTIVE";
}

function normalizeReasonItem(
  value: unknown,
): string {
  if (
    typeof value === "string" ||
    typeof value === "number"
  ) {
    return String(value).trim();
  }

  if (isRecord(value)) {
    return toText(
      firstDefined(value, [
        "label",
        "name",
        "type",
        "confirmation",
        "reason",
        "description",
        "message",
      ]),
    );
  }

  return "";
}

function toReasons(
  value: unknown,
): string[] {
  let reasons: string[] = [];

  if (Array.isArray(value)) {
    reasons = value
      .map(normalizeReasonItem)
      .filter(Boolean);
  } else if (isRecord(value)) {
    reasons = Object.entries(value)
      .filter(([, confirmed]) =>
        Boolean(confirmed),
      )
      .map(([name, confirmed]) => {
        const normalized =
          normalizeReasonItem(
            confirmed,
          );

        return normalized || name;
      })
      .filter(Boolean);
  } else if (typeof value === "string") {
    reasons = value
      .split(/[,|;]/)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  return Array.from(
    new Set(reasons),
  );
}

function getConfirmationCount(
  source: UnknownRecord,
  reasons: string[],
): number {
  const explicitCount =
    firstDefined(source, [
      "confirmations_count",
      "confirmation_count",
      "total_confirmations",
      "confirmation_total",
    ]);

  const explicitNumeric =
    toNumber(
      explicitCount,
      Number.NaN,
    );

  if (
    Number.isFinite(
      explicitNumeric,
    )
  ) {
    return Math.max(
      Math.trunc(explicitNumeric),
      reasons.length,
      0,
    );
  }

  const confirmations =
    source.confirmations;

  if (Array.isArray(confirmations)) {
    return Math.max(
      confirmations.length,
      reasons.length,
    );
  }

  if (isRecord(confirmations)) {
    return Math.max(
      Object.values(confirmations)
        .filter(Boolean).length,
      reasons.length,
    );
  }

  const numericConfirmations =
    toNumber(
      confirmations,
      Number.NaN,
    );

  if (
    Number.isFinite(
      numericConfirmations,
    )
  ) {
    return Math.max(
      Math.trunc(
        numericConfirmations,
      ),
      reasons.length,
      0,
    );
  }

  return reasons.length;
}

function formatPrice(
  value: unknown,
): string {
  const numericValue =
    toNumber(
      value,
      Number.NaN,
    );

  if (
    Number.isFinite(
      numericValue,
    ) &&
    numericValue > 0
  ) {
    return numericValue.toFixed(2);
  }

  return "—";
}

function formatOptionalPrice(
  value: unknown,
): string | null {
  const formatted =
    formatPrice(value);

  return formatted === "—"
    ? null
    : formatted;
}

function formatRiskReward(
  value: unknown,
): string {
  const numericValue =
    toNumber(
      value,
      Number.NaN,
    );

  if (
    Number.isFinite(
      numericValue,
    ) &&
    numericValue > 0
  ) {
    return `1:${numericValue.toFixed(2)}`;
  }

  return "—";
}

function getNestedItems(
  value: unknown,
): unknown[] {
  if (Array.isArray(value)) {
    return value;
  }

  if (!isRecord(value)) {
    return [];
  }

  const nested =
    firstDefined(value, [
      "signals",
      "records",
      "results",
      "items",
      "history",
      "data",
    ]);

  if (Array.isArray(nested)) {
    return nested;
  }

  if (isRecord(nested)) {
    return getNestedItems(nested);
  }

  return [];
}

function getCreatedAt(
  source: UnknownRecord,
): string | null {
  const value = toText(
    firstDefined(source, [
      "published_at",
      "created_at",
      "createdAt",
      "generated_at",
      "timestamp",
      "opened_at",
    ]),
  );

  return value || null;
}

export function normalizeTradingSignal(
  value: unknown,
  index = 0,
): TradingSignal | null {
  if (!isRecord(value)) {
    return null;
  }

  const rawStatus =
    firstDefined(value, [
      "status",
      "signal_status",
      "trade_status",
      "state",
      "result",
    ]);

  const explicitlyBlocked =
    isBlockedStatus(rawStatus) ||
    value.is_trade_allowed === false ||
    value.trade_allowed === false ||
    value.approved === false ||
    value.is_approved === false;

  const direction = toDirection(
    firstDefined(value, [
      "direction",
      "signal",
      "side",
      "trade_direction",
      "bias",
    ]),
  );

  if (!direction) {
    return null;
  }

  const symbol = toText(
    firstDefined(value, [
      "symbol",
      "pair",
      "market",
      "instrument",
      "ticker",
    ]),
  ).toUpperCase();

  const timeframe = toText(
    firstDefined(value, [
      "timeframe",
      "interval",
      "tf",
      "period",
    ]),
  ).toUpperCase();

  if (!symbol || !timeframe) {
    return null;
  }

  const confidence = Math.min(
    Math.max(
      toNumber(
        firstDefined(value, [
          "final_confidence",
          "confidence",
          "confidence_score",
          "confidence_level",
          "score",
        ]),
      ),
      0,
    ),
    100,
  );

  const reasons = toReasons(
    firstDefined(value, [
      "reasons",
      "confirmations",
      "confirmations_list",
      "confirmation_reasons",
      "analysis_reasons",
      "confluence_reasons",
    ]),
  );

  const confirmations =
    getConfirmationCount(
      value,
      reasons,
    );

  const createdAt =
    getCreatedAt(value);

  const id =
    toText(
      firstDefined(value, [
        "signal_uid",
        "id",
        "signal_id",
        "trade_uid",
        "uuid",
        "uid",
      ]),
    ) ||
    `${symbol}-${timeframe}-${direction}-${createdAt ?? index}`;

  return {
    id,
    symbol,
    timeframe,
    direction,
    entry: formatPrice(
      firstDefined(value, [
        "entry_price",
        "entry",
        "entry_level",
        "price",
      ]),
    ),
    stopLoss: formatPrice(
      firstDefined(value, [
        "stop_loss",
        "stopLoss",
        "sl",
        "stop",
      ]),
    ),
    takeProfit1: formatPrice(
      firstDefined(value, [
        "take_profit_1",
        "takeProfit1",
        "tp1",
        "take_profit",
        "target_1",
      ]),
    ),
    takeProfit2:
      formatOptionalPrice(
        firstDefined(value, [
          "take_profit_2",
          "takeProfit2",
          "tp2",
          "target_2",
        ]),
      ),
    confidence,
    confirmations,
    riskReward:
      formatRiskReward(
        firstDefined(value, [
          "risk_reward_ratio",
          "risk_reward",
          "riskReward",
          "rr",
          "rr_ratio",
        ]),
      ),
    marketStructure:
      toText(
        firstDefined(value, [
          "market_structure",
          "marketStructure",
          "structure",
          "structure_state",
          "market_bias",
        ]),
      ) || null,
    status: explicitlyBlocked
      ? "CLOSED"
      : toStatus(rawStatus),
    createdAt,
    reasons,
  };
}

export function normalizeTradingSignals(
  payload: unknown,
): TradingSignal[] {
  const items =
    Array.isArray(payload)
      ? payload
      : getNestedItems(payload);

  if (
    items.length === 0 &&
    isRecord(payload)
  ) {
    const singleSignal =
      normalizeTradingSignal(payload);

    return singleSignal
      ? [singleSignal]
      : [];
  }

  return items
    .map((item, index) =>
      normalizeTradingSignal(
        item,
        index,
      ),
    )
    .filter(
      (
        signal,
      ): signal is TradingSignal =>
        signal !== null,
    );
}