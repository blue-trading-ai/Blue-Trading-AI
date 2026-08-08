"use client";

import {
  type FormEvent,
  useMemo,
  useState,
} from "react";
import Link from "next/link";
import {
  useRouter,
  useSearchParams,
} from "next/navigation";

import {
  API_BASE_URL,
  ApiError,
  clearAccessToken,
  getAccessToken,
} from "@/lib/api";

type UnknownRecord = Record<string, unknown>;

type VerificationRequestResponse = {
  status?: string;
  message?: string;
  email?: string | null;
  email_verified?: boolean;
  verification_email_sent?: boolean;
  verification_email_error?: string | null;
  development_verification_token?: string | null;
  verification_expires_at?: string | null;
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

export default function RequestEmailVerificationPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const emailHint = useMemo(
    () =>
      searchParams.get("email")?.trim() || "",
    [searchParams],
  );

  const [isLoading, setIsLoading] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  const [success, setSuccess] =
    useState<string | null>(null);

  const [deliveryNotice, setDeliveryNotice] =
    useState<string | null>(null);

  const [
    developmentVerificationToken,
    setDevelopmentVerificationToken,
  ] = useState<string | null>(null);

  async function handleSubmit(
    event: FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    const accessToken = getAccessToken();

    if (!accessToken) {
      setError(
        "Your session is missing or has expired. Sign in before requesting a new verification link.",
      );
      setSuccess(null);
      setDeliveryNotice(null);
      setDevelopmentVerificationToken(null);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      setSuccess(null);
      setDeliveryNotice(null);
      setDevelopmentVerificationToken(null);

      const response = await fetch(
        `${API_BASE_URL}/auth/request-email-verification`,
        {
          method: "POST",
          headers: {
            Accept: "application/json",
            Authorization: `Bearer ${accessToken}`,
          },
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
            `Verification request failed with status ${response.status}`,
          ),
          response.status,
          payload,
        );
      }

      const result = isRecord(payload)
        ? (payload as VerificationRequestResponse)
        : {};

      if (result.email_verified === true) {
        setSuccess(
          result.message ||
            "Your email address is already verified.",
        );
      } else {
        setSuccess(
          result.message ||
            "A new verification link has been created for your account.",
        );
      }

      if (
        result.verification_email_sent === false
      ) {
        setDeliveryNotice(
          result.verification_email_error ||
            "The verification request was created, but the email could not be delivered.",
        );
      } else if (
        result.verification_email_sent === true
      ) {
        setDeliveryNotice(
          "The verification email was sent successfully.",
        );
      }

      if (
        typeof result.development_verification_token ===
          "string" &&
        result.development_verification_token.trim()
      ) {
        setDevelopmentVerificationToken(
          result.development_verification_token.trim(),
        );
      }
    } catch (requestError) {
      if (
        requestError instanceof ApiError &&
        requestError.status === 401
      ) {
        clearAccessToken();

        setError(
          "Your session has expired. Sign in again before requesting a new verification link.",
        );

        window.setTimeout(() => {
          router.replace("/login");
        }, 1800);

        return;
      }

      if (
        requestError instanceof ApiError &&
        requestError.status === 409
      ) {
        setSuccess(
          requestError.message ||
            "Your email address is already verified.",
        );
        return;
      }

      const message =
        requestError instanceof Error &&
        requestError.message.trim()
          ? requestError.message
          : "Unable to request a new verification email.";

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
            Email Verification
          </p>

          <h1 className="mt-2 text-3xl font-black tracking-tight text-white">
            Request a new verification link
          </h1>

          <p className="mt-3 text-sm leading-6 text-slate-500">
            Blue-Trading-AI will send a new secure verification
            link to the email address attached to your signed-in
            account.
          </p>
        </div>

        {emailHint ? (
          <div className="mt-6 rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4">
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
              Account email
            </p>

            <p className="mt-2 break-all text-sm font-bold text-cyan-200">
              {emailHint}
            </p>

            <p className="mt-2 text-[10px] leading-4 text-slate-600">
              The backend still verifies the account using your
              authenticated session.
            </p>
          </div>
        ) : null}

        <form
          onSubmit={handleSubmit}
          className="mt-8 space-y-5"
        >
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

              {deliveryNotice ? (
                <p className="mt-2 text-[11px] leading-5 text-slate-500">
                  {deliveryNotice}
                </p>
              ) : null}
            </div>
          ) : null}

          {developmentVerificationToken ? (
            <div className="rounded-xl border border-amber-400/20 bg-amber-400/[0.05] px-4 py-3">
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-amber-300">
                Development verification token
              </p>

              <p className="mt-2 break-all font-mono text-[11px] leading-5 text-amber-100">
                {developmentVerificationToken}
              </p>

              <Link
                href={`/verify-email?token=${encodeURIComponent(
                  developmentVerificationToken,
                )}`}
                className="mt-3 inline-flex text-xs font-black text-cyan-300 hover:text-cyan-200"
              >
                Verify using this token →
              </Link>

              <p className="mt-2 text-[10px] leading-4 text-slate-600">
                This token must never be exposed in production.
              </p>
            </div>
          ) : null}

          <button
            type="submit"
            disabled={isLoading}
            className="midnight-button w-full rounded-xl py-3.5 text-sm font-black disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isLoading
              ? "Sending verification link..."
              : "Send Verification Link"}
          </button>
        </form>

        <div className="mt-6 rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4">
          <p className="text-xs leading-5 text-slate-600">
            This action requires a valid signed-in session.
            Verification links are single-use and expire
            automatically. Dashboard access also requires owner
            approval.
          </p>
        </div>
      </section>
    </main>
  );
}