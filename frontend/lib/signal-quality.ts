import {
  ApiError,
  apiRequest,
} from "@/lib/api";

export type SignalQualityStatus = {
  status: string;
  published_today: number;
  preferred_daily_target: number;
  daily_signal_limit: number;
  remaining_signal_slots: number;
  quality_over_quantity: boolean;
  broker_execution_enabled: boolean;
};

export type SignalQualityConfiguration = {
  status: string;
  quality_api_version: number;
  quality_over_quantity: boolean;
  preferred_daily_target: number;
  daily_signal_limit: number;
  duplicate_cooldown_hours: number;
  minimum_confidence: number | string;
  minimum_confirmations: number;
  minimum_risk_reward: number | string;
  broker_execution_enabled: boolean;
  endpoints: string[];
};

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
    const text = String(value).trim();

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
    const parsed = Number.parseFloat(
      value.replace("%", "").trim(),
    );

    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }

  return fallback;
}

function toNonNegativeInteger(
  value: unknown,
  fallback = 0,
): number {
  return Math.max(
    Math.trunc(
      toNumber(value, fallback),
    ),
    0,
  );
}

function toBoolean(
  value: unknown,
  fallback = false,
): boolean {
  if (typeof value === "boolean") {
    return value;
  }

  if (typeof value === "number") {
    return value !== 0;
  }

  const normalized =
    toText(value).toLowerCase();

  if (
    [
      "true",
      "1",
      "yes",
      "enabled",
      "active",
      "on",
    ].includes(normalized)
  ) {
    return true;
  }

  if (
    [
      "false",
      "0",
      "no",
      "disabled",
      "inactive",
      "off",
    ].includes(normalized)
  ) {
    return false;
  }

  return fallback;
}

function getNestedData(
  payload: unknown,
): UnknownRecord {
  if (!isRecord(payload)) {
    return {};
  }

  const nested = firstDefined(
    payload,
    [
      "data",
      "result",
      "quality",
      "configuration",
      "status_data",
    ],
  );

  return isRecord(nested)
    ? nested
    : payload;
}

function normalizeThreshold(
  value: unknown,
  fallback: number,
): number | string {
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
    const trimmed = value.trim();
    const parsed = Number.parseFloat(
      trimmed.replace("%", ""),
    );

    return Number.isFinite(parsed)
      ? parsed
      : trimmed;
  }

  return fallback;
}

function normalizeEndpoints(
  value: unknown,
): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return Array.from(
    new Set(
      value
        .map((item) =>
          toText(item),
        )
        .filter(Boolean),
    ),
  );
}

function normalizeStatusPayload(
  payload: unknown,
): SignalQualityStatus {
  const data = getNestedData(payload);

  const dailySignalLimit =
    toNonNegativeInteger(
      firstDefined(data, [
        "daily_signal_limit",
        "dailySignalLimit",
        "signal_limit",
        "max_signals_per_day",
      ]),
    );

  const publishedToday =
    Math.min(
      toNonNegativeInteger(
        firstDefined(data, [
          "published_today",
          "publishedToday",
          "signals_today",
          "daily_signal_count",
        ]),
      ),
      dailySignalLimit || Number.MAX_SAFE_INTEGER,
    );

  const reportedRemaining =
    firstDefined(data, [
      "remaining_signal_slots",
      "remainingSignalSlots",
      "remaining_slots",
    ]);

  const calculatedRemaining =
    Math.max(
      dailySignalLimit -
        publishedToday,
      0,
    );

  const remainingSignalSlots =
    reportedRemaining === undefined
      ? calculatedRemaining
      : Math.min(
          toNonNegativeInteger(
            reportedRemaining,
          ),
          dailySignalLimit,
        );

  return {
    status: toText(
      firstDefined(data, [
        "status",
        "state",
      ]),
      "UNKNOWN",
    ).toUpperCase(),
    published_today:
      publishedToday,
    preferred_daily_target:
      toNonNegativeInteger(
        firstDefined(data, [
          "preferred_daily_target",
          "preferredDailyTarget",
          "daily_target",
        ]),
      ),
    daily_signal_limit:
      dailySignalLimit,
    remaining_signal_slots:
      remainingSignalSlots,
    quality_over_quantity:
      toBoolean(
        firstDefined(data, [
          "quality_over_quantity",
          "qualityOverQuantity",
        ]),
        true,
      ),
    broker_execution_enabled:
      toBoolean(
        firstDefined(data, [
          "broker_execution_enabled",
          "brokerExecutionEnabled",
          "execution_enabled",
        ]),
        false,
      ),
  };
}

function normalizeConfigurationPayload(
  payload: unknown,
): SignalQualityConfiguration {
  const data = getNestedData(payload);

  return {
    status: toText(
      firstDefined(data, [
        "status",
        "state",
      ]),
      "UNKNOWN",
    ).toUpperCase(),
    quality_api_version:
      toNonNegativeInteger(
        firstDefined(data, [
          "quality_api_version",
          "qualityApiVersion",
          "version",
        ]),
      ),
    quality_over_quantity:
      toBoolean(
        firstDefined(data, [
          "quality_over_quantity",
          "qualityOverQuantity",
        ]),
        true,
      ),
    preferred_daily_target:
      toNonNegativeInteger(
        firstDefined(data, [
          "preferred_daily_target",
          "preferredDailyTarget",
          "daily_target",
        ]),
      ),
    daily_signal_limit:
      toNonNegativeInteger(
        firstDefined(data, [
          "daily_signal_limit",
          "dailySignalLimit",
          "signal_limit",
          "max_signals_per_day",
        ]),
      ),
    duplicate_cooldown_hours:
      toNonNegativeInteger(
        firstDefined(data, [
          "duplicate_cooldown_hours",
          "duplicateCooldownHours",
          "cooldown_hours",
        ]),
      ),
    minimum_confidence:
      normalizeThreshold(
        firstDefined(data, [
          "minimum_confidence",
          "minimumConfidence",
          "confidence_threshold",
        ]),
        80,
      ),
    minimum_confirmations:
      toNonNegativeInteger(
        firstDefined(data, [
          "minimum_confirmations",
          "minimumConfirmations",
          "confirmation_threshold",
        ]),
        3,
      ),
    minimum_risk_reward:
      normalizeThreshold(
        firstDefined(data, [
          "minimum_risk_reward",
          "minimumRiskReward",
          "risk_reward_threshold",
        ]),
        0,
      ),
    broker_execution_enabled:
      toBoolean(
        firstDefined(data, [
          "broker_execution_enabled",
          "brokerExecutionEnabled",
          "execution_enabled",
        ]),
        false,
      ),
    endpoints: normalizeEndpoints(
      firstDefined(data, [
        "endpoints",
        "routes",
        "available_endpoints",
      ]),
    ),
  };
}

export async function getSignalQualityStatus(): Promise<SignalQualityStatus> {
  const payload =
    await apiRequest<unknown>(
      "/signals/quality/status",
      {
        method: "GET",
      },
    );

  return normalizeStatusPayload(
    payload,
  );
}

export async function getSignalQualityConfiguration(): Promise<SignalQualityConfiguration> {
  const payload =
    await apiRequest<unknown>(
      "/signals/quality/",
      {
        method: "GET",
      },
    );

  return normalizeConfigurationPayload(
    payload,
  );
}

export function assertSignalQualityConfiguration(
  configuration: SignalQualityConfiguration,
): void {
  const minimumConfidence =
    toNumber(
      configuration.minimum_confidence,
      0,
    );

  const minimumRiskReward =
    toNumber(
      configuration.minimum_risk_reward,
      0,
    );

  if (
    minimumConfidence < 0 ||
    minimumConfidence > 100
  ) {
    throw new ApiError(
      "The backend returned an invalid confidence threshold.",
      502,
      configuration,
    );
  }

  if (
    configuration.minimum_confirmations < 0
  ) {
    throw new ApiError(
      "The backend returned an invalid confirmation threshold.",
      502,
      configuration,
    );
  }

  if (minimumRiskReward < 0) {
    throw new ApiError(
      "The backend returned an invalid risk-reward threshold.",
      502,
      configuration,
    );
  }
}