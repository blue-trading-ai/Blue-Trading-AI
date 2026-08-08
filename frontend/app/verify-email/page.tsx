"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import {
  API_BASE_URL,
  ApiError,
} from "@/lib/api";

type UnknownRecord = Record<string, unknown>;

type VerifyEmailResponse = {
  status?: string;
  message?: string;
  email_verified?: boolean;
  user?: unknown;
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

function getFailureMessage(
  error: unknown,
): string {
  if (error instanceof ApiError) {
    if (error.status === 410) {
      return "This email-verification token has expired. Request a new verification link.";
    }

    if (error.status === 409) {
      return "This email-verification token has already been used.";
    }

    if (error.status === 401) {
      return "This email-verification token is invalid.";
    }

    return error.message;
  }

  if (
    error instanceof Error &&
    error.message.trim()
  ) {
    return error.message;
  }

  return "Unable to verify the email address.";
}

export default function VerifyEmailPage() {
  const searchParams = useSearchParams();

  const token = useMemo(
    () =>
      searchParams.get("token")?.trim() || "",
    [searchParams],
  );

  const verificationStartedRef =
    useRef<string | null>(null);

  const [status, setStatus] = useState<
    "idle" | "loading" | "success" | "error"
  >("idle");

  const [message, setMessage] =
    useState<string>("");

  useEffect(() => {
    let isActive = true;

    async function verifyEmail() {
      if (!token) {
        setStatus("error");
        setMessage(
          "The email-verification token is missing from this link.",
        );
        return;
      }

      if (token.length < 20) {
        setStatus("error");
        setMessage(
          "The email-verification token is invalid or incomplete.",
        );
        return;
      }

      if (
        verificationStartedRef.current === token
      ) {
        return;
      }

      verificationStartedRef.current = token;

      try {
        setStatus("loading");
        setMessage(
          "Verifying your email address...",
        );

        const response = await fetch(
          `${API_BASE_URL}/auth/verify-email`,
          {
            method: "POST",
            headers: {
              Accept: "application/json",
              "Content-Type":
                "application/json",
            },
            body: JSON.stringify({
              token,
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
              `Email verification failed with status ${response.status}`,
            ),
            response.status,
            payload,
          );
        }

        if (!isActive) {
          return;
        }

        const result = isRecord(payload)
          ? (payload as VerifyEmailResponse)
          : {};

        setStatus("success");
        setMessage(
          result.message ||
            "Your email address has been verified successfully.",
        );
      } catch (requestError) {
        if (!isActive) {
          return;
        }

        setStatus("error");
        setMessage(
          getFailureMessage(requestError),
        );
      }
    }

    void verifyEmail();

    return () => {
      isActive = false;
    };
  }, [token]);

  const isLoading = status === "loading";
  const isSuccess = status === "success";
  const isError = status === "error";

  return (
    <main className="midnight-page flex min-h-screen items-center justify-center p-5 text-white">
      <section className="midnight-panel w-full max-w-lg rounded-3xl p-6 text-center sm:p-8">
        <div
          className={`mx-auto flex h-20 w-20 items-center justify-center rounded-3xl border text-3xl font-black ${
            isSuccess
              ? "border-emerald-400/20 bg-emerald-400/[0.06] text-emerald-300 shadow-[0_0_30px_rgba(52,211,153,0.16)]"
              : isError
                ? "border-rose-400/20 bg-rose-400/[0.06] text-rose-300 shadow-[0_0_30px_rgba(251,113,133,0.16)]"
                : "midnight-pulse border-cyan-300/20 bg-blue-500/[0.06] text-cyan-200"
          }`}
        >
          {isSuccess
            ? "✓"
            : isError
              ? "!"
              : "B"}
        </div>

        <p className="mt-6 text-[10px] font-black uppercase tracking-[0.22em] text-slate-600">
          Email Verification
        </p>

        <h1 className="mt-2 text-3xl font-black tracking-tight text-white">
          {isLoading
            ? "Verifying your email"
            : isSuccess
              ? "Email verified"
              : "Verification failed"}
        </h1>

        <p
          className={`mx-auto mt-4 max-w-md text-sm leading-6 ${
            isSuccess
              ? "text-emerald-300"
              : isError
                ? "text-rose-300"
                : "text-slate-500"
          }`}
        >
          {message ||
            "Preparing secure email verification..."}
        </p>

        {isLoading ? (
          <div className="mx-auto mt-6 h-2 w-full max-w-xs overflow-hidden rounded-full bg-slate-900">
            <div className="midnight-pulse h-full w-2/3 rounded-full bg-gradient-to-r from-blue-600 to-cyan-300" />
          </div>
        ) : null}

        {isSuccess ? (
          <div className="mt-6 rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4">
            <p className="text-xs leading-5 text-slate-500">
              Your email is confirmed. Dashboard access still
              depends on owner approval.
            </p>
          </div>
        ) : null}

        {isError ? (
          <div className="mt-6 rounded-2xl border border-amber-400/20 bg-amber-400/[0.05] p-4">
            <p className="text-xs leading-5 text-amber-300">
              Verification links are single-use and expire
              automatically. Request a new link when necessary.
            </p>
          </div>
        ) : null}

        <div className="mt-7 flex flex-col gap-3 sm:flex-row sm:justify-center">
          <Link
            href="/login"
            className="midnight-button rounded-xl px-6 py-3 text-sm font-black"
          >
            Continue to Login
          </Link>

          {isError ? (
            <Link
              href="/request-email-verification"
              className="rounded-xl border border-blue-400/10 bg-blue-500/[0.04] px-6 py-3 text-sm font-black text-cyan-200 transition hover:border-cyan-300/20 hover:bg-blue-500/[0.08]"
            >
              Request New Link
            </Link>
          ) : null}
        </div>
      </section>
    </main>
  );
}