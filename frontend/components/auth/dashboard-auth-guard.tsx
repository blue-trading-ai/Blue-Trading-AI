"use client";

import type { ReactNode } from "react";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useCurrentUser } from "@/hooks/use-current-user";

type DashboardAuthGuardProps = {
  children: ReactNode;
};

type RedirectDecision = {
  destination: string;
  message: string;
};

function normalizeStatus(
  value: unknown,
): string {
  return typeof value === "string"
    ? value.trim().toUpperCase()
    : "";
}

function encodeReason(
  value: string,
): string {
  return encodeURIComponent(
    value.slice(0, 300),
  );
}

function getUserRedirectDecision(
  user: {
    account_status?: string | null;
    status?: string | null;
    is_active?: boolean;
    is_approved?: boolean;
    can_access_platform?: boolean;
    is_email_verified?: boolean;
  },
): RedirectDecision | null {
  const accountStatus =
    normalizeStatus(
      user.account_status ??
        user.status,
    );

  if (
    [
      "REJECTED",
      "BLOCKED",
      "DISABLED",
    ].includes(accountStatus)
  ) {
    return {
      destination:
        "/unauthorized?status=rejected",
      message:
        "This account cannot access the platform. Redirecting securely...",
    };
  }

  if (
    accountStatus === "SUSPENDED"
  ) {
    return {
      destination:
        "/unauthorized?status=suspended",
      message:
        "This account is suspended. Redirecting securely...",
    };
  }

  if (
    accountStatus === "INACTIVE" ||
    user.is_active === false
  ) {
    return {
      destination:
        "/unauthorized?status=inactive",
      message:
        "This account is inactive. Redirecting securely...",
    };
  }

  if (
    accountStatus === "PENDING" ||
    accountStatus === "WAITING" ||
    accountStatus ===
      "UNDER_REVIEW" ||
    user.is_approved === false
  ) {
    return {
      destination:
        "/pending-approval?status=pending",
      message:
        "Your account is awaiting owner approval...",
    };
  }

  if (
    user.is_email_verified === false ||
    accountStatus === "UNVERIFIED"
  ) {
    return {
      destination:
        "/unauthorized?status=unverified",
      message:
        "Email verification is required. Redirecting securely...",
    };
  }

  if (
    user.can_access_platform === false
  ) {
    return {
      destination:
        "/unauthorized?status=forbidden",
      message:
        "Platform access is blocked. Redirecting securely...",
    };
  }

  return null;
}

function getErrorRedirectDecision(
  error: string | null,
  errorStatus: number | null,
): RedirectDecision {
  const message =
    error?.trim() ||
    "Unable to verify your session.";

  const normalized =
    message.toLowerCase();

  if (
    normalized.includes("rejected") ||
    normalized.includes("blocked") ||
    normalized.includes("disabled")
  ) {
    return {
      destination:
        `/unauthorized?status=rejected&reason=${encodeReason(
          message,
        )}`,
      message:
        "This account cannot access the platform. Redirecting securely...",
    };
  }

  if (
    normalized.includes("suspended")
  ) {
    return {
      destination:
        `/unauthorized?status=suspended&reason=${encodeReason(
          message,
        )}`,
      message:
        "This account is suspended. Redirecting securely...",
    };
  }

  if (
    normalized.includes("inactive")
  ) {
    return {
      destination:
        `/unauthorized?status=inactive&reason=${encodeReason(
          message,
        )}`,
      message:
        "This account is inactive. Redirecting securely...",
    };
  }

  if (
    normalized.includes("pending") ||
    normalized.includes("approval")
  ) {
    return {
      destination:
        "/pending-approval?status=pending",
      message:
        "Your account is awaiting owner approval...",
    };
  }

  if (
    normalized.includes("email") &&
    (
      normalized.includes(
        "not verified",
      ) ||
      normalized.includes(
        "unverified",
      ) ||
      normalized.includes(
        "verify",
      )
    )
  ) {
    return {
      destination:
        "/unauthorized?status=unverified",
      message:
        "Email verification is required. Redirecting securely...",
    };
  }

  if (errorStatus === 403) {
    return {
      destination:
        `/unauthorized?status=forbidden&reason=${encodeReason(
          message,
        )}`,
      message:
        "This account cannot access the platform. Redirecting securely...",
    };
  }

  return {
    destination: "/login",
    message:
      errorStatus === 401
        ? "Your session is missing or expired. Redirecting to login..."
        : "Unable to verify your session. Redirecting to login...",
  };
}

export function DashboardAuthGuard({
  children,
}: DashboardAuthGuardProps) {
  const router = useRouter();

  const {
    user,
    isLoading,
    error,
    errorStatus,
  } = useCurrentUser();

  const userDecision =
    user
      ? getUserRedirectDecision(
          user,
        )
      : null;

  const errorDecision =
    !isLoading &&
    !user
      ? getErrorRedirectDecision(
          error,
          errorStatus,
        )
      : null;

  const redirectDecision =
    userDecision ??
    errorDecision;

  const isAuthenticated =
    !isLoading &&
    Boolean(user) &&
    redirectDecision === null;

  useEffect(() => {
    if (!redirectDecision) {
      return;
    }

    router.replace(
      redirectDecision.destination,
    );
  }, [
    redirectDecision,
    router,
  ]);

  if (isAuthenticated) {
    return <>{children}</>;
  }

  const isRedirecting =
    redirectDecision !== null;

  return (
    <main
      aria-live="polite"
      aria-busy={!isRedirecting}
      className="midnight-page flex min-h-screen items-center justify-center p-5 text-white"
    >
      <section className="midnight-panel w-full max-w-md rounded-3xl p-8 text-center">
        {!isRedirecting ? (
          <div className="mx-auto h-16 w-16 animate-spin rounded-2xl border-4 border-blue-400/15 border-t-cyan-300" />
        ) : (
          <div className="midnight-pulse mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-amber-400/20 bg-amber-400/[0.06] text-lg font-black text-amber-300">
            403
          </div>
        )}

        <p className="mt-5 text-sm font-black text-white">
          {isRedirecting
            ? "Redirecting securely"
            : "Verifying secure access"}
        </p>

        <p className="mt-2 text-xs leading-5 text-slate-600">
          {redirectDecision?.message ??
            "Checking your secure session with Blue-Trading-AI..."}
        </p>
      </section>
    </main>
  );
}