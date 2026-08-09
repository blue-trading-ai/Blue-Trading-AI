"use client";

import {
  useCallback,
  useRef,
  useState,
} from "react";

import {
  runMarketAnalysis,
  type MarketAnalysisResult,
} from "@/lib/market-analysis-service";

type UseMarketAnalysisResult = {
  result: MarketAnalysisResult | null;
  isAnalyzing: boolean;
  error: string | null;
  lastAnalyzed: Date | null;
  analyze: (
    symbol: string,
  ) => Promise<MarketAnalysisResult | null>;
  clear: () => void;
};

export function useMarketAnalysis(): UseMarketAnalysisResult {
  const [result, setResult] =
    useState<MarketAnalysisResult | null>(null);

  const [isAnalyzing, setIsAnalyzing] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  const [lastAnalyzed, setLastAnalyzed] =
    useState<Date | null>(null);

  const controllerRef =
    useRef<AbortController | null>(null);

  const analyze = useCallback(
    async (
      symbol: string,
    ): Promise<MarketAnalysisResult | null> => {
      controllerRef.current?.abort();

      const controller =
        new AbortController();

      controllerRef.current =
        controller;

      setIsAnalyzing(true);
      setError(null);

      try {
        const analysisResult =
          await runMarketAnalysis(
            symbol,
            controller.signal,
          );

        if (controller.signal.aborted) {
          return null;
        }

        setResult(analysisResult);
        setLastAnalyzed(new Date());

        return analysisResult;
      } catch (requestError) {
        if (controller.signal.aborted) {
          return null;
        }

        const message =
          requestError instanceof Error
            ? requestError.message
            : "Unable to complete market analysis.";

        setError(message);
        setResult(null);

        return null;
      } finally {
        if (!controller.signal.aborted) {
          setIsAnalyzing(false);
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
    setLastAnalyzed(null);
    setIsAnalyzing(false);
  }, []);

  return {
    result,
    isAnalyzing,
    error,
    lastAnalyzed,
    analyze,
    clear,
  };
}