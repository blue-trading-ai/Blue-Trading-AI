"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import { ApiError } from "@/lib/api";
import {
  getMonitoringData,
  type MonitoringData,
} from "@/lib/monitoring-service";

type UseMonitoringResult = {
  data: MonitoringData | null;
  isLoading: boolean;
  error: string | null;
  errorStatus: number | null;
  errorDetails: unknown;
  lastUpdated: Date | null;
  load: (
    period: string,
    serviceStatus: string,
  ) => Promise<MonitoringData | null>;
  clear: () => void;
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

  return "Unable to load system monitoring data.";
}

export function useMonitoring(): UseMonitoringResult {
  const [data, setData] =
    useState<MonitoringData | null>(null);

  const [isLoading, setIsLoading] =
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

  const load = useCallback(
    async (
      period: string,
      serviceStatus: string,
    ): Promise<MonitoringData | null> => {
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
        setError(null);
        setErrorStatus(null);
        setErrorDetails(null);
      }

      try {
        const result =
          await getMonitoringData(
            period,
            serviceStatus,
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

        setError(
          getErrorMessage(requestError),
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
          setErrorDetails(
            requestError,
          );
        }

        return null;
      } finally {
        if (
          isMountedRef.current &&
          !controller.signal.aborted &&
          requestId === requestIdRef.current
        ) {
          setIsLoading(false);
        }
      }
    },
    [],
  );

  const clear = useCallback(() => {
    controllerRef.current?.abort();
    controllerRef.current = null;

    requestIdRef.current += 1;

    setData(null);
    setError(null);
    setErrorStatus(null);
    setErrorDetails(null);
    setLastUpdated(null);
    setIsLoading(false);
  }, []);

  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;
      requestIdRef.current += 1;

      controllerRef.current?.abort();
      controllerRef.current = null;
    };
  }, []);

  return {
    data,
    isLoading,
    error,
    errorStatus,
    errorDetails,
    lastUpdated,
    load,
    clear,
  };
}