"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useCurrentUser } from "@/hooks/use-current-user";
import {
  getNavigationForRole,
  type NavigationItem,
} from "@/lib/navigation";

type NavigationMenuProps = {
  onNavigate?: () => void;
};

type NavigationIconProps = {
  icon: NavigationItem["icon"];
};

function NavigationIcon({
  icon,
}: NavigationIconProps) {
  const commonProps = {
    width: 19,
    height: 19,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };

  const paths: Record<
    NavigationItem["icon"],
    React.ReactNode
  > = {
    dashboard: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
      </>
    ),
    analysis: (
      <>
        <path d="M4 19V9" />
        <path d="M10 19V5" />
        <path d="M16 19v-7" />
        <path d="M22 19H2" />
      </>
    ),
    signals: (
      <>
        <path d="M5 12.5 9 16l10-10" />
        <path d="M4 5h5" />
        <path d="M4 19h16" />
      </>
    ),
    structure: (
      <>
        <path d="M4 18 9 13l4 3 7-9" />
        <circle cx="4" cy="18" r="1" />
        <circle cx="9" cy="13" r="1" />
        <circle cx="13" cy="16" r="1" />
        <circle cx="20" cy="7" r="1" />
      </>
    ),
    performance: (
      <>
        <path d="M4 19V10" />
        <path d="M10 19V6" />
        <path d="M16 19v-4" />
        <path d="M22 19H2" />
      </>
    ),
    history: (
      <>
        <path d="M3 12a9 9 0 1 0 3-6.7" />
        <path d="M3 4v5h5" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    news: (
      <>
        <path d="M5 4h14v16H5z" />
        <path d="M8 8h8" />
        <path d="M8 12h8" />
        <path d="M8 16h5" />
      </>
    ),
    monitoring: (
      <>
        <path d="M3 12h4l2-5 4 10 2-5h6" />
        <path d="M4 4h16v16H4z" />
      </>
    ),
    admin: (
      <>
        <path d="M12 3 4 7v5c0 5 3.4 8.4 8 9 4.6-.6 8-4 8-9V7z" />
        <path d="M9.5 12 11 13.5l3.5-3.5" />
      </>
    ),
    settings: (
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3V2.8h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" />
      </>
    ),
  };

  return (
    <svg {...commonProps}>
      {paths[icon]}
    </svg>
  );
}

function isRouteActive(
  pathname: string,
  href: string,
): boolean {
  return (
    pathname === href ||
    pathname.startsWith(`${href}/`)
  );
}

export function NavigationMenu({
  onNavigate,
}: NavigationMenuProps) {
  const pathname = usePathname();

  const {
    user,
    isLoading,
  } = useCurrentUser();

  if (isLoading) {
    return (
      <nav
        aria-label="Loading navigation"
        className="space-y-2"
      >
        {Array.from({ length: 7 }).map(
          (_, index) => (
            <div
              key={index}
              className="h-11 animate-pulse rounded-xl border border-blue-400/[0.06] bg-blue-500/[0.03]"
            />
          ),
        )}
      </nav>
    );
  }

  const items = getNavigationForRole(
    user?.role,
  );

  return (
    <nav
      aria-label="Main navigation"
      className="space-y-1.5"
    >
      {items.map((item) => {
        const active = isRouteActive(
          pathname,
          item.href,
        );

        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={
              active ? "page" : undefined
            }
            className={`group flex items-center gap-3 rounded-xl border px-3.5 py-3 text-sm font-bold transition ${
              active
                ? "border-cyan-300/20 bg-gradient-to-r from-blue-600/20 to-cyan-300/[0.06] text-cyan-100 shadow-[0_0_20px_rgba(34,211,238,0.07)]"
                : "border-transparent text-slate-500 hover:border-blue-400/10 hover:bg-blue-500/[0.04] hover:text-slate-200"
            }`}
          >
            <span
              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition ${
                active
                  ? "bg-cyan-300/[0.09] text-cyan-300"
                  : "bg-blue-500/[0.035] text-slate-600 group-hover:text-cyan-300"
              }`}
            >
              <NavigationIcon
                icon={item.icon}
              />
            </span>

            <span className="truncate">
              {item.label}
            </span>

            {active ? (
              <span className="ml-auto h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-300 shadow-[0_0_9px_rgba(34,211,238,0.85)]" />
            ) : null}
          </Link>
        );
      })}
    </nav>
  );
}