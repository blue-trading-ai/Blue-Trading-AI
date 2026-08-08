import {
  ApiError,
  apiRequest,
  clearAccessToken,
} from "@/lib/api";

export type AuthenticatedUser = {
  id?: number | string;
  username?: string;
  email?: string;
  full_name?: string | null;
  role?: string | null;
  roles?: string[];
  permissions?: string[];
  status?: string | null;
  account_status?: string | null;
  is_active?: boolean;
  is_approved?: boolean;
  can_access_platform?: boolean;
  is_owner?: boolean;
  is_email_verified?: boolean;
  [key: string]: unknown;
};

type UnknownRecord =
  Record<string, unknown>;

const REFRESH_TOKEN_STORAGE_KEY =
  "blue_trading_ai_refresh_token";

function isRecord(
  value: unknown,
): value is UnknownRecord {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value)
  );
}

function clearStoredSession(): void {
  clearAccessToken();

  if (typeof window !== "undefined") {
    window.localStorage.removeItem(
      REFRESH_TOKEN_STORAGE_KEY,
    );
  }
}

function normalizeUppercaseString(
  value: unknown,
): string | null {
  if (
    typeof value !== "string" &&
    typeof value !== "number"
  ) {
    return null;
  }

  const normalized =
    String(value)
      .trim()
      .toUpperCase();

  return normalized || null;
}

function normalizeBoolean(
  value: unknown,
): boolean | undefined {
  if (typeof value === "boolean") {
    return value;
  }

  if (typeof value === "number") {
    return value !== 0;
  }

  if (typeof value !== "string") {
    return undefined;
  }

  const normalized =
    value.trim().toLowerCase();

  if (
    [
      "true",
      "1",
      "yes",
      "active",
      "approved",
      "enabled",
      "verified",
    ].includes(normalized)
  ) {
    return true;
  }

  if (
    [
      "false",
      "0",
      "no",
      "inactive",
      "rejected",
      "disabled",
      "unverified",
    ].includes(normalized)
  ) {
    return false;
  }

  return undefined;
}

function normalizeStringArray(
  value: unknown,
): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  const normalized = value
    .map((item) => {
      if (
        typeof item === "string" ||
        typeof item === "number"
      ) {
        return String(item)
          .trim()
          .toUpperCase();
      }

      if (isRecord(item)) {
        const candidate =
          item.name ??
          item.role ??
          item.code ??
          item.permission;

        return normalizeUppercaseString(
          candidate,
        ) ?? "";
      }

      return "";
    })
    .filter(Boolean);

  return Array.from(
    new Set(normalized),
  );
}

function looksLikeUser(
  value: UnknownRecord,
): boolean {
  return (
    "id" in value ||
    "email" in value ||
    "username" in value ||
    "role" in value ||
    "roles" in value ||
    "account_status" in value ||
    "is_owner" in value
  );
}

function extractUser(
  payload: unknown,
  depth = 0,
): AuthenticatedUser {
  if (
    !isRecord(payload) ||
    depth > 4
  ) {
    throw new ApiError(
      "The backend returned an invalid user response.",
      502,
      payload,
    );
  }

  if (looksLikeUser(payload)) {
    return payload as AuthenticatedUser;
  }

  for (const key of [
    "user",
    "data",
    "result",
    "profile",
    "account",
  ] as const) {
    const candidate = payload[key];

    if (isRecord(candidate)) {
      try {
        return extractUser(
          candidate,
          depth + 1,
        );
      } catch (error) {
        if (
          !(
            error instanceof ApiError &&
            error.status === 502
          )
        ) {
          throw error;
        }
      }
    }
  }

  throw new ApiError(
    "The backend returned an invalid user response.",
    502,
    payload,
  );
}

function normalizeUser(
  user: AuthenticatedUser,
): AuthenticatedUser {
  const roles =
    normalizeStringArray(
      user.roles,
    );

  const directRole =
    normalizeUppercaseString(
      user.role,
    );

  const isOwner =
    normalizeBoolean(
      user.is_owner,
    ) === true;

  if (
    isOwner &&
    !roles.includes("OWNER")
  ) {
    roles.unshift("OWNER");
  }

  if (
    directRole &&
    !roles.includes(directRole)
  ) {
    roles.push(directRole);
  }

  if (roles.length === 0) {
    roles.push(
      isOwner
        ? "OWNER"
        : "USER",
    );
  }

  const primaryRole =
    roles.includes("OWNER")
      ? "OWNER"
      : roles.includes("ADMIN")
        ? "ADMIN"
        : roles.includes("USER")
          ? "USER"
          : roles[0];

  const accountStatus =
    normalizeUppercaseString(
      user.account_status ??
        user.status,
    );

  return {
    ...user,
    id:
      typeof user.id === "string"
        ? user.id.trim()
        : user.id,
    username:
      typeof user.username === "string"
        ? user.username.trim()
        : user.username,
    email:
      typeof user.email === "string"
        ? user.email
            .trim()
            .toLowerCase()
        : user.email,
    full_name:
      typeof user.full_name === "string"
        ? user.full_name.trim() || null
        : user.full_name,
    role: primaryRole,
    roles,
    permissions:
      normalizeStringArray(
        user.permissions,
      ),
    status:
      normalizeUppercaseString(
        user.status,
      ),
    account_status:
      accountStatus,
    is_active:
      normalizeBoolean(
        user.is_active,
      ),
    is_approved:
      normalizeBoolean(
        user.is_approved,
      ),
    can_access_platform:
      normalizeBoolean(
        user.can_access_platform,
      ),
    is_owner: isOwner,
    is_email_verified:
      normalizeBoolean(
        user.is_email_verified,
      ),
  };
}

function getAccessError(
  user: AuthenticatedUser,
): string | null {
  const accountStatus =
    normalizeUppercaseString(
      user.account_status ??
        user.status,
    ) ?? "";

  if (
    [
      "REJECTED",
      "BLOCKED",
      "DISABLED",
    ].includes(accountStatus)
  ) {
    return "This account cannot access the platform.";
  }

  if (accountStatus === "SUSPENDED") {
    return "This account is suspended.";
  }

  if (
    accountStatus === "INACTIVE" ||
    user.is_active === false
  ) {
    return "This account is inactive.";
  }

  if (
    accountStatus === "PENDING" ||
    accountStatus === "WAITING" ||
    accountStatus === "UNDER_REVIEW" ||
    user.is_approved === false
  ) {
    return "This account is pending owner approval.";
  }

  if (
    user.is_email_verified === false ||
    accountStatus === "UNVERIFIED"
  ) {
    return "This account email is not verified.";
  }

  if (
    user.can_access_platform === false
  ) {
    return "This account cannot access the platform.";
  }

  return null;
}

export async function validateCurrentSession(): Promise<AuthenticatedUser> {
  try {
    const response =
      await apiRequest<unknown>(
        "/auth/me",
        {
          method: "GET",
        },
      );

    const user =
      normalizeUser(
        extractUser(response),
      );

    const accessError =
      getAccessError(user);

    if (accessError) {
      throw new ApiError(
        accessError,
        403,
        user,
      );
    }

    return user;
  } catch (error) {
    if (
      error instanceof ApiError &&
      error.status === 401
    ) {
      clearStoredSession();
    }

    throw error;
  }
}