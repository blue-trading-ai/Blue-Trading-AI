"use client";

import { useMemo } from "react";

import { useCurrentUser } from "@/hooks/use-current-user";
import {
  getNavigationForRole,
  type NavigationItem,
} from "@/lib/navigation";

type UseNavigationResult = {
  items: NavigationItem[];
  role: string | null;
  isLoading: boolean;
  error: string | null;
};

export function useNavigation(): UseNavigationResult {
  const {
    user,
    isLoading,
    error,
  } = useCurrentUser();

  const role =
    typeof user?.role === "string"
      ? user.role.trim().toUpperCase()
      : null;

  const items = useMemo(
    () =>
      getNavigationForRole(role),
    [role],
  );

  return {
    items,
    role,
    isLoading,
    error,
  };
}