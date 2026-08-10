"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useCurrentUser } from "@/hooks/use-current-user";
import {
  hasAllowedRole,
  ACCESS_ROLES,
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
  if (href === "/") {
    return pathname === "/";
  }

  return (
    pathname === href ||
    pathname.startsWith(`${href}/`)
  );
}

function NavigationLink({
  label,
  href,
  active = false,
}: {
  label: string;
  href: string;
  active?: boolean;
}) {
  return (
    <Link
      href={href}
      aria-current={
        active ? "page" : undefined
      }
      className={`group relative flex items-center rounded-xl px-4 py-3 text-sm font-semibold transition ${
        active
          ? "border border-cyan-300/20 bg-blue-500/10 text-cyan-200 shadow-[0_0_24px_rgba(37,99,235,0.14)]"
          : "border border-transparent text-slate-500 hover:border-blue-400/10 hover:bg-blue-500/[0.05] hover:text-slate-100"
      }`}
    >
      {active ? (
        <span
          className="absolute inset-y-2 left-0 w-1 rounded-r-full bg-cyan-300 shadow-[0_0_14px_rgba(103,232,249,0.8)]"
          aria-hidden="true"
        />
      ) : null}

      <span className="relative z-10">
        {label}
      </span>

      <span
        className={`ml-auto h-1.5 w-1.5 rounded-full transition ${
          active
            ? "bg-cyan-300 shadow-[0_0_10px_rgba(34,211,238,0.8)]"
            : "bg-slate-800 group-hover:bg-blue-400"
        }`}
      />
    </Link>
  );
}

export function Sidebar() {
  const pathname =
    usePathname();

  const {
    user,
    isLoading,
  } = useCurrentUser();

  const canAccessManagement =
    !isLoading &&
    hasAllowedRole(
      user?.role,
      ACCESS_ROLES.administration,
    );

  const visibleManagementItems =
    canAccessManagement
      ? [
          ...privilegedManagementItems,
          ...accountItems,
        ]
      : accountItems;

  return (
    <aside className="hidden h-screen w-72 shrink-0 flex-col border-r border-blue-400/10 bg-[#050b16]/95 p-5 backdrop-blur-xl lg:flex">
      <Link
        href="/dashboard"
        className="flex items-center gap-3"
      >
        <div className="relative flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-blue-400/30 bg-gradient-to-br from-blue-600/20 to-cyan-400/10 p-1.5 shadow-[0_0_30px_rgba(37,99,235,0.28)]">
          <Image
            src="/blue-trading-ai-logo.png"
            alt="Blue-Trading-AI logo"
            width={64}
            height={64}
            priority
            className="h-full w-full object-contain"
          />
          <span className="absolute inset-0 rounded-2xl ring-1 ring-inset ring-white/5" />
        </div>

        <div className="min-w-0">
          <p className="truncate text-sm font-black tracking-tight text-white">
            Blue-Trading-AI
          </p>

          <p className="mt-1 truncate text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-600">
            Intelligence Before Execution
          </p>
        </div>
      </Link>

      <div className="mt-9">
        <p className="px-3 text-[10px] font-black uppercase tracking-[0.24em] text-slate-700">
          Workspace
        </p>

        <nav className="mt-3 space-y-1.5">
          {navigationItems.map(
            (item) => (
              <NavigationLink
                key={item.href}
                label={item.label}
                href={item.href}
                active={isActivePath(
                  pathname,
                  item.href,
                )}
              />
            ),
          )}
        </nav>
      </div>

      <div className="mt-8">
        <p className="px-3 text-[10px] font-black uppercase tracking-[0.24em] text-slate-700">
          Management
        </p>

        <nav className="mt-3 space-y-1.5">
          {isLoading ? (
            <>
              <div className="h-11 animate-pulse rounded-xl bg-blue-500/[0.035]" />
              <div className="h-11 animate-pulse rounded-xl bg-blue-500/[0.035]" />
            </>
          ) : (
            visibleManagementItems.map(
              (item) => (
                <NavigationLink
                  key={item.href}
                  label={item.label}
                  href={item.href}
                  active={isActivePath(
                    pathname,
                    item.href,
                  )}
                />
              ),
            )
          )}
        </nav>
      </div>

      <div className="mt-auto space-y-3">
        <div className="rounded-2xl border border-blue-400/10 bg-blue-500/[0.04] p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
                Daily Quality Target
              </p>

              <p className="mt-2 text-2xl font-black text-white">
                5
                <span className="ml-1 text-xs font-semibold text-slate-600">
                  signals
                </span>
              </p>
            </div>

            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-cyan-300/15 bg-cyan-300/[0.06] text-xs font-black text-cyan-200">
              HQ
            </div>
          </div>

          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-900">
            <div className="h-full w-1/2 rounded-full bg-gradient-to-r from-blue-500 to-cyan-300 shadow-[0_0_12px_rgba(34,211,238,0.4)]" />
          </div>

          <p className="mt-2 text-[10px] leading-4 text-slate-600">
            Maximum 10 signals per day. Quality over quantity.
          </p>
        </div>

        <div className="rounded-2xl border border-emerald-400/10 bg-emerald-400/[0.04] p-4">
          <div className="flex items-center gap-2">
            <span className="midnight-status-dot midnight-pulse h-2 w-2 rounded-full bg-emerald-400" />

            <p className="text-xs font-black text-emerald-300">
              System operational
            </p>
          </div>

          <p className="mt-2 text-[11px] leading-5 text-slate-600">
            API, monitoring and background processing are online.
          </p>
        </div>
      </div>
    </aside>
  );
}