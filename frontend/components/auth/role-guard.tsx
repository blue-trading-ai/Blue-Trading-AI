"use client";

import {
  type ReactNode,
  useEffect,
} from "react";
import { useRouter } from "next/navigation";

import { useCurrentUser } from "@/hooks/use-current-user";
import { hasAllowedRole } from "@/lib/access-control";

type RoleGuardProps = {
  children: ReactNode;
  allowedRoles: readonly string[];
  fallbackPath?: string;
};

type AccessDecision =
  | {
      status: "loading";
      destination: null;
      message: string;
    }
  | {
      status: "allowed";
      destination: null;
      message: string;
    }
  | {
      status: "redirect";
      destination: string;
      message: string;
    };

function normalizeRole(
  value: unknown,
): string | null {
  if (typeof value !== "string") {
    return null;
  }

  const normalized = value
    .trim()
    .toUpperCase();

  return normalized || null;
}

function normalizeStatus(
  value: unknown,
): string {
  return typeof value === "string"
    ? value.trim().toUpperCase()
    : "";
}

function getUserRoles(
  role: unknown,
  roles: unknown,
  isOwner: unknown,
): string[] {
  const normalizedRoles =
    Array.isArray(roles)
      ? roles
          .map(normalizeRole)
          .filter(
            (
              item,
            ): item is string =>
              item !== null,
          )
      : [];

  const primaryRole =
    normalizeRole(role);

  if (
    primaryRole &&
    !normalizedRoles.includes(
      primaryRole,
    )
  ) {
    normalizedRoles.push(
      primaryRole,
    );
  }

  if (
    isOwner === true &&
    !normalizedRoles.includes(
      "OWNER",
    )
  ) {
    normalizedRoles.unshift(
      "OWNER",
    );
  }

  if (normalizedRoles.length === 0) {
    normalizedRoles.push("USER");
  }

  return Array.from(
    new Set(normalizedRoles),
  );
}

function encodeReason(
  value: string,
): string {
  return encodeURIComponent(
    value.slice(0, 300),
  );
}

function getErrorDecision(
  error: string | null,
  errorStatus: number | null,
): AccessDecision {
  const message =
    error?.trim() ||
    "Unable to verify your account access.";

  const normalized =
    message.toLowerCase();

  if (
    normalized.includes("rejected") ||
    normalized.includes("blocked") ||
    normalized.includes("disabled")
  ) {
    return {
      status: "redirect",
      destination:
        `/unauthorized?status=rejected&reason=${encodeReason(
          message,
        )}`,
      message:
        "This account cannot access the platform.",
    };
  }

  if (
    normalized.includes("suspended")
  ) {
    return {
      status: "redirect",
      destination:
        `/unauthorized?status=suspended&reason=${encodeReason(
          message,
        )}`,
      message:
        "This account is suspended.",
    };
  }

  if (
    normalized.includes("inactive")
  ) {
    return {
      status: "redirect",
      destination:
        `/unauthorized?status=inactive&reason=${encodeReason(
          message,
        )}`,
      message:
        "This account is inactive.",
    };
  }

  if (
    normalized.includes("pending") ||
    normalized.includes("approval")
  ) {
    return {
      status: "redirect",
      destination:
        "/pending-approval?status=pending",
      message:
        "Owner approval is still pending.",
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
      status: "redirect",
      destination:
        "/unauthorized?status=unverified",
      message:
        "Email verification is required.",
    };
  }

  if (errorStatus === 403) {
    return {
      status: "redirect",
      destination:
        `/unauthorized?status=forbidden&reason=${encodeReason(
          message,
        )}`,
      message:
        "This account cannot access this section.",
    };
  }

  return {
    status: "redirect",
    destination: "/login",
    message:
      errorStatus === 401
        ? "Your session is missing or expired."
        : "Unable to verify your authenticated session.",
  };
}

function getFallbackDestination(
  fallbackPath: string,
): string {
  if (
    fallbackPath ===
    "/unauthorized"
  ) {
    return `${fallbackPath}?status=forbidden`;
  }

  const separator =
    fallbackPath.includes("?")
      ? "&"
      : "?";

  return `${fallbackPath}${separator}reason=${encodeReason(
    "This account does not have an allowed role for the requested page.",
  )}`;
}

export function RoleGuard({
  children,
  allowedRoles,
  fallbackPath = "/unauthorized",
}: RoleGuardProps) {
  const router = useRouter();

  const {
    user,
    isLoading,
    error,
    errorStatus,
  } = useCurrentUser();

  let decision: AccessDecision;

  if (isLoading) {
    decision = {
      status: "loading",
      destination: null,
      message:
        "Checking your Blue-Trading-AI role.",
    };
  } else if (!user) {
    decision = getErrorDecision(
      error,
      errorStatus,
    );
  } else {
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
      decision = {
        status: "redirect",
        destination:
          "/unauthorized?status=rejected",
        message:
          "This account cannot access the platform.",
      };
    } else if (
      accountStatus ===
      "SUSPENDED"
    ) {
      decision = {
        status: "redirect",
        destination:
          "/unauthorized?status=suspended",
        message:
          "This account is suspended.",
      };
    } else if (
      accountStatus ===
        "INACTIVE" ||
      user.is_active === false
    ) {
      decision = {
        status: "redirect",
        destination:
          "/unauthorized?status=inactive",
        message:
          "This account is inactive.",
      };
    } else if (
      accountStatus ===
        "PENDING" ||
      accountStatus ===
        "WAITING" ||
      accountStatus ===
        "UNDER_REVIEW" ||
      user.is_approved === false
    ) {
      decision = {
        status: "redirect",
        destination:
          "/pending-approval?status=pending",
        message:
          "Owner approval is still pending.",
      };
    } else if (
      user.is_email_verified ===
        false ||
      accountStatus ===
        "UNVERIFIED"
    ) {
      decision = {
        status: "redirect",
        destination:
          "/unauthorized?status=unverified",
        message:
          "Email verification is required.",
      };
    } else if (
      user.can_access_platform ===
      false
    ) {
      decision = {
        status: "redirect",
        destination:
          "/unauthorized?status=forbidden",
        message:
          "Platform access is blocked.",
      };
    } else {
      const userRoles =
        getUserRoles(
          user.role,
          user.roles,
          user.is_owner,
        );

      const hasAccess =
        userRoles.some((role) =>
          hasAllowedRole(
            role,
            allowedRoles,
          ),
        );

      decision = hasAccess
        ? {
            status: "allowed",
            destination: null,
            message:
              "Access permission confirmed.",
          }
        : {
            status: "redirect",
            destination:
              getFallbackDestination(
                fallbackPath,
              ),
            message:
              "This section requires a different approved role.",
          };
    }
  }

  const destination =
    decision.status ===
    "redirect"
      ? decision.destination
      : null;

  useEffect(() => {
    if (!destination) {
      return;
    }

    router.replace(destination);
  }, [
    destination,
    router,
  ]);

  if (
    decision.status ===
    "allowed"
  ) {
    return <>{children}</>;
  }

  return (
    <section
      aria-live="polite"
      aria-busy={
        decision.status ===
        "loading"
      }
      className="midnight-panel flex min-h-[420px] items-center justify-center rounded-3xl p-6"
    >
      <div className="text-center">
        {decision.status ===
        "loading" ? (
          <div className="mx-auto h-12 w-12 animate-spin rounded-full border-4 border-blue-400/15 border-t-cyan-300" />
        ) : (
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl border border-amber-400/20 bg-amber-400/[0.06] text-lg font-black text-amber-300">
            403
          </div>
        )}

        <p className="mt-5 text-sm font-black text-white">
          {decision.status ===
          "loading"
            ? "Verifying access permission"
            : "Redirecting securely"}
        </p>

        <p className="mt-2 text-xs leading-5 text-slate-600">
          {decision.message}
        </p>
      </div>
    </section>
  );
}