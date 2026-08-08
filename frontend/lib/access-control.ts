export const USER_ROLES = {
  USER: "USER",
  ADMIN: "ADMIN",
  OWNER: "OWNER",
} as const;

export type UserRole =
  (typeof USER_ROLES)[keyof typeof USER_ROLES];

export const ACCESS_ROLES = {
  authenticated: [
    USER_ROLES.USER,
    USER_ROLES.ADMIN,
    USER_ROLES.OWNER,
  ],
  administration: [
    USER_ROLES.ADMIN,
    USER_ROLES.OWNER,
  ],
  monitoring: [
    USER_ROLES.ADMIN,
    USER_ROLES.OWNER,
  ],
  ownerOnly: [
    USER_ROLES.OWNER,
  ],
} as const;

const ROLE_HIERARCHY: Readonly<
  Record<UserRole, readonly UserRole[]>
> = {
  USER: [
    USER_ROLES.USER,
  ],
  ADMIN: [
    USER_ROLES.USER,
    USER_ROLES.ADMIN,
  ],
  OWNER: [
    USER_ROLES.USER,
    USER_ROLES.ADMIN,
    USER_ROLES.OWNER,
  ],
};

const VALID_USER_ROLES = new Set<string>(
  Object.values(USER_ROLES),
);

export function normalizeUserRole(
  value: unknown,
): string {
  return typeof value === "string"
    ? value.trim().toUpperCase()
    : "";
}

export function isUserRole(
  value: unknown,
): value is UserRole {
  return VALID_USER_ROLES.has(
    normalizeUserRole(value),
  );
}

export function getEffectiveRoles(
  role: unknown,
): readonly UserRole[] {
  const normalizedRole =
    normalizeUserRole(role);

  if (!isUserRole(normalizedRole)) {
    return [];
  }

  return ROLE_HIERARCHY[normalizedRole];
}

export function hasAllowedRole(
  currentRole: unknown,
  allowedRoles: readonly string[],
): boolean {
  const effectiveRoles =
    getEffectiveRoles(currentRole);

  if (effectiveRoles.length === 0) {
    return false;
  }

  const normalizedAllowedRoles =
    new Set<UserRole>();

  for (const role of allowedRoles) {
    const normalizedRole =
      normalizeUserRole(role);

    if (isUserRole(normalizedRole)) {
      normalizedAllowedRoles.add(
        normalizedRole,
      );
    }
  }

  if (normalizedAllowedRoles.size === 0) {
    return false;
  }

  return effectiveRoles.some((role) =>
    normalizedAllowedRoles.has(role),
  );
}

export function hasAnyAllowedRole(
  currentRoles: readonly unknown[],
  allowedRoles: readonly string[],
): boolean {
  if (
    currentRoles.length === 0 ||
    allowedRoles.length === 0
  ) {
    return false;
  }

  return currentRoles.some((role) =>
    hasAllowedRole(
      role,
      allowedRoles,
    ),
  );
}

export function isAdminRole(
  role: unknown,
): boolean {
  return hasAllowedRole(
    role,
    [
      USER_ROLES.ADMIN,
    ],
  );
}

export function isOwnerRole(
  role: unknown,
): boolean {
  return hasAllowedRole(
    role,
    ACCESS_ROLES.ownerOnly,
  );
}

export function canAccessMonitoring(
  role: unknown,
): boolean {
  return hasAllowedRole(
    role,
    [
      USER_ROLES.ADMIN,
    ],
  );
}