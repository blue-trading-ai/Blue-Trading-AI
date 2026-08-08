"use client";

import {
  useCallback,
  useRef,
  useState,
} from "react";

import {
  getMarketStructure,
  type MarketStructureResult,
} from "@/lib/market-structure-service";

type UseMarketStructureResult = {
  result: MarketStructureResult | null;
  isLoading: boolean;
  error: string | null;
  lastUpdated: Date | null;
  analyze: (
    symbol: string,
    timeframe: string,
  ) => Promise<MarketStructureResult | null>;
  clear: () => void;
};

export function useMarketStructure(): UseMarketStructureResult {
  const [result, setResult] =
    useState<MarketStructureResult | null>(null);

  const [isLoading, setIsLoading] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  const [lastUpdated, setLastUpdated] =
    useState<Date | null>(null);

  const controllerRef =
    useRef<AbortController | null>(null);

  const analyze = useCallback(
    async (
      symbol: string,
      timeframe: string,
    ): Promise<MarketStructureResult | null> => {
      controllerRef.current?.abort();

      const controller =
        new AbortController();

      controllerRef.current =
        controller;

      setIsLoading(true);
      setError(null);

      try {
        const structureResult =
          await getMarketStructure(
            symbol,
            timeframe,
            controller.signal,
          );

        if (controller.signal.aborted) {
          return null;
        }

        setResult(structureResult);
        setLastUpdated(new Date());

        return structureResult;
      } catch (requestError) {
        if (controller.signal.aborted) {
          return null;
        }

        const message =
          requestError instanceof Error
            ? requestError.message
            : "Unable to load market structure.";

        setError(message);
        setResult(null);

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

    setResult(null);
    setError(null);
    setLastUpdated(null);
    setIsLoading(false);
  }, []);

  return {
    result,
    isLoading,
    error,
    lastUpdated,
    analyze,
    clear,
  };
}