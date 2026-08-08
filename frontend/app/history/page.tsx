"use client";

import { useState } from "react";

import { useTradeHistory } from "@/hooks/use-trade-history";
import type { TradeHistoryRecord } from "@/lib/history-service";

const markets = ["All Markets", "XAUUSD", "BTCUSD", "GBPUSD"];
const directions = ["All Directions", "BUY", "SELL"];
const statuses = ["All Statuses", "OPEN", "TP HIT", "SL HIT", "CANCELLED"];
const periods = ["7 Days", "30 Days", "90 Days", "All Time"];

function formatDate(value: string | null): string {
  if (!value) return "—";

  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString([], {
        year: "numeric",
        month: "short",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
}

function formatValue(value: number | string | null): string {
  return value === null || value === "" ? "—" : String(value);
}

function getStatusClasses(status: string): string {
  const normalized = status.toUpperCase();

  if (
    normalized.includes("TP") ||
    normalized === "WIN" ||
    normalized === "WON"
  ) {
    return "border-emerald-400/20 bg-emerald-400/[0.08] text-emerald-300";
  }

  if (
    normalized.includes("SL") ||
    normalized === "LOSS" ||
    normalized === "LOST"
  ) {
    return "border-rose-400/20 bg-rose-400/[0.08] text-rose-300";
  }

  if (["OPEN", "ACTIVE", "PENDING"].includes(normalized)) {
    return "border-cyan-300/20 bg-cyan-300/[0.08] text-cyan-200";
  }

  return "border-slate-400/15 bg-slate-400/[0.06] text-slate-400";
}

function HistoryRow({ record }: { record: TradeHistoryRecord }) {
  const directionClasses =
    record.direction === "BUY" ? "text-emerald-300" : "text-rose-300";

  return (
    <tr className="border-b border-blue-400/[0.07] transition hover:bg-blue-500/[0.025]">
      <td className="px-5 py-4">
        <p className="max-w-[150px] truncate text-xs font-black text-white">
          {record.id}
        </p>
        <p className="mt-1 text-[10px] text-slate-600">
          {record.confirmations} confirmations
        </p>
      </td>
      <td className="px-5 py-4 text-sm font-black text-white">
        {record.symbol}
      </td>
      <td className="px-5 py-4 text-xs font-bold text-slate-400">
        {record.timeframe}
      </td>
      <td className={`px-5 py-4 text-xs font-black ${directionClasses}`}>
        {record.direction}
      </td>
      <td className="px-5 py-4 text-xs text-slate-300">
        {formatValue(record.entry)}
      </td>
      <td className="px-5 py-4 text-xs text-rose-300">
        {formatValue(record.stopLoss)}
      </td>
      <td className="px-5 py-4 text-xs text-emerald-300">
        {formatValue(record.takeProfit1)}
      </td>
      <td className="px-5 py-4">
        <span className="rounded-lg border border-blue-400/10 bg-blue-500/[0.04] px-2.5 py-1.5 text-xs font-black text-cyan-200">
          {record.confidence.toFixed(1)}%
        </span>
      </td>
      <td className="px-5 py-4 text-xs font-black text-white">
        {formatValue(record.riskReward)}
      </td>
      <td className="px-5 py-4">
        <span
          className={`inline-flex rounded-lg border px-2.5 py-1.5 text-[10px] font-black uppercase tracking-[0.1em] ${getStatusClasses(record.status)}`}
        >
          {record.status}
        </span>
      </td>
      <td className="px-5 py-4 text-xs text-slate-500">
        {formatDate(record.createdAt)}
      </td>
    </tr>
  );
}

export default function HistoryPage() {
  const [market, setMarket] = useState("All Markets");
  const [direction, setDirection] = useState("All Directions");
  const [status, setStatus] = useState("All Statuses");
  const [period, setPeriod] = useState("30 Days");

  const {
    data,
    isLoading,
    error,
    lastUpdated,
    load,
    clear,
  } = useTradeHistory();

  async function handleRefresh() {
    await load(market, direction, status, period);
  }

  function resetFilters() {
    setMarket("All Markets");
    setDirection("All Directions");
    setStatus("All Statuses");
    setPeriod("30 Days");
  }

  const cards = [
    ["Total Records", data ? String(data.total) : "—", "Approved historical signals"],
    ["TP Hit", data ? String(data.tpHit) : "—", "Successful completed signals"],
    ["SL Hit", data ? String(data.slHit) : "—", "Losing completed signals"],
    ["Open Signals", data ? String(data.open) : "—", "Still awaiting final outcome"],
  ];

  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-cyan-300">
            Historical Intelligence
          </p>
          <h1 className="mt-2 text-3xl font-black tracking-tight text-white">
            Trade History
          </h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">
            Review approved Blue-Trading-AI signals, final outcomes,
            confidence, confirmations, risk–reward, and audit information.
          </p>
        </div>

        <div className="flex items-center gap-3 rounded-2xl border border-emerald-400/15 bg-emerald-400/[0.05] px-4 py-3">
          <span className="midnight-status-dot h-2.5 w-2.5 rounded-full bg-emerald-400" />
          <div>
            <p className="text-xs font-black text-emerald-300">
              History Tracking Ready
            </p>
            <p className="mt-1 text-[10px] uppercase tracking-[0.12em] text-slate-600">
              Approved and auditable records only
            </p>
          </div>
        </div>
      </section>

      {error ? (
        <section className="rounded-2xl border border-rose-400/20 bg-rose-400/[0.05] p-4">
          <p className="text-xs font-black text-rose-300">
            Trade history request failed
          </p>
          <p className="mt-2 text-xs leading-5 text-slate-500">{error}</p>
        </section>
      ) : null}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map(([label, value, note]) => (
          <article key={label} className="midnight-panel rounded-2xl p-5">
            <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-600">
              {label}
            </p>
            <p className="mt-3 text-3xl font-black text-white">{value}</p>
            <p className="mt-2 text-xs text-slate-600">{note}</p>
          </article>
        ))}
      </section>

      <section className="midnight-panel rounded-3xl p-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
              History Filters
            </p>
            <h2 className="mt-2 text-lg font-black text-white">
              Find verified signal records
            </h2>
          </div>

          <div className="flex gap-3">
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

        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          {[
            ["Market", market, setMarket, markets],
            ["Direction", direction, setDirection, directions],
            ["Status", status, setStatus, statuses],
            ["Period", period, setPeriod, periods],
          ].map(([label, value, setter, options]) => (
            <label key={String(label)} className="block">
              <span className="text-xs font-black text-slate-300">
                {String(label)}
              </span>
              <select
                value={String(value)}
                onChange={(event) =>
                  (setter as React.Dispatch<React.SetStateAction<string>>)(
                    event.target.value,
                  )
                }
                disabled={isLoading}
                className="mt-2 w-full rounded-xl border border-blue-400/10 bg-[#091426] px-4 py-3 text-sm text-white disabled:opacity-60"
              >
                {(options as string[]).map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </label>
          ))}

          <button
            type="button"
            onClick={() => void handleRefresh()}
            disabled={isLoading}
            className="midnight-button self-end rounded-xl px-5 py-3 text-sm font-black disabled:opacity-60"
          >
            {isLoading ? "Loading History..." : "Refresh History"}
          </button>
        </div>
      </section>

      <section className="midnight-panel overflow-hidden rounded-3xl">
        <div className="flex flex-col gap-3 border-b border-blue-400/10 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
              Verified Records
            </p>
            <h2 className="mt-2 text-lg font-black text-white">
              Historical signal outcomes
            </h2>
          </div>

          <div className="text-right">
            <p className="rounded-xl border border-blue-400/10 bg-blue-500/[0.04] px-3 py-2 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500">
              {market} · {direction} · {status} · {period}
            </p>
            <p className="mt-2 text-[10px] text-slate-700">
              Updated {lastUpdated ? lastUpdated.toLocaleTimeString() : "not yet"}
            </p>
          </div>
        </div>

        {data?.records.length ? (
          <div className="overflow-x-auto">
            <table className="min-w-[1100px] w-full text-left">
              <thead className="border-b border-blue-400/10 bg-blue-500/[0.025]">
                <tr>
                  {[
                    "Signal",
                    "Market",
                    "Timeframe",
                    "Direction",
                    "Entry",
                    "Stop Loss",
                    "TP1",
                    "Confidence",
                    "R:R",
                    "Status",
                    "Created",
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
                {data.records.map((record) => (
                  <HistoryRow key={record.id} record={record} />
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="flex min-h-[360px] items-center justify-center p-6">
            <div className="max-w-md text-center">
              <div className="midnight-pulse mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-cyan-300/20 bg-blue-500/[0.06] text-xl font-black text-cyan-200">
                H
              </div>
              <h3 className="mt-5 text-lg font-black text-white">
                {data ? "No matching history records" : "Ready for verified history"}
              </h3>
              <p className="mt-3 text-sm leading-6 text-slate-500">
                {data
                  ? "The backend returned no verified records for the selected filters."
                  : "Choose the filters and refresh history to load official backend records."}
              </p>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}