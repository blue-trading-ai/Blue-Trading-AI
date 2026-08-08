"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import type { TradingSignal } from "@/components/signals/signal-card";
import { ApiError } from "@/lib/api";
import { getApprovedSignals } from "@/lib/approved-signals-service";

type UseApprovedSignalsResult = {
  signals: TradingSignal[];
  total: number;
  isLoading: boolean;
  isRefreshing: boolean;
  error: string | null;
  errorStatus: number | null;
  errorDetails: unknown;
  lastUpdated: Date | null;
  refresh: () => Promise<void>;
};

function getErrorMessage(
  error: unknown,
): string {
  if (
    error instanceof Error &&
    error.message.trim()
  ) {
    return error.message;
  }

  return "Unable to load approved trading signals.";
}

export function useApprovedSignals(): UseApprovedSignalsResult {
  const [signals, setSignals] =
    useState<TradingSignal[]>([]);

  const [isLoading, setIsLoading] =
    useState(true);

  const [isRefreshing, setIsRefreshing] =
    useState(false);

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
  const hasLoadedRef = useRef(false);

  const loadSignals = useCallback(
    async (
      manualRefresh = false,
    ): Promise<void> => {
      controllerRef.current?.abort();

      const controller =
        new AbortController();

      controllerRef.current =
        controller;

      const requestId =
        requestIdRef.current + 1;

      requestIdRef.current =
        requestId;

      if (isMountedRef.current) {
        if (
          manualRefresh &&
          hasLoadedRef.current
        ) {
          setIsRefreshing(true);
        } else {
          setIsLoading(true);
        }

        setError(null);
        setErrorStatus(null);
        setErrorDetails(null);
      }

      try {
        const result =
          await getApprovedSignals(
            controller.signal,
          );

        if (
          !isMountedRef.current ||
          controller.signal.aborted ||
          requestId !==
            requestIdRef.current
        ) {
          return;
        }

        setSignals(result.signals);
        setLastUpdated(new Date());
        hasLoadedRef.current = true;
      } catch (requestError) {
        if (
          !isMountedRef.current ||
          controller.signal.aborted ||
          requestId !==
            requestIdRef.current
        ) {
          return;
        }

        setError(
          getErrorMessage(
            requestError,
          ),
        );

        if (
          requestError instanceof ApiError
        ) {
          setErrorStatus(
            requestError.status,
          );
          setErrorDetails(
            requestError.details,
          );
        } else {
          setErrorStatus(null);
          setErrorDetails(
            requestError,
          );
        }
      } finally {
        if (
          isMountedRef.current &&
          !controller.signal.aborted &&
          requestId ===
            requestIdRef.current
        ) {
          setIsLoading(false);
          setIsRefreshing(false);
        }
      }
    },
    [],
  );

  useEffect(() => {
    isMountedRef.current = true;

    queueMicrotask(() => {
      if (isMountedRef.current) {
        void loadSignals(false);
      }
    });

    return () => {
      isMountedRef.current = false;
      requestIdRef.current += 1;

      controllerRef.current?.abort();
      controllerRef.current = null;
    };
  }, [loadSignals]);

  const refresh = useCallback(
    async (): Promise<void> => {
      await loadSignals(true);
    },
    [loadSignals],
  );

  return {
    signals,
    total: signals.length,
    isLoading,
    isRefreshing,
    error,
    errorStatus,
    errorDetails,
    lastUpdated,
    refresh,
  };
}