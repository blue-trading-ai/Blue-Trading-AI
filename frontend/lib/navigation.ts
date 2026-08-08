import {
  ACCESS_ROLES,
  USER_ROLES,
} from "@/lib/access-control";

export type NavigationItem = {
  label: string;
  href: string;
  icon:
    | "dashboard"
    | "analysis"
    | "signals"
    | "structure"
    | "performance"
    | "history"
    | "news"
    | "monitoring"
    | "admin"
    | "settings";
  allowedRoles: readonly string[];
};

export const NAVIGATION_ITEMS: readonly NavigationItem[] = [
  {
    label: "Dashboard",
    href: "/dashboard",
    icon: "dashboard",
    allowedRoles: ACCESS_ROLES.authenticated,
  },
  {
    label: "Market Analysis",
    href: "/analysis",
    icon: "analysis",
    allowedRoles: ACCESS_ROLES.authenticated,
  },
  {
    label: "Signals",
    href: "/signals",
    icon: "signals",
    allowedRoles: ACCESS_ROLES.authenticated,
  },
  {
    label: "Market Structure",
    href: "/market-structure",
    icon: "structure",
    allowedRoles: ACCESS_ROLES.authenticated,
  },
  {
    label: "Performance",
    href: "/performance",
    icon: "performance",
    allowedRoles: ACCESS_ROLES.authenticated,
  },
  {
    label: "Trade History",
    href: "/history",
    icon: "history",
    allowedRoles: ACCESS_ROLES.authenticated,
  },
  {
    label: "Market News",
    href: "/news",
    icon: "news",
    allowedRoles: ACCESS_ROLES.authenticated,
  },
  {
    label: "System Monitoring",
    href: "/monitoring",
    icon: "monitoring",
    allowedRoles: ACCESS_ROLES.monitoring,
  },
  {
    label: "Admin",
    href: "/admin",
    icon: "admin",
    allowedRoles: ACCESS_ROLES.administration,
  },
  {
    label: "Settings",
    href: "/settings",
    icon: "settings",
    allowedRoles: ACCESS_ROLES.authenticated,
  },
] as const;

export function getNavigationForRole(
  role: unknown,
): NavigationItem[] {
  const normalizedRole =
    typeof role === "string"
      ? role.trim().toUpperCase()
      : "";

  if (!normalizedRole) {
    return [];
  }

  return NAVIGATION_ITEMS.filter((item) =>
    item.allowedRoles.includes(
      normalizedRole,
    ),
  );
}

export function isKnownRole(
  role: unknown,
): boolean {
  const normalizedRole =
    typeof role === "string"
      ? role.trim().toUpperCase()
      : "";

  return [
    USER_ROLES.USER,
    USER_ROLES.ADMIN,
    USER_ROLES.OWNER,
  ].includes(
    normalizedRole as
      | typeof USER_ROLES.USER
      | typeof USER_ROLES.ADMIN
      | typeof USER_ROLES.OWNER,
  );
}