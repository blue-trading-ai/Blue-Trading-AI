import {
  API_BASE_URL,
  ApiError,
  getAccessToken,
} from "@/lib/api";

export type StructurePoint = {
  index: number | null;
  price: number | string | null;
  type: string | null;
};

export type MarketStructureResult = {
  symbol: string;
  timeframe: string;
  bias: string | null;
  structure: string | null;
  bos: string | boolean | null;
  choch: string | boolean | null;
  support: Array<number | string>;
  resistance: Array<number | string>;
  swingHighs: StructurePoint[];
  swingLows: StructurePoint[];
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
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    const text = String(value).trim();

    return text || null;
  }

  return null;
}

function toNumberOrText(
  value: unknown,
): number | string | null {
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
      value,
    );

    return Number.isFinite(parsed)
      ? parsed
      : value.trim();
  }

  return null;
}

function toNumberOrTextArray(
  value: unknown,
): Array<number | string> {
  if (Array.isArray(value)) {
    return value
      .map(toNumberOrText)
      .filter(
        (
          item,
        ): item is number | string =>
          item !== null,
      );
  }

  const single = toNumberOrText(value);

  return single === null ? [] : [single];
}

function toStructurePoints(
  value: unknown,
): StructurePoint[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item): StructurePoint | null => {
      if (!isRecord(item)) {
        const price =
          toNumberOrText(item);

        return price === null
          ? null
          : {
              index: null,
              price,
              type: null,
            };
      }

      const indexValue = firstDefined(
        item,
        [
          "index",
          "candle_index",
          "position",
        ],
      );

      const parsedIndex =
        typeof indexValue === "number"
          ? indexValue
          : typeof indexValue === "string"
            ? Number.parseInt(
                indexValue,
                10,
              )
            : Number.NaN;

      return {
        index: Number.isFinite(
          parsedIndex,
        )
          ? parsedIndex
          : null,
        price: toNumberOrText(
          firstDefined(item, [
            "price",
            "level",
            "value",
          ]),
        ),
        type: toText(
          firstDefined(item, [
            "type",
            "label",
            "structure_type",
          ]),
        ),
      };
    })
    .filter(
      (
        point,
      ): point is StructurePoint =>
        point !== null,
    );
}

function toReasons(
  value: unknown,
): string[] {
  if (Array.isArray(value)) {
    return value
      .map(toText)
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
    const message = toText(
      firstDefined(payload, [
        "detail",
        "message",
        "error",
      ]),
    );

    if (message) {
      return message;
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

function getNestedStructureSource(
  payload: UnknownRecord,
): UnknownRecord {
  const nested = firstDefined(
    payload,
    [
      "market_structure",
      "structure",
      "structure_analysis",
      "analysis",
    ],
  );

  return isRecord(nested)
    ? nested
    : payload;
}

export async function getMarketStructure(
  symbol: string,
  timeframe: string,
  signal?: AbortSignal,
): Promise<MarketStructureResult> {
  const accessToken = getAccessToken();

  if (!accessToken) {
    throw new ApiError(
      "Authentication is required to load market structure.",
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
    `${encodeURIComponent(
      normalizedSymbol,
    )}` +
    `?interval=${encodeURIComponent(
      normalizedTimeframe,
    )}`;

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
        `Market structure request failed with status ${response.status}`,
      ),
      response.status,
      payload,
    );
  }

  const root = isRecord(payload)
    ? payload
    : {};

  const source =
    getNestedStructureSource(root);

  return {
    symbol:
      toText(
        firstDefined(root, [
          "symbol",
          "pair",
          "market",
        ]),
      ) || normalizedSymbol,
    timeframe:
      toText(
        firstDefined(root, [
          "timeframe",
          "interval",
          "tf",
        ]),
      ) || timeframe.toUpperCase(),
    bias: toText(
      firstDefined(source, [
        "bias",
        "trend_bias",
        "direction",
        "trend",
      ]),
    ),
    structure: toText(
      firstDefined(source, [
        "structure",
        "market_structure",
        "structure_state",
        "classification",
      ]),
    ),
    bos: firstDefined(source, [
      "bos",
      "break_of_structure",
      "breakOfStructure",
    ]) as string | boolean | null,
    choch: firstDefined(source, [
      "choch",
      "change_of_character",
      "changeOfCharacter",
    ]) as string | boolean | null,
    support: toNumberOrTextArray(
      firstDefined(source, [
        "support",
        "supports",
        "support_levels",
      ]),
    ),
    resistance: toNumberOrTextArray(
      firstDefined(source, [
        "resistance",
        "resistances",
        "resistance_levels",
      ]),
    ),
    swingHighs: toStructurePoints(
      firstDefined(source, [
        "swing_highs",
        "swingHighs",
        "highs",
      ]),
    ),
    swingLows: toStructurePoints(
      firstDefined(source, [
        "swing_lows",
        "swingLows",
        "lows",
      ]),
    ),
    reasons: toReasons(
      firstDefined(source, [
        "reasons",
        "analysis_reasons",
        "confirmations",
      ]),
    ),
    raw: payload,
  };
}