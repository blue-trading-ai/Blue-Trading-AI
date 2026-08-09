"use client";

import {
  useCallback,
  useEffect,
  useState,
} from "react";

import { ApiError } from "@/lib/api";
import {
  type AuthenticatedUser,
  validateCurrentSession,
} from "@/lib/auth-session";

type CurrentUserState = {
  user: AuthenticatedUser | null;
  isLoading: boolean;
  error: string | null;
  errorStatus: number | null;
  errorDetails: unknown;
  refreshUser: () => Promise<void>;
};

type CurrentUserSnapshot = Omit<
  CurrentUserState,
  "refreshUser"
>;

type CurrentUserListener = (
  snapshot: CurrentUserSnapshot,
) => void;

const CACHE_DURATION_MS = 15_000;

let sharedSnapshot: CurrentUserSnapshot = {
  user: null,
  isLoading: true,
  error: null,
  errorStatus: null,
  errorDetails: null,
};

let lastCompletedAt = 0;
let requestVersion = 0;

let activeRequest:
  | Promise<void>
  | null = null;

let activeRequestVersion:
  | number
  | null = null;

const listeners =
  new Set<CurrentUserListener>();

function publishSnapshot(
  nextSnapshot: CurrentUserSnapshot,
): void {
  sharedSnapshot = nextSnapshot;

  for (const listener of listeners) {
    listener(sharedSnapshot);
  }
}

function subscribe(
  listener: CurrentUserListener,
): () => void {
  listeners.add(listener);

  listener(sharedSnapshot);

  return () => {
    listeners.delete(listener);
  };
}

function getErrorMessage(
  error: unknown,
): string {
  if (
    error instanceof Error &&
    error.message.trim()
  ) {
    return error.message;
  }

  return "Unable to load the current user.";
}

function cacheIsFresh(): boolean {
  return (
    lastCompletedAt > 0 &&
    Date.now() - lastCompletedAt <
      CACHE_DURATION_MS
  );
}

async function performCurrentUserRequest(
  currentVersion: number,
): Promise<void> {
  try {
    const currentUser =
      await validateCurrentSession();

    if (
      currentVersion !==
      requestVersion
    ) {
      return;
    }

    publishSnapshot({
      user: currentUser,
      isLoading: false,
      error: null,
      errorStatus: null,
      errorDetails: null,
    });
  } catch (requestError) {
    if (
      currentVersion !==
      requestVersion
    ) {
      return;
    }

    if (
      requestError instanceof ApiError
    ) {
      publishSnapshot({
        user: null,
        isLoading: false,
        error:
          requestError.message ||
          "Unable to load the current user.",
        errorStatus:
          requestError.status,
        errorDetails:
          requestError.details,
      });

      return;
    }

    publishSnapshot({
      user: null,
      isLoading: false,
      error:
        getErrorMessage(
          requestError,
        ),
      errorStatus: null,
      errorDetails:
        requestError,
    });
  } finally {
    if (
      currentVersion ===
      requestVersion
    ) {
      lastCompletedAt =
        Date.now();
    }

    if (
      activeRequestVersion ===
      currentVersion
    ) {
      activeRequest = null;
      activeRequestVersion = null;
    }
  }
}

async function loadCurrentUser(
  forceRefresh = false,
): Promise<void> {
  if (activeRequest) {
    return activeRequest;
  }

  if (
    !forceRefresh &&
    cacheIsFresh()
  ) {
    return;
  }

  const currentVersion =
    requestVersion + 1;

  requestVersion =
    currentVersion;

  publishSnapshot({
    ...sharedSnapshot,
    isLoading: true,
    error: null,
    errorStatus: null,
    errorDetails: null,
  });

  activeRequestVersion =
    currentVersion;

  const requestPromise =
    performCurrentUserRequest(
      currentVersion,
    );

  activeRequest =
    requestPromise;

  return requestPromise;
}

export function clearCurrentUserCache(): void {
  requestVersion += 1;
  activeRequest = null;
  activeRequestVersion = null;
  lastCompletedAt = 0;

  publishSnapshot({
    user: null,
    isLoading: true,
    error: null,
    errorStatus: null,
    errorDetails: null,
  });
}

export function setCurrentUserCache(
  user: AuthenticatedUser,
): void {
  requestVersion += 1;
  activeRequest = null;
  activeRequestVersion = null;
  lastCompletedAt = Date.now();

  publishSnapshot({
    user,
    isLoading: false,
    error: null,
    errorStatus: null,
    errorDetails: null,
  });
}

export function useCurrentUser(): CurrentUserState {
  const [snapshot, setSnapshot] =
    useState(
      sharedSnapshot,
    );

  useEffect(() => {
    const unsubscribe =
      subscribe(setSnapshot);

    queueMicrotask(() => {
      void loadCurrentUser(false);
    });

    return unsubscribe;
  }, []);

  const refreshUser = useCallback(
    async (): Promise<void> => {
      await loadCurrentUser(true);
    },
    [],
  );

  return {
    ...snapshot,
    refreshUser,
  };
}