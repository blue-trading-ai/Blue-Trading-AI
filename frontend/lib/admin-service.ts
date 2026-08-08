import {
  ApiError,
  apiRequest,
} from "@/lib/api";

export type AdminUser = {
  id: string;
  fullName: string;
  email: string;
  emailVerified: boolean;
  status: string;
  role: string;
  createdAt: string | null;
};

export type AdminServiceStatus = {
  name: string;
  status: string;
  message: string | null;
};

export type AdminDashboardData = {
  users: AdminUser[];
  pendingUsers: number;
  approvedUsers: number;
  signalsToday: number;
  systemHealth: string;
  systemMode: string;
  services: AdminServiceStatus[];
};

type UnknownRecord = Record<string, unknown>;

const ADMIN_DASHBOARD_ENDPOINT =
  process.env
    .NEXT_PUBLIC_ADMIN_DASHBOARD_ENDPOINT
    ?.trim() ||
  "/admin/dashboard/";

const ADMIN_USERS_ENDPOINT =
  process.env
    .NEXT_PUBLIC_ADMIN_USERS_ENDPOINT
    ?.trim() ||
  "/admin/users";

const ADMIN_SYSTEM_MODE_ENDPOINT =
  process.env
    .NEXT_PUBLIC_ADMIN_SYSTEM_MODE_ENDPOINT
    ?.trim() || "";

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
): number {
  if (
    typeof value === "number" &&
    Number.isFinite(value)
  ) {
    return value;
  }

  if (typeof value === "string") {
    const parsed =
      Number.parseFloat(value);

    return Number.isFinite(parsed)
      ? parsed
      : 0;
  }

  return 0;
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

  return [
    "true",
    "1",
    "yes",
    "verified",
    "active",
    "approved",
  ].includes(
    toText(value).toLowerCase(),
  );
}

function normalizeEndpoint(
  value: string,
): string {
  const trimmed = value.trim();

  if (!trimmed) {
    return "";
  }

  return trimmed.startsWith("/")
    ? trimmed
    : `/${trimmed}`;
}

function normalizeApprovalStatus(
  approvalStatus: string,
): string | null {
  const normalized = approvalStatus
    .trim()
    .toLowerCase();

  if (
    normalized === "all users" ||
    normalized === "all"
  ) {
    return null;
  }

  if (
    normalized === "pending approval" ||
    normalized === "pending"
  ) {
    return "pending";
  }

  if (
    normalized === "approved" ||
    normalized === "active"
  ) {
    return "approved";
  }

  if (normalized === "rejected") {
    return "rejected";
  }

  return normalized
    .replace(/\s+/g, "_");
}

function normalizeUser(
  value: unknown,
  index: number,
): AdminUser | null {
  if (!isRecord(value)) {
    return null;
  }

  const email = toText(
    firstDefined(value, [
      "email",
      "user_email",
      "username",
    ]),
  );

  if (!email) {
    return null;
  }

  const firstName = toText(
    firstDefined(value, [
      "first_name",
      "firstName",
    ]),
  );

  const lastName = toText(
    firstDefined(value, [
      "last_name",
      "lastName",
    ]),
  );

  const combinedName = [
    firstName,
    lastName,
  ]
    .filter(Boolean)
    .join(" ")
    .trim();

  return {
    id:
      toText(
        firstDefined(value, [
          "id",
          "user_id",
          "uuid",
        ]),
      ) || `admin-user-${index}`,
    fullName:
      toText(
        firstDefined(value, [
          "full_name",
          "fullName",
          "name",
          "display_name",
          "username",
        ]),
      ) ||
      combinedName ||
      email.split("@")[0] ||
      "Unnamed User",
    email,
    emailVerified: toBoolean(
      firstDefined(value, [
        "is_email_verified",
        "email_verified",
        "emailVerified",
        "is_verified",
        "verified",
      ]),
    ),
    status:
      toText(
        firstDefined(value, [
          "account_status",
          "approval_status",
          "status",
        ]),
        "PENDING",
      ).toUpperCase(),
    role:
      toText(
        firstDefined(value, [
          "role",
          "primary_role",
          "user_role",
          "account_role",
        ]),
        "USER",
      ).toUpperCase(),
    createdAt:
      toText(
        firstDefined(value, [
          "created_at",
          "createdAt",
          "registered_at",
          "registration_date",
        ]),
      ) || null,
  };
}

function normalizeService(
  value: unknown,
): AdminServiceStatus | null {
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

function getArray(
  source: UnknownRecord,
  keys: readonly string[],
): unknown[] {
  const value =
    firstDefined(source, keys);

  return Array.isArray(value)
    ? value
    : [];
}

function getNestedData(
  payload: unknown,
): UnknownRecord {
  if (!isRecord(payload)) {
    return {};
  }

  const nested =
    firstDefined(payload, [
      "dashboard",
      "admin",
      "data",
      "result",
    ]);

  return isRecord(nested)
    ? nested
    : payload;
}

function countUsersByStatus(
  users: readonly AdminUser[],
  expectedStatus: string,
): number {
  return users.filter((user) =>
    user.status
      .toUpperCase()
      .includes(expectedStatus),
  ).length;
}

export async function getAdminDashboard(
  approvalStatus: string,
  signal?: AbortSignal,
): Promise<AdminDashboardData> {
  const query =
    new URLSearchParams();

  const normalizedStatus =
    normalizeApprovalStatus(
      approvalStatus,
    );

  if (normalizedStatus) {
    query.set(
      "status",
      normalizedStatus,
    );
  }

  const endpoint =
    `${normalizeEndpoint(
      ADMIN_DASHBOARD_ENDPOINT,
    )}${
      query.size > 0
        ? `?${query.toString()}`
        : ""
    }`;

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

  const users = getArray(data, [
    "users",
    "accounts",
    "user_list",
    "items",
  ])
    .map(normalizeUser)
    .filter(
      (user): user is AdminUser =>
        user !== null,
    );

  const services = getArray(data, [
    "services",
    "service_statuses",
    "health_checks",
    "components",
  ])
    .map(normalizeService)
    .filter(
      (
        service,
      ): service is AdminServiceStatus =>
        service !== null,
    );

  const pendingValue =
    firstDefined(data, [
      "pending_users",
      "pendingUsers",
      "pending_count",
      "pending_approval_count",
    ]);

  const approvedValue =
    firstDefined(data, [
      "approved_users",
      "approvedUsers",
      "approved_count",
      "active_users",
    ]);

  return {
    users,
    pendingUsers:
      pendingValue === undefined
        ? countUsersByStatus(
            users,
            "PENDING",
          )
        : Math.max(
            Math.trunc(
              toNumber(pendingValue),
            ),
            0,
          ),
    approvedUsers:
      approvedValue === undefined
        ? countUsersByStatus(
            users,
            "APPROVED",
          )
        : Math.max(
            Math.trunc(
              toNumber(
                approvedValue,
              ),
            ),
            0,
          ),
    signalsToday: Math.max(
      Math.trunc(
        toNumber(
          firstDefined(data, [
            "signals_today",
            "signalsToday",
            "daily_signal_count",
            "signals_generated_today",
          ]),
        ),
      ),
      0,
    ),
    systemHealth: toText(
      firstDefined(data, [
        "system_health",
        "systemHealth",
        "health",
        "overall_status",
      ]),
      "UNKNOWN",
    ).toUpperCase(),
    systemMode: toText(
      firstDefined(data, [
        "system_mode",
        "systemMode",
        "mode",
      ]),
      "UNAVAILABLE",
    ),
    services,
  };
}

export async function updateAdminUser(
  userId: string,
  action: "approve" | "reject",
): Promise<void> {
  const normalizedUserId =
    userId.trim();

  if (!normalizedUserId) {
    throw new ApiError(
      "A valid user ID is required.",
      400,
      null,
    );
  }

  const endpoint =
    `${normalizeEndpoint(
      ADMIN_USERS_ENDPOINT,
    )}/${encodeURIComponent(
      normalizedUserId,
    )}/${action}`;

  await apiRequest<unknown>(
    endpoint,
    {
      method: "POST",
      body: JSON.stringify({
        action,
      }),
    },
  );
}

export async function setAdminSystemMode(
  mode: string,
): Promise<void> {
  const endpoint =
    normalizeEndpoint(
      ADMIN_SYSTEM_MODE_ENDPOINT,
    );

  if (!endpoint) {
    throw new ApiError(
      "System-mode changes are unavailable because no confirmed backend endpoint is configured.",
      501,
      {
        feature:
          "admin-system-mode",
        requested_mode:
          mode.trim(),
        enabled: false,
      },
    );
  }

  await apiRequest<unknown>(
    endpoint,
    {
      method: "PUT",
      body: JSON.stringify({
        mode: mode.trim(),
      }),
    },
  );
}