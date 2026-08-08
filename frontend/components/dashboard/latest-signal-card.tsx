"use client";

import Link from "next/link";

export type LatestSignal = {
  symbol: string;
  timeframe: string;
  direction: "BUY" | "SELL";
  confidence: number;
  entry: string;
  stopLoss: string;
  takeProfit1: string;
  takeProfit2: string;
  confirmations: string[];
};

type LatestSignalCardProps = {
  signal?: LatestSignal | null;
  isLoading?: boolean;
  error?: string | null;
};

const MINIMUM_CONFIDENCE = 80;
const MINIMUM_CONFIRMATIONS = 3;

function clampConfidence(
  value: number,
): number {
  if (!Number.isFinite(value)) {
    return 0;
  }

  return Math.min(
    Math.max(value, 0),
    100,
  );
}

function safeText(
  value: unknown,
  fallback: string,
): string {
  if (
    typeof value === "string" &&
    value.trim()
  ) {
    return value.trim();
  }

  if (
    typeof value === "number" &&
    Number.isFinite(value)
  ) {
    return String(value);
  }

  return fallback;
}

function normalizeConfirmations(
  values: unknown,
): string[] {
  if (!Array.isArray(values)) {
    return [];
  }

  return Array.from(
    new Set(
      values
        .filter(
          (item): item is string =>
            typeof item === "string",
        )
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  );
}

function EmptySignalState() {
  return (
    <article className="midnight-panel rounded-3xl p-5 sm:p-6">
      <div className="flex min-h-[420px] items-center justify-center text-center">
        <div>
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-blue-400/15 bg-blue-500/[0.05] text-xl text-cyan-200">
            —
          </div>

          <p className="mt-4 text-sm font-black text-slate-300">
            No approved signal yet
          </p>

          <p className="mt-2 max-w-sm text-xs leading-5 text-slate-600">
            Blue-Trading-AI displays only setups with at least
            {` ${MINIMUM_CONFIDENCE}% `}
            confidence and
            {` ${MINIMUM_CONFIRMATIONS} `}
            independent confirmations.
          </p>
        </div>
      </div>
    </article>
  );
}

function RejectedSignalState({
  confidence,
  confirmationCount,
}: {
  confidence: number;
  confirmationCount: number;
}) {
  const reasons: string[] = [];

  if (
    confidence <
    MINIMUM_CONFIDENCE
  ) {
    reasons.push(
      `Confidence is ${confidence.toFixed(0)}%, below the ${MINIMUM_CONFIDENCE}% requirement.`,
    );
  }

  if (
    confirmationCount <
    MINIMUM_CONFIRMATIONS
  ) {
    reasons.push(
      `Only ${confirmationCount} confirmation${
        confirmationCount === 1
          ? ""
          : "s"
      } detected; at least ${MINIMUM_CONFIRMATIONS} are required.`,
    );
  }

  return (
    <article className="midnight-panel rounded-3xl p-5 sm:p-6">
      <div className="rounded-2xl border border-amber-300/20 bg-amber-400/[0.05] p-5">
        <p className="text-[10px] font-black uppercase tracking-[0.2em] text-amber-300">
          Quality Protection
        </p>

        <h2 className="mt-3 text-xl font-black text-white">
          No Trade
        </h2>

        <p className="mt-2 text-xs leading-5 text-slate-500">
          This setup was blocked because it did not pass every
          Blue-Trading-AI entry rule.
        </p>

        <div className="mt-4 space-y-2">
          {reasons.map((reason) => (
            <div
              key={reason}
              className="rounded-xl border border-amber-300/10 bg-amber-400/[0.035] px-4 py-3 text-xs leading-5 text-amber-200"
            >
              {reason}
            </div>
          ))}
        </div>
      </div>
    </article>
  );
}

export function LatestSignalCard({
  signal = null,
  isLoading = false,
  error = null,
}: LatestSignalCardProps) {
  if (isLoading) {
    return (
      <article className="midnight-panel rounded-3xl p-5 sm:p-6">
        <div className="h-3 w-40 animate-pulse rounded-full bg-blue-500/10" />

        <div className="mt-4 h-8 w-32 animate-pulse rounded-xl bg-blue-500/10" />

        <div className="mt-5 h-24 animate-pulse rounded-2xl bg-blue-500/[0.04]" />

        <div className="mt-4 grid grid-cols-2 gap-3">
          {Array.from({
            length: 4,
          }).map((_, index) => (
            <div
              key={index}
              className="h-20 animate-pulse rounded-2xl bg-blue-500/[0.04]"
            />
          ))}
        </div>
      </article>
    );
  }

  if (error) {
    return (
      <article className="midnight-panel rounded-3xl p-5 sm:p-6">
        <div className="rounded-2xl border border-amber-400/20 bg-amber-400/[0.05] p-5">
          <p className="text-sm font-black text-amber-300">
            Latest signal unavailable
          </p>

          <p className="mt-2 text-xs leading-5 text-slate-500">
            {error}
          </p>
        </div>
      </article>
    );
  }

  if (!signal) {
    return <EmptySignalState />;
  }

  const confidence =
    clampConfidence(
      signal.confidence,
    );

  const confirmations =
    normalizeConfirmations(
      signal.confirmations,
    );

  if (
    confidence <
      MINIMUM_CONFIDENCE ||
    confirmations.length <
      MINIMUM_CONFIRMATIONS
  ) {
    return (
      <RejectedSignalState
        confidence={confidence}
        confirmationCount={
          confirmations.length
        }
      />
    );
  }

  const direction =
    signal.direction === "SELL"
      ? "SELL"
      : "BUY";

  const isBuy =
    direction === "BUY";

  const directionStyle = isBuy
    ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-300 shadow-[0_0_18px_rgba(52,211,153,0.14)]"
    : "border-rose-400/20 bg-rose-400/10 text-rose-300 shadow-[0_0_18px_rgba(251,113,133,0.14)]";

  const confidenceWidth =
    `${confidence}%`;

  const tradeLevels = [
    {
      label: "Entry",
      value: safeText(
        signal.entry,
        "Unavailable",
      ),
      accent: "text-cyan-200",
    },
    {
      label: "Stop Loss",
      value: safeText(
        signal.stopLoss,
        "Unavailable",
      ),
      accent: "text-rose-300",
    },
    {
      label: "TP1",
      value: safeText(
        signal.takeProfit1,
        "Unavailable",
      ),
      accent: "text-emerald-300",
    },
    {
      label: "TP2",
      value: safeText(
        signal.takeProfit2,
        "Unavailable",
      ),
      accent: "text-emerald-200",
    },
  ];

  return (
    <article className="midnight-panel rounded-3xl p-5 sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-slate-600">
            Latest Approved Signal
          </p>

          <div className="mt-2 flex items-center gap-3">
            <h2 className="break-all text-xl font-black text-white">
              {safeText(
                signal.symbol,
                "UNKNOWN",
              )}
            </h2>

            <span className="rounded-full border border-blue-400/15 bg-blue-500/[0.06] px-2.5 py-1 text-[10px] font-black text-blue-200">
              {safeText(
                signal.timeframe,
                "—",
              )}
            </span>
          </div>
        </div>

        <span
          className={`rounded-full border px-3 py-1.5 text-xs font-black ${directionStyle}`}
        >
          {direction}
        </span>
      </div>

      <div className="mt-5 rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-600">
              Confidence
            </p>

            <p className="mt-1 text-xs font-semibold text-slate-500">
              Passed the minimum quality threshold
            </p>
          </div>

          <span className="midnight-accent-text text-2xl font-black">
            {confidence.toFixed(0)}%
          </span>
        </div>

        <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-900">
          <div
            className="h-full rounded-full bg-gradient-to-r from-blue-600 via-blue-400 to-cyan-300 shadow-[0_0_18px_rgba(34,211,238,0.35)]"
            style={{
              width:
                confidenceWidth,
            }}
          />
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3">
        {tradeLevels.map(
          (level) => (
            <div
              key={level.label}
              className="midnight-card rounded-2xl p-4"
            >
              <p className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-600">
                {level.label}
              </p>

              <p
                className={`mt-2 break-words text-base font-black ${level.accent}`}
              >
                {level.value}
              </p>
            </div>
          ),
        )}
      </div>

      <div className="mt-5 flex items-center justify-between gap-3">
        <p className="text-xs font-black text-slate-300">
          Confirmations
        </p>

        <span className="rounded-full border border-cyan-300/15 bg-cyan-300/[0.05] px-2.5 py-1 text-[10px] font-black text-cyan-200">
          {confirmations.length} confirmed
        </span>
      </div>

      <div className="mt-3 space-y-2">
        {confirmations.map(
          (item) => (
            <div
              key={item}
              className="flex items-center justify-between gap-3 rounded-xl border border-blue-400/10 bg-blue-500/[0.025] px-3 py-3 transition hover:border-cyan-300/15 hover:bg-blue-500/[0.05]"
            >
              <span className="text-xs font-semibold text-slate-400">
                {item}
              </span>

              <div className="flex shrink-0 items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.75)]" />

                <span className="text-[10px] font-black uppercase tracking-[0.12em] text-emerald-300">
                  Confirmed
                </span>
              </div>
            </div>
          ),
        )}
      </div>

      <Link
        href="/analysis"
        className="midnight-button mt-5 block w-full rounded-xl py-3.5 text-center text-sm font-black"
      >
        View Full Analysis
      </Link>
    </article>
  );
}