"use client";

import { useState } from "react";

import { SignalFeed } from "@/components/signals/signal-feed";
import { useApprovedSignals } from "@/hooks/use-approved-signals";

const symbols = [
  "All Markets",
  "XAUUSD",
  "BTCUSD",
  "GBPUSD",
] as const;

const timeframes = [
  "All Timeframes",
  "M15",
  "M30",
  "H1",
  "H4",
  "D1",
] as const;

const directions = [
  "All Directions",
  "BUY",
  "SELL",
] as const;

type SymbolFilter =
  (typeof symbols)[number];

type TimeframeFilter =
  (typeof timeframes)[number];

type DirectionFilter =
  (typeof directions)[number];

function formatUpdatedTime(
  value: Date | null,
): string {
  if (!value) {
    return "Not updated yet";
  }

  return value.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function SignalsPage() {
  const [symbol, setSymbol] =
    useState<SymbolFilter>(
      "All Markets",
    );

  const [timeframe, setTimeframe] =
    useState<TimeframeFilter>(
      "All Timeframes",
    );

  const [direction, setDirection] =
    useState<DirectionFilter>(
      "All Directions",
    );

  const {
    signals,
    total,
    isLoading,
    isRefreshing,
    error,
    lastUpdated,
    refresh,
  } = useApprovedSignals();

  const filtersAreActive =
    symbol !== "All Markets" ||
    timeframe !== "All Timeframes" ||
    direction !== "All Directions";

  function resetFilters() {
    setSymbol("All Markets");
    setTimeframe("All Timeframes");
    setDirection("All Directions");
  }

  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-cyan-300">
            Trading Intelligence
          </p>

          <h1 className="mt-2 text-3xl font-black tracking-tight text-white">
            Approved Trading Signals
          </h1>

          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">
            Only setups that pass the confidence,
            confirmation, market-structure,
            multi-timeframe and risk-management
            requirements are published.
          </p>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row">
          <div className="flex items-center gap-3 rounded-2xl border border-emerald-400/15 bg-emerald-400/[0.05] px-4 py-3">
            <span className="midnight-status-dot h-2.5 w-2.5 rounded-full bg-emerald-400" />

            <div>
              <p className="text-xs font-black text-emerald-300">
                Signal Engine Active
              </p>

              <p className="mt-1 text-[10px] uppercase tracking-[0.12em] text-slate-600">
                Analysis only · No broker execution
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={() =>
              void refresh()
            }
            disabled={
              isLoading ||
              isRefreshing
            }
            className="midnight-button rounded-2xl px-5 py-3 text-xs font-black disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isRefreshing
              ? "Refreshing..."
              : "Refresh Signals"}
          </button>
        </div>
      </section>

      {error ? (
        <section className="rounded-2xl border border-rose-400/20 bg-rose-400/[0.05] p-4">
          <p className="text-xs font-black text-rose-300">
            Unable to refresh approved signals
          </p>

          <p className="mt-2 text-xs leading-5 text-slate-500">
            {error}
          </p>

          {signals.length > 0 ? (
            <p className="mt-2 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-600">
              Showing the last successfully loaded data
            </p>
          ) : null}
        </section>
      ) : null}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[
          {
            label:
              "Minimum Confidence",
            value: "80%",
            note:
              "Lower scores are blocked",
          },
          {
            label:
              "Confirmations",
            value: "3+",
            note:
              "Required before approval",
          },
          {
            label:
              "Risk Management",
            value: "Required",
            note:
              "Backend validates trade levels",
          },
          {
            label:
              "Loaded Approved Signals",
            value:
              isLoading
                ? "—"
                : String(total),
            note:
              `Updated ${formatUpdatedTime(
                lastUpdated,
              )}`,
          },
        ].map((item) => (
          <article
            key={item.label}
            className="midnight-panel rounded-2xl p-5"
          >
            <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-600">
              {item.label}
            </p>

            <p className="mt-3 text-2xl font-black text-white">
              {item.value}
            </p>

            <p className="mt-2 text-xs text-slate-600">
              {item.note}
            </p>
          </article>
        ))}
      </section>

      <section className="midnight-panel rounded-3xl p-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
              Signal Filters
            </p>

            <h2 className="mt-2 text-lg font-black text-white">
              Find approved setups
            </h2>
          </div>

          <button
            type="button"
            onClick={resetFilters}
            disabled={!filtersAreActive}
            className="text-xs font-black text-cyan-300 transition hover:text-cyan-200 disabled:cursor-not-allowed disabled:text-slate-700"
          >
            Reset filters
          </button>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-3">
          <label className="block">
            <span className="text-xs font-black text-slate-300">
              Market
            </span>

            <select
              value={symbol}
              onChange={(event) =>
                setSymbol(
                  event.target
                    .value as SymbolFilter,
                )
              }
              disabled={
                isLoading ||
                isRefreshing
              }
              className="mt-2 w-full rounded-xl border border-blue-400/10 bg-[#091426] px-4 py-3 text-sm text-white focus:border-cyan-300/30 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {symbols.map((item) => (
                <option
                  key={item}
                  value={item}
                >
                  {item}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-xs font-black text-slate-300">
              Timeframe
            </span>

            <select
              value={timeframe}
              onChange={(event) =>
                setTimeframe(
                  event.target
                    .value as TimeframeFilter,
                )
              }
              disabled={
                isLoading ||
                isRefreshing
              }
              className="mt-2 w-full rounded-xl border border-blue-400/10 bg-[#091426] px-4 py-3 text-sm text-white focus:border-cyan-300/30 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {timeframes.map((item) => (
                <option
                  key={item}
                  value={item}
                >
                  {item}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-xs font-black text-slate-300">
              Direction
            </span>

            <select
              value={direction}
              onChange={(event) =>
                setDirection(
                  event.target
                    .value as DirectionFilter,
                )
              }
              disabled={
                isLoading ||
                isRefreshing
              }
              className="mt-2 w-full rounded-xl border border-blue-400/10 bg-[#091426] px-4 py-3 text-sm text-white focus:border-cyan-300/30 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {directions.map((item) => (
                <option
                  key={item}
                  value={item}
                >
                  {item}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      <section className="midnight-panel overflow-hidden rounded-3xl">
        <div className="flex flex-col gap-3 border-b border-blue-400/10 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
              Live Signal Feed
            </p>

            <h2 className="mt-2 text-lg font-black text-white">
              Published setups
            </h2>
          </div>

          <div className="rounded-xl border border-blue-400/10 bg-blue-500/[0.04] px-3 py-2">
            <p className="text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500">
              {symbol} · {timeframe} · {direction}
            </p>
          </div>
        </div>

        <SignalFeed
          signals={signals}
          symbol={symbol}
          timeframe={timeframe}
          direction={direction}
          isLoading={isLoading}
        />
      </section>
    </div>
  );
}