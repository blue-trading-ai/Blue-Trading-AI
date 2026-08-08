"use client";

import { useState } from "react";

import { usePerformance } from "@/hooks/use-performance";

const periods = [
  "7 Days",
  "30 Days",
  "90 Days",
  "All Time",
];

const markets = [
  "All Markets",
  "XAUUSD",
  "BTCUSD",
  "GBPUSD",
];

function formatNumber(
  value: number | null | undefined,
  digits = 0,
): string {
  if (
    value === null ||
    value === undefined ||
    !Number.isFinite(value)
  ) {
    return "—";
  }

  return value.toFixed(digits);
}

function formatPercent(
  value: number | null | undefined,
): string {
  if (
    value === null ||
    value === undefined ||
    !Number.isFinite(value)
  ) {
    return "—";
  }

  return `${value.toFixed(1)}%`;
}

function formatTime(
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

export default function PerformancePage() {
  const [period, setPeriod] =
    useState("30 Days");

  const [market, setMarket] =
    useState("All Markets");

  const {
    summary,
    isLoading,
    error,
    lastUpdated,
    load,
    clear,
  } = usePerformance();

  async function handleRefresh() {
    await load(period, market);
  }

  const summaryCards = [
    {
      label: "Win Rate",
      value: summary
        ? formatPercent(summary.winRate)
        : "—",
      note: "Calculated from verified results",
    },
    {
      label: "Total Signals",
      value: summary
        ? String(summary.totalSignals)
        : "—",
      note: "Approved signals only",
    },
    {
      label: "Successful Signals",
      value: summary
        ? String(summary.successfulSignals)
        : "—",
      note: "TP reached before stop loss",
    },
    {
      label: "Average Confidence",
      value: summary
        ? formatPercent(
            summary.averageConfidence,
          )
        : "—",
      note: "Minimum approval threshold: 80%",
    },
  ];

  const qualityMetrics = [
    {
      title: "Average Risk–Reward",
      value: summary
        ? `1:${formatNumber(
            summary.averageRiskReward,
            2,
          )}`
        : "—",
      description:
        "Average planned reward relative to initial risk.",
    },
    {
      title: "Best Performing Market",
      value:
        summary?.bestMarket || "—",
      description:
        "Market with the strongest verified signal performance.",
    },
    {
      title: "Best Timeframe",
      value:
        summary?.bestTimeframe || "—",
      description:
        "Timeframe producing the most consistent approved setups.",
    },
    {
      title: "Maximum Drawdown",
      value: summary
        ? formatPercent(
            summary.maximumDrawdown,
          )
        : "—",
      description:
        "Largest decline across completed signal outcomes.",
    },
    {
      title: "Average Confirmations",
      value: summary
        ? formatNumber(
            summary.averageConfirmations,
            1,
          )
        : "—",
      description:
        "Average confirmations for approved signals.",
    },
    {
      title: "No-Trade Rejections",
      value: summary
        ? String(
            summary.rejectedSignals,
          )
        : "—",
      description:
        "Setups blocked by confidence, risk, structure, or news rules.",
    },
  ];

  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-cyan-300">
            Performance Intelligence
          </p>

          <h1 className="mt-2 text-3xl font-black tracking-tight text-white">
            Signal Performance
          </h1>

          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">
            Review verified performance of approved
            Blue-Trading-AI signals. Rejected and
            low-confidence setups are excluded from
            official results.
          </p>
        </div>

        <div className="flex items-center gap-3 rounded-2xl border border-emerald-400/15 bg-emerald-400/[0.05] px-4 py-3">
          <span className="midnight-status-dot h-2.5 w-2.5 rounded-full bg-emerald-400" />

          <div>
            <p className="text-xs font-black text-emerald-300">
              Performance Tracking Ready
            </p>

            <p className="mt-1 text-[10px] uppercase tracking-[0.12em] text-slate-600">
              Closed and verified signals only
            </p>
          </div>
        </div>
      </section>

      {error ? (
        <section className="rounded-2xl border border-rose-400/20 bg-rose-400/[0.05] p-4">
          <p className="text-xs font-black text-rose-300">
            Performance request failed
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
              Performance Period
            </span>

            <select
              value={period}
              onChange={(event) =>
                setPeriod(event.target.value)
              }
              disabled={isLoading}
              className="mt-2 w-full rounded-xl border border-blue-400/10 bg-[#091426] px-4 py-3 text-sm text-white focus:border-cyan-300/30 disabled:opacity-60"
            >
              {periods.map((item) => (
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
              Market
            </span>

            <select
              value={market}
              onChange={(event) =>
                setMarket(event.target.value)
              }
              disabled={isLoading}
              className="mt-2 w-full rounded-xl border border-blue-400/10 bg-[#091426] px-4 py-3 text-sm text-white focus:border-cyan-300/30 disabled:opacity-60"
            >
              {markets.map((item) => (
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
            onClick={() => void handleRefresh()}
            disabled={isLoading}
            className="midnight-button rounded-xl px-6 py-3 text-sm font-black disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isLoading
              ? "Loading Performance..."
              : "Refresh Performance"}
          </button>

          <button
            type="button"
            onClick={clear}
            disabled={isLoading || !summary}
            className="rounded-xl border border-blue-400/10 bg-blue-500/[0.04] px-6 py-3 text-sm font-black text-cyan-200 transition hover:border-cyan-300/20 hover:bg-blue-500/[0.08] disabled:cursor-not-allowed disabled:opacity-40"
          >
            Clear
          </button>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {summaryCards.map((item) => (
          <article
            key={item.label}
            className="midnight-panel rounded-2xl p-5"
          >
            <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-600">
              {item.label}
            </p>

            <p className="mt-3 text-3xl font-black text-white">
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
          <div className="flex flex-col gap-3 border-b border-blue-400/10 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
                Performance Overview
              </p>

              <h2 className="mt-2 text-lg font-black text-white">
                {market} · {period}
              </h2>
            </div>

            <span className="rounded-xl border border-blue-400/10 bg-blue-500/[0.04] px-3 py-2 text-[10px] font-black uppercase tracking-[0.12em] text-slate-500">
              Updated {formatTime(lastUpdated)}
            </span>
          </div>

          {summary ? (
            <div className="space-y-5 p-5">
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                {[
                  {
                    label: "Winning Signals",
                    value:
                      summary.successfulSignals,
                  },
                  {
                    label: "Losing Signals",
                    value:
                      summary.losingSignals,
                  },
                  {
                    label: "Open Signals",
                    value:
                      summary.openSignals,
                  },
                  {
                    label: "Rejected Setups",
                    value:
                      summary.rejectedSignals,
                  },
                ].map((item) => (
                  <div
                    key={item.label}
                    className="rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4"
                  >
                    <p className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-600">
                      {item.label}
                    </p>

                    <p className="mt-2 text-2xl font-black text-white">
                      {item.value}
                    </p>
                  </div>
                ))}
              </div>

              <div className="rounded-2xl border border-cyan-300/15 bg-cyan-300/[0.04] p-5">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-600">
                      Verified Win Rate
                    </p>

                    <p className="mt-2 text-3xl font-black text-cyan-200">
                      {formatPercent(
                        summary.winRate,
                      )}
                    </p>
                  </div>

                  <div className="h-3 flex-1 overflow-hidden rounded-full bg-slate-900">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-blue-600 to-cyan-300"
                      style={{
                        width: `${Math.min(
                          Math.max(
                            summary.winRate,
                            0,
                          ),
                          100,
                        )}%`,
                      }}
                    />
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-5">
                <p className="text-[10px] font-black uppercase tracking-[0.14em] text-slate-600">
                  Data policy
                </p>

                <p className="mt-3 text-xs leading-6 text-slate-500">
                  These statistics come from the official
                  Blue-Trading-AI performance endpoint.
                  Open signals are separated from completed
                  outcomes, and rejected setups are not
                  counted as approved trades.
                </p>
              </div>
            </div>
          ) : (
            <div className="flex min-h-[420px] items-center justify-center p-6">
              <div className="max-w-md text-center">
                <div className="midnight-pulse mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-cyan-300/20 bg-blue-500/[0.06] text-xl font-black text-cyan-200">
                  P
                </div>

                <h3 className="mt-5 text-lg font-black text-white">
                  Ready for verified performance data
                </h3>

                <p className="mt-3 text-sm leading-6 text-slate-500">
                  Select a period and market, then refresh
                  performance to load the official backend
                  statistics.
                </p>
              </div>
            </div>
          )}
        </div>

        <aside className="midnight-panel rounded-3xl p-5">
          <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
            Performance Rules
          </p>

          <h2 className="mt-2 text-lg font-black text-white">
            Official result policy
          </h2>

          <div className="mt-5 space-y-3">
            {[
              "Only approved signals are counted",
              "Open signals are excluded from final win rate",
              "TP must be reached before stop loss",
              "Cancelled or invalid signals are identified separately",
              "Duplicate signals are not counted twice",
              "Performance records must remain auditable",
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

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {qualityMetrics.map((item) => (
          <article
            key={item.title}
            className="midnight-panel rounded-2xl p-5"
          >
            <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-600">
              {item.title}
            </p>

            <p className="mt-3 text-2xl font-black text-white">
              {item.value}
            </p>

            <p className="mt-3 text-xs leading-5 text-slate-600">
              {item.description}
            </p>
          </article>
        ))}
      </section>
    </div>
  );
}