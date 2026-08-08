import {
  API_BASE_URL,
  ApiError,
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from "@/lib/api";

export type LoginCredentials = {
  email: string;
  password: string;
};

export type LoginResponse = {
  status?: string;
  message?: string;
  access_token: string;
  refresh_token?: string;
  token_type?: string;
  refresh_token_type?: string;
  access_token_expires_at?: string;
  refresh_token_expires_at?: string;
  refresh_token_rotated?: boolean;
  refresh_token_family_id?: string;
  access_granted?: boolean;
  owner_approval_required?: boolean;
  failed_login_attempts_reset?: boolean;
  session?: unknown;
  user?: unknown;
};

export type RefreshResponse = {
  status?: string;
  message?: string;
  access_token: string;
  refresh_token: string;
  token_type?: string;
  refresh_token_type?: string;
  access_token_expires_at?: string;
  refresh_token_expires_at?: string;
  session_id?: string;
  refresh_token_rotated?: boolean;
  refresh_token_family_id?: string;
};

const REFRESH_TOKEN_STORAGE_KEY =
  "blue_trading_ai_refresh_token";

function isRecord(
  value: unknown,
): value is Record<string, unknown> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value)
  );
}

function getErrorMessage(
  payload: unknown,
  fallback: string,
): string {
  if (isRecord(payload)) {
    const detail =
      payload.detail ??
      payload.message ??
      payload.error;

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

    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => {
          if (
            isRecord(item) &&
            typeof item.msg === "string"
          ) {
            return item.msg.trim();
          }

          return "";
        })
        .filter(Boolean);

      if (messages.length > 0) {
        return messages.join(", ");
      }
    }

    if (detail !== undefined) {
      try {
        return JSON.stringify(detail);
      } catch {
        return fallback;
      }
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

async function parseResponse(
  response: Response,
): Promise<unknown> {
  if (
    response.status === 204 ||
    response.status === 205
  ) {
    return null;
  }

  const raw = await response.text();

  if (!raw.trim()) {
    return null;
  }

  const contentType =
    response.headers.get("content-type") || "";

  if (
    contentType.includes(
      "application/json",
    )
  ) {
    try {
      return JSON.parse(raw) as unknown;
    } catch {
      throw new ApiError(
        "The backend returned invalid JSON.",
        response.status,
        raw,
      );
    }
  }

  return raw;
}

async function clearSharedCurrentUserCache(): Promise<void> {
  if (typeof window === "undefined") {
    return;
  }

  try {
    const {
      clearCurrentUserCache,
    } = await import(
      "@/hooks/use-current-user"
    );

    clearCurrentUserCache();
  } catch {
    // Token handling must still succeed if the UI cache module is unavailable.
  }
}

export function getStoredRefreshToken():
  | string
  | null {
  if (typeof window === "undefined") {
    return null;
  }

  const token =
    window.localStorage.getItem(
      REFRESH_TOKEN_STORAGE_KEY,
    );

  return token?.trim() || null;
}

function setStoredRefreshToken(
  token: string,
): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(
    REFRESH_TOKEN_STORAGE_KEY,
    token,
  );
}

export function clearStoredRefreshToken(): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(
    REFRESH_TOKEN_STORAGE_KEY,
  );
}

function clearStoredAuthentication(): void {
  clearAccessToken();
  clearStoredRefreshToken();
}

function validateLoginResponse(
  payload: unknown,
  responseStatus: number,
): LoginResponse {
  if (!isRecord(payload)) {
    clearStoredAuthentication();

    throw new ApiError(
      "The backend returned an invalid login response.",
      responseStatus,
      payload,
    );
  }

  const accessToken =
    typeof payload.access_token === "string"
      ? payload.access_token.trim()
      : "";

  if (!accessToken) {
    clearStoredAuthentication();

    throw new ApiError(
      "The backend did not return a valid access token.",
      responseStatus,
      payload,
    );
  }

  return {
    ...payload,
    access_token: accessToken,
    refresh_token:
      typeof payload.refresh_token === "string"
        ? payload.refresh_token.trim() ||
          undefined
        : undefined,
  } as LoginResponse;
}

function validateRefreshResponse(
  payload: unknown,
  responseStatus: number,
): RefreshResponse {
  if (!isRecord(payload)) {
    clearStoredAuthentication();

    throw new ApiError(
      "The backend returned an invalid refresh response.",
      responseStatus,
      payload,
    );
  }

  const accessToken =
    typeof payload.access_token === "string"
      ? payload.access_token.trim()
      : "";

  const refreshToken =
    typeof payload.refresh_token === "string"
      ? payload.refresh_token.trim()
      : "";

  if (!accessToken || !refreshToken) {
    clearStoredAuthentication();

    throw new ApiError(
      "The backend returned an invalid refreshed token pair.",
      responseStatus,
      payload,
    );
  }

  return {
    ...payload,
    access_token: accessToken,
    refresh_token: refreshToken,
  } as RefreshResponse;
}

export async function login(
  credentials: LoginCredentials,
): Promise<LoginResponse> {
  const normalizedEmail =
    credentials.email
      .trim()
      .toLowerCase();

  if (!normalizedEmail) {
    throw new ApiError(
      "Enter your registered email address.",
      400,
      null,
    );
  }

  if (!credentials.password) {
    throw new ApiError(
      "Enter your password.",
      400,
      null,
    );
  }

  const formData =
    new URLSearchParams();

  formData.set(
    "username",
    normalizedEmail,
  );

  formData.set(
    "password",
    credentials.password,
  );

  formData.set(
    "grant_type",
    "password",
  );

  let response: Response;

  try {
    response = await fetch(
      `${API_BASE_URL}/auth/login`,
      {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type":
            "application/x-www-form-urlencoded",
        },
        body: formData.toString(),
        cache: "no-store",
      },
    );
  } catch (error) {
    throw new ApiError(
      "Unable to connect to the authentication server.",
      0,
      error,
    );
  }

  const payload =
    await parseResponse(response);

  if (!response.ok) {
    throw new ApiError(
      getErrorMessage(
        payload,
        `Login failed with status ${response.status}`,
      ),
      response.status,
      payload,
    );
  }

  const result =
    validateLoginResponse(
      payload,
      response.status,
    );

  setAccessToken(
    result.access_token,
  );

  if (result.refresh_token) {
    setStoredRefreshToken(
      result.refresh_token,
    );
  } else {
    clearStoredRefreshToken();
  }

  await clearSharedCurrentUserCache();

  return result;
}

export async function refreshAccessToken(): Promise<RefreshResponse> {
  const refreshToken =
    getStoredRefreshToken();

  if (!refreshToken) {
    clearStoredAuthentication();
    await clearSharedCurrentUserCache();

    throw new ApiError(
      "No refresh token is available. Please log in again.",
      401,
      null,
    );
  }

  let response: Response;

  try {
    response = await fetch(
      `${API_BASE_URL}/auth/refresh`,
      {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type":
            "application/json",
        },
        body: JSON.stringify({
          refresh_token:
            refreshToken,
        }),
        cache: "no-store",
      },
    );
  } catch (error) {
    throw new ApiError(
      "Unable to connect to the authentication server.",
      0,
      error,
    );
  }

  const payload =
    await parseResponse(response);

  if (!response.ok) {
    if (
      response.status === 400 ||
      response.status === 401 ||
      response.status === 403
    ) {
      clearStoredAuthentication();
      await clearSharedCurrentUserCache();
    }

    throw new ApiError(
      getErrorMessage(
        payload,
        "Unable to refresh the authentication session.",
      ),
      response.status,
      payload,
    );
  }

  const result =
    validateRefreshResponse(
      payload,
      response.status,
    );

  setAccessToken(
    result.access_token,
  );

  setStoredRefreshToken(
    result.refresh_token,
  );

  return result;
}

export async function logout(): Promise<void> {
  const accessToken =
    getAccessToken();

  const refreshToken =
    getStoredRefreshToken();

  clearStoredAuthentication();
  await clearSharedCurrentUserCache();

  if (!accessToken) {
    return;
  }

  try {
    await fetch(
      `${API_BASE_URL}/auth/logout`,
      {
        method: "POST",
        headers: {
          Accept: "application/json",
          Authorization:
            `Bearer ${accessToken}`,
          ...(refreshToken
            ? {
                "Content-Type":
                  "application/json",
              }
            : {}),
        },
        body: refreshToken
          ? JSON.stringify({
              refresh_token:
                refreshToken,
            })
          : undefined,
        cache: "no-store",
      },
    );
  } catch {
    // Local credentials and the shared user cache are already cleared.
  }
}