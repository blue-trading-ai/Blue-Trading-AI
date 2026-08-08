"use client";

import {
  useMemo,
  useState,
} from "react";
import Link from "next/link";
import {
  useRouter,
  useSearchParams,
} from "next/navigation";

import { logout } from "@/lib/auth";

type AccessState =
  | "forbidden"
  | "rejected"
  | "suspended"
  | "inactive"
  | "unverified"
  | "pending";

function normalizeAccessState(
  value: string | null,
): AccessState {
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

  if (
    normalized === "unverified" ||
    normalized === "email-unverified"
  ) {
    return "unverified";
  }

  if (normalized === "pending") {
    return "pending";
  }

  return "forbidden";
}

function getPageContent(
  state: AccessState,
): {
  code: string;
  eyebrow: string;
  title: string;
  description: string;
  accentClass: string;
} {
  if (state === "rejected") {
    return {
      code: "403",
      eyebrow: "Account Rejected",
      title: "This account was not approved",
      description:
        "The Blue-Trading-AI owner rejected access for this account. Protected pages remain unavailable.",
      accentClass:
        "border-rose-300/20 bg-rose-400/[0.06] text-rose-300 shadow-[0_0_35px_rgba(251,113,133,0.14)]",
    };
  }

  if (state === "suspended") {
    return {
      code: "403",
      eyebrow: "Account Suspended",
      title: "This account is temporarily blocked",
      description:
        "The account is suspended and cannot access Blue-Trading-AI until the owner restores access.",
      accentClass:
        "border-rose-300/20 bg-rose-400/[0.06] text-rose-300 shadow-[0_0_35px_rgba(251,113,133,0.14)]",
    };
  }

  if (state === "inactive") {
    return {
      code: "403",
      eyebrow: "Account Inactive",
      title: "This account is not active",
      description:
        "The account is inactive and cannot open protected Blue-Trading-AI pages.",
      accentClass:
        "border-rose-300/20 bg-rose-400/[0.06] text-rose-300 shadow-[0_0_35px_rgba(251,113,133,0.14)]",
    };
  }

  if (state === "unverified") {
    return {
      code: "403",
      eyebrow: "Email Verification Required",
      title: "Verify your email before continuing",
      description:
        "Your email address must be verified before protected Blue-Trading-AI access can be granted.",
      accentClass:
        "border-amber-300/20 bg-amber-400/[0.06] text-amber-300 shadow-[0_0_35px_rgba(252,211,77,0.14)]",
    };
  }

  if (state === "pending") {
    return {
      code: "403",
      eyebrow: "Owner Approval Required",
      title: "Your account is still under review",
      description:
        "Dashboard access remains unavailable until the Blue-Trading-AI owner approves this account.",
      accentClass:
        "border-amber-300/20 bg-amber-400/[0.06] text-amber-300 shadow-[0_0_35px_rgba(252,211,77,0.14)]",
    };
  }

  return {
    code: "403",
    eyebrow: "Access Denied",
    title: "You do not have permission to open this page",
    description:
      "This section requires a verified account, an approved role, or additional owner authorization.",
    accentClass:
      "border-amber-300/20 bg-amber-400/[0.06] text-amber-300 shadow-[0_0_35px_rgba(252,211,77,0.14)]",
  };
}

export default function UnauthorizedPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const state = useMemo(
    () =>
      normalizeAccessState(
        searchParams.get("status"),
      ),
    [searchParams],
  );

  const reason = useMemo(
    () =>
      searchParams.get("reason")?.trim() ||
      "",
    [searchParams],
  );

  const [isSigningOut, setIsSigningOut] =
    useState(false);

  const [logoutError, setLogoutError] =
    useState<string | null>(null);

  const content = getPageContent(state);

  const pendingLink =
    state === "pending"
      ? "/pending-approval?status=pending"
      : null;

  const verificationLink =
    state === "unverified"
      ? "/request-email-verification"
      : null;

  async function handleSignOut() {
    try {
      setIsSigningOut(true);
      setLogoutError(null);

      await logout();
    } catch (error) {
      setLogoutError(
        error instanceof Error &&
          error.message.trim()
          ? error.message
          : "The backend logout request failed, but the local session will be cleared.",
      );
    } finally {
      router.replace("/login");
      router.refresh();
      setIsSigningOut(false);
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#030712] px-6 py-12">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-1/2 top-[-180px] h-[420px] w-[420px] -translate-x-1/2 rounded-full bg-amber-400/[0.08] blur-[120px]" />
        <div className="absolute bottom-[-180px] right-[-120px] h-[360px] w-[360px] rounded-full bg-blue-500/[0.08] blur-[110px]" />
      </div>

      <section className="midnight-panel relative w-full max-w-2xl rounded-3xl p-8 text-center sm:p-12">
        <div
          className={`mx-auto flex h-24 w-24 items-center justify-center rounded-3xl border text-3xl font-black ${content.accentClass}`}
        >
          {content.code}
        </div>

        <p className="mt-7 text-[10px] font-black uppercase tracking-[0.24em] text-amber-300">
          {content.eyebrow}
        </p>

        <h1 className="mt-3 text-3xl font-black tracking-tight text-white sm:text-4xl">
          {content.title}
        </h1>

        <p className="mx-auto mt-4 max-w-lg text-sm leading-6 text-slate-500">
          {content.description}
        </p>

        {reason ? (
          <div className="mt-6 rounded-2xl border border-rose-400/15 bg-rose-400/[0.04] p-4 text-left">
            <p className="text-[10px] font-black uppercase tracking-[0.16em] text-rose-300">
              Access reason
            </p>

            <p className="mt-2 break-words text-xs leading-5 text-slate-400">
              {reason}
            </p>
          </div>
        ) : null}

        <div className="mt-7 rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-5 text-left">
          <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-600">
            Protected access behaviour
          </p>

          <p className="mt-2 text-xs leading-5 text-slate-500">
            Blue-Trading-AI does not expose admin controls,
            monitoring details, account-management data, or
            owner-only functions to unauthorized roles. USER
            accounts cannot open ADMIN or OWNER sections, and
            ADMIN accounts cannot use OWNER-only controls.
          </p>
        </div>

        {logoutError ? (
          <div className="mt-5 rounded-xl border border-amber-400/20 bg-amber-400/[0.05] px-4 py-3 text-left">
            <p className="text-xs font-bold leading-5 text-amber-300">
              {logoutError}
            </p>
          </div>
        ) : null}

        <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row sm:flex-wrap">
          <button
            type="button"
            onClick={handleSignOut}
            disabled={isSigningOut}
            className="midnight-button rounded-xl px-7 py-3 text-sm font-black disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSigningOut
              ? "Signing out..."
              : "Sign Out and Return to Login"}
          </button>

          {pendingLink ? (
            <Link
              href={pendingLink}
              className="rounded-xl border border-blue-400/10 bg-blue-500/[0.04] px-7 py-3 text-sm font-black text-cyan-200 transition hover:border-cyan-300/20 hover:bg-blue-500/[0.08]"
            >
              View Approval Status
            </Link>
          ) : null}

          {verificationLink ? (
            <Link
              href={verificationLink}
              className="rounded-xl border border-blue-400/10 bg-blue-500/[0.04] px-7 py-3 text-sm font-black text-cyan-200 transition hover:border-cyan-300/20 hover:bg-blue-500/[0.08]"
            >
              Request Verification Link
            </Link>
          ) : null}
        </div>

        <p className="mt-7 text-[10px] font-bold uppercase tracking-[0.14em] text-slate-700">
          Blue-Trading-AI · Role-Protected Access
        </p>
      </section>
    </main>
  );
}