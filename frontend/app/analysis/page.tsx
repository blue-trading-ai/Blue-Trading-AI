"use client";

import { useState } from "react";

import { useMarketAnalysis } from "@/hooks/use-market-analysis";

const symbols = [
  "XAUUSD",
  "BTCUSD",
  "GBPUSD",
];

function formatValue(
  value: number | string | null,
): string {
  if (
    value === null ||
    value === ""
  ) {
    return "—";
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

export default function AnalysisPage() {
  const [symbol, setSymbol] =
    useState("XAUUSD");

  const {
    result,
    isAnalyzing,
    error,
    lastAnalyzed,
    analyze,
    clear,
  } = useMarketAnalysis();

  async function handleAnalyze() {
    await analyze(symbol);
  }

  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-cyan-300">
            Market Intelligence
          </p>

          <h1 className="mt-2 text-3xl font-black tracking-tight text-white">
            Technical Market Analysis
          </h1>

          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">
            Review market structure, Smart Money Concepts,
            trend, momentum and multi-timeframe confirmation
            before any signal is approved.
          </p>
        </div>

        <div className="flex items-center gap-3 rounded-2xl border border-emerald-400/15 bg-emerald-400/[0.05] px-4 py-3">
          <span className="midnight-status-dot h-2.5 w-2.5 rounded-full bg-emerald-400" />

          <div>
            <p className="text-xs font-black text-emerald-300">
              Analysis Engine Ready
            </p>

            <p className="mt-1 text-[10px] uppercase tracking-[0.12em] text-slate-600">
              No trade below quality threshold
            </p>
          </div>
        </div>
      </section>

      {error ? (
        <section className="rounded-2xl border border-rose-400/20 bg-rose-400/[0.05] p-4">
          <p className="text-xs font-black text-rose-300">
            Analysis request failed
          </p>

          <p className="mt-2 text-xs leading-5 text-slate-500">
            {error}
          </p>
        </section>
      ) : null}

      <section className="midnight-panel rounded-3xl p-5">
        <div className="grid gap-4 lg:grid-cols-[1fr_auto_auto] lg:items-end">
          <label className="block">
            <span className="text-xs font-black text-slate-300">
              Market
            </span>

            <select
              value={symbol}
              onChange={(event) =>
                setSymbol(event.target.value)
              }
              disabled={isAnalyzing}
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

          <button
            type="button"
            onClick={() => void handleAnalyze()}
            disabled={isAnalyzing}
            className="midnight-button rounded-xl px-6 py-3 text-sm font-black disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isAnalyzing
              ? "Analyzing..."
              : "Run Analysis"}
          </button>

          <button
            type="button"
            onClick={clear}
            disabled={isAnalyzing || !result}
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
            note: "Live backend analysis",
          },
          {
            label: "Analysis Mode",
            value: "Multi-Timeframe",
            note: "M5 · M15 · M30 · H1 · H4 · D1",
          },
          {
            label: "Confidence",
            value: result
              ? `${result.confidence}%`
              : "—",
            note: "Minimum required: 80%",
          },
          {
            label: "Confirmations",
            value: result
              ? String(result.confirmations)
              : "—",
            note: `Last analysis: ${formatTime(
              lastAnalyzed,
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

      <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="midnight-panel overflow-hidden rounded-3xl">
          <div className="border-b border-blue-400/10 p-5">
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
              Analysis Result
            </p>

            <h2 className="mt-2 text-lg font-black text-white">
              {result
                ? `${result.symbol} · ${result.timeframe}`
                : `${symbol} · Multi-Timeframe`}
            </h2>
          </div>

          {result ? (
            <div className="space-y-5 p-5">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-600">
                    Direction
                  </p>

                  <p className="mt-2 text-3xl font-black text-cyan-200">
                    {result.signal || "NO TRADE"}
                  </p>
                </div>

                <div className="rounded-2xl border border-cyan-300/15 bg-cyan-300/[0.04] p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-600">
                    Market Structure
                  </p>

                  <p className="mt-2 text-sm font-black text-white">
                    {result.marketStructure ||
                      "Not provided"}
                  </p>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                {[
                  {
                    label: "Entry",
                    value: formatValue(
                      result.entry,
                    ),
                  },
                  {
                    label: "Stop Loss",
                    value: formatValue(
                      result.stopLoss,
                    ),
                  },
                  {
                    label: "Take Profit 1",
                    value: formatValue(
                      result.takeProfit1,
                    ),
                  },
                  {
                    label: "Take Profit 2",
                    value: formatValue(
                      result.takeProfit2,
                    ),
                  },
                  {
                    label: "Risk–Reward",
                    value: formatValue(
                      result.riskReward,
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
                <div className="rounded-2xl border border-cyan-300/15 bg-cyan-300/[0.04] p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-600">
                    Confidence
                  </p>

                  <div className="mt-3 flex items-center gap-3">
                    <p className="text-2xl font-black text-cyan-200">
                      {result.confidence}%
                    </p>

                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-900">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-blue-600 to-cyan-300"
                        style={{
                          width: `${Math.min(
                            Math.max(
                              result.confidence,
                              0,
                            ),
                            100,
                          )}%`,
                        }}
                      />
                    </div>
                  </div>
                </div>

                <div className="rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4">
                  <p className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-600">
                    Confirmations
                  </p>

                  <p className="mt-3 text-2xl font-black text-white">
                    {result.confirmations}
                  </p>

                  <p className="mt-1 text-[10px] text-slate-600">
                    Minimum required: 3
                  </p>
                </div>
              </div>

              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-600">
                  Analysis Reasons
                </p>

                {result.reasons.length > 0 ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {result.reasons.map((reason) => (
                      <span
                        key={reason}
                        className="rounded-full border border-blue-400/10 bg-blue-500/[0.04] px-3 py-1.5 text-[10px] font-bold text-slate-400"
                      >
                        {reason}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="mt-3 text-xs text-slate-600">
                    No detailed reasons were returned by the backend.
                  </p>
                )}
              </div>
            </div>
          ) : (
            <div className="flex min-h-[420px] items-center justify-center p-6">
              <div className="max-w-md text-center">
                <div className="midnight-pulse mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-cyan-300/20 bg-blue-500/[0.06] text-xl font-black text-cyan-200">
                  A
                </div>

                <h3 className="mt-5 text-lg font-black text-white">
                  Ready for live market analysis
                </h3>

                <p className="mt-3 text-sm leading-6 text-slate-500">
                  Select a market, then run the automatic
                  multi-timeframe analysis to load the real backend result.
                </p>
              </div>
            </div>
          )}
        </div>

        <aside className="midnight-panel rounded-3xl p-5">
          <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
            Signal Approval Gate
          </p>

          <h2 className="mt-2 text-lg font-black text-white">
            Mandatory checks
          </h2>

          <div className="mt-5 space-y-3">
            {[
              "Confidence must be 80% or higher",
              "At least three confirmations",
              "Market structure must be valid",
              "Multi-timeframe bias must align",
              "Risk–reward must be at least 1:1.5",
              "News or fundamental conflict must be blocked",
              "Duplicate signals remain on cooldown",
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