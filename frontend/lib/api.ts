const DEFAULT_API_URL = "http://127.0.0.1:8000";

const ACCESS_TOKEN_STORAGE_KEY =
  "blue_trading_ai_access_token";

const REFRESH_TOKEN_STORAGE_KEY =
  "blue_trading_ai_refresh_token";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.trim().replace(/\/+$/, "") ||
  DEFAULT_API_URL;

type ApiRequestOptions = RequestInit & {
  accessToken?: string | null;
  retryOnUnauthorized?: boolean;
};

type UnknownRecord = Record<string, unknown>;

type RefreshTokenResponse = {
  access_token: string;
  refresh_token: string;
};

type TokenRotationResult = {
  accessToken: string | null;
  authenticationInvalid: boolean;
};

let refreshPromise:
  | Promise<TokenRotationResult>
  | null = null;

export class ApiError extends Error {
  status: number;
  details: unknown;

  constructor(
    message: string,
    status: number,
    details: unknown = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;

    Object.setPrototypeOf(
      this,
      ApiError.prototype,
    );
  }
}

function isRecord(
  value: unknown,
): value is UnknownRecord {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value)
  );
}

function isAbortError(
  error: unknown,
): boolean {
  return (
    error instanceof DOMException &&
    error.name === "AbortError"
  );
}

function normalizeEndpoint(
  endpoint: string,
): string {
  const trimmed = endpoint.trim();

  if (!trimmed) {
    return "";
  }

  return trimmed.startsWith("/")
    ? trimmed
    : `/${trimmed}`;
}

function buildApiUrl(
  endpoint: string,
): string {
  return `${API_BASE_URL}${normalizeEndpoint(endpoint)}`;
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

  let raw: string;

  try {
    raw = await response.text();
  } catch (error) {
    throw new ApiError(
      "Unable to read the backend response.",
      response.status,
      error,
    );
  }

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

function isFormDataBody(
  body: BodyInit,
): boolean {
  return (
    typeof FormData !== "undefined" &&
    body instanceof FormData
  );
}

function isUrlSearchParamsBody(
  body: BodyInit,
): boolean {
  return (
    typeof URLSearchParams !== "undefined" &&
    body instanceof URLSearchParams
  );
}

function isBlobBody(
  body: BodyInit,
): boolean {
  return (
    typeof Blob !== "undefined" &&
    body instanceof Blob
  );
}

function isArrayBufferBody(
  body: BodyInit,
): boolean {
  return (
    typeof ArrayBuffer !== "undefined" &&
    body instanceof ArrayBuffer
  );
}

function shouldSetJsonContentType(
  body: BodyInit | null | undefined,
  headers: Headers,
): boolean {
  if (
    body === undefined ||
    body === null ||
    headers.has("Content-Type")
  ) {
    return false;
  }

  return !(
    isFormDataBody(body) ||
    isUrlSearchParamsBody(body) ||
    isBlobBody(body) ||
    isArrayBufferBody(body)
  );
}

function getStoredRefreshToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  const token = window.localStorage.getItem(
    REFRESH_TOKEN_STORAGE_KEY,
  );

  return token?.trim() || null;
}

function hasStoredRefreshToken(): boolean {
  return Boolean(
    getStoredRefreshToken(),
  );
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

function clearStoredRefreshToken(): void {
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

function isRefreshableEndpoint(
  endpoint: string,
): boolean {
  const normalized =
    normalizeEndpoint(endpoint);

  return ![
    "/auth/login",
    "/auth/register",
    "/auth/refresh",
    "/auth/logout",
    "/auth/forgot-password",
    "/auth/reset-password",
    "/auth/verify-email",
  ].some((path) =>
    normalized.startsWith(path),
  );
}

async function performTokenRotation(): Promise<
  TokenRotationResult
> {
  const refreshToken =
    getStoredRefreshToken();

  if (!refreshToken) {
    clearAccessToken();

    return {
      accessToken: null,
      authenticationInvalid: true,
    };
  }

  let response: Response;

  try {
    response = await fetch(
      buildApiUrl("/auth/refresh"),
      {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type":
            "application/json",
        },
        body: JSON.stringify({
          refresh_token: refreshToken,
        }),
        cache: "no-store",
      },
    );
  } catch {
    return {
      accessToken: null,
      authenticationInvalid: false,
    };
  }

  let payload: unknown;

  try {
    payload =
      await parseResponse(response);
  } catch {
    if (
      response.status === 400 ||
      response.status === 401 ||
      response.status === 403
    ) {
      clearStoredAuthentication();
    }

    return {
      accessToken: null,
      authenticationInvalid:
        response.status === 400 ||
        response.status === 401 ||
        response.status === 403,
    };
  }

  if (!response.ok) {
    if (
      response.status === 400 ||
      response.status === 401 ||
      response.status === 403
    ) {
      clearStoredAuthentication();
    }

    return {
      accessToken: null,
      authenticationInvalid:
        response.status === 400 ||
        response.status === 401 ||
        response.status === 403,
    };
  }

  if (
    !isRecord(payload) ||
    typeof payload.access_token !== "string" ||
    !payload.access_token.trim() ||
    typeof payload.refresh_token !== "string" ||
    !payload.refresh_token.trim()
  ) {
    clearStoredAuthentication();

    return {
      accessToken: null,
      authenticationInvalid: true,
    };
  }

  const tokenPair =
    payload as RefreshTokenResponse;

  const nextAccessToken =
    tokenPair.access_token.trim();

  const nextRefreshToken =
    tokenPair.refresh_token.trim();

  setAccessToken(
    nextAccessToken,
  );

  setStoredRefreshToken(
    nextRefreshToken,
  );

  return {
    accessToken: nextAccessToken,
    authenticationInvalid: false,
  };
}

async function rotateTokenPair(): Promise<
  TokenRotationResult
> {
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise =
    performTokenRotation();

  try {
    return await refreshPromise;
  } finally {
    refreshPromise = null;
  }
}

export async function apiRequest<T>(
  endpoint: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const {
    accessToken,
    retryOnUnauthorized = true,
    headers,
    body,
    ...requestOptions
  } = options;

  const normalizedEndpoint =
    normalizeEndpoint(endpoint);

  if (!normalizedEndpoint) {
    throw new ApiError(
      "An API endpoint is required.",
      400,
      endpoint,
    );
  }

  const resolvedHeaders =
    new Headers(headers);

  if (!resolvedHeaders.has("Accept")) {
    resolvedHeaders.set(
      "Accept",
      "application/json",
    );
  }

  if (
    shouldSetJsonContentType(
      body,
      resolvedHeaders,
    )
  ) {
    resolvedHeaders.set(
      "Content-Type",
      "application/json",
    );
  }

  const resolvedAccessToken =
    accessToken === undefined
      ? getAccessToken()
      : accessToken;

  if (resolvedAccessToken?.trim()) {
    resolvedHeaders.set(
      "Authorization",
      `Bearer ${resolvedAccessToken.trim()}`,
    );
  } else {
    resolvedHeaders.delete(
      "Authorization",
    );
  }

  let response: Response;

  try {
    response = await fetch(
      buildApiUrl(normalizedEndpoint),
      {
        ...requestOptions,
        body,
        headers: resolvedHeaders,
        cache: "no-store",
      },
    );
  } catch (error) {
    if (isAbortError(error)) {
      throw error;
    }

    throw new ApiError(
      "Unable to connect to the Blue-Trading-AI backend.",
      0,
      error,
    );
  }

  if (
    response.status === 401 &&
    retryOnUnauthorized &&
    (
      Boolean(
        resolvedAccessToken,
      ) ||
      hasStoredRefreshToken()
    ) &&
    isRefreshableEndpoint(
      normalizedEndpoint,
    )
  ) {
    const rotationResult =
      await rotateTokenPair();

    if (
      rotationResult.accessToken
    ) {
      const retryHeaders =
        new Headers(
          options.headers,
        );

      retryHeaders.delete(
        "Authorization",
      );

      return apiRequest<T>(
        normalizedEndpoint,
        {
          ...options,
          headers: retryHeaders,
          accessToken:
            rotationResult.accessToken,
          retryOnUnauthorized: false,
        },
      );
    }

    if (
      rotationResult.authenticationInvalid
    ) {
      clearStoredAuthentication();
    }
  }

  const payload =
    await parseResponse(response);

  if (!response.ok) {
    if (
      response.status === 401 &&
      !hasStoredRefreshToken()
    ) {
      clearStoredAuthentication();
    }

    throw new ApiError(
      getErrorMessage(
        payload,
        `API request failed with status ${response.status}`,
      ),
      response.status,
      payload,
    );
  }

  return payload as T;
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  const token = window.localStorage.getItem(
    ACCESS_TOKEN_STORAGE_KEY,
  );

  return token?.trim() || null;
}

export function setAccessToken(
  token: string,
): void {
  if (typeof window === "undefined") {
    return;
  }

  const normalizedToken =
    token.trim();

  if (!normalizedToken) {
    clearAccessToken();
    return;
  }

  window.localStorage.setItem(
    ACCESS_TOKEN_STORAGE_KEY,
    normalizedToken,
  );
}

export function clearAccessToken(): void {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(
    ACCESS_TOKEN_STORAGE_KEY,
  );
}