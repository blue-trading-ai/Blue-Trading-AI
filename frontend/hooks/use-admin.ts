"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import { ApiError } from "@/lib/api";
import {
  getAdminDashboard,
  updateAdminUser,
  type AdminDashboardData,
} from "@/lib/admin-service";

type AdminAction =
  | "loading"
  | "approving"
  | "rejecting"
  | "updating-mode"
  | null;

type UseAdminResult = {
  data: AdminDashboardData | null;
  isLoading: boolean;
  action: AdminAction;
  error: string | null;
  errorStatus: number | null;
  errorDetails: unknown;
  lastUpdated: Date | null;
  load: (
    approvalStatus: string,
  ) => Promise<AdminDashboardData | null>;
  approveUser: (
    userId: string,
    approvalStatus: string,
  ) => Promise<boolean>;
  rejectUser: (
    userId: string,
    approvalStatus: string,
  ) => Promise<boolean>;
  updateSystemMode: (
    mode: string,
    approvalStatus: string,
  ) => Promise<boolean>;
  clear: () => void;
};

type LoadOptions = {
  showLoadingAction: boolean;
  preserveExistingData: boolean;
};

function getErrorMessage(
  error: unknown,
  fallback: string,
): string {
  if (
    error instanceof Error &&
    error.message.trim()
  ) {
    return error.message;
  }

  return fallback;
}

export function useAdmin(): UseAdminResult {
  const [data, setData] =
    useState<AdminDashboardData | null>(null);

  const [isLoading, setIsLoading] =
    useState(false);

  const [action, setAction] =
    useState<AdminAction>(null);

  const [error, setError] =
    useState<string | null>(null);

  const [errorStatus, setErrorStatus] =
    useState<number | null>(null);

  const [errorDetails, setErrorDetails] =
    useState<unknown>(null);

  const [lastUpdated, setLastUpdated] =
    useState<Date | null>(null);

  const controllerRef =
    useRef<AbortController | null>(null);

  const requestIdRef = useRef(0);
  const isMountedRef = useRef(false);
  const mutationInProgressRef =
    useRef(false);

  const clearError = useCallback(() => {
    setError(null);
    setErrorStatus(null);
    setErrorDetails(null);
  }, []);

  const setRequestError = useCallback(
    (
      requestError: unknown,
      fallback: string,
    ) => {
      setError(
        getErrorMessage(
          requestError,
          fallback,
        ),
      );

      if (requestError instanceof ApiError) {
        setErrorStatus(
          requestError.status,
        );
        setErrorDetails(
          requestError.details,
        );
      } else {
        setErrorStatus(null);
        setErrorDetails(requestError);
      }
    },
    [],
  );

  const loadAdminData = useCallback(
    async (
      approvalStatus: string,
      options: LoadOptions,
    ): Promise<AdminDashboardData | null> => {
      controllerRef.current?.abort();

      const controller =
        new AbortController();

      controllerRef.current =
        controller;

      const requestId =
        requestIdRef.current + 1;

      requestIdRef.current = requestId;

      if (isMountedRef.current) {
        setIsLoading(true);
        clearError();

        if (
          options.showLoadingAction &&
          !mutationInProgressRef.current
        ) {
          setAction("loading");
        }
      }

      try {
        const result =
          await getAdminDashboard(
            approvalStatus,
            controller.signal,
          );

        if (
          !isMountedRef.current ||
          controller.signal.aborted ||
          requestId !== requestIdRef.current
        ) {
          return null;
        }

        setData(result);
        setLastUpdated(new Date());

        return result;
      } catch (requestError) {
        if (
          !isMountedRef.current ||
          controller.signal.aborted ||
          requestId !== requestIdRef.current
        ) {
          return null;
        }

        setRequestError(
          requestError,
          "Unable to load admin data.",
        );

        if (!options.preserveExistingData) {
          setData(null);
          setLastUpdated(null);
        }

        return null;
      } finally {
        if (
          isMountedRef.current &&
          !controller.signal.aborted &&
          requestId === requestIdRef.current
        ) {
          setIsLoading(false);

          if (
            options.showLoadingAction &&
            !mutationInProgressRef.current
          ) {
            setAction(null);
          }
        }
      }
    },
    [
      clearError,
      setRequestError,
    ],
  );

  const load = useCallback(
    async (
      approvalStatus: string,
    ): Promise<AdminDashboardData | null> =>
      loadAdminData(
        approvalStatus,
        {
          showLoadingAction: true,
          preserveExistingData: false,
        },
      ),
    [loadAdminData],
  );

  const approveUser = useCallback(
    async (
      userId: string,
      approvalStatus: string,
    ): Promise<boolean> => {
      const normalizedUserId =
        userId.trim();

      if (!normalizedUserId) {
        setError(
          "A valid user ID is required.",
        );
        setErrorStatus(400);
        setErrorDetails(null);
        return false;
      }

      mutationInProgressRef.current = true;
      setAction("approving");
      clearError();

      try {
        await updateAdminUser(
          normalizedUserId,
          "approve",
        );

        const refreshed =
          await loadAdminData(
            approvalStatus,
            {
              showLoadingAction: false,
              preserveExistingData: true,
            },
          );

        return refreshed !== null;
      } catch (requestError) {
        if (isMountedRef.current) {
          setRequestError(
            requestError,
            "Unable to approve user.",
          );
        }

        return false;
      } finally {
        mutationInProgressRef.current =
          false;

        if (isMountedRef.current) {
          setAction(null);
          setIsLoading(false);
        }
      }
    },
    [
      clearError,
      loadAdminData,
      setRequestError,
    ],
  );

  const rejectUser = useCallback(
    async (
      userId: string,
      approvalStatus: string,
    ): Promise<boolean> => {
      const normalizedUserId =
        userId.trim();

      if (!normalizedUserId) {
        setError(
          "A valid user ID is required.",
        );
        setErrorStatus(400);
        setErrorDetails(null);
        return false;
      }

      mutationInProgressRef.current = true;
      setAction("rejecting");
      clearError();

      try {
        await updateAdminUser(
          normalizedUserId,
          "reject",
        );

        const refreshed =
          await loadAdminData(
            approvalStatus,
            {
              showLoadingAction: false,
              preserveExistingData: true,
            },
          );

        return refreshed !== null;
      } catch (requestError) {
        if (isMountedRef.current) {
          setRequestError(
            requestError,
            "Unable to reject user.",
          );
        }

        return false;
      } finally {
        mutationInProgressRef.current =
          false;

        if (isMountedRef.current) {
          setAction(null);
          setIsLoading(false);
        }
      }
    },
    [
      clearError,
      loadAdminData,
      setRequestError,
    ],
  );

  const updateSystemMode =
    useCallback(
      async (
        mode: string,
        approvalStatus: string,
      ): Promise<boolean> => {
        void mode;
        void approvalStatus;

        clearError();

        setError(
          "System-mode changes are unavailable because the backend does not expose a confirmed endpoint.",
        );
        setErrorStatus(501);
        setErrorDetails({
          feature:
            "admin-system-mode",
          enabled: false,
        });

        return false;
      },
      [clearError],
    );

  const clear = useCallback(() => {
    controllerRef.current?.abort();
    controllerRef.current = null;

    requestIdRef.current += 1;
    mutationInProgressRef.current = false;

    setData(null);
    setError(null);
    setErrorStatus(null);
    setErrorDetails(null);
    setLastUpdated(null);
    setIsLoading(false);
    setAction(null);
  }, []);

  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;
      mutationInProgressRef.current = false;
      requestIdRef.current += 1;

      controllerRef.current?.abort();
      controllerRef.current = null;
    };
  }, []);

  return {
    data,
    isLoading,
    action,
    error,
    errorStatus,
    errorDetails,
    lastUpdated,
    load,
    approveUser,
    rejectUser,
    updateSystemMode,
    clear,
  };
}