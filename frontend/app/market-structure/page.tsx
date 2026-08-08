"use client";

import { useState } from "react";

import { useMarketStructure } from "@/hooks/use-market-structure";

const symbols = [
  "XAUUSD",
  "BTCUSD",
  "GBPUSD",
];

const timeframes = [
  "M15",
  "M30",
  "H1",
  "H4",
  "D1",
];

function formatValue(
  value: string | boolean | number | null,
): string {
  if (
    value === null ||
    value === ""
  ) {
    return "—";
  }

  if (typeof value === "boolean") {
    return value ? "Confirmed" : "Not confirmed";
  }

  return String(value);
}

function formatTime(
  value: Date | null,
): string {
  if (!value) {
    return "Not analyzed yet";
  }

  return value.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function MarketStructurePage() {
  const [symbol, setSymbol] =
    useState("XAUUSD");

  const [timeframe, setTimeframe] =
    useState("H1");

  const {
    result,
    isLoading,
    error,
    lastUpdated,
    analyze,
    clear,
  } = useMarketStructure();

  async function handleAnalyze() {
    await analyze(symbol, timeframe);
  }

  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-cyan-300">
            Structure Intelligence
          </p>

          <h1 className="mt-2 text-3xl font-black tracking-tight text-white">
            Market Structure Analysis
          </h1>

          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">
            Evaluate swing highs, swing lows, Break of Structure,
            Change of Character, support and resistance, and
            directional bias before a trading signal is approved.
          </p>
        </div>

        <div className="flex items-center gap-3 rounded-2xl border border-emerald-400/15 bg-emerald-400/[0.05] px-4 py-3">
          <span className="midnight-status-dot h-2.5 w-2.5 rounded-full bg-emerald-400" />

          <div>
            <p className="text-xs font-black text-emerald-300">
              Structure Engine Ready
            </p>

            <p className="mt-1 text-[10px] uppercase tracking-[0.12em] text-slate-600">
              Multi-timeframe confirmation required
            </p>
          </div>
        </div>
      </section>

      {error ? (
        <section className="rounded-2xl border border-rose-400/20 bg-rose-400/[0.05] p-4">
          <p className="text-xs font-black text-rose-300">
            Structure request failed
          </p>

          <p className="mt-2 text-xs leading-5 text-slate-500">
            {error}
          </p>
        </section>
      ) : null}

      <section className="midnight-panel rounded-3xl p-5">
        <div className="grid gap-4 lg:grid-cols-[1fr_1fr_auto_auto] lg:items-end">
          <label className="block">
            <span className="text-xs font-black text-slate-300">
              Market
            </span>

            <select
              value={symbol}
              onChange={(event) =>
                setSymbol(event.target.value)
              }
              disabled={isLoading}
              className="mt-2 w-full rounded-xl border border-blue-400/10 bg-[#091426] px-4 py-3 text-sm text-white focus:border-cyan-300/30 disabled:opacity-60"
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
                setTimeframe(event.target.value)
              }
              disabled={isLoading}
              className="mt-2 w-full rounded-xl border border-blue-400/10 bg-[#091426] px-4 py-3 text-sm text-white focus:border-cyan-300/30 disabled:opacity-60"
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

          <button
            type="button"
            onClick={() => void handleAnalyze()}
            disabled={isLoading}
            className="midnight-button rounded-xl px-6 py-3 text-sm font-black disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isLoading
              ? "Analyzing Structure..."
              : "Analyze Structure"}
          </button>

          <button
            type="button"
            onClick={clear}
            disabled={isLoading || !result}
            className="rounded-xl border border-blue-400/10 bg-blue-500/[0.04] px-6 py-3 text-sm font-black text-cyan-200 transition hover:border-cyan-300/20 hover:bg-blue-500/[0.08] disabled:cursor-not-allowed disabled:opacity-40"
          >
            Clear
          </button>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[
          {
            label: "Selected Market",
            value: symbol,
            note: "Live structure target",
          },
          {
            label: "Primary Timeframe",
            value: timeframe,
            note: "Higher timeframe alignment required",
          },
          {
            label: "Current Bias",
            value: result?.bias || "—",
            note: "Backend structure direction",
          },
          {
            label: "Last Updated",
            value: formatTime(lastUpdated),
            note: "Latest completed analysis",
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

      <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="midnight-panel overflow-hidden rounded-3xl">
          <div className="border-b border-blue-400/10 p-5">
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
              Structure Result
            </p>

            <h2 className="mt-2 text-lg font-black text-white">
              {result
                ? `${result.symbol} · ${result.timeframe}`
                : `${symbol} · ${timeframe}`}
            </h2>
          </div>

          {result ? (
            <div className="space-y-5 p-5">
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {[
                  {
                    label: "Structure",
                    value:
                      result.structure ||
                      "Not provided",
                  },
                  {
                    label: "Bias",
                    value:
                      result.bias ||
                      "Not provided",
                  },
                  {
                    label: "BOS",
                    value: formatValue(
                      result.bos,
                    ),
                  },
                  {
                    label: "CHoCH",
                    value: formatValue(
                      result.choch,
                    ),
                  },
                ].map((item) => (
                  <div
                    key={item.label}
                    className="rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4"
                  >
                    <p className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-600">
                      {item.label}
                    </p>

                    <p className="mt-2 text-sm font-black text-white">
                      {item.value}
                    </p>
                  </div>
                ))}
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-2xl border border-emerald-400/15 bg-emerald-400/[0.04] p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-600">
                    Support Levels
                  </p>

                  {result.support.length > 0 ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {result.support.map(
                        (level, index) => (
                          <span
                            key={`${level}-${index}`}
                            className="rounded-full border border-emerald-400/15 bg-emerald-400/[0.05] px-3 py-1.5 text-[10px] font-black text-emerald-300"
                          >
                            {level}
                          </span>
                        ),
                      )}
                    </div>
                  ) : (
                    <p className="mt-3 text-xs text-slate-600">
                      No support levels returned.
                    </p>
                  )}
                </div>

                <div className="rounded-2xl border border-rose-400/15 bg-rose-400/[0.04] p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-600">
                    Resistance Levels
                  </p>

                  {result.resistance.length > 0 ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {result.resistance.map(
                        (level, index) => (
                          <span
                            key={`${level}-${index}`}
                            className="rounded-full border border-rose-400/15 bg-rose-400/[0.05] px-3 py-1.5 text-[10px] font-black text-rose-300"
                          >
                            {level}
                          </span>
                        ),
                      )}
                    </div>
                  ) : (
                    <p className="mt-3 text-xs text-slate-600">
                      No resistance levels returned.
                    </p>
                  )}
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-600">
                    Swing Highs
                  </p>

                  {result.swingHighs.length > 0 ? (
                    <div className="mt-3 space-y-2">
                      {result.swingHighs.map(
                        (point, index) => (
                          <div
                            key={`${point.index}-${index}`}
                            className="flex items-center justify-between rounded-xl border border-blue-400/10 px-3 py-2"
                          >
                            <span className="text-[10px] font-bold text-slate-500">
                              {point.type ||
                                `High ${index + 1}`}
                            </span>

                            <span className="text-xs font-black text-white">
                              {point.price ?? "—"}
                            </span>
                          </div>
                        ),
                      )}
                    </div>
                  ) : (
                    <p className="mt-3 text-xs text-slate-600">
                      No swing highs returned.
                    </p>
                  )}
                </div>

                <div className="rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-600">
                    Swing Lows
                  </p>

                  {result.swingLows.length > 0 ? (
                    <div className="mt-3 space-y-2">
                      {result.swingLows.map(
                        (point, index) => (
                          <div
                            key={`${point.index}-${index}`}
                            className="flex items-center justify-between rounded-xl border border-blue-400/10 px-3 py-2"
                          >
                            <span className="text-[10px] font-bold text-slate-500">
                              {point.type ||
                                `Low ${index + 1}`}
                            </span>

                            <span className="text-xs font-black text-white">
                              {point.price ?? "—"}
                            </span>
                          </div>
                        ),
                      )}
                    </div>
                  ) : (
                    <p className="mt-3 text-xs text-slate-600">
                      No swing lows returned.
                    </p>
                  )}
                </div>
              </div>

              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-600">
                  Structure Reasons
                </p>

                {result.reasons.length > 0 ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {result.reasons.map(
                      (reason) => (
                        <span
                          key={reason}
                          className="rounded-full border border-blue-400/10 bg-blue-500/[0.04] px-3 py-1.5 text-[10px] font-bold text-slate-400"
                        >
                          {reason}
                        </span>
                      ),
                    )}
                  </div>
                ) : (
                  <p className="mt-3 text-xs text-slate-600">
                    No detailed structure reasons were returned.
                  </p>
                )}
              </div>
            </div>
          ) : (
            <div className="flex min-h-[430px] items-center justify-center p-6">
              <div className="max-w-md text-center">
                <div className="midnight-pulse mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-cyan-300/20 bg-blue-500/[0.06] text-xl font-black text-cyan-200">
                  M
                </div>

                <h3 className="mt-5 text-lg font-black text-white">
                  Ready for live structure mapping
                </h3>

                <p className="mt-3 text-sm leading-6 text-slate-500">
                  Select a market and timeframe, then run
                  the structure analysis to load the real
                  backend result.
                </p>
              </div>
            </div>
          )}
        </div>

        <aside className="midnight-panel rounded-3xl p-5">
          <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
            Structure Validation
          </p>

          <h2 className="mt-2 text-lg font-black text-white">
            Mandatory checks
          </h2>

          <div className="mt-5 space-y-3">
            {[
              "Swing highs and lows must be confirmed",
              "BOS must break a valid structural level",
              "CHoCH must show a genuine control shift",
              "Higher timeframe bias must agree",
              "Support and resistance must be respected",
              "Duplicate structure signals stay on cooldown",
            ].map((rule) => (
              <div
                key={rule}
                className="flex items-start gap-3 rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4"
              >
                <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-cyan-300 shadow-[0_0_10px_rgba(34,211,238,0.7)]" />

                <p className="text-xs leading-5 text-slate-400">
                  {rule}
                </p>
              </div>
            ))}
          </div>
        </aside>
      </section>
    </div>
  );
}