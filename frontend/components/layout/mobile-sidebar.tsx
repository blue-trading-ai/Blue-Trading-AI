"use client";

import Link from "next/link";
import {
  useEffect,
  useRef,
  useState,
} from "react";
import { usePathname } from "next/navigation";

import { useCurrentUser } from "@/hooks/use-current-user";
import {
  ACCESS_ROLES,
  hasAllowedRole,
} from "@/lib/access-control";

type NavigationItem = {
  label: string;
  href: string;
};

const navigationItems: NavigationItem[] = [
  {
    label: "Dashboard",
    href: "/dashboard",
  },
  {
    label: "Live Analysis",
    href: "/analysis",
  },
  {
    label: "Trading Signals",
    href: "/signals",
  },
  {
    label: "Market Structure",
    href: "/market-structure",
  },
  {
    label: "Performance",
    href: "/performance",
  },
  {
    label: "Signal History",
    href: "/history",
  },
  {
    label: "Economic News",
    href: "/news",
  },
];

const privilegedManagementItems: NavigationItem[] = [
  {
    label: "Admin Dashboard",
    href: "/admin",
  },
  {
    label: "Monitoring",
    href: "/monitoring",
  },
];

const accountItems: NavigationItem[] = [
  {
    label: "Settings",
    href: "/settings",
  },
];

function isActivePath(
  pathname: string,
  href: string,
): boolean {
  return (
    pathname === href ||
    pathname.startsWith(`${href}/`)
  );
}

function MobileNavigationLink({
  item,
  pathname,
  onNavigate,
}: {
  item: NavigationItem;
  pathname: string;
  onNavigate: () => void;
}) {
  const active = isActivePath(
    pathname,
    item.href,
  );

  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={
        active ? "page" : undefined
      }
      className={`relative flex items-center rounded-xl px-4 py-3 text-sm font-semibold transition ${
        active
          ? "border border-cyan-300/20 bg-blue-500/10 text-cyan-200"
          : "border border-transparent text-slate-500 hover:border-blue-400/10 hover:bg-blue-500/[0.05] hover:text-white"
      }`}
    >
      {active ? (
        <span className="absolute bottom-2 left-0 top-2 w-1 rounded-r-full bg-gradient-to-b from-blue-400 to-cyan-300 shadow-[0_0_14px_rgba(34,211,238,0.65)]" />
      ) : null}

      <span className="relative z-10">
        {item.label}
      </span>
    </Link>
  );
}

export function MobileSidebar() {
  const pathname = usePathname();

  const {
    user,
    isLoading,
  } = useCurrentUser();

  const [isOpen, setIsOpen] =
    useState(false);

  const closeButtonRef =
    useRef<HTMLButtonElement | null>(
      null,
    );

  const triggerButtonRef =
    useRef<HTMLButtonElement | null>(
      null,
    );

  const canAccessManagement =
    !isLoading &&
    hasAllowedRole(
      user?.role,
      ACCESS_ROLES.administration,
    );

  const managementItems =
    canAccessManagement
      ? [
          ...privilegedManagementItems,
          ...accountItems,
        ]
      : accountItems;

  function closeMenu() {
    setIsOpen(false);
  }

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const previousOverflow =
      document.body.style.overflow;

    const triggerButton =
      triggerButtonRef.current;

    document.body.style.overflow =
      "hidden";

    const handleKeyDown = (
      event: KeyboardEvent,
    ) => {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    };

    window.addEventListener(
      "keydown",
      handleKeyDown,
    );

    window.setTimeout(() => {
      closeButtonRef.current?.focus();
    }, 0);

    return () => {
      document.body.style.overflow =
        previousOverflow;

      window.removeEventListener(
        "keydown",
        handleKeyDown,
      );

      triggerButton?.focus();
    };
  }, [isOpen]);

  return (
    <>
      <button
        ref={triggerButtonRef}
        type="button"
        aria-label="Open navigation menu"
        aria-expanded={isOpen}
        aria-controls="mobile-navigation-panel"
        onClick={() =>
          setIsOpen(true)
        }
        className="flex h-11 w-11 items-center justify-center rounded-xl border border-blue-400/15 bg-blue-500/[0.05] text-lg font-black text-cyan-200 transition hover:border-cyan-300/25 hover:bg-blue-500/[0.1] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/50 lg:hidden"
      >
        ☰
      </button>

      {isOpen ? (
        <div
          className="fixed inset-0 z-50 lg:hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Mobile navigation"
        >
          <button
            type="button"
            aria-label="Close navigation menu"
            onClick={closeMenu}
            className="absolute inset-0 bg-[#020617]/85 backdrop-blur-sm"
          />

          <aside
            id="mobile-navigation-panel"
            className="midnight-panel relative z-10 flex h-full w-[86%] max-w-sm flex-col border-y-0 border-l-0 p-5 shadow-[20px_0_70px_rgba(0,0,0,0.55)]"
          >
            <div className="flex items-center justify-between gap-4">
              <Link
                href="/dashboard"
                onClick={closeMenu}
                className="flex items-center gap-3"
              >
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-blue-400/30 bg-gradient-to-br from-blue-600/30 to-cyan-400/10 text-lg font-black text-cyan-200 shadow-[0_0_24px_rgba(37,99,235,0.22)]">
                  B
                </div>

                <div>
                  <p className="text-sm font-black tracking-tight text-white">
                    Blue-Trading-AI
                  </p>

                  <p className="mt-1 text-[9px] font-semibold uppercase tracking-[0.15em] text-slate-600">
                    Intelligence Before Execution
                  </p>
                </div>
              </Link>

              <button
                ref={closeButtonRef}
                type="button"
                aria-label="Close navigation menu"
                onClick={closeMenu}
                className="flex h-10 w-10 items-center justify-center rounded-xl border border-blue-400/10 bg-blue-500/[0.04] text-lg text-slate-500 transition hover:border-rose-400/20 hover:text-rose-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/50"
              >
                ×
              </button>
            </div>

            <div className="mt-8 overflow-y-auto pr-1">
              <p className="px-3 text-[10px] font-black uppercase tracking-[0.24em] text-slate-700">
                Workspace
              </p>

              <nav
                className="mt-3 space-y-1.5"
                aria-label="Workspace navigation"
              >
                {navigationItems.map(
                  (item) => (
                    <MobileNavigationLink
                      key={item.href}
                      item={item}
                      pathname={pathname}
                      onNavigate={
                        closeMenu
                      }
                    />
                  ),
                )}
              </nav>

              <p className="mt-8 px-3 text-[10px] font-black uppercase tracking-[0.24em] text-slate-700">
                Management
              </p>

              <nav
                className="mt-3 space-y-1.5"
                aria-label="Management navigation"
              >
                {isLoading ? (
                  <>
                    <div className="h-11 animate-pulse rounded-xl bg-blue-500/[0.035]" />
                    <div className="h-11 animate-pulse rounded-xl bg-blue-500/[0.035]" />
                  </>
                ) : (
                  managementItems.map(
                    (item) => (
                      <MobileNavigationLink
                        key={item.href}
                        item={item}
                        pathname={
                          pathname
                        }
                        onNavigate={
                          closeMenu
                        }
                      />
                    ),
                  )
                )}
              </nav>
            </div>

            <div className="mt-auto pt-5">
              <div className="rounded-2xl border border-emerald-400/10 bg-emerald-400/[0.04] p-4">
                <div className="flex items-center gap-2">
                  <span className="midnight-status-dot midnight-pulse h-2 w-2 rounded-full bg-emerald-400" />

                  <p className="text-xs font-black text-emerald-300">
                    System operational
                  </p>
                </div>

                <p className="mt-2 text-[11px] leading-5 text-slate-600">
                  Version 49 high-quality signal controls are active.
                </p>
              </div>
            </div>
          </aside>
        </div>
      ) : null}
    </>
  );
}