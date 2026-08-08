"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  LatestSignalCard,
  type LatestSignal,
} from "@/components/dashboard/latest-signal-card";
import { getLatestApprovedSignal } from "@/lib/signals";

function getErrorMessage(
  error: unknown,
): string {
  if (
    error instanceof Error &&
    error.message.trim()
  ) {
    return error.message;
  }

  return "Unable to load the latest approved signal.";
}

export function LiveLatestSignalCard() {
  const [signal, setSignal] =
    useState<LatestSignal | null>(null);

  const [isLoading, setIsLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);

  const requestIdRef = useRef(0);
  const isMountedRef = useRef(false);

  const loadLatestSignal =
    useCallback(async () => {
      const requestId =
        requestIdRef.current + 1;

      requestIdRef.current =
        requestId;

      if (isMountedRef.current) {
        setIsLoading(true);
        setError(null);
      }

      try {
        const latestSignal =
          await getLatestApprovedSignal();

        if (
          !isMountedRef.current ||
          requestId !==
            requestIdRef.current
        ) {
          return;
        }

        setSignal(latestSignal);
      } catch (requestError) {
        if (
          !isMountedRef.current ||
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
      } finally {
        if (
          isMountedRef.current &&
          requestId ===
            requestIdRef.current
        ) {
          setIsLoading(false);
        }
      }
    }, []);

  useEffect(() => {
    isMountedRef.current = true;

    queueMicrotask(() => {
      if (isMountedRef.current) {
        void loadLatestSignal();
      }
    });

    return () => {
      isMountedRef.current = false;
      requestIdRef.current += 1;
    };
  }, [loadLatestSignal]);

  return (
    <div className="space-y-3">
      <LatestSignalCard
        signal={signal}
        isLoading={isLoading}
        error={error}
      />

      <button
        type="button"
        disabled={isLoading}
        onClick={() =>
          void loadLatestSignal()
        }
        className="w-full rounded-xl border border-blue-400/10 bg-blue-500/[0.035] px-4 py-3 text-xs font-black text-cyan-200 transition hover:border-cyan-300/20 hover:bg-blue-500/[0.07] disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isLoading
          ? "Refreshing latest signal..."
          : "Refresh Latest Signal"}
      </button>
    </div>
  );
}