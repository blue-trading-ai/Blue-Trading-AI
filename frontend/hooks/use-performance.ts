"use client";

import {
  useCallback,
  useRef,
  useState,
} from "react";

import {
  getPerformanceSummary,
  type PerformanceSummary,
} from "@/lib/performance-service";

type UsePerformanceResult = {
  summary: PerformanceSummary | null;
  isLoading: boolean;
  error: string | null;
  lastUpdated: Date | null;
  load: (
    period: string,
    market: string,
  ) => Promise<PerformanceSummary | null>;
  clear: () => void;
};

export function usePerformance(): UsePerformanceResult {
  const [summary, setSummary] =
    useState<PerformanceSummary | null>(null);

  const [isLoading, setIsLoading] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  const [lastUpdated, setLastUpdated] =
    useState<Date | null>(null);

  const controllerRef =
    useRef<AbortController | null>(null);

  const load = useCallback(
    async (
      period: string,
      market: string,
    ): Promise<PerformanceSummary | null> => {
      controllerRef.current?.abort();

      const controller =
        new AbortController();

      controllerRef.current =
        controller;

      setIsLoading(true);
      setError(null);

      try {
        const result =
          await getPerformanceSummary(
            period,
            market,
            controller.signal,
          );

        if (controller.signal.aborted) {
          return null;
        }

        setSummary(result);
        setLastUpdated(new Date());

        return result;
      } catch (requestError) {
        if (controller.signal.aborted) {
          return null;
        }

        const message =
          requestError instanceof Error
            ? requestError.message
            : "Unable to load performance statistics.";

        setError(message);
        setSummary(null);

        return null;
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    },
    [],
  );

  const clear = useCallback(() => {
    controllerRef.current?.abort();
    controllerRef.current = null;

    setSummary(null);
    setError(null);
    setLastUpdated(null);
    setIsLoading(false);
  }, []);

  return {
    summary,
    isLoading,
    error,
    lastUpdated,
    load,
    clear,
  };
}