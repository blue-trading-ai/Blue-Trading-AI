"use client";

import {
  SignalCard,
  type TradingSignal,
} from "@/components/signals/signal-card";

type SignalFeedProps = {
  signals: TradingSignal[];
  symbol: string;
  timeframe: string;
  direction: string;
  isLoading?: boolean;
};

function normalizeFilterValue(
  value: string,
): string {
  return value.trim().toUpperCase();
}

function getSignalIdentity(
  signal: TradingSignal,
): string {
  return [
    signal.id,
    signal.symbol,
    signal.timeframe,
    signal.direction,
    signal.entry,
    signal.stopLoss,
    signal.takeProfit1,
    signal.takeProfit2 ?? "",
    signal.createdAt ?? "",
  ]
    .map((value) =>
      String(value ?? "")
        .trim()
        .toUpperCase(),
    )
    .join("|");
}

function getVisibleSignals(
  signals: readonly TradingSignal[],
  symbol: string,
  timeframe: string,
  direction: string,
): TradingSignal[] {
  const normalizedSymbol =
    normalizeFilterValue(symbol);

  const normalizedTimeframe =
    normalizeFilterValue(timeframe);

  const normalizedDirection =
    normalizeFilterValue(direction);

  const seen =
    new Set<string>();

  return signals.filter((signal) => {
    if (signal.status === "CLOSED") {
      return false;
    }

    const identity =
      getSignalIdentity(signal);

    if (
      !identity ||
      seen.has(identity)
    ) {
      return false;
    }

    const signalSymbol =
      normalizeFilterValue(
        signal.symbol,
      );

    const signalTimeframe =
      normalizeFilterValue(
        signal.timeframe,
      );

    const signalDirection =
      normalizeFilterValue(
        signal.direction,
      );

    const matchesSymbol =
      normalizedSymbol ===
        "ALL MARKETS" ||
      signalSymbol ===
        normalizedSymbol;

    const matchesTimeframe =
      normalizedTimeframe ===
        "ALL TIMEFRAMES" ||
      signalTimeframe ===
        normalizedTimeframe;

    const matchesDirection =
      normalizedDirection ===
        "ALL DIRECTIONS" ||
      signalDirection ===
        normalizedDirection;

    if (
      !matchesSymbol ||
      !matchesTimeframe ||
      !matchesDirection
    ) {
      return false;
    }

    seen.add(identity);
    return true;
  });
}

export function SignalFeed({
  signals,
  symbol,
  timeframe,
  direction,
  isLoading = false,
}: SignalFeedProps) {
  const filteredSignals =
    getVisibleSignals(
      signals,
      symbol,
      timeframe,
      direction,
    );

  if (isLoading) {
    return (
      <div
        className="space-y-4 p-5"
        aria-busy="true"
        aria-label="Loading approved signals"
      >
        {Array.from({
          length: 3,
        }).map((_, index) => (
          <div
            key={`signal-skeleton-${index}`}
            className="midnight-panel rounded-3xl p-5"
          >
            <div className="flex items-center justify-between gap-4">
              <div className="space-y-3">
                <div className="h-6 w-40 animate-pulse rounded-lg bg-blue-400/10" />
                <div className="h-3 w-28 animate-pulse rounded-full bg-blue-400/[0.07]" />
              </div>

              <div className="h-8 w-20 animate-pulse rounded-full bg-blue-400/10" />
            </div>

            <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              {Array.from({
                length: 5,
              }).map(
                (
                  _,
                  metricIndex,
                ) => (
                  <div
                    key={`signal-skeleton-${index}-metric-${metricIndex}`}
                    className="h-20 animate-pulse rounded-2xl border border-blue-400/10 bg-blue-500/[0.035]"
                  />
                ),
              )}
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (
    filteredSignals.length === 0
  ) {
    return (
      <div className="flex min-h-[360px] items-center justify-center p-6">
        <div className="max-w-md text-center">
          <div className="midnight-pulse mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-cyan-300/20 bg-blue-500/[0.06] text-xl font-black text-cyan-200">
            S
          </div>

          <h3 className="mt-5 text-lg font-black text-white">
            No approved signals found
          </h3>

          <p className="mt-3 text-sm leading-6 text-slate-500">
            No active or pending signal currently
            matches these filters. Only signals that
            pass the required quality checks are shown.
          </p>

          <div className="mt-5 flex flex-wrap justify-center gap-2">
            {[
              "80%+ confidence",
              "3+ confirmations",
              "Valid trade levels",
              "Risk controls applied",
            ].map((rule) => (
              <span
                key={rule}
                className="rounded-full border border-blue-400/10 bg-blue-500/[0.04] px-3 py-1.5 text-[10px] font-bold text-slate-500"
              >
                {rule}
              </span>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs font-bold text-slate-500">
          {filteredSignals.length} approved{" "}
          {filteredSignals.length === 1
            ? "signal"
            : "signals"}
        </p>

        <p className="text-[10px] font-black uppercase tracking-[0.12em] text-emerald-300">
          Quality rules passed
        </p>
      </div>

      {filteredSignals.map(
        (signal, index) => (
          <SignalCard
            key={`${getSignalIdentity(
              signal,
            )}-${index}`}
            signal={signal}
          />
        ),
      )}
    </div>
  );
}