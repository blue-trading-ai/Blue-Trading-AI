"use client";

import { useState } from "react";

import { useMarketNews } from "@/hooks/use-market-news";
import type { MarketNewsEvent } from "@/lib/news-service";

const impactLevels = [
  "All Impact",
  "High",
  "Medium",
  "Low",
];

const markets = [
  "All Markets",
  "XAUUSD",
  "BTCUSD",
  "GBPUSD",
  "USD",
];

const periods = [
  "Today",
  "Next 24 Hours",
  "This Week",
  "All Upcoming",
];

function formatDateTime(
  value: string | null,
): string {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getImpactClasses(
  impact: MarketNewsEvent["impact"],
): string {
  if (impact === "HIGH") {
    return "border-rose-400/20 bg-rose-400/[0.08] text-rose-300";
  }

  if (impact === "MEDIUM") {
    return "border-amber-300/20 bg-amber-400/[0.08] text-amber-300";
  }

  if (impact === "LOW") {
    return "border-cyan-300/20 bg-cyan-300/[0.08] text-cyan-200";
  }

  return "border-slate-400/15 bg-slate-400/[0.06] text-slate-400";
}

function getActionClasses(
  event: MarketNewsEvent,
): string {
  if (event.conflict) {
    return "border-rose-400/20 bg-rose-400/[0.08] text-rose-300";
  }

  if (event.impact === "HIGH") {
    return "border-amber-300/20 bg-amber-400/[0.08] text-amber-300";
  }

  return "border-emerald-400/20 bg-emerald-400/[0.08] text-emerald-300";
}

function NewsRow({
  event,
}: {
  event: MarketNewsEvent;
}) {
  return (
    <tr className="border-b border-blue-400/[0.07] transition hover:bg-blue-500/[0.025]">
      <td className="px-5 py-4 text-xs text-slate-400">
        {formatDateTime(event.eventTime)}
      </td>

      <td className="px-5 py-4 text-xs font-black text-white">
        {event.currency}
      </td>

      <td className="px-5 py-4">
        <p className="max-w-[260px] text-xs font-black text-white">
          {event.title}
        </p>

        {event.source ? (
          <p className="mt-1 text-[10px] text-slate-600">
            Source: {event.source}
          </p>
        ) : null}
      </td>

      <td className="px-5 py-4">
        <span
          className={`inline-flex rounded-lg border px-2.5 py-1.5 text-[10px] font-black uppercase tracking-[0.1em] ${getImpactClasses(event.impact)}`}
        >
          {event.impact}
        </span>
      </td>

      <td className="px-5 py-4 text-xs text-slate-300">
        {event.forecast || "—"}
      </td>

      <td className="px-5 py-4 text-xs text-slate-300">
        {event.previous || "—"}
      </td>

      <td className="px-5 py-4">
        <div className="flex max-w-[240px] flex-wrap gap-1.5">
          {event.affectedMarkets.length ? (
            event.affectedMarkets.map((item) => (
              <span
                key={item}
                className="rounded-lg border border-blue-400/10 bg-blue-500/[0.04] px-2 py-1 text-[10px] font-black text-cyan-200"
              >
                {item}
              </span>
            ))
          ) : (
            <span className="text-xs text-slate-600">
              —
            </span>
          )}
        </div>
      </td>

      <td className="px-5 py-4">
        <span
          className={`inline-flex whitespace-nowrap rounded-lg border px-2.5 py-1.5 text-[10px] font-black uppercase tracking-[0.1em] ${getActionClasses(event)}`}
        >
          {event.signalAction}
        </span>
      </td>
    </tr>
  );
}

export default function NewsPage() {
  const [impact, setImpact] =
    useState("All Impact");

  const [market, setMarket] =
    useState("All Markets");

  const [period, setPeriod] =
    useState("Today");

  const {
    data,
    isLoading,
    error,
    lastUpdated,
    load,
    clear,
  } = useMarketNews();

  async function handleRefresh() {
    await load(
      impact,
      market,
      period,
    );
  }

  function resetFilters() {
    setImpact("All Impact");
    setMarket("All Markets");
    setPeriod("Today");
  }

  const cards = [
    {
      label: "Upcoming Events",
      value: data
        ? String(data.total)
        : "—",
      note: "Events matching selected filters",
    },
    {
      label: "High Impact",
      value: data
        ? String(data.highImpact)
        : "—",
      note: "Major market-moving events",
    },
    {
      label: "Signal Conflicts",
      value: data
        ? String(data.conflicts)
        : "—",
      note: "Setups requiring protection",
    },
    {
      label: "Affected Markets",
      value: data
        ? String(data.affectedMarkets)
        : "—",
      note: "Markets exposed to event risk",
    },
  ];

  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-cyan-300">
            Fundamental Intelligence
          </p>

          <h1 className="mt-2 text-3xl font-black tracking-tight text-white">
            Market News
          </h1>

          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">
            Track economic events, market-moving
            news, affected instruments, and potential
            conflicts before Blue-Trading-AI approves
            a signal.
          </p>
        </div>

        <div className="flex items-center gap-3 rounded-2xl border border-amber-400/15 bg-amber-400/[0.05] px-4 py-3">
          <span className="h-2.5 w-2.5 rounded-full bg-amber-300 shadow-[0_0_12px_rgba(252,211,77,0.75)]" />

          <div>
            <p className="text-xs font-black text-amber-300">
              News Conflict Protection
            </p>

            <p className="mt-1 text-[10px] uppercase tracking-[0.12em] text-slate-600">
              High-impact conflicts can block signals
            </p>
          </div>
        </div>
      </section>

      {error ? (
        <section className="rounded-2xl border border-rose-400/20 bg-rose-400/[0.05] p-4">
          <p className="text-xs font-black text-rose-300">
            Market news request failed
          </p>

          <p className="mt-2 text-xs leading-5 text-slate-500">
            {error}
          </p>
        </section>
      ) : null}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((item) => (
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

      <section className="midnight-panel rounded-3xl p-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
              News Filters
            </p>

            <h2 className="mt-2 text-lg font-black text-white">
              Find relevant economic events
            </h2>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={resetFilters}
              disabled={isLoading}
              className="rounded-xl border border-blue-400/10 bg-blue-500/[0.04] px-4 py-2.5 text-xs font-black text-cyan-200 disabled:opacity-50"
            >
              Reset Filters
            </button>

            <button
              type="button"
              onClick={clear}
              disabled={isLoading || !data}
              className="rounded-xl border border-blue-400/10 bg-blue-500/[0.04] px-4 py-2.5 text-xs font-black text-slate-400 disabled:opacity-40"
            >
              Clear Results
            </button>
          </div>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <label className="block">
            <span className="text-xs font-black text-slate-300">
              Impact
            </span>

            <select
              value={impact}
              onChange={(event) =>
                setImpact(event.target.value)
              }
              disabled={isLoading}
              className="mt-2 w-full rounded-xl border border-blue-400/10 bg-[#091426] px-4 py-3 text-sm text-white disabled:opacity-60"
            >
              {impactLevels.map((item) => (
                <option key={item}>
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
              className="mt-2 w-full rounded-xl border border-blue-400/10 bg-[#091426] px-4 py-3 text-sm text-white disabled:opacity-60"
            >
              {markets.map((item) => (
                <option key={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-xs font-black text-slate-300">
              Period
            </span>

            <select
              value={period}
              onChange={(event) =>
                setPeriod(event.target.value)
              }
              disabled={isLoading}
              className="mt-2 w-full rounded-xl border border-blue-400/10 bg-[#091426] px-4 py-3 text-sm text-white disabled:opacity-60"
            >
              {periods.map((item) => (
                <option key={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>

          <button
            type="button"
            onClick={() => void handleRefresh()}
            disabled={isLoading}
            className="midnight-button self-end rounded-xl px-5 py-3 text-sm font-black disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isLoading
              ? "Loading News..."
              : "Refresh Market News"}
          </button>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.25fr_0.75fr]">
        <div className="midnight-panel overflow-hidden rounded-3xl">
          <div className="flex flex-col gap-3 border-b border-blue-400/10 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
                Economic Calendar
              </p>

              <h2 className="mt-2 text-lg font-black text-white">
                Upcoming market events
              </h2>
            </div>

            <div className="text-right">
              <p className="rounded-xl border border-blue-400/10 bg-blue-500/[0.04] px-3 py-2 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500">
                {impact} · {market} · {period}
              </p>

              <p className="mt-2 text-[10px] text-slate-700">
                Updated{" "}
                {lastUpdated
                  ? lastUpdated.toLocaleTimeString()
                  : "not yet"}
              </p>
            </div>
          </div>

          {data?.events.length ? (
            <div className="overflow-x-auto">
              <table className="min-w-[1000px] w-full text-left">
                <thead className="border-b border-blue-400/10 bg-blue-500/[0.025]">
                  <tr>
                    {[
                      "Time",
                      "Currency",
                      "Event",
                      "Impact",
                      "Forecast",
                      "Previous",
                      "Affected Markets",
                      "Signal Action",
                    ].map((heading) => (
                      <th
                        key={heading}
                        className="px-5 py-4 text-[10px] font-black uppercase tracking-[0.14em] text-slate-600"
                      >
                        {heading}
                      </th>
                    ))}
                  </tr>
                </thead>

                <tbody>
                  {data.events.map((event) => (
                    <NewsRow
                      key={event.id}
                      event={event}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="flex min-h-[420px] items-center justify-center p-6">
              <div className="max-w-md text-center">
                <div className="midnight-pulse mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-amber-300/20 bg-amber-400/[0.06] text-xl font-black text-amber-300">
                  N
                </div>

                <h3 className="mt-5 text-lg font-black text-white">
                  {data
                    ? "No matching economic events"
                    : "Ready for live economic events"}
                </h3>

                <p className="mt-3 text-sm leading-6 text-slate-500">
                  {data
                    ? "The backend returned no verified events for the selected filters."
                    : "Choose the filters and refresh market news to load official backend data."}
                </p>
              </div>
            </div>
          )}
        </div>

        <aside className="space-y-6">
          <section className="midnight-panel rounded-3xl p-5">
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
              Signal Protection
            </p>

            <h2 className="mt-2 text-lg font-black text-white">
              News conflict rules
            </h2>

            <div className="mt-5 space-y-3">
              {[
                "Block signals near high-impact events",
                "Reduce confidence during uncertain releases",
                "Check event direction against technical bias",
                "Protect XAUUSD around major USD events",
                "Protect BTCUSD during major crypto events",
                "Record every news-based rejection reason",
              ].map((rule) => (
                <div
                  key={rule}
                  className="flex items-start gap-3 rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4"
                >
                  <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-amber-300 shadow-[0_0_10px_rgba(252,211,77,0.7)]" />

                  <p className="text-xs leading-5 text-slate-400">
                    {rule}
                  </p>
                </div>
              ))}
            </div>
          </section>

          <section className="midnight-panel rounded-3xl p-5">
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
              Current Protection State
            </p>

            <div
              className={`mt-4 rounded-2xl border p-5 ${
                data?.conflicts
                  ? "border-rose-400/20 bg-rose-400/[0.05]"
                  : data
                    ? "border-emerald-400/20 bg-emerald-400/[0.05]"
                    : "border-slate-400/10 bg-slate-400/[0.035]"
              }`}
            >
              <p
                className={`text-sm font-black ${
                  data?.conflicts
                    ? "text-rose-300"
                    : data
                      ? "text-emerald-300"
                      : "text-white"
                }`}
              >
                {data?.conflicts
                  ? `${data.conflicts} active news conflict${data.conflicts === 1 ? "" : "s"}`
                  : data
                    ? "No active conflict in loaded data"
                    : "Waiting for live news data"}
              </p>

              <p className="mt-3 text-xs leading-5 text-slate-500">
                {data?.conflicts
                  ? "Conflicting setups must remain blocked or under manual review."
                  : data
                    ? "Loaded events currently show no explicit signal conflict."
                    : "Blue-Trading-AI will not mark a market safe or blocked until verified event data is available."}
              </p>
            </div>
          </section>
        </aside>
      </section>
    </div>
  );
}