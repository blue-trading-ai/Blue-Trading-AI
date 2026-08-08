"use client";

import {
  useCallback,
  useRef,
  useState,
} from "react";

import {
  getTradeHistory,
  type TradeHistoryResponse,
} from "@/lib/history-service";

type UseTradeHistoryResult = {
  data: TradeHistoryResponse | null;
  isLoading: boolean;
  error: string | null;
  lastUpdated: Date | null;
  load: (
    market: string,
    direction: string,
    status: string,
    period: string,
  ) => Promise<TradeHistoryResponse | null>;
  clear: () => void;
};

export function useTradeHistory(): UseTradeHistoryResult {
  const [data, setData] =
    useState<TradeHistoryResponse | null>(null);

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
      market: string,
      direction: string,
      status: string,
      period: string,
    ): Promise<TradeHistoryResponse | null> => {
      controllerRef.current?.abort();

      const controller =
        new AbortController();

      controllerRef.current =
        controller;

      setIsLoading(true);
      setError(null);

      try {
        const result =
          await getTradeHistory(
            market,
            direction,
            status,
            period,
            controller.signal,
          );

        if (controller.signal.aborted) {
          return null;
        }

        setData(result);
        setLastUpdated(new Date());

        return result;
      } catch (requestError) {
        if (controller.signal.aborted) {
          return null;
        }

        const message =
          requestError instanceof Error
            ? requestError.message
            : "Unable to load trade history.";

        setError(message);
        setData(null);

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

    setData(null);
    setError(null);
    setLastUpdated(null);
    setIsLoading(false);
  }, []);

  return {
    data,
    isLoading,
    error,
    lastUpdated,
    load,
    clear,
  };
}