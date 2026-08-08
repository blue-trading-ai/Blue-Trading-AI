"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { API_BASE_URL, ApiError } from "@/lib/api";

type RegisterResponse = {
  status?: string;
  message?: string;
  access_granted?: boolean;
  owner_approval_required?: boolean;
  email_verification_required?: boolean;
  verification_email_sent?: boolean;
  verification_email_error?: string | null;
  development_verification_token?: string | null;
  user?: unknown;
};

function getErrorMessage(
  payload: unknown,
  fallback: string,
): string {
  if (
    typeof payload === "object" &&
    payload !== null &&
    "detail" in payload
  ) {
    const detail = (
      payload as { detail: unknown }
    ).detail;

    if (typeof detail === "string") {
      return detail;
    }

    if (
      typeof detail === "object" &&
      detail !== null &&
      "message" in detail
    ) {
      return String(
        (
          detail as {
            message: unknown;
          }
        ).message,
      );
    }

    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => {
          if (
            typeof item === "object" &&
            item !== null &&
            "msg" in item
          ) {
            return String(
              (
                item as {
                  msg: unknown;
                }
              ).msg,
            );
          }

          return "";
        })
        .filter(Boolean);

      if (messages.length > 0) {
        return messages.join(", ");
      }
    }

    try {
      return JSON.stringify(detail);
    } catch {
      return fallback;
    }
  }

  if (
    typeof payload === "object" &&
    payload !== null &&
    "message" in payload
  ) {
    return String(
      (
        payload as {
          message: unknown;
        }
      ).message,
    );
  }

  if (
    typeof payload === "string" &&
    payload.trim()
  ) {
    return payload.trim();
  }

  return fallback;
}

export default function RegisterPage() {
  const router = useRouter();

  const [fullName, setFullName] =
    useState("");
  const [email, setEmail] =
    useState("");
  const [password, setPassword] =
    useState("");
  const [confirmPassword, setConfirmPassword] =
    useState("");

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

    const username = fullName.trim();
    const normalizedEmail = email
      .trim()
      .toLowerCase();

    if (username.length < 3) {
      setError(
        "Username must contain at least 3 characters.",
      );
      return;
    }

    if (password.length < 10) {
      setError(
        "Password must contain at least 10 characters.",
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
        `${API_BASE_URL}/auth/register`,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            username,
            email: normalizedEmail,
            password,
          }),
          cache: "no-store",
        },
      );

      const contentType =
        response.headers.get(
          "content-type",
        ) || "";

      const payload: unknown =
        contentType.includes(
          "application/json",
        )
          ? await response.json()
          : await response.text();

      if (!response.ok) {
        throw new ApiError(
          getErrorMessage(
            payload,
            `Registration failed with status ${response.status}`,
          ),
          response.status,
          payload,
        );
      }

      const result =
        payload as RegisterResponse;

      const verificationMessage =
        result.verification_email_sent === false
          ? " Registration succeeded, but the verification email could not be sent."
          : "";

      setSuccess(
        `${
          result.message ||
          "Registration successful. Your account is waiting for owner approval."
        }${verificationMessage}`,
      );

      window.setTimeout(() => {
        router.push(
          `/pending-approval?email=${encodeURIComponent(
            normalizedEmail,
          )}`,
        );
      }, 1500);
    } catch (requestError) {
      const message =
        requestError instanceof Error
          ? requestError.message
          : "Unable to create account.";

      setError(message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="midnight-page flex min-h-screen items-center justify-center p-5 text-white">
      <section className="grid w-full max-w-6xl overflow-hidden rounded-3xl border border-blue-400/10 bg-[#07101f]/90 shadow-[0_30px_100px_rgba(0,0,0,0.5)] backdrop-blur-xl lg:grid-cols-[0.95fr_1.05fr]">
        <div className="relative hidden min-h-[720px] overflow-hidden border-r border-blue-400/10 p-10 lg:flex lg:flex-col">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_25%_20%,rgba(37,99,235,0.28),transparent_35%),radial-gradient(circle_at_75%_75%,rgba(34,211,238,0.14),transparent_30%)]" />

          <div className="absolute inset-0 bg-[linear-gradient(rgba(59,130,246,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(59,130,246,0.04)_1px,transparent_1px)] bg-[size:42px_42px]" />

          <div className="relative z-10">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-blue-400/30 bg-gradient-to-br from-blue-600/30 to-cyan-400/10 text-lg font-black text-cyan-200 shadow-[0_0_28px_rgba(37,99,235,0.3)]">
                B
              </div>

              <div>
                <p className="text-lg font-black text-white">
                  Blue-Trading-AI
                </p>

                <p className="mt-1 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-600">
                  Intelligence Before Execution
                </p>
              </div>
            </div>

            <p className="mt-16 text-[10px] font-black uppercase tracking-[0.24em] text-cyan-300">
              Secure Registration
            </p>

            <h1 className="mt-4 max-w-lg text-4xl font-black leading-tight tracking-tight text-white">
              Join a controlled, high-quality trading intelligence platform.
            </h1>

            <p className="mt-5 max-w-lg text-sm leading-7 text-slate-500">
              New accounts remain pending until approved by the
              Blue-Trading-AI owner. This protects the platform,
              signals and user access.
            </p>
          </div>

          <div className="relative z-10 mt-auto space-y-3">
            {[
              "Owner approval required",
              "Secure backend authentication",
              "Protected dashboard access",
              "Analysis and signals only",
            ].map((item) => (
              <div
                key={item}
                className="rounded-2xl border border-blue-400/10 bg-blue-500/[0.04] p-4"
              >
                <div className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-cyan-300 shadow-[0_0_12px_rgba(34,211,238,0.75)]" />

                  <p className="text-xs font-bold text-slate-300">
                    {item}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="flex min-h-[720px] items-center p-6 sm:p-10">
          <div className="mx-auto w-full max-w-md">
            <p className="text-[10px] font-black uppercase tracking-[0.22em] text-slate-600">
              Create Account
            </p>

            <h2 className="mt-2 text-3xl font-black tracking-tight text-white">
              Register securely
            </h2>

            <p className="mt-3 text-sm leading-6 text-slate-500">
              Complete your details. Access begins only after owner approval.
            </p>

            <form
              onSubmit={handleSubmit}
              className="mt-8 space-y-4"
            >
              <div>
                <label
                  htmlFor="fullName"
                  className="text-xs font-black text-slate-300"
                >
                  Username
                </label>

                <input
                  id="fullName"
                  type="text"
                  required
                  value={fullName}
                  onChange={(event) =>
                    setFullName(
                      event.target.value,
                    )
                  }
                  className="mt-2 w-full rounded-xl border border-blue-400/10 bg-blue-500/[0.035] px-4 py-3.5 text-sm text-white placeholder:text-slate-700 focus:border-cyan-300/30"
                  minLength={3}
                  maxLength={100}
                  autoComplete="username"
                  placeholder="Choose a username"
                />
              </div>

              <div>
                <label
                  htmlFor="email"
                  className="text-xs font-black text-slate-300"
                >
                  Email address
                </label>

                <input
                  id="email"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(event) =>
                    setEmail(
                      event.target.value,
                    )
                  }
                  className="mt-2 w-full rounded-xl border border-blue-400/10 bg-blue-500/[0.035] px-4 py-3.5 text-sm text-white placeholder:text-slate-700 focus:border-cyan-300/30"
                  placeholder="you@example.com"
                />
              </div>

              <div>
                <label
                  htmlFor="password"
                  className="text-xs font-black text-slate-300"
                >
                  Password
                </label>

                <input
                  id="password"
                  type="password"
                  required
                  minLength={10}
                  maxLength={128}
                  autoComplete="new-password"
                  value={password}
                  onChange={(event) =>
                    setPassword(
                      event.target.value,
                    )
                  }
                  className="mt-2 w-full rounded-xl border border-blue-400/10 bg-blue-500/[0.035] px-4 py-3.5 text-sm text-white placeholder:text-slate-700 focus:border-cyan-300/30"
                  placeholder="Minimum 10 characters"
                />
              </div>

              <div>
                <label
                  htmlFor="confirmPassword"
                  className="text-xs font-black text-slate-300"
                >
                  Confirm password
                </label>

                <input
                  id="confirmPassword"
                  type="password"
                  required
                  minLength={10}
                  maxLength={128}
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(event) =>
                    setConfirmPassword(
                      event.target.value,
                    )
                  }
                  className="mt-2 w-full rounded-xl border border-blue-400/10 bg-blue-500/[0.035] px-4 py-3.5 text-sm text-white placeholder:text-slate-700 focus:border-cyan-300/30"
                  placeholder="Repeat your password"
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
                  <p className="text-xs font-bold text-emerald-300">
                    {success}
                  </p>

                  <p className="mt-1 text-[10px] text-slate-600">
                    Opening the pending approval page...
                  </p>
                </div>
              ) : null}

              <button
                type="submit"
                disabled={isLoading}
                className="midnight-button w-full rounded-xl py-3.5 text-sm font-black disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isLoading
                  ? "Creating account..."
                  : "Create Account"}
              </button>
            </form>

            <p className="mt-6 text-center text-xs text-slate-600">
              Already registered?{" "}
              <Link
                href="/login"
                className="font-black text-cyan-300 hover:text-cyan-200"
              >
                Sign in
              </Link>
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}