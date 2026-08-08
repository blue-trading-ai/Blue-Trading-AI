"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { getAccessToken } from "@/lib/api";

type AccountState =
  | "pending"
  | "rejected"
  | "suspended"
  | "inactive";

function normalizeAccountState(
  value: string | null,
): AccountState {
  const normalized = value
    ?.trim()
    .toLowerCase();

  if (normalized === "rejected") {
    return "rejected";
  }

  if (normalized === "suspended") {
    return "suspended";
  }

  if (normalized === "inactive") {
    return "inactive";
  }

  return "pending";
}

function getStateContent(
  state: AccountState,
): {
  icon: string;
  eyebrow: string;
  title: string;
  description: string;
  accentClass: string;
} {
  if (state === "rejected") {
    return {
      icon: "!",
      eyebrow: "Account Review",
      title: "Account access was rejected",
      description:
        "The owner did not approve this Blue-Trading-AI account. Dashboard access is unavailable.",
      accentClass:
        "border-rose-400/20 bg-rose-400/[0.06] text-rose-300 shadow-[0_0_30px_rgba(251,113,133,0.14)]",
    };
  }

  if (state === "suspended") {
    return {
      icon: "!",
      eyebrow: "Account Access",
      title: "Account access is suspended",
      description:
        "This Blue-Trading-AI account is currently suspended. Dashboard access remains blocked.",
      accentClass:
        "border-rose-400/20 bg-rose-400/[0.06] text-rose-300 shadow-[0_0_30px_rgba(251,113,133,0.14)]",
    };
  }

  if (state === "inactive") {
    return {
      icon: "!",
      eyebrow: "Account Access",
      title: "Account is inactive",
      description:
        "This Blue-Trading-AI account is inactive and cannot access protected platform pages.",
      accentClass:
        "border-rose-400/20 bg-rose-400/[0.06] text-rose-300 shadow-[0_0_30px_rgba(251,113,133,0.14)]",
    };
  }

  return {
    icon: "⏳",
    eyebrow: "Account Review",
    title: "Approval is still pending",
    description:
      "Your Blue-Trading-AI account has been created, but dashboard access requires approval from the platform owner.",
    accentClass:
      "border-amber-400/20 bg-amber-400/[0.06] text-amber-300 shadow-[0_0_30px_rgba(251,191,36,0.14)]",
  };
}

export default function PendingApprovalPage() {
  const searchParams = useSearchParams();

  const email = useMemo(
    () =>
      searchParams.get("email")?.trim() || "",
    [searchParams],
  );

  const accountState = useMemo(
    () =>
      normalizeAccountState(
        searchParams.get("status"),
      ),
    [searchParams],
  );

  const hasAuthenticatedSession =
    Boolean(getAccessToken());

  const content =
    getStateContent(accountState);

  const isPending =
    accountState === "pending";

  const verificationLink = email
    ? `/request-email-verification?email=${encodeURIComponent(
        email,
      )}`
    : "/request-email-verification";

  return (
    <main className="midnight-page flex min-h-screen items-center justify-center p-5 text-white">
      <section className="midnight-panel w-full max-w-xl rounded-3xl p-6 text-center sm:p-8">
        <div
          className={`mx-auto flex h-20 w-20 items-center justify-center rounded-3xl border text-3xl font-black ${content.accentClass}`}
        >
          {content.icon}
        </div>

        <p className="mt-6 text-[10px] font-black uppercase tracking-[0.22em] text-slate-600">
          {content.eyebrow}
        </p>

        <h1 className="mt-2 text-3xl font-black tracking-tight text-white">
          {content.title}
        </h1>

        <p className="mx-auto mt-4 max-w-md text-sm leading-6 text-slate-500">
          {content.description}
        </p>

        {email ? (
          <div className="mt-5 rounded-2xl border border-cyan-300/15 bg-cyan-300/[0.05] p-4">
            <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-600">
              Registered account
            </p>

            <p className="mt-2 break-all text-sm font-black text-cyan-200">
              {email}
            </p>
          </div>
        ) : null}

        {isPending ? (
          <>
            <div className="mt-6 grid gap-3 sm:grid-cols-3">
              {[
                {
                  step: "01",
                  label: "Account created",
                  status: "Complete",
                  style:
                    "border-emerald-400/15 bg-emerald-400/[0.05] text-emerald-300",
                },
                {
                  step: "02",
                  label: "Email verification",
                  status: "Check inbox",
                  style:
                    "border-blue-400/15 bg-blue-500/[0.05] text-cyan-200",
                },
                {
                  step: "03",
                  label: "Owner approval",
                  status: "Pending",
                  style:
                    "border-amber-400/15 bg-amber-400/[0.05] text-amber-300",
                },
              ].map((item) => (
                <div
                  key={item.step}
                  className={`rounded-2xl border p-4 ${item.style}`}
                >
                  <p className="text-[10px] font-black uppercase tracking-[0.16em] opacity-70">
                    Step {item.step}
                  </p>

                  <p className="mt-2 text-xs font-black text-white">
                    {item.label}
                  </p>

                  <p className="mt-1 text-[10px] font-bold uppercase tracking-[0.12em]">
                    {item.status}
                  </p>
                </div>
              ))}
            </div>

            <div className="mt-6 rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-5 text-left">
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
                What happens next?
              </p>

              <p className="mt-3 text-xs leading-6 text-slate-500">
                Check your inbox for the verification email sent
                during registration. The owner can then review
                your account. After approval, sign in to access
                the dashboard, market analysis and approved
                trading signals.
              </p>
            </div>

            {!hasAuthenticatedSession ? (
              <div className="mt-4 rounded-2xl border border-amber-400/15 bg-amber-400/[0.04] p-4 text-left">
                <p className="text-xs leading-5 text-amber-200">
                  Requesting another verification link requires
                  an authenticated session. Sign in first when
                  the backend permits access to this action.
                </p>
              </div>
            ) : null}
          </>
        ) : (
          <div className="mt-6 rounded-2xl border border-rose-400/15 bg-rose-400/[0.04] p-5 text-left">
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-rose-300">
              Access blocked
            </p>

            <p className="mt-3 text-xs leading-6 text-slate-500">
              This page does not grant dashboard access. Contact
              the platform owner when you believe this account
              status is incorrect.
            </p>
          </div>
        )}

        <div className="mt-7 flex flex-col gap-3 sm:flex-row sm:justify-center">
          <Link
            href="/login"
            className="midnight-button rounded-xl px-6 py-3 text-sm font-black"
          >
            Return to Login
          </Link>

          {isPending &&
          hasAuthenticatedSession ? (
            <Link
              href={verificationLink}
              className="rounded-xl border border-blue-400/10 bg-blue-500/[0.04] px-6 py-3 text-sm font-black text-cyan-200 transition hover:border-cyan-300/20 hover:bg-blue-500/[0.08]"
            >
              Request Verification Link
            </Link>
          ) : null}
        </div>

        <div className="mt-6 flex items-center justify-center gap-2">
          <span className="midnight-status-dot h-2 w-2 rounded-full bg-emerald-400" />

          <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-slate-600">
            Your account information remains protected
          </p>
        </div>
      </section>
    </main>
  );
}