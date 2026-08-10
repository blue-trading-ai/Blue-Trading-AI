"use client";

import {
  API_BASE_URL,
  ApiError,
  getAccessToken,
} from "@/lib/api";

export type MarketNewsEvent = {
  id: string;
  title: string;
  currency: string;
  impact: "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN";
  eventTime: string | null;
  forecast: string | null;
  previous: string | null;
  actual: string | null;
  affectedMarkets: string[];
  signalAction: string;
  conflict: boolean;
  source: string | null;
  raw: unknown;
};

export type MarketNewsResponse = {
  events: MarketNewsEvent[];
  total: number;
  highImpact: number;
  conflicts: number;
  affectedMarkets: number;
};

type UnknownRecord = Record<string, unknown>;

const NEWS_API_PREFIX = "/economic-news";

const SYMBOL_CURRENCY_FILTERS: Record<string, string[]> = {
  XAUUSD: ["USD"],
  BTCUSD: ["USD"],
  ETHUSD: ["USD"],
  EURUSD: ["EUR", "USD"],
  GBPUSD: ["GBP", "USD"],
  USDJPY: ["USD", "JPY"],
  AUDUSD: ["AUD", "USD"],
  NZDUSD: ["NZD", "USD"],
  USDCAD: ["USD", "CAD"],
  USDCHF: ["USD", "CHF"],
  EURGBP: ["EUR", "GBP"],
  EURJPY: ["EUR", "JPY"],
  GBPJPY: ["GBP", "JPY"],
  AUDJPY: ["AUD", "JPY"],
  CADJPY: ["CAD", "JPY"],
  CHFJPY: ["CHF", "JPY"],
};

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

function toBoolean(
  value: unknown,
): boolean {
  if (typeof value === "boolean") {
    return value;
  }

  if (typeof value === "number") {
    return value !== 0;
  }

  const normalized =
    toText(value)?.toLowerCase() || "";

  return [
    "true",
    "1",
    "yes",
    "blocked",
    "conflict",
    "active",
  ].includes(normalized);
}

function toImpact(
  value: unknown,
): MarketNewsEvent["impact"] {
  const normalized =
    toText(value)?.toUpperCase() || "";

  if (
    normalized.includes("HIGH") ||
    normalized === "3" ||
    normalized === "RED"
  ) {
    return "HIGH";
  }

  if (
    normalized.includes("MEDIUM") ||
    normalized.includes("MODERATE") ||
    normalized === "2" ||
    normalized === "ORANGE"
  ) {
    return "MEDIUM";
  }

  if (
    normalized.includes("LOW") ||
    normalized === "1" ||
    normalized === "YELLOW"
  ) {
    return "LOW";
  }

  return "UNKNOWN";
}

function toStringArray(
  value: unknown,
): string[] {
  if (Array.isArray(value)) {
    return value
      .map(toText)
      .filter(
        (item): item is string =>
          Boolean(item),
      )
      .map((item) =>
        item.toUpperCase(),
      );
  }

  const text = toText(value);

  if (!text) {
    return [];
  }

  return text
    .split(/[,|/]/)
    .map((item) =>
      item.trim().toUpperCase(),
    )
    .filter(Boolean);
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

    if (
      typeof detail === "string" &&
      detail.trim()
    ) {
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
      "events",
      "news",
      "calendar",
      "upcoming",
      "economic_events",
      "items",
      "results",
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
        "events",
        "news",
        "calendar",
        "upcoming",
        "economic_events",
        "items",
        "results",
      ],
    );

    return Array.isArray(nestedItems)
      ? nestedItems
      : [];
  }

  return [];
}

function normalizeEvent(
  value: unknown,
  index: number,
): MarketNewsEvent | null {
  if (!isRecord(value)) {
    return null;
  }

  const title = toText(
    firstDefined(value, [
      "title",
      "event",
      "name",
      "headline",
      "event_name",
      "category",
    ]),
  );

  if (!title) {
    return null;
  }

  const currency =
    toText(
      firstDefined(value, [
        "currency",
        "country",
        "symbol",
        "asset",
        "affected_currency",
      ]),
    )?.toUpperCase() || "N/A";

  const impact = toImpact(
    firstDefined(value, [
      "impact",
      "importance",
      "severity",
      "priority",
      "impact_level",
    ]),
  );

  let affectedMarkets = toStringArray(
    firstDefined(value, [
      "affected_markets",
      "affectedMarkets",
      "markets",
      "symbols",
      "instruments",
      "affected_symbols",
    ]),
  );

  if (
    affectedMarkets.length === 0 &&
    currency !== "N/A"
  ) {
    affectedMarkets = [currency];
  }

  const conflict = toBoolean(
    firstDefined(value, [
      "conflict",
      "signal_conflict",
      "signalConflict",
      "blocked",
      "is_blocking",
      "blackout_active",
      "blocks_signal",
    ]),
  );

  const signalAction =
    toText(
      firstDefined(value, [
        "signal_action",
        "signalAction",
        "action",
        "recommendation",
        "protection_action",
        "decision",
      ]),
    ) ||
    (conflict
      ? "BLOCK SIGNAL"
      : impact === "HIGH"
        ? "REVIEW REQUIRED"
        : "MONITOR");

  const id =
    toText(
      firstDefined(value, [
        "id",
        "event_id",
        "news_id",
        "uuid",
        "uid",
      ]),
    ) ||
    `${currency}-${impact}-${index}`;

  return {
    id,
    title,
    currency,
    impact,
    eventTime: toText(
      firstDefined(value, [
        "scheduled_datetime",
        "event_time",
        "eventTime",
        "datetime",
        "date_time",
        "time",
        "timestamp",
        "scheduled_at",
        "scheduled_time",
        "release_time",
      ]),
    ),
    forecast: toText(
      firstDefined(value, [
        "forecast",
        "expected",
        "consensus",
        "forecast_value",
      ]),
    ),
    previous: toText(
      firstDefined(value, [
        "previous",
        "prior",
        "last",
        "previous_value",
      ]),
    ),
    actual: toText(
      firstDefined(value, [
        "actual",
        "released",
        "result",
        "actual_value",
      ]),
    ),
    affectedMarkets,
    signalAction,
    conflict,
    source: toText(
      firstDefined(value, [
        "source",
        "provider",
        "publisher",
        "data_source",
      ]),
    ),
    raw: value,
  };
}

function getCalendarRequest(
  impact: string,
  market: string,
  period: string,
): {
  endpoint: string;
  query: URLSearchParams;
} {
  const query = new URLSearchParams();

  const normalizedPeriod =
    period.trim().toLowerCase();

  let endpoint = `${NEWS_API_PREFIX}/upcoming`;

  if (
    normalizedPeriod === "this week" ||
    normalizedPeriod === "week" ||
    normalizedPeriod === "weekly"
  ) {
    endpoint = `${NEWS_API_PREFIX}/calendar/weekly`;
  } else if (
    normalizedPeriod === "this month" ||
    normalizedPeriod === "month" ||
    normalizedPeriod === "monthly"
  ) {
    endpoint = `${NEWS_API_PREFIX}/calendar/monthly`;
  } else if (
    normalizedPeriod === "all upcoming" ||
    normalizedPeriod === "all"
  ) {
    query.set("hours", "168");
  } else {
    query.set("hours", "24");
  }

  const isCalendarEndpoint =
    endpoint.includes("/calendar/");

  if (
    isCalendarEndpoint &&
    impact !== "All Impact"
  ) {
    query.set(
      "impacts",
      impact.trim().toUpperCase(),
    );
  }

  if (
    isCalendarEndpoint &&
    market !== "All Markets"
  ) {
    const normalizedMarket =
      market
        .trim()
        .toUpperCase()
        .replace("/", "")
        .replace("-", "")
        .replace("_", "");

    const currencies =
      SYMBOL_CURRENCY_FILTERS[
        normalizedMarket
      ] ||
      (/^[A-Z]{3}$/.test(
        normalizedMarket
      )
        ? [normalizedMarket]
        : []);

    if (currencies.length > 0) {
      query.set(
        "currencies",
        currencies.join(","),
      );
    }
  }

  return {
    endpoint,
    query,
  };
}

export async function getMarketNews(
  impact: string,
  market: string,
  period: string,
  signal?: AbortSignal,
): Promise<MarketNewsResponse> {
  const accessToken = getAccessToken();

  if (!accessToken) {
    throw new ApiError(
      "Authentication is required to load market news.",
      401,
      null,
    );
  }

  const {
    endpoint,
    query,
  } = getCalendarRequest(
    impact,
    market,
    period,
  );

  const queryString =
    query.toString();

  const requestUrl =
    `${API_BASE_URL}${endpoint}` +
    (
      queryString
        ? `?${queryString}`
        : ""
    );

  const response = await fetch(
    requestUrl,
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
    response.headers.get(
      "content-type",
    ) || "";

  const payload: unknown =
    contentType.includes(
      "application/json",
    )
      ? await response.json()
      : await response.text();

  if (!response.ok) {
    throw new ApiError(
      getErrorMessage(
        payload,
        `Market news request failed with status ${response.status}`,
      ),
      response.status,
      payload,
    );
  }

  let events = getItems(payload)
    .map(normalizeEvent)
    .filter(
      (
        event,
      ): event is MarketNewsEvent =>
        event !== null,
    );

  /*
   * /upcoming currently accepts only the hours window.
   * Keep impact/market filtering client-side for those views.
   * Weekly/monthly filtering is handled by the backend.
   */
  if (
    !endpoint.includes("/calendar/")
  ) {
    if (impact !== "All Impact") {
      const normalizedImpact =
        impact.trim().toUpperCase();

      events = events.filter(
        (event) =>
          event.impact ===
          normalizedImpact,
      );
    }

    if (market !== "All Markets") {
      const normalizedMarket =
        market
          .trim()
          .toUpperCase()
          .replace("/", "")
          .replace("-", "")
          .replace("_", "");

      const currencies =
        SYMBOL_CURRENCY_FILTERS[
          normalizedMarket
        ] ||
        (/^[A-Z]{3}$/.test(
          normalizedMarket
        )
          ? [normalizedMarket]
          : []);

      if (currencies.length > 0) {
        events = events.filter(
          (event) =>
            currencies.includes(
              event.currency,
            ),
        );
      }
    }
  }

  events.sort(
    (
      first,
      second,
    ) => {
      const firstTime =
        first.eventTime
          ? Date.parse(
              first.eventTime,
            )
          : Number.MAX_SAFE_INTEGER;

      const secondTime =
        second.eventTime
          ? Date.parse(
              second.eventTime,
            )
          : Number.MAX_SAFE_INTEGER;

      return firstTime - secondTime;
    },
  );

  const uniqueMarkets = new Set(
    events.flatMap(
      (event) =>
        event.affectedMarkets,
    ),
  );

  return {
    events,
    total: events.length,
    highImpact: events.filter(
      (event) =>
        event.impact === "HIGH",
    ).length,
    conflicts: events.filter(
      (event) =>
        event.conflict,
    ).length,
    affectedMarkets:
      uniqueMarkets.size,
  };
}