"use client";

import {
  type FormEvent,
  useState,
} from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  type LoginResponse,
  login,
} from "@/lib/auth";
import { ApiError } from "@/lib/api";

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

function normalizeText(
  value: unknown,
): string {
  return typeof value === "string"
    ? value.trim().toUpperCase()
    : "";
}

function getUserRoles(
  response: LoginResponse,
): string[] {
  if (!isRecord(response.user)) {
    return [];
  }

  const roles = Array.isArray(
    response.user.roles,
  )
    ? response.user.roles
        .map(normalizeText)
        .filter(Boolean)
    : [];

  const directRole = normalizeText(
    response.user.role,
  );

  if (
    directRole &&
    !roles.includes(directRole)
  ) {
    roles.push(directRole);
  }

  if (
    response.user.is_owner === true &&
    !roles.includes("OWNER")
  ) {
    roles.unshift("OWNER");
  }

  return roles;
}

function getAccountStatus(
  response: LoginResponse,
): string {
  if (!isRecord(response.user)) {
    return "";
  }

  return normalizeText(
    response.user.account_status ??
      response.user.status,
  );
}

function getSuccessfulLoginRoute(
  response: LoginResponse,
  normalizedEmail: string,
): string {
  const accountStatus =
    getAccountStatus(response);

  if (
    response.owner_approval_required === true ||
    response.access_granted === false ||
    accountStatus === "PENDING"
  ) {
    return `/pending-approval?email=${encodeURIComponent(
      normalizedEmail,
    )}`;
  }

  if (
    accountStatus === "REJECTED" ||
    accountStatus === "SUSPENDED" ||
    accountStatus === "INACTIVE"
  ) {
    return "/unauthorized";
  }

  if (
    isRecord(response.user) &&
    response.user.is_email_verified === false
  ) {
    return `/request-email-verification?email=${encodeURIComponent(
      normalizedEmail,
    )}`;
  }

  const roles = getUserRoles(response);

  if (
    roles.includes("OWNER") ||
    roles.includes("ADMIN")
  ) {
    return "/admin";
  }

  return "/dashboard";
}

function getFailedLoginRoute(
  error: ApiError,
  normalizedEmail: string,
): string | null {
  const message = error.message.toLowerCase();

  if (
    message.includes("pending") ||
    message.includes("approval required") ||
    message.includes("waiting for owner")
  ) {
    return `/pending-approval?email=${encodeURIComponent(
      normalizedEmail,
    )}`;
  }

  if (
    message.includes("email") &&
    (
      message.includes("not verified") ||
      message.includes("unverified") ||
      message.includes("verify")
    )
  ) {
    return `/request-email-verification?email=${encodeURIComponent(
      normalizedEmail,
    )}`;
  }

  if (
    message.includes("rejected") ||
    message.includes("suspended") ||
    message.includes("inactive") ||
    message.includes("disabled") ||
    message.includes("cannot access")
  ) {
    return "/unauthorized";
  }

  return null;
}

export default function LoginPage() {
  const router = useRouter();

  const [email, setEmail] =
    useState("");

  const [password, setPassword] =
    useState("");

  const [isLoading, setIsLoading] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

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

    if (!password) {
      setError("Enter your password.");
      return;
    }

    try {
      setIsLoading(true);
      setError(null);

      const result = await login({
        email: normalizedEmail,
        password,
      });

      const destination =
        getSuccessfulLoginRoute(
          result,
          normalizedEmail,
        );

      router.replace(destination);
      router.refresh();
    } catch (requestError) {
      if (requestError instanceof ApiError) {
        const destination =
          getFailedLoginRoute(
            requestError,
            normalizedEmail,
          );

        if (destination) {
          router.replace(destination);
          return;
        }

        if (requestError.status === 429) {
          setError(
            "Too many login attempts. Wait briefly and try again.",
          );
          return;
        }

        if (
          requestError.status === 401 ||
          requestError.status === 400
        ) {
          setError(
            requestError.message ||
              "The email address or password is incorrect.",
          );
          return;
        }

        setError(
          requestError.message ||
            "Unable to sign in.",
        );
        return;
      }

      const message =
        requestError instanceof Error &&
        requestError.message.trim()
          ? requestError.message
          : "Unable to sign in.";

      setError(message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="midnight-page flex min-h-screen items-center justify-center p-5 text-white">
      <section className="grid w-full max-w-6xl overflow-hidden rounded-3xl border border-blue-400/10 bg-[#07101f]/90 shadow-[0_30px_100px_rgba(0,0,0,0.5)] backdrop-blur-xl lg:grid-cols-[1.05fr_0.95fr]">
        <div className="relative hidden min-h-[680px] overflow-hidden border-r border-blue-400/10 p-10 lg:flex lg:flex-col">
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
              Midnight Electric
            </p>

            <h1 className="mt-4 max-w-lg text-4xl font-black leading-tight tracking-tight text-white">
              High-quality market intelligence,
              without signal overload.
            </h1>

            <p className="mt-5 max-w-lg text-sm leading-7 text-slate-500">
              Blue-Trading-AI publishes only approved setups
              that pass confidence, confirmation, market
              structure, multi-timeframe and risk controls.
            </p>
          </div>

          <div className="relative z-10 mt-auto grid gap-3 sm:grid-cols-2">
            {[
              "80% minimum confidence",
              "3+ confirmations",
              "Maximum 10 signals daily",
              "Analysis only",
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

        <div className="flex min-h-[680px] items-center p-6 sm:p-10">
          <div className="mx-auto w-full max-w-md">
            <div className="lg:hidden">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-blue-400/30 bg-gradient-to-br from-blue-600/30 to-cyan-400/10 text-lg font-black text-cyan-200">
                  B
                </div>

                <div>
                  <p className="font-black text-white">
                    Blue-Trading-AI
                  </p>

                  <p className="text-[9px] uppercase tracking-[0.16em] text-slate-600">
                    Intelligence Before Execution
                  </p>
                </div>
              </div>
            </div>

            <p className="mt-10 text-[10px] font-black uppercase tracking-[0.22em] text-slate-600 lg:mt-0">
              Secure Access
            </p>

            <h2 className="mt-2 text-3xl font-black tracking-tight text-white">
              Welcome back
            </h2>

            <p className="mt-3 text-sm leading-6 text-slate-500">
              Sign in to access the live dashboard,
              approved signals and system monitoring.
            </p>

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

              <div>
                <div className="flex items-center justify-between gap-3">
                  <label
                    htmlFor="password"
                    className="text-xs font-black text-slate-300"
                  >
                    Password
                  </label>

                  <Link
                    href="/forgot-password"
                    className="text-[11px] font-black text-cyan-300 transition hover:text-cyan-200"
                  >
                    Forgot password?
                  </Link>
                </div>

                <input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  maxLength={128}
                  value={password}
                  onChange={(event) =>
                    setPassword(event.target.value)
                  }
                  placeholder="Enter your password"
                  className="mt-2 w-full rounded-xl border border-blue-400/10 bg-blue-500/[0.035] px-4 py-3.5 text-sm text-white placeholder:text-slate-700 transition focus:border-cyan-300/30 focus:bg-blue-500/[0.06] focus:shadow-[0_0_22px_rgba(37,99,235,0.12)]"
                />
              </div>

              {error ? (
                <div className="rounded-xl border border-rose-400/20 bg-rose-400/[0.05] px-4 py-3">
                  <p className="text-xs font-bold leading-5 text-rose-300">
                    {error}
                  </p>
                </div>
              ) : null}

              <button
                type="submit"
                disabled={isLoading}
                className="midnight-button w-full rounded-xl py-3.5 text-sm font-black disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isLoading
                  ? "Signing in..."
                  : "Sign In"}
              </button>
            </form>

            <div className="mt-6 rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4 text-center">
              <p className="text-xs text-slate-500">
                New to Blue-Trading-AI?
              </p>

              <Link
                href="/register"
                className="mt-2 inline-flex text-xs font-black text-cyan-300 transition hover:text-cyan-200"
              >
                Create an account
              </Link>
            </div>

            <div className="mt-6 flex items-center justify-center gap-2">
              <span className="midnight-status-dot h-2 w-2 rounded-full bg-emerald-400" />

              <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-600">
                Secure backend authentication active
              </p>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}