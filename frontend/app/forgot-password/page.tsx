"use client";

import {
  type FormEvent,
  useState,
} from "react";
import Link from "next/link";

import {
  API_BASE_URL,
  ApiError,
} from "@/lib/api";

type ForgotPasswordResponse = {
  status?: string;
  message?: string;
  email_delivery_connected?: boolean;
  password_reset_email_sent?: boolean;
  password_reset_email_error?: string | null;
  development_password_reset_token?: string | null;
  password_reset_expires_at?: string | null;
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
  }

  if (
    typeof payload === "string" &&
    payload.trim()
  ) {
    return payload.trim();
  }

  return fallback;
}

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");

  const [isLoading, setIsLoading] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  const [success, setSuccess] =
    useState<string | null>(null);

  const [deliveryNotice, setDeliveryNotice] =
    useState<string | null>(null);

  const [
    developmentResetToken,
    setDevelopmentResetToken,
  ] = useState<string | null>(null);

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    const normalizedEmail = email
      .trim()
      .toLowerCase();

    if (!normalizedEmail) {
      setError(
        "Enter your registered email address.",
      );
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      setSuccess(null);
      setDeliveryNotice(null);
      setDevelopmentResetToken(null);

      const response = await fetch(
        `${API_BASE_URL}/auth/forgot-password`,
        {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            email: normalizedEmail,
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
            `Password-reset request failed with status ${response.status}`,
          ),
          response.status,
          payload,
        );
      }

      const result =
        isRecord(payload)
          ? (payload as ForgotPasswordResponse)
          : {};

      setSuccess(
        result.message ||
          "If an active account exists for that email, password-reset instructions have been created.",
      );

      if (
        result.password_reset_email_sent === false
      ) {
        setDeliveryNotice(
          result.password_reset_email_error ||
            "The reset request was created, but the email could not be delivered.",
        );
      } else if (
        result.password_reset_email_sent === true
      ) {
        setDeliveryNotice(
          "Password-reset instructions were sent successfully.",
        );
      }

      if (
        typeof result.development_password_reset_token ===
          "string" &&
        result.development_password_reset_token.trim()
      ) {
        setDevelopmentResetToken(
          result.development_password_reset_token.trim(),
        );
      }
    } catch (requestError) {
      const message =
        requestError instanceof Error &&
        requestError.message.trim()
          ? requestError.message
          : "Unable to request a password reset.";

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
            Account Recovery
          </p>

          <h1 className="mt-2 text-3xl font-black tracking-tight text-white">
            Forgot your password?
          </h1>

          <p className="mt-3 text-sm leading-6 text-slate-500">
            Enter your registered email address.
            Blue-Trading-AI will create secure reset
            instructions when the account is eligible.
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="mt-8 space-y-5"
        >
          <div>
            <label
              htmlFor="email"
              className="text-xs font-black text-slate-300"
            >
              Email address
            </label>

            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              maxLength={255}
              value={email}
              onChange={(event) =>
                setEmail(event.target.value)
              }
              placeholder="you@example.com"
              className="mt-2 w-full rounded-xl border border-blue-400/10 bg-blue-500/[0.035] px-4 py-3.5 text-sm text-white placeholder:text-slate-700 transition focus:border-cyan-300/30 focus:bg-blue-500/[0.06] focus:shadow-[0_0_22px_rgba(37,99,235,0.12)]"
            />
          </div>

          {error ? (
            <div className="rounded-xl border border-rose-400/20 bg-rose-400/[0.05] px-4 py-3">
              <p className="text-xs font-bold text-rose-300">
                {error}
              </p>
            </div>
          ) : null}

          {success ? (
            <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/[0.05] px-4 py-3">
              <p className="text-xs font-bold leading-5 text-emerald-300">
                {success}
              </p>

              {deliveryNotice ? (
                <p className="mt-2 text-[11px] leading-5 text-slate-500">
                  {deliveryNotice}
                </p>
              ) : null}
            </div>
          ) : null}

          {developmentResetToken ? (
            <div className="rounded-xl border border-amber-400/20 bg-amber-400/[0.05] px-4 py-3">
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-amber-300">
                Development reset token
              </p>

              <p className="mt-2 break-all font-mono text-[11px] leading-5 text-amber-100">
                {developmentResetToken}
              </p>

              <p className="mt-2 text-[10px] leading-4 text-slate-600">
                This token should never appear in production.
              </p>
            </div>
          ) : null}

          <button
            type="submit"
            disabled={isLoading}
            className="midnight-button w-full rounded-xl py-3.5 text-sm font-black disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isLoading
              ? "Sending instructions..."
              : "Send Reset Instructions"}
          </button>
        </form>

        <div className="mt-6 rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4">
          <p className="text-xs leading-5 text-slate-600">
            For security, the response does not confirm
            whether an email address exists in the system.
          </p>
        </div>
      </section>
    </main>
  );
}