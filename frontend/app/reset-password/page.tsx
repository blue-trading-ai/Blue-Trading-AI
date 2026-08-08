"use client";

import {
  type FormEvent,
  useMemo,
  useState,
} from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import {
  API_BASE_URL,
  ApiError,
  clearAccessToken,
} from "@/lib/api";

type UnknownRecord = Record<string, unknown>;

type ResetPasswordResponse = {
  status?: string;
  message?: string;
  relogin_required?: boolean;
  password_version?: number;
  password_changed_at?: string | null;
  revoked_sessions?: number;
  revoked_refresh_tokens?: number;
  revoked_action_tokens?: number;
};

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

function getMessage(
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

function clearStoredAuthentication(): void {
  clearAccessToken();

  if (typeof window !== "undefined") {
    window.localStorage.removeItem(
      REFRESH_TOKEN_STORAGE_KEY,
    );
  }
}

export default function ResetPasswordPage() {
  const searchParams = useSearchParams();

  const token = useMemo(
    () =>
      searchParams.get("token")?.trim() || "",
    [searchParams],
  );

  const [password, setPassword] =
    useState("");

  const [
    confirmPassword,
    setConfirmPassword,
  ] = useState("");

  const [isLoading, setIsLoading] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  const [success, setSuccess] =
    useState<string | null>(null);

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!token) {
      setError(
        "The password-reset token is missing from this link.",
      );
      return;
    }

    if (token.length < 20) {
      setError(
        "The password-reset token is invalid or incomplete.",
      );
      return;
    }

    if (password.length < 10) {
      setError(
        "The new password must contain at least 10 characters.",
      );
      return;
    }

    if (password.length > 128) {
      setError(
        "The new password cannot exceed 128 characters.",
      );
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      setSuccess(null);

      const response = await fetch(
        `${API_BASE_URL}/auth/reset-password`,
        {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            token,
            new_password: password,
          }),
          cache: "no-store",
        },
      );

      const contentType =
        response.headers.get("content-type") ||
        "";

      const payload: unknown =
        contentType.includes(
          "application/json",
        )
          ? await response.json()
          : await response.text();

      if (!response.ok) {
        throw new ApiError(
          getMessage(
            payload,
            `Password reset failed with status ${response.status}`,
          ),
          response.status,
          payload,
        );
      }

      const result = isRecord(payload)
        ? (payload as ResetPasswordResponse)
        : {};

      clearStoredAuthentication();

      setSuccess(
        result.message ||
          "Your password has been reset successfully. All existing sessions were revoked. You may now sign in.",
      );

      setPassword("");
      setConfirmPassword("");
    } catch (requestError) {
      const message =
        requestError instanceof Error &&
        requestError.message.trim()
          ? requestError.message
          : "Unable to reset the password.";

      setError(message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="midnight-page flex min-h-screen items-center justify-center p-5 text-white">
      <section className="midnight-panel w-full max-w-lg rounded-3xl p-6 sm:p-8">
        <Link
          href="/login"
          className="inline-flex text-xs font-black text-slate-500 transition hover:text-cyan-300"
        >
          ← Back to login
        </Link>

        <div className="mt-8">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl border border-cyan-300/20 bg-blue-500/[0.06] text-xl font-black text-cyan-200 shadow-[0_0_26px_rgba(37,99,235,0.18)]">
            B
          </div>

          <p className="mt-6 text-[10px] font-black uppercase tracking-[0.22em] text-slate-600">
            Secure Password Reset
          </p>

          <h1 className="mt-2 text-3xl font-black tracking-tight text-white">
            Create a new password
          </h1>

          <p className="mt-3 text-sm leading-6 text-slate-500">
            Enter a strong new password for your
            Blue-Trading-AI account.
          </p>
        </div>

        {!token ? (
          <div className="mt-6 rounded-xl border border-amber-400/20 bg-amber-400/[0.05] px-4 py-3">
            <p className="text-xs font-bold leading-5 text-amber-300">
              This reset link does not contain a valid token.
              Request a new password-reset email.
            </p>
          </div>
        ) : null}

        <form
          onSubmit={handleSubmit}
          className="mt-8 space-y-5"
        >
          <div>
            <label
              htmlFor="password"
              className="text-xs font-black text-slate-300"
            >
              New password
            </label>

            <input
              id="password"
              type="password"
              autoComplete="new-password"
              required
              minLength={10}
              maxLength={128}
              value={password}
              onChange={(event) =>
                setPassword(event.target.value)
              }
              placeholder="Minimum 10 characters"
              className="mt-2 w-full rounded-xl border border-blue-400/10 bg-blue-500/[0.035] px-4 py-3.5 text-sm text-white placeholder:text-slate-700 transition focus:border-cyan-300/30 focus:bg-blue-500/[0.06]"
            />
          </div>

          <div>
            <label
              htmlFor="confirmPassword"
              className="text-xs font-black text-slate-300"
            >
              Confirm new password
            </label>

            <input
              id="confirmPassword"
              type="password"
              autoComplete="new-password"
              required
              minLength={10}
              maxLength={128}
              value={confirmPassword}
              onChange={(event) =>
                setConfirmPassword(
                  event.target.value,
                )
              }
              placeholder="Repeat your new password"
              className="mt-2 w-full rounded-xl border border-blue-400/10 bg-blue-500/[0.035] px-4 py-3.5 text-sm text-white placeholder:text-slate-700 transition focus:border-cyan-300/30 focus:bg-blue-500/[0.06]"
            />
          </div>

          {error ? (
            <div className="rounded-xl border border-rose-400/20 bg-rose-400/[0.05] px-4 py-3">
              <p className="text-xs font-bold leading-5 text-rose-300">
                {error}
              </p>
            </div>
          ) : null}

          {success ? (
            <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/[0.05] px-4 py-3">
              <p className="text-xs font-bold leading-5 text-emerald-300">
                {success}
              </p>

              <Link
                href="/login"
                className="mt-3 inline-flex text-xs font-black text-cyan-300"
              >
                Continue to login →
              </Link>
            </div>
          ) : null}

          <button
            type="submit"
            disabled={isLoading || !token}
            className="midnight-button w-full rounded-xl py-3.5 text-sm font-black disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isLoading
              ? "Resetting password..."
              : "Reset Password"}
          </button>
        </form>

        <div className="mt-6 rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4">
          <p className="text-xs leading-5 text-slate-600">
            Password-reset tokens are single-use and expire
            automatically. A successful reset revokes all
            existing sessions and requires a fresh login.
          </p>
        </div>
      </section>
    </main>
  );
}