"use client";

import { useState } from "react";

import { RoleGuard } from "@/components/auth/role-guard";
import { useMonitoring } from "@/hooks/use-monitoring";
import { ACCESS_ROLES } from "@/lib/access-control";
import type {
  MonitoringAlert,
  MonitoringService,
} from "@/lib/monitoring-service";

const monitoringPeriods = [
  "Last 15 Minutes",
  "Last Hour",
  "Last 24 Hours",
  "Last 7 Days",
];

const serviceFilters = [
  "All Services",
  "Healthy",
  "Warning",
  "Critical",
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
    second: "2-digit",
  });
}

function getStatusClasses(
  status: string,
): string {
  const normalized =
    status.toUpperCase();

  if (
    normalized.includes("HEALTHY") ||
    normalized.includes("ONLINE") ||
    normalized.includes("ACTIVE") ||
    normalized.includes("OK")
  ) {
    return "border-emerald-400/20 bg-emerald-400/[0.08] text-emerald-300";
  }

  if (
    normalized.includes("WARNING") ||
    normalized.includes("DEGRADED")
  ) {
    return "border-amber-300/20 bg-amber-400/[0.08] text-amber-300";
  }

  if (
    normalized.includes("CRITICAL") ||
    normalized.includes("ERROR") ||
    normalized.includes("DOWN") ||
    normalized.includes("OFFLINE")
  ) {
    return "border-rose-400/20 bg-rose-400/[0.08] text-rose-300";
  }

  return "border-slate-400/15 bg-slate-400/[0.06] text-slate-400";
}

function getAlertClasses(
  severity: MonitoringAlert["severity"],
): string {
  if (severity === "CRITICAL") {
    return "border-rose-400/20 bg-rose-400/[0.06]";
  }

  if (severity === "WARNING") {
    return "border-amber-300/20 bg-amber-400/[0.06]";
  }

  return "border-cyan-300/15 bg-cyan-300/[0.04]";
}

function ServiceCard({
  service,
}: {
  service: MonitoringService;
}) {
  return (
    <article className="rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-black text-slate-300">
            {service.name}
          </p>

          {service.message ? (
            <p className="mt-1 text-[10px] leading-4 text-slate-600">
              {service.message}
            </p>
          ) : null}
        </div>

        <span
          className={`rounded-lg border px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.1em] ${getStatusClasses(service.status)}`}
        >
          {service.status}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3">
        <div>
          <p className="text-[10px] uppercase tracking-[0.1em] text-slate-700">
            Response
          </p>

          <p className="mt-1 text-sm font-black text-white">
            {service.responseTimeMs === null
              ? "—"
              : `${service.responseTimeMs.toFixed(0)} ms`}
          </p>
        </div>

        <div>
          <p className="text-[10px] uppercase tracking-[0.1em] text-slate-700">
            Last Check
          </p>

          <p className="mt-1 text-xs font-black text-white">
            {formatDateTime(
              service.lastCheckedAt,
            )}
          </p>
        </div>
      </div>
    </article>
  );
}

function AlertCard({
  alert,
}: {
  alert: MonitoringAlert;
}) {
  return (
    <article
      className={`rounded-2xl border p-4 ${getAlertClasses(alert.severity)}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-black text-white">
            {alert.title}
          </p>

          <p className="mt-2 text-xs leading-5 text-slate-500">
            {alert.message}
          </p>
        </div>

        <span
          className={`shrink-0 rounded-lg border px-2 py-1 text-[9px] font-black uppercase tracking-[0.1em] ${getStatusClasses(alert.severity)}`}
        >
          {alert.severity}
        </span>
      </div>

      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-slate-600">
        <span>
          Service: {alert.service || "General"}
        </span>

        <span>
          {formatDateTime(alert.createdAt)}
        </span>
      </div>
    </article>
  );
}

function MonitoringContent() {
  const [period, setPeriod] =
    useState("Last Hour");

  const [serviceFilter, setServiceFilter] =
    useState("All Services");

  const {
    data,
    isLoading,
    error,
    lastUpdated,
    load,
    clear,
  } = useMonitoring();

  async function handleRefresh() {
    await load(
      period,
      serviceFilter,
    );
  }

  function resetFilters() {
    setPeriod("Last Hour");
    setServiceFilter("All Services");
  }

  const summaryCards = [
    {
      label: "System Health",
      value: data?.systemHealth || "—",
      note: "Overall platform condition",
    },
    {
      label: "API Response Time",
      value: data
        ? `${data.averageResponseTimeMs.toFixed(0)} ms`
        : "—",
      note: "Average backend latency",
    },
    {
      label: "Active Alerts",
      value: data
        ? String(data.activeAlerts)
        : "—",
      note: "Warning and critical events",
    },
    {
      label: "Uptime",
      value: data
        ? `${data.uptimePercent.toFixed(2)}%`
        : "—",
      note: "Verified operational availability",
    },
  ];

  const criticalServices =
    data?.services.filter((service) => {
      const status =
        service.status.toUpperCase();

      return (
        status.includes("CRITICAL") ||
        status.includes("ERROR") ||
        status.includes("DOWN") ||
        status.includes("OFFLINE")
      );
    }).length || 0;

  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-cyan-300">
            Operational Intelligence
          </p>

          <h1 className="mt-2 text-3xl font-black tracking-tight text-white">
            System Monitoring
          </h1>

          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">
            Monitor Blue-Trading-AI backend services,
            database health, market-data providers,
            authentication, signal processing, and
            operational alerts.
          </p>
        </div>

        <div className="flex items-center gap-3 rounded-2xl border border-emerald-400/15 bg-emerald-400/[0.05] px-4 py-3">
          <span className="midnight-status-dot h-2.5 w-2.5 rounded-full bg-emerald-400" />

          <div>
            <p className="text-xs font-black text-emerald-300">
              Monitoring Ready
            </p>

            <p className="mt-1 text-[10px] uppercase tracking-[0.12em] text-slate-600">
              Protected telemetry endpoint
            </p>
          </div>
        </div>
      </section>

      {error ? (
        <section className="rounded-2xl border border-rose-400/20 bg-rose-400/[0.05] p-4">
          <p className="text-xs font-black text-rose-300">
            Monitoring request failed
          </p>

          <p className="mt-2 text-xs leading-5 text-slate-500">
            {error}
          </p>
        </section>
      ) : null}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {summaryCards.map((item) => (
          <article
            key={item.label}
            className="midnight-panel rounded-2xl p-5"
          >
            <p className="text-[10px] font-black uppercase tracking-[0.16em] text-slate-600">
              {item.label}
            </p>

            <p className="mt-3 break-words text-2xl font-black text-white">
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
              Monitoring Filters
            </p>

            <h2 className="mt-2 text-lg font-black text-white">
              Load verified platform telemetry
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
              Clear
            </button>
          </div>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-3">
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
              {monitoringPeriods.map((item) => (
                <option key={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-xs font-black text-slate-300">
              Service Status
            </span>

            <select
              value={serviceFilter}
              onChange={(event) =>
                setServiceFilter(
                  event.target.value,
                )
              }
              disabled={isLoading}
              className="mt-2 w-full rounded-xl border border-blue-400/10 bg-[#091426] px-4 py-3 text-sm text-white disabled:opacity-60"
            >
              {serviceFilters.map((item) => (
                <option key={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>

          <button
            type="button"
            onClick={() =>
              void handleRefresh()
            }
            disabled={isLoading}
            className="midnight-button self-end rounded-xl px-5 py-3 text-sm font-black disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isLoading
              ? "Loading Telemetry..."
              : "Refresh Monitoring"}
          </button>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="midnight-panel overflow-hidden rounded-3xl">
          <div className="flex flex-col gap-3 border-b border-blue-400/10 p-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
                Service Health
              </p>

              <h2 className="mt-2 text-lg font-black text-white">
                Platform components
              </h2>
            </div>

            <div className="text-right">
              <p className="rounded-xl border border-blue-400/10 bg-blue-500/[0.04] px-3 py-2 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-500">
                {serviceFilter} · {period}
              </p>

              <p className="mt-2 text-[10px] text-slate-700">
                Updated{" "}
                {lastUpdated
                  ? lastUpdated.toLocaleTimeString()
                  : "not yet"}
              </p>
            </div>
          </div>

          {data?.services.length ? (
            <div className="grid gap-3 p-5 md:grid-cols-2">
              {data.services.map((service) => (
                <ServiceCard
                  key={service.name}
                  service={service}
                />
              ))}
            </div>
          ) : (
            <div className="flex min-h-[360px] items-center justify-center p-6">
              <div className="max-w-md text-center">
                <div className="midnight-pulse mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-cyan-300/20 bg-blue-500/[0.06] text-xl font-black text-cyan-200">
                  M
                </div>

                <h3 className="mt-5 text-lg font-black text-white">
                  {data
                    ? "No matching services"
                    : "Ready for live telemetry"}
                </h3>

                <p className="mt-3 text-sm leading-6 text-slate-500">
                  {data
                    ? "The backend returned no service records for the selected status."
                    : "Choose the filters and refresh monitoring to load verified platform telemetry."}
                </p>
              </div>
            </div>
          )}
        </div>

        <aside className="space-y-6">
          <section className="midnight-panel rounded-3xl p-5">
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
              Operational Alerts
            </p>

            <h2 className="mt-2 text-lg font-black text-white">
              Warning and critical events
            </h2>

            <div className="mt-5 space-y-3">
              {data?.alerts.length ? (
                data.alerts.map((alert) => (
                  <AlertCard
                    key={alert.id}
                    alert={alert}
                  />
                ))
              ) : (
                <div className="flex min-h-[260px] items-center justify-center rounded-2xl border border-blue-400/10 bg-blue-500/[0.025] p-5">
                  <div className="max-w-xs text-center">
                    <div className="midnight-pulse mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-emerald-400/20 bg-emerald-400/[0.06] text-lg font-black text-emerald-300">
                      ✓
                    </div>

                    <p className="mt-4 text-sm font-black text-white">
                      {data
                        ? "No active alerts returned"
                        : "Waiting for live alerts"}
                    </p>

                    <p className="mt-2 text-xs leading-5 text-slate-500">
                      {data
                        ? "The loaded monitoring data contains no warning or critical events."
                        : "Refresh monitoring to load verified operational alerts."}
                    </p>
                  </div>
                </div>
              )}
            </div>
          </section>

          <section className="midnight-panel rounded-3xl p-5">
            <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
              Protection State
            </p>

            <div
              className={`mt-4 rounded-2xl border p-5 ${
                criticalServices > 0
                  ? "border-rose-400/20 bg-rose-400/[0.05]"
                  : data
                    ? "border-emerald-400/20 bg-emerald-400/[0.05]"
                    : "border-slate-400/10 bg-slate-400/[0.035]"
              }`}
            >
              <p
                className={`text-sm font-black ${
                  criticalServices > 0
                    ? "text-rose-300"
                    : data
                      ? "text-emerald-300"
                      : "text-white"
                }`}
              >
                {criticalServices > 0
                  ? `${criticalServices} critical service${criticalServices === 1 ? "" : "s"} detected`
                  : data
                    ? "No critical service failures"
                    : "Monitoring data unavailable"}
              </p>

              <p className="mt-3 text-xs leading-5 text-slate-500">
                {criticalServices > 0
                  ? "New signal generation should remain paused until critical services recover."
                  : data
                    ? "Loaded telemetry currently shows no critical component failure."
                    : "Blue-Trading-AI will not mark services as healthy until verified telemetry is available."}
              </p>
            </div>
          </section>
        </aside>
      </section>

      <section className="grid gap-6 xl:grid-cols-2">
        <article className="midnight-panel rounded-3xl p-5">
          <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
            API Performance
          </p>

          <h2 className="mt-2 text-lg font-black text-white">
            Request health
          </h2>

          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            {[
              {
                label: "Average Latency",
                value: data
                  ? `${data.averageResponseTimeMs.toFixed(0)} ms`
                  : "—",
              },
              {
                label: "Slow Requests",
                value: data
                  ? String(data.slowRequests)
                  : "—",
              },
              {
                label: "Error Rate",
                value: data
                  ? `${data.errorRatePercent.toFixed(2)}%`
                  : "—",
              },
              {
                label: "Requests Processed",
                value: data
                  ? String(data.requestsProcessed)
                  : "—",
              },
            ].map((metric) => (
              <div
                key={metric.label}
                className="rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4"
              >
                <p className="text-[10px] font-black uppercase tracking-[0.12em] text-slate-600">
                  {metric.label}
                </p>

                <p className="mt-2 text-2xl font-black text-cyan-200">
                  {metric.value}
                </p>
              </div>
            ))}
          </div>
        </article>

        <article className="midnight-panel rounded-3xl p-5">
          <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
            Monitoring Rules
          </p>

          <h2 className="mt-2 text-lg font-black text-white">
            Operational safety
          </h2>

          <div className="mt-5 space-y-3">
            {[
              "Critical service failures must pause new signals",
              "Market-data outages must block analysis",
              "Authentication failures must trigger alerts",
              "Database errors must preserve audit integrity",
              "Provider latency must be measured continuously",
              "Every operational alert must include a timestamp",
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
        </article>
      </section>
    </div>
  );
}

export default function MonitoringPage() {
  return (
    <RoleGuard
      allowedRoles={ACCESS_ROLES.monitoring}
    >
      <MonitoringContent />
    </RoleGuard>
  );
}