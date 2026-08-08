"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  getSignalQualityStatus,
  type SignalQualityStatus,
} from "@/lib/signal-quality";

type MetricCard = {
  label: string;
  value: string;
  note: string;
  accent:
    | "blue"
    | "cyan"
    | "violet"
    | "emerald";
};

const loadingMetrics: MetricCard[] = [
  {
    label:
      "High-Quality Signals Today",
    value: "—",
    note:
      "Loading approved signals",
    accent: "blue",
  },
  {
    label:
      "Preferred Daily Target",
    value: "—",
    note:
      "Loading quality target",
    accent: "cyan",
  },
  {
    label:
      "Remaining Signal Slots",
    value: "—",
    note:
      "Loading daily capacity",
    accent: "violet",
  },
  {
    label:
      "Daily Signal Limit",
    value: "—",
    note:
      "Loading publication limit",
    accent: "emerald",
  },
];

const accentStyles = {
  blue: {
    badge:
      "border-blue-400/20 bg-blue-500/10 text-blue-200",
    glow:
      "from-blue-500/20 via-blue-500/5 to-transparent",
    dot:
      "bg-blue-400 shadow-[0_0_14px_rgba(96,165,250,0.8)]",
  },
  cyan: {
    badge:
      "border-cyan-300/20 bg-cyan-300/10 text-cyan-200",
    glow:
      "from-cyan-300/20 via-cyan-300/5 to-transparent",
    dot:
      "bg-cyan-300 shadow-[0_0_14px_rgba(34,211,238,0.8)]",
  },
  violet: {
    badge:
      "border-violet-400/20 bg-violet-500/10 text-violet-200",
    glow:
      "from-violet-500/20 via-violet-500/5 to-transparent",
    dot:
      "bg-violet-400 shadow-[0_0_14px_rgba(167,139,250,0.8)]",
  },
  emerald: {
    badge:
      "border-emerald-400/20 bg-emerald-400/10 text-emerald-200",
    glow:
      "from-emerald-400/20 via-emerald-400/5 to-transparent",
    dot:
      "bg-emerald-400 shadow-[0_0_14px_rgba(52,211,153,0.8)]",
  },
} satisfies Record<
  MetricCard["accent"],
  {
    badge: string;
    glow: string;
    dot: string;
  }
>;

function safeNonNegativeInteger(
  value: unknown,
): number {
  const numberValue =
    typeof value === "number"
      ? value
      : Number(value);

  if (
    !Number.isFinite(numberValue)
  ) {
    return 0;
  }

  return Math.max(
    Math.trunc(numberValue),
    0,
  );
}

function buildMetrics(
  status: SignalQualityStatus,
): MetricCard[] {
  const publishedToday =
    safeNonNegativeInteger(
      status.published_today,
    );

  const preferredTarget =
    safeNonNegativeInteger(
      status.preferred_daily_target,
    );

  const dailyLimit =
    safeNonNegativeInteger(
      status.daily_signal_limit,
    );

  const remainingSlots =
    Math.min(
      safeNonNegativeInteger(
        status.remaining_signal_slots,
      ),
      dailyLimit,
    );

  return [
    {
      label:
        "High-Quality Signals Today",
      value:
        String(publishedToday),
      note:
        "Only approved setups",
      accent: "blue",
    },
    {
      label:
        "Preferred Daily Target",
      value:
        String(preferredTarget),
      note:
        "Quality over quantity",
      accent: "cyan",
    },
    {
      label:
        "Remaining Signal Slots",
      value:
        String(remainingSlots),
      note:
        `${Math.min(
          publishedToday,
          dailyLimit,
        )} of ${dailyLimit} used`,
      accent: "violet",
    },
    {
      label:
        "Daily Signal Limit",
      value:
        String(dailyLimit),
      note:
        status.broker_execution_enabled
          ? "Broker execution enabled"
          : "Analysis and signals only",
      accent: "emerald",
    },
  ];
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

  return "Unable to load signal-quality status.";
}

export function SignalQualityMetrics() {
  const [status, setStatus] =
    useState<SignalQualityStatus | null>(
      null,
    );

  const [error, setError] =
    useState<string | null>(null);

  const [isLoading, setIsLoading] =
    useState(true);

  const requestIdRef =
    useRef(0);

  const isMountedRef =
    useRef(false);

  const loadStatus =
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
        const result =
          await getSignalQualityStatus();

        if (
          !isMountedRef.current ||
          requestId !==
            requestIdRef.current
        ) {
          return;
        }

        setStatus(result);
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
        void loadStatus();
      }
    });

    return () => {
      isMountedRef.current = false;
      requestIdRef.current += 1;
    };
  }, [loadStatus]);

  const metrics =
    status
      ? buildMetrics(status)
      : loadingMetrics;

  return (
    <section>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-slate-600">
            Version 49 Intelligence
          </p>

          <h2 className="mt-1 text-lg font-black text-white">
            Signal Quality Overview
          </h2>
        </div>

        <div className="rounded-full border border-cyan-300/15 bg-cyan-300/[0.05] px-3 py-1.5 text-[10px] font-black uppercase tracking-[0.16em] text-cyan-200">
          High quality only
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map(
          (metric, index) => {
            const accent =
              accentStyles[
                metric.accent
              ];

            return (
              <article
                key={metric.label}
                className="midnight-card group relative rounded-2xl p-5"
              >
                <div
                  className={`absolute inset-x-0 top-0 h-px bg-gradient-to-r ${accent.glow}`}
                />

                <div className="relative z-10 flex items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold leading-5 text-slate-500">
                      {metric.label}
                    </p>

                    <p className="mt-3 text-3xl font-black tracking-tight text-white">
                      {metric.value}
                    </p>

                    <p className="mt-2 text-xs leading-5 text-slate-600">
                      {metric.note}
                    </p>
                  </div>

                  <div
                    className={`flex h-10 min-w-10 items-center justify-center rounded-xl border text-xs font-black ${accent.badge}`}
                  >
                    {String(
                      index + 1,
                    ).padStart(
                      2,
                      "0",
                    )}
                  </div>
                </div>

                <div className="relative z-10 mt-4 flex items-center gap-2">
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${accent.dot}`}
                  />

                  <span className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-700">
                    {status
                      ? "Live backend metric"
                      : "Awaiting backend metric"}
                  </span>
                </div>
              </article>
            );
          },
        )}
      </div>

      {isLoading ? (
        <div className="mt-3 flex items-center gap-2 rounded-xl border border-blue-400/10 bg-blue-500/[0.04] px-4 py-3">
          <span className="midnight-pulse h-2 w-2 rounded-full bg-cyan-300" />

          <p className="text-xs font-semibold text-slate-500">
            Connecting to the Version 49 quality API...
          </p>
        </div>
      ) : null}

      {error ? (
        <div className="mt-3 flex flex-col gap-3 rounded-xl border border-amber-400/20 bg-amber-400/[0.05] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-black text-amber-300">
              Signal-quality data is unavailable.
            </p>

            <p className="mt-1 text-xs text-slate-500">
              {error}
            </p>
          </div>

          <button
            type="button"
            disabled={isLoading}
            onClick={() =>
              void loadStatus()
            }
            className="shrink-0 rounded-xl border border-amber-300/20 bg-amber-400/[0.06] px-4 py-2.5 text-xs font-black text-amber-200 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Retry
          </button>
        </div>
      ) : null}
    </section>
  );
}