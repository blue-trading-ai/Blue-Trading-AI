"use client";

import {
  useCallback,
  useRef,
  useState,
} from "react";

import {
  getMarketNews,
  type MarketNewsResponse,
} from "@/lib/news-service";

type UseMarketNewsResult = {
  data: MarketNewsResponse | null;
  isLoading: boolean;
  error: string | null;
  lastUpdated: Date | null;
  load: (
    impact: string,
    market: string,
    period: string,
  ) => Promise<MarketNewsResponse | null>;
  clear: () => void;
};

export function useMarketNews(): UseMarketNewsResult {
  const [data, setData] =
    useState<MarketNewsResponse | null>(null);

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
      impact: string,
      market: string,
      period: string,
    ): Promise<MarketNewsResponse | null> => {
      controllerRef.current?.abort();

      const controller =
        new AbortController();

      controllerRef.current =
        controller;

      setIsLoading(true);
      setError(null);

      try {
        const result =
          await getMarketNews(
            impact,
            market,
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
            : "Unable to load market news.";

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