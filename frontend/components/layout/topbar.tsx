"use client";

import {
  Bell,
  ShieldCheck,
} from "lucide-react";
import Image from "next/image";
import { usePathname } from "next/navigation";

import { MobileSidebar } from "@/components/layout/mobile-sidebar";
import { OwnerMenu } from "@/components/layout/owner-menu";
import { useCurrentUser } from "@/hooks/use-current-user";
import {
  ACCESS_ROLES,
  hasAllowedRole,
  isOwnerRole,
} from "@/lib/access-control";

type PageDetails = {
  eyebrow: string;
  title: string;
};

type AccountStatusTone =
  | "healthy"
  | "pending"
  | "blocked";

type AccountStatusPresentation = {
  label: string;
  tone: AccountStatusTone;
  classes: string;
  dotClassName: string;
};

const PAGE_DETAILS: Record<string, PageDetails> = {
  "/dashboard": {
    eyebrow: "Trading Workspace",
    title: "Market Dashboard",
  },
  "/analysis": {
    eyebrow: "Market Intelligence",
    title: "Market Analysis",
  },
  "/signals": {
    eyebrow: "Signal Intelligence",
    title: "Trading Signals",
  },
  "/market-structure": {
    eyebrow: "Structure Intelligence",
    title: "Market Structure",
  },
  "/performance": {
    eyebrow: "Performance Intelligence",
    title: "Performance",
  },
  "/history": {
    eyebrow: "Signal Records",
    title: "Trade History",
  },
  "/news": {
    eyebrow: "Fundamental Intelligence",
    title: "Market News",
  },
  "/monitoring": {
    eyebrow: "System Operations",
    title: "System Monitoring",
  },
  "/admin": {
    eyebrow: "Platform Administration",
    title: "Admin Control Center",
  },
  "/settings": {
    eyebrow: "Account Control",
    title: "Settings",
  },
};

function getPageDetails(
  pathname: string,
): PageDetails {
  const matchedRoute =
    Object.keys(PAGE_DETAILS)
      .sort(
        (first, second) =>
          second.length -
          first.length,
      )
      .find(
        (route) =>
          pathname === route ||
          pathname.startsWith(
            `${route}/`,
          ),
      );

  return matchedRoute
    ? PAGE_DETAILS[matchedRoute]
    : {
        eyebrow: "Blue Trading AI",
        title: "Trading Workspace",
      };
}

function normalizeRole(
  role: unknown,
): string {
  return typeof role === "string" &&
    role.trim()
    ? role.trim().toUpperCase()
    : "USER";
}

function normalizeStatus(
  value: unknown,
): string {
  return typeof value === "string" &&
    value.trim()
    ? value.trim().toUpperCase()
    : "";
}

function getAccountStatus({
  status,
  isActive,
  isApproved,
  isEmailVerified,
}: {
  status: unknown;
  isActive: unknown;
  isApproved: unknown;
  isEmailVerified: unknown;
}): AccountStatusPresentation {
  const normalized =
    normalizeStatus(status);

  const isBlocked =
    isActive === false ||
    [
      "INACTIVE",
      "SUSPENDED",
      "REJECTED",
      "BLOCKED",
      "DISABLED",
      "DEACTIVATED",
    ].some((state) =>
      normalized.includes(state),
    );

  if (isBlocked) {
    return {
      label:
        normalized || "INACTIVE",
      tone: "blocked",
      classes:
        "border-rose-400/15 bg-rose-400/[0.06] text-rose-300",
      dotClassName:
        "bg-rose-400",
    };
  }

  const isPending =
    isApproved === false ||
    [
      "PENDING",
      "WAITING",
      "REVIEW",
      "UNAPPROVED",
    ].some((state) =>
      normalized.includes(state),
    );

  if (isPending) {
    return {
      label: "PENDING",
      tone: "pending",
      classes:
        "border-amber-300/15 bg-amber-400/[0.06] text-amber-300",
      dotClassName:
        "bg-amber-300",
    };
  }

  const isUnverified =
    isEmailVerified === false ||
    normalized.includes(
      "UNVERIFIED",
    );

  if (isUnverified) {
    return {
      label: "UNVERIFIED",
      tone: "pending",
      classes:
        "border-amber-300/15 bg-amber-400/[0.06] text-amber-300",
      dotClassName:
        "bg-amber-300",
    };
  }

  const healthyLabel =
    [
      "ACTIVE",
      "APPROVED",
      "VERIFIED",
      "ENABLED",
    ].some(
      (state) =>
        normalized === state,
    )
      ? normalized
      : normalized || "ACTIVE";

  return {
    label: healthyLabel,
    tone: "healthy",
    classes:
      "border-emerald-400/15 bg-emerald-400/[0.06] text-emerald-300",
    dotClassName:
      "midnight-status-dot midnight-pulse bg-emerald-400",
  };
}

export function Topbar() {
  const pathname =
    usePathname();

  const {
    user,
    isLoading,
  } = useCurrentUser();

  const page =
    getPageDetails(pathname);

  const primaryRole =
    normalizeRole(user?.role);

  const additionalRoles =
    Array.isArray(user?.roles)
      ? user.roles
      : [];

  const isOwner =
    user?.is_owner === true ||
    isOwnerRole(
      user?.role,
    ) ||
    additionalRoles.some(
      isOwnerRole,
    );

  const isPrivileged =
    isOwner ||
    hasAllowedRole(
      user?.role,
      ACCESS_ROLES.administration,
    ) ||
    additionalRoles.some(
      (role) =>
        hasAllowedRole(
          role,
          ACCESS_ROLES.administration,
        ),
    );

  const displayRole =
    isOwner
      ? "OWNER"
      : isPrivileged
        ? "ADMIN"
        : primaryRole;

  const accountStatus =
    getAccountStatus({
      status:
        user?.account_status ??
        user?.status,
      isActive:
        user?.is_active,
      isApproved:
        user?.is_approved,
      isEmailVerified:
        user?.is_email_verified,
    });

  return (
    <header className="flex min-h-20 items-center justify-between border-b border-blue-400/10 bg-[#050b16]/85 px-3 py-3 backdrop-blur-xl sm:px-5 lg:px-6">
      <div className="flex min-w-0 items-center gap-3 sm:gap-4">
        <MobileSidebar />

        <div className="hidden shrink-0 items-center sm:flex">
          <Image
            src="/blue-trading-ai-logo.png"
            alt="Blue Trading AI"
            width={180}
            height={120}
            priority
            className="h-12 w-auto object-contain drop-shadow-[0_0_18px_rgba(34,211,238,0.16)] lg:h-14"
          />
        </div>

        <div className="hidden h-10 w-px shrink-0 bg-gradient-to-b from-transparent via-blue-400/20 to-transparent md:block" />

        <div className="min-w-0">
          <p className="truncate text-[10px] font-black uppercase tracking-[0.22em] text-slate-600">
            {page.eyebrow}
          </p>

          <div className="mt-1 flex min-w-0 items-center gap-3">
            <h1 className="truncate text-lg font-black tracking-tight text-white sm:text-2xl">
              {page.title}
            </h1>

            {!isLoading &&
            user ? (
              <span
                className={`hidden shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[9px] font-black uppercase tracking-[0.16em] sm:inline-flex ${
                  isPrivileged
                    ? "border-cyan-300/15 bg-cyan-300/[0.06] text-cyan-200"
                    : "border-blue-400/15 bg-blue-500/[0.06] text-blue-200"
                }`}
              >
                {isPrivileged ? (
                  <ShieldCheck
                    className="h-3 w-3"
                    aria-hidden="true"
                  />
                ) : null}

                {displayRole}
              </span>
            ) : (
              <span
                className="hidden h-6 w-16 animate-pulse rounded-full bg-white/[0.04] sm:inline-flex"
                aria-hidden="true"
              />
            )}
          </div>
        </div>
      </div>

      <div className="ml-3 flex shrink-0 items-center gap-2 sm:gap-3">
        <div className="hidden rounded-xl border border-blue-400/10 bg-blue-500/[0.04] px-4 py-2 lg:block">
          <p className="text-[9px] font-black uppercase tracking-[0.16em] text-slate-600">
            Signal Policy
          </p>

          <p className="mt-1 text-xs font-bold text-cyan-200">
            High quality only
          </p>
        </div>

        {!isLoading &&
        user ? (
          <div
            className={`hidden rounded-xl border px-4 py-2 md:block ${accountStatus.classes}`}
            data-status-tone={
              accountStatus.tone
            }
          >
            <div className="flex items-center gap-2">
              <span
                className={`h-2 w-2 rounded-full ${accountStatus.dotClassName}`}
                aria-hidden="true"
              />

              <div>
                <p className="text-[9px] font-black uppercase tracking-[0.16em] text-slate-600">
                  Account
                </p>

                <p className="mt-1 text-xs font-bold">
                  {accountStatus.label}
                </p>
              </div>
            </div>
          </div>
        ) : (
          <div
            className="hidden h-14 w-28 animate-pulse rounded-xl border border-blue-400/10 bg-blue-500/[0.04] md:block"
            aria-hidden="true"
          />
        )}

        <button
          type="button"
          aria-label="Notifications"
          title="Notifications"
          className="relative hidden h-11 w-11 items-center justify-center rounded-xl border border-blue-400/10 bg-blue-500/[0.04] text-slate-400 transition hover:border-cyan-300/20 hover:bg-blue-500/[0.08] hover:text-cyan-200 hover:shadow-[0_0_20px_rgba(37,99,235,0.18)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/50 sm:flex"
        >
          <Bell
            className="h-[18px] w-[18px]"
            aria-hidden="true"
          />
        </button>

        {!isLoading &&
        user ? (
          <OwnerMenu />
        ) : (
          <div
            className="h-11 w-11 animate-pulse rounded-xl border border-blue-400/10 bg-blue-500/[0.04] sm:w-32"
            aria-label="Loading account menu"
          />
        )}
      </div>
    </header>
  );
}