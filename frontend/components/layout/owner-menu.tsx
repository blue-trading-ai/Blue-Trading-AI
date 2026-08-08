"use client";

import {
  Activity,
  ChevronDown,
  LogOut,
  Settings,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { useRouter } from "next/navigation";
import {
  useEffect,
  useRef,
  useState,
} from "react";

import { useCurrentUser } from "@/hooks/use-current-user";
import {
  ACCESS_ROLES,
  hasAllowedRole,
  isOwnerRole,
} from "@/lib/access-control";
import { logout } from "@/lib/auth";

function getInitials(
  fullName?: string | null,
  email?: string | null,
): string {
  const resolvedName = String(
    fullName || "",
  ).trim();

  if (resolvedName) {
    return resolvedName
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) =>
        part.charAt(0),
      )
      .join("")
      .toUpperCase();
  }

  const emailName = String(
    email || "",
  )
    .split("@")[0]
    .replace(
      /[^a-zA-Z0-9]+/g,
      " ",
    )
    .trim();

  if (!emailName) {
    return "BT";
  }

  return emailName
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) =>
      part.charAt(0),
    )
    .join("")
    .toUpperCase();
}

function normalizeRole(
  role: unknown,
): string {
  return typeof role === "string" &&
    role.trim()
    ? role.trim().toUpperCase()
    : "USER";
}

function getRoleLabel(
  role: string,
): string {
  if (role === "OWNER") {
    return "Platform Owner";
  }

  if (role === "ADMIN") {
    return "Administrator";
  }

  return "Approved User";
}

function normalizeStatus(
  status: unknown,
): string {
  return typeof status === "string" &&
    status.trim()
    ? status.trim().toUpperCase()
    : "";
}

type AccountStatusTone =
  | "healthy"
  | "pending"
  | "blocked";

type AccountStatusPresentation = {
  label: string;
  tone: AccountStatusTone;
  dotClassName: string;
  textClassName: string;
};

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
      dotClassName:
        "bg-rose-400",
      textClassName:
        "text-rose-300",
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
      dotClassName:
        "bg-amber-300",
      textClassName:
        "text-amber-300",
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
      dotClassName:
        "bg-amber-300",
      textClassName:
        "text-amber-300",
    };
  }

  return {
    label:
      normalized || "ACTIVE",
    tone: "healthy",
    dotClassName:
      "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]",
    textClassName:
      "text-emerald-300",
  };
}

export function OwnerMenu() {
  const router = useRouter();

  const menuRef =
    useRef<HTMLDivElement | null>(
      null,
    );

  const triggerRef =
    useRef<HTMLButtonElement | null>(
      null,
    );

  const firstItemRef =
    useRef<HTMLButtonElement | null>(
      null,
    );

  const {
    user,
    isLoading,
    error,
  } = useCurrentUser();

  const [isOpen, setIsOpen] =
    useState(false);

  const [isSigningOut, setIsSigningOut] =
    useState(false);

  const displayName =
    user?.full_name?.trim() ||
    user?.username?.trim() ||
    user?.email?.split("@")[0] ||
    "Blue-Trading-AI User";

  const email =
    user?.email ||
    "User information unavailable";

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

  const role =
    isOwner
      ? "OWNER"
      : isPrivileged
        ? "ADMIN"
        : normalizeRole(
            user?.role,
          );

  const roleLabel =
    getRoleLabel(role);

  const initials =
    getInitials(
      user?.full_name ||
        user?.username,
      user?.email,
    );

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

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const triggerButton =
      triggerRef.current;

    function handleEscape(
      event: KeyboardEvent,
    ) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }

    function handlePointerDown(
      event: MouseEvent,
    ) {
      if (
        menuRef.current &&
        !menuRef.current.contains(
          event.target as Node,
        )
      ) {
        setIsOpen(false);
      }
    }

    document.addEventListener(
      "keydown",
      handleEscape,
    );

    document.addEventListener(
      "mousedown",
      handlePointerDown,
    );

    window.setTimeout(() => {
      firstItemRef.current?.focus();
    }, 0);

    return () => {
      document.removeEventListener(
        "keydown",
        handleEscape,
      );

      document.removeEventListener(
        "mousedown",
        handlePointerDown,
      );

      triggerButton?.focus();
    };
  }, [isOpen]);

  function navigateTo(
    path: string,
  ) {
    setIsOpen(false);
    router.push(path);
  }

  async function handleLogout() {
    if (isSigningOut) {
      return;
    }

    try {
      setIsSigningOut(true);
      setIsOpen(false);
      await logout();
    } finally {
      router.replace("/login");
      router.refresh();
    }
  }

  return (
    <div
      ref={menuRef}
      className="relative"
    >
      <button
        ref={triggerRef}
        type="button"
        aria-expanded={isOpen}
        aria-haspopup="menu"
        aria-controls="account-menu"
        aria-label="Open account menu"
        disabled={
          isLoading ||
          isSigningOut ||
          !user
        }
        onClick={() =>
          setIsOpen(
            (current) => !current,
          )
        }
        className="group flex items-center gap-3 rounded-xl border border-blue-400/10 bg-blue-500/[0.04] px-2.5 py-2 text-left transition hover:border-cyan-300/20 hover:bg-blue-500/[0.08] hover:shadow-[0_0_20px_rgba(37,99,235,0.16)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/50 disabled:cursor-wait disabled:opacity-70 sm:px-3"
      >
        <div className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-blue-400/20 bg-gradient-to-br from-blue-600/30 to-cyan-400/10 text-xs font-black text-cyan-200">
          {isLoading
            ? "…"
            : initials}

          <span
            className={`absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full border-2 border-[#07101f] ${accountStatus.dotClassName}`}
            data-status-tone={
              accountStatus.tone
            }
            aria-hidden="true"
          />
        </div>

        <div className="hidden min-w-0 sm:block">
          <p className="max-w-32 truncate text-xs font-black text-slate-100 transition group-hover:text-white">
            {isLoading
              ? "Loading user..."
              : displayName}
          </p>

          <p className="mt-0.5 max-w-32 truncate text-[10px] font-semibold text-slate-600">
            {isLoading
              ? "Validating session"
              : roleLabel}
          </p>
        </div>

        <ChevronDown
          className={`hidden h-4 w-4 shrink-0 text-slate-700 transition sm:block ${
            isOpen
              ? "rotate-180 text-cyan-300"
              : "group-hover:text-cyan-300"
          }`}
          aria-hidden="true"
        />
      </button>

      {isOpen &&
      user ? (
        <div
          id="account-menu"
          role="menu"
          aria-label="Account menu"
          className="midnight-panel absolute right-0 top-[calc(100%+0.75rem)] z-40 w-72 rounded-2xl p-2 shadow-[0_24px_70px_rgba(0,0,0,0.48)]"
        >
          <div className="rounded-xl border border-blue-400/10 bg-blue-500/[0.035] p-4">
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
              Signed in as
            </p>

            <p className="mt-2 truncate text-sm font-black text-white">
              {displayName}
            </p>

            <p className="mt-1 break-all text-[10px] leading-4 text-slate-600">
              {email}
            </p>

            <div className="mt-3 flex flex-wrap items-center gap-2">
              {isPrivileged ? (
                <ShieldCheck
                  className="h-3.5 w-3.5 text-cyan-300"
                  aria-hidden="true"
                />
              ) : (
                <UserRound
                  className="h-3.5 w-3.5 text-emerald-300"
                  aria-hidden="true"
                />
              )}

              <p
                className={`text-[10px] font-bold uppercase tracking-[0.14em] ${
                  isPrivileged
                    ? "text-cyan-300"
                    : "text-emerald-300"
                }`}
              >
                {role}
              </p>

              <span className="text-slate-800">
                ·
              </span>

              <p
                className={`text-[10px] font-bold uppercase tracking-[0.12em] ${accountStatus.textClassName}`}
                data-status-tone={
                  accountStatus.tone
                }
              >
                {accountStatus.label}
              </p>
            </div>

            {error ? (
              <p className="mt-3 rounded-lg border border-rose-400/10 bg-rose-400/[0.04] px-3 py-2 text-[10px] leading-4 text-rose-300">
                Session details may be incomplete.
              </p>
            ) : null}
          </div>

          <div className="mt-2 space-y-1">
            <button
              ref={firstItemRef}
              type="button"
              role="menuitem"
              onClick={() =>
                navigateTo(
                  "/settings",
                )
              }
              className="flex w-full items-center justify-between rounded-xl px-4 py-3 text-left text-xs font-bold text-slate-400 transition hover:bg-blue-500/[0.06] hover:text-cyan-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/40"
            >
              <span className="flex items-center gap-3">
                <Settings
                  className="h-4 w-4"
                  aria-hidden="true"
                />

                Account settings
              </span>

              <span className="text-slate-700">
                ›
              </span>
            </button>

            {isPrivileged ? (
              <>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() =>
                    navigateTo(
                      "/admin",
                    )
                  }
                  className="flex w-full items-center justify-between rounded-xl px-4 py-3 text-left text-xs font-bold text-slate-400 transition hover:bg-blue-500/[0.06] hover:text-cyan-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/40"
                >
                  <span className="flex items-center gap-3">
                    <ShieldCheck
                      className="h-4 w-4"
                      aria-hidden="true"
                    />

                    Admin control
                  </span>

                  <span className="text-slate-700">
                    ›
                  </span>
                </button>

                <button
                  type="button"
                  role="menuitem"
                  onClick={() =>
                    navigateTo(
                      "/monitoring",
                    )
                  }
                  className="flex w-full items-center justify-between rounded-xl px-4 py-3 text-left text-xs font-bold text-slate-400 transition hover:bg-blue-500/[0.06] hover:text-cyan-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/40"
                >
                  <span className="flex items-center gap-3">
                    <Activity
                      className="h-4 w-4"
                      aria-hidden="true"
                    />

                    System monitoring
                  </span>

                  <span className="text-slate-700">
                    ›
                  </span>
                </button>
              </>
            ) : null}

            <div className="my-1 border-t border-white/5" />

            <button
              type="button"
              role="menuitem"
              disabled={isSigningOut}
              onClick={() =>
                void handleLogout()
              }
              className="flex w-full items-center justify-between rounded-xl px-4 py-3 text-left text-xs font-black text-rose-300 transition hover:bg-rose-400/[0.07] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-300/40 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <span className="flex items-center gap-3">
                <LogOut
                  className="h-4 w-4"
                  aria-hidden="true"
                />

                {isSigningOut
                  ? "Signing out..."
                  : "Sign out"}
              </span>

              <span className="text-rose-400">
                →
              </span>
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}