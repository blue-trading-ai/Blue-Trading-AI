import { apiRequest } from "@/lib/api";

export type MonitoringService = {
  name: string;
  status: string;
  responseTimeMs: number | null;
  lastCheckedAt: string | null;
  message: string | null;
};

export type MonitoringAlert = {
  id: string;
  severity:
    | "CRITICAL"
    | "WARNING"
    | "INFO";
  title: string;
  message: string;
  service: string | null;
  createdAt: string | null;
};

export type MonitoringData = {
  systemHealth: string;
  averageResponseTimeMs: number;
  activeAlerts: number;
  uptimePercent: number;
  errorRatePercent: number;
  slowRequests: number;
  requestsProcessed: number;
  services: MonitoringService[];
  alerts: MonitoringAlert[];
};

type UnknownRecord =
  Record<string, unknown>;

const MONITORING_ENDPOINT =
  process.env
    .NEXT_PUBLIC_MONITORING_ENDPOINT
    ?.trim() ||
  "/monitoring/summary";

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
): number {
  if (
    typeof value === "number" &&
    Number.isFinite(value)
  ) {
    return value;
  }

  if (typeof value === "string") {
    const parsed =
      Number.parseFloat(
        value
          .replace("%", "")
          .trim(),
      );

    return Number.isFinite(parsed)
      ? parsed
      : 0;
  }

  return 0;
}

function toNullableNumber(
  value: unknown,
): number | null {
  if (
    value === undefined ||
    value === null ||
    value === ""
  ) {
    return null;
  }

  const numberValue =
    toNumber(value);

  return Number.isFinite(numberValue)
    ? numberValue
    : null;
}

function normalizeEndpoint(
  endpoint: string,
): string {
  const normalized =
    endpoint.trim();

  if (!normalized) {
    return "/monitoring/summary";
  }

  return normalized.startsWith("/")
    ? normalized
    : `/${normalized}`;
}

function normalizePeriod(
  period: string,
): string {
  const mapping:
    Record<string, string> = {
      "Last 15 Minutes": "15m",
      "Last Hour": "1h",
      "Last 24 Hours": "24h",
      "Last 7 Days": "7d",
    };

  const normalized =
    period.trim();

  return (
    mapping[normalized] ||
    normalized ||
    "1h"
  );
}

function normalizeServiceStatus(
  serviceStatus: string,
): string | null {
  const normalized =
    serviceStatus
      .trim()
      .toLowerCase();

  if (
    !normalized ||
    normalized ===
      "all services" ||
    normalized === "all"
  ) {
    return null;
  }

  if (
    normalized === "healthy" ||
    normalized === "online" ||
    normalized === "active"
  ) {
    return "healthy";
  }

  if (
    normalized === "warning" ||
    normalized === "degraded"
  ) {
    return "warning";
  }

  if (
    normalized === "critical" ||
    normalized === "error" ||
    normalized === "offline" ||
    normalized === "down"
  ) {
    return "critical";
  }

  return normalized.replace(
    /\s+/g,
    "_",
  );
}

function getItems(
  source: UnknownRecord,
  keys: readonly string[],
): unknown[] {
  const value =
    firstDefined(
      source,
      keys,
    );

  return Array.isArray(value)
    ? value
    : [];
}

function normalizeService(
  value: unknown,
): MonitoringService | null {
  if (!isRecord(value)) {
    return null;
  }

  const name = toText(
    firstDefined(value, [
      "name",
      "service",
      "component",
      "service_name",
    ]),
  );

  if (!name) {
    return null;
  }

  const responseTimeMs =
    toNullableNumber(
      firstDefined(value, [
        "response_time_ms",
        "responseTimeMs",
        "latency_ms",
        "latency",
        "duration_ms",
      ]),
    );

  return {
    name,
    status: toText(
      firstDefined(value, [
        "status",
        "state",
        "health",
      ]),
      "UNKNOWN",
    ).toUpperCase(),
    responseTimeMs:
      responseTimeMs === null
        ? null
        : Math.max(
            responseTimeMs,
            0,
          ),
    lastCheckedAt:
      toText(
        firstDefined(value, [
          "last_checked_at",
          "lastCheckedAt",
          "checked_at",
          "timestamp",
          "updated_at",
        ]),
      ) || null,
    message:
      toText(
        firstDefined(value, [
          "message",
          "detail",
          "description",
          "reason",
        ]),
      ) || null,
  };
}

function normalizeSeverity(
  value: unknown,
): MonitoringAlert["severity"] {
  const normalized =
    toText(value)
      .toUpperCase();

  if (
    normalized.includes(
      "CRITICAL",
    ) ||
    normalized.includes(
      "ERROR",
    ) ||
    normalized.includes(
      "HIGH",
    ) ||
    normalized.includes(
      "DOWN",
    )
  ) {
    return "CRITICAL";
  }

  if (
    normalized.includes(
      "WARNING",
    ) ||
    normalized.includes(
      "WARN",
    ) ||
    normalized.includes(
      "MEDIUM",
    ) ||
    normalized.includes(
      "DEGRADED",
    )
  ) {
    return "WARNING";
  }

  return "INFO";
}

function normalizeAlert(
  value: unknown,
  index: number,
): MonitoringAlert | null {
  if (!isRecord(value)) {
    return null;
  }

  const title = toText(
    firstDefined(value, [
      "title",
      "name",
      "alert",
      "event",
    ]),
  );

  const message = toText(
    firstDefined(value, [
      "message",
      "detail",
      "description",
      "reason",
    ]),
  );

  if (!title && !message) {
    return null;
  }

  return {
    id:
      toText(
        firstDefined(value, [
          "id",
          "alert_id",
          "uuid",
        ]),
      ) ||
      `monitoring-alert-${index}`,
    severity:
      normalizeSeverity(
        firstDefined(value, [
          "severity",
          "level",
          "priority",
          "status",
        ]),
      ),
    title:
      title ||
      "System Alert",
    message:
      message ||
      "No additional details available.",
    service:
      toText(
        firstDefined(value, [
          "service",
          "component",
          "source",
          "service_name",
        ]),
      ) || null,
    createdAt:
      toText(
        firstDefined(value, [
          "created_at",
          "createdAt",
          "timestamp",
          "occurred_at",
          "updated_at",
        ]),
      ) || null,
  };
}

function getNestedData(
  payload: unknown,
): UnknownRecord {
  if (!isRecord(payload)) {
    return {};
  }

  const nested =
    firstDefined(payload, [
      "monitoring",
      "summary",
      "overview",
      "telemetry",
      "data",
      "result",
    ]);

  return isRecord(nested)
    ? nested
    : payload;
}

function clampPercent(
  value: unknown,
): number {
  return Math.min(
    Math.max(
      toNumber(value),
      0,
    ),
    100,
  );
}

export async function getMonitoringData(
  period: string,
  serviceStatus: string,
  signal?: AbortSignal,
): Promise<MonitoringData> {
  const query =
    new URLSearchParams();

  query.set(
    "period",
    normalizePeriod(period),
  );

  const normalizedStatus =
    normalizeServiceStatus(
      serviceStatus,
    );

  if (normalizedStatus) {
    query.set(
      "status",
      normalizedStatus,
    );
  }

  const endpoint =
    `${normalizeEndpoint(
      MONITORING_ENDPOINT,
    )}?${query.toString()}`;

  const payload =
    await apiRequest<unknown>(
      endpoint,
      {
        method: "GET",
        signal,
      },
    );

  const data =
    getNestedData(payload);

  const services = getItems(
    data,
    [
      "services",
      "components",
      "service_health",
      "health_checks",
    ],
  )
    .map(normalizeService)
    .filter(
      (
        service,
      ): service is MonitoringService =>
        service !== null,
    );

  const alerts = getItems(
    data,
    [
      "alerts",
      "events",
      "incidents",
      "warnings",
    ],
  )
    .map(normalizeAlert)
    .filter(
      (
        alert,
      ): alert is MonitoringAlert =>
        alert !== null,
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

        const safeFirstTime =
          Number.isFinite(
            firstTime,
          )
            ? firstTime
            : 0;

        const safeSecondTime =
          Number.isFinite(
            secondTime,
          )
            ? secondTime
            : 0;

        return (
          safeSecondTime -
          safeFirstTime
        );
      },
    );

  const activeAlertsValue =
    firstDefined(data, [
      "active_alerts",
      "activeAlerts",
      "alert_count",
      "active_alert_count",
    ]);

  const calculatedAlerts =
    alerts.filter(
      (alert) =>
        alert.severity !==
        "INFO",
    ).length;

  const activeAlerts =
    activeAlertsValue ===
    undefined
      ? calculatedAlerts
      : Math.max(
          Math.trunc(
            toNumber(
              activeAlertsValue,
            ),
          ),
          calculatedAlerts,
          0,
        );

  return {
    systemHealth: toText(
      firstDefined(data, [
        "system_health",
        "systemHealth",
        "health",
        "status",
        "overall_status",
      ]),
      "UNKNOWN",
    ).toUpperCase(),
    averageResponseTimeMs:
      Math.max(
        toNumber(
          firstDefined(data, [
            "average_response_time_ms",
            "averageResponseTimeMs",
            "avg_latency_ms",
            "average_latency",
            "response_time_ms",
          ]),
        ),
        0,
      ),
    activeAlerts,
    uptimePercent:
      clampPercent(
        firstDefined(data, [
          "uptime_percent",
          "uptimePercent",
          "uptime",
          "availability",
        ]),
      ),
    errorRatePercent:
      clampPercent(
        firstDefined(data, [
          "error_rate_percent",
          "errorRatePercent",
          "error_rate",
        ]),
      ),
    slowRequests: Math.max(
      Math.trunc(
        toNumber(
          firstDefined(data, [
            "slow_requests",
            "slowRequests",
            "slow_request_count",
          ]),
        ),
      ),
      0,
    ),
    requestsProcessed:
      Math.max(
        Math.trunc(
          toNumber(
            firstDefined(data, [
              "requests_processed",
              "requestsProcessed",
              "request_count",
              "total_requests",
            ]),
          ),
        ),
        0,
      ),
    services,
    alerts,
  };
}