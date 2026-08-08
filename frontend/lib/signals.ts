import { apiRequest } from "@/lib/api";

export type BackendTradingSignal = {
  id?: number | string;
  signal_uid?: string;
  symbol?: string;
  timeframe?: string;
  direction?: string;
  confidence?: number | string;
  confidence_score?: number | string;
  final_confidence?: number | string;
  entry_price?: number | string | null;
  entry?: number | string | null;
  stop_loss?: number | string | null;
  take_profit_1?: number | string | null;
  take_profit_2?: number | string | null;
  risk_reward?: number | string | null;
  risk_reward_ratio?: number | string | null;
  confirmations?: unknown;
  confirmations_count?: number | string;
  total_confirmations?: number | string;
  status?: string;
  result?: string;
  created_at?: string;
  published_at?: string;
  generated_at?: string;
  is_trade_allowed?: boolean;
  trade_allowed?: boolean;
  approved?: boolean;
  is_approved?: boolean;
};

export type LatestApprovedSignal = {
  id: string;
  symbol: string;
  timeframe: string;
  direction: "BUY" | "SELL";
  confidence: number;
  entry: string;
  stopLoss: string;
  takeProfit1: string;
  takeProfit2: string;
  confirmations: string[];
  confirmationsCount: number;
  riskReward: string;
  status: string;
  createdAt: string | null;
};

type SignalListContainer = {
  signals?: BackendTradingSignal[];
  items?: BackendTradingSignal[];
  results?: BackendTradingSignal[];
  records?: BackendTradingSignal[];
  data?:
    | BackendTradingSignal[]
    | SignalListContainer;
};

type SignalListResponse =
  | BackendTradingSignal[]
  | SignalListContainer;

const MINIMUM_CONFIDENCE = 80;
const MINIMUM_CONFIRMATIONS = 3;

function isRecord(
  value: unknown,
): value is Record<string, unknown> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value)
  );
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
    const parsed = Number.parseFloat(
      value
        .replace("%", "")
        .replace(/^1:/, "")
        .trim(),
    );

    return Number.isFinite(parsed)
      ? parsed
      : null;
  }

  return null;
}

function formatPrice(
  value: unknown,
): string | null {
  const numericValue =
    toFiniteNumber(value);

  if (
    numericValue === null ||
    numericValue <= 0
  ) {
    return null;
  }

  return numericValue.toFixed(2);
}

function formatRiskReward(
  value: unknown,
): string {
  const numericValue =
    toFiniteNumber(value);

  if (
    numericValue === null ||
    numericValue <= 0
  ) {
    return "—";
  }

  return `1:${numericValue.toFixed(2)}`;
}

function normalizeDirection(
  direction: unknown,
): "BUY" | "SELL" | null {
  const resolved = String(
    direction || "",
  )
    .trim()
    .toUpperCase();

  if (
    resolved === "BUY" ||
    resolved === "LONG" ||
    resolved === "BULLISH"
  ) {
    return "BUY";
  }

  if (
    resolved === "SELL" ||
    resolved === "SHORT" ||
    resolved === "BEARISH"
  ) {
    return "SELL";
  }

  return null;
}

function normalizeConfirmations(
  value: unknown,
): string[] {
  let confirmations: string[] = [];

  if (Array.isArray(value)) {
    confirmations = value
      .map((item) => {
        if (typeof item === "string") {
          return item.trim();
        }

        if (isRecord(item)) {
          return String(
            item.label ??
              item.name ??
              item.type ??
              item.confirmation ??
              item.reason ??
              "",
          ).trim();
        }

        return "";
      })
      .filter(Boolean);
  } else if (isRecord(value)) {
    confirmations = Object.entries(value)
      .filter(([, confirmed]) =>
        Boolean(confirmed),
      )
      .map(([name]) => name.trim())
      .filter(Boolean);
  } else if (
    typeof value === "string" &&
    value.trim()
  ) {
    confirmations = value
      .split(/[,|;]/)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  return Array.from(
    new Set(confirmations),
  );
}

function extractSignals(
  response: SignalListResponse,
): BackendTradingSignal[] {
  if (Array.isArray(response)) {
    return response;
  }

  const direct =
    response.signals ??
    response.items ??
    response.results ??
    response.records;

  if (Array.isArray(direct)) {
    return direct;
  }

  if (Array.isArray(response.data)) {
    return response.data;
  }

  if (
    response.data &&
    isRecord(response.data)
  ) {
    return extractSignals(
      response.data as SignalListContainer,
    );
  }

  return [];
}

function getCreatedAt(
  signal: BackendTradingSignal,
): string | null {
  const value =
    signal.published_at ??
    signal.created_at ??
    signal.generated_at;

  if (
    typeof value !== "string" ||
    !value.trim()
  ) {
    return null;
  }

  return value.trim();
}

function getTimestamp(
  signal: BackendTradingSignal,
): number {
  const createdAt =
    getCreatedAt(signal);

  if (!createdAt) {
    return 0;
  }

  const parsed =
    Date.parse(createdAt);

  return Number.isFinite(parsed)
    ? parsed
    : 0;
}

function getConfidence(
  signal: BackendTradingSignal,
): number {
  const numericValue =
    toFiniteNumber(
      signal.final_confidence ??
        signal.confidence_score ??
        signal.confidence,
    );

  if (numericValue === null) {
    return 0;
  }

  return Math.min(
    Math.max(
      Math.round(numericValue),
      0,
    ),
    100,
  );
}

function getConfirmationCount(
  signal: BackendTradingSignal,
  confirmations: string[],
): number {
  const numericValue =
    toFiniteNumber(
      signal.confirmations_count ??
        signal.total_confirmations,
    );

  if (numericValue === null) {
    return confirmations.length;
  }

  return Math.max(
    Math.trunc(numericValue),
    confirmations.length,
    0,
  );
}

function hasExplicitBlock(
  signal: BackendTradingSignal,
): boolean {
  const status = String(
    signal.status || "",
  )
    .trim()
    .toUpperCase();

  const result = String(
    signal.result || "",
  )
    .trim()
    .toUpperCase();

  const blockedStatuses = new Set([
    "CANCELLED",
    "CANCELED",
    "EXPIRED",
    "REJECTED",
    "BLOCKED",
    "NO_TRADE",
    "NO TRADE",
    "FAILED",
    "HOLD",
    "SKIP",
  ]);

  return (
    blockedStatuses.has(status) ||
    blockedStatuses.has(result) ||
    signal.is_trade_allowed === false ||
    signal.trade_allowed === false ||
    signal.approved === false ||
    signal.is_approved === false
  );
}

function hasApprovalEvidence(
  signal: BackendTradingSignal,
): boolean {
  const status = String(
    signal.status || "",
  )
    .trim()
    .toUpperCase();

  return (
    signal.is_trade_allowed === true ||
    signal.trade_allowed === true ||
    signal.approved === true ||
    signal.is_approved === true ||
    [
      "APPROVED",
      "PUBLISHED",
      "ACTIVE",
      "VALID",
      "READY",
    ].includes(status)
  );
}

function normalizeSignal(
  signal: BackendTradingSignal,
): LatestApprovedSignal | null {
  if (hasExplicitBlock(signal)) {
    return null;
  }

  const direction =
    normalizeDirection(
      signal.direction,
    );

  if (!direction) {
    return null;
  }

  const confidence =
    getConfidence(signal);

  const confirmations =
    normalizeConfirmations(
      signal.confirmations,
    );

  const confirmationsCount =
    getConfirmationCount(
      signal,
      confirmations,
    );

  if (
    confidence <
      MINIMUM_CONFIDENCE ||
    confirmationsCount <
      MINIMUM_CONFIRMATIONS ||
    confirmations.length <
      MINIMUM_CONFIRMATIONS
  ) {
    return null;
  }

  const entry = formatPrice(
    signal.entry_price ??
      signal.entry,
  );

  const stopLoss =
    formatPrice(
      signal.stop_loss,
    );

  const takeProfit1 =
    formatPrice(
      signal.take_profit_1,
    );

  const takeProfit2 =
    formatPrice(
      signal.take_profit_2,
    );

  if (
    !entry ||
    !stopLoss ||
    !takeProfit1 ||
    !takeProfit2
  ) {
    return null;
  }

  const entryValue = Number(entry);
  const stopLossValue =
    Number(stopLoss);
  const takeProfit1Value =
    Number(takeProfit1);
  const takeProfit2Value =
    Number(takeProfit2);

  const levelsAreValid =
    direction === "BUY"
      ? stopLossValue <
          entryValue &&
        takeProfit1Value >
          entryValue &&
        takeProfit2Value >
          takeProfit1Value
      : stopLossValue >
          entryValue &&
        takeProfit1Value <
          entryValue &&
        takeProfit2Value <
          takeProfit1Value;

  if (!levelsAreValid) {
    return null;
  }

  const symbol = String(
    signal.symbol || "",
  )
    .trim()
    .toUpperCase();

  const timeframe = String(
    signal.timeframe || "",
  )
    .trim()
    .toUpperCase();

  if (!symbol || !timeframe) {
    return null;
  }

  const approvalStatus =
    hasApprovalEvidence(signal)
      ? String(
          signal.status ||
            "APPROVED",
        )
          .trim()
          .toUpperCase()
      : "QUALITY_APPROVED";

  return {
    id: String(
      signal.signal_uid ??
        signal.id ??
        `${symbol}-${timeframe}-${getTimestamp(
          signal,
        )}`,
    ),
    symbol,
    timeframe,
    direction,
    confidence,
    entry,
    stopLoss,
    takeProfit1,
    takeProfit2,
    confirmations,
    confirmationsCount,
    riskReward:
      formatRiskReward(
        signal.risk_reward_ratio ??
          signal.risk_reward,
      ),
    status:
      approvalStatus,
    createdAt:
      getCreatedAt(signal),
  };
}

export async function getLatestApprovedSignal(): Promise<LatestApprovedSignal | null> {
  const response =
    await apiRequest<SignalListResponse>(
      "/signals/list?limit=10",
      {
        method: "GET",
      },
    );

  const approvedSignals =
    extractSignals(response)
      .map(normalizeSignal)
      .filter(
        (
          signal,
        ): signal is LatestApprovedSignal =>
          signal !== null,
      )
      .sort(
        (first, second) => {
          const firstTime =
            first.createdAt
              ? Date.parse(
                  first.createdAt,
                )
              : 0;

          const secondTime =
            second.createdAt
              ? Date.parse(
                  second.createdAt,
                )
              : 0;

          const safeFirst =
            Number.isFinite(
              firstTime,
            )
              ? firstTime
              : 0;

          const safeSecond =
            Number.isFinite(
              secondTime,
            )
              ? secondTime
              : 0;

          return (
            safeSecond -
            safeFirst
          );
        },
      );

  return approvedSignals[0] ?? null;
}