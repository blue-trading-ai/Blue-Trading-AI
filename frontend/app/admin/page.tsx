"use client";

import { useState } from "react";

import { RoleGuard } from "@/components/auth/role-guard";
import { useAdmin } from "@/hooks/use-admin";
import { useCurrentUser } from "@/hooks/use-current-user";
import {
  ACCESS_ROLES,
  isOwnerRole,
} from "@/lib/access-control";
import type {
  AdminServiceStatus,
  AdminUser,
} from "@/lib/admin-service";

const approvalFilters = [
  "Pending Approval",
  "Approved",
  "Rejected",
  "All Users",
] as const;

function formatDate(
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
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function normalizeStatus(
  value: unknown,
): string {
  return typeof value === "string"
    ? value.trim().toUpperCase()
    : "";
}

function getStatusClasses(
  status: string,
): string {
  const normalized =
    normalizeStatus(status);

  if (
    normalized.includes("APPROVED") ||
    normalized.includes("HEALTHY") ||
    normalized.includes("ONLINE") ||
    normalized.includes("ACTIVE")
  ) {
    return "border-emerald-400/20 bg-emerald-400/[0.08] text-emerald-300";
  }

  if (
    normalized.includes("PENDING") ||
    normalized.includes("WARNING") ||
    normalized.includes("DEGRADED")
  ) {
    return "border-amber-300/20 bg-amber-400/[0.08] text-amber-300";
  }

  if (
    normalized.includes("REJECTED") ||
    normalized.includes("ERROR") ||
    normalized.includes("DOWN") ||
    normalized.includes("OFFLINE") ||
    normalized.includes("SUSPENDED") ||
    normalized.includes("INACTIVE")
  ) {
    return "border-rose-400/20 bg-rose-400/[0.08] text-rose-300";
  }

  return "border-slate-400/15 bg-slate-400/[0.06] text-slate-400";
}

function AdminUserRow({
  user,
  isBusy,
  onApprove,
  onReject,
}: {
  user: AdminUser;
  isBusy: boolean;
  onApprove: (userId: string) => void;
  onReject: (userId: string) => void;
}) {
  const normalizedStatus =
    normalizeStatus(user.status);

  const isApproved =
    normalizedStatus.includes(
      "APPROVED",
    );

  const isRejected =
    normalizedStatus.includes(
      "REJECTED",
    );

  const isPrivilegedAccount =
    isOwnerRole(user.role);

  return (
    <tr className="border-b border-blue-400/[0.07] transition hover:bg-blue-500/[0.025]">
      <td className="px-5 py-4">
        <p className="text-xs font-black text-white">
          {user.fullName}
        </p>

        <p className="mt-1 max-w-[150px] truncate text-[10px] text-slate-600">
          {user.id}
        </p>
      </td>

      <td className="px-5 py-4 text-xs text-slate-300">
        {user.email}
      </td>

      <td className="px-5 py-4 text-xs text-slate-500">
        {formatDate(user.createdAt)}
      </td>

      <td className="px-5 py-4">
        <span
          className={`inline-flex rounded-lg border px-2.5 py-1.5 text-[10px] font-black uppercase tracking-[0.1em] ${
            user.emailVerified
              ? "border-emerald-400/20 bg-emerald-400/[0.08] text-emerald-300"
              : "border-amber-300/20 bg-amber-400/[0.08] text-amber-300"
          }`}
        >
          {user.emailVerified
            ? "Verified"
            : "Unverified"}
        </span>
      </td>

      <td className="px-5 py-4">
        <span
          className={`inline-flex rounded-lg border px-2.5 py-1.5 text-[10px] font-black uppercase tracking-[0.1em] ${getStatusClasses(
            user.status,
          )}`}
        >
          {user.status}
        </span>
      </td>

      <td className="px-5 py-4 text-xs font-black text-cyan-200">
        {user.role}
      </td>

      <td className="px-5 py-4">
        {isPrivilegedAccount ? (
          <span className="inline-flex rounded-lg border border-amber-300/20 bg-amber-400/[0.06] px-3 py-2 text-[10px] font-black uppercase tracking-[0.08em] text-amber-300">
            Protected
          </span>
        ) : (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() =>
                onApprove(user.id)
              }
              disabled={
                isBusy ||
                isApproved
              }
              className="rounded-lg border border-emerald-400/20 bg-emerald-400/[0.07] px-3 py-2 text-[10px] font-black uppercase tracking-[0.08em] text-emerald-300 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Approve
            </button>

            <button
              type="button"
              onClick={() =>
                onReject(user.id)
              }
              disabled={
                isBusy ||
                isRejected
              }
              className="rounded-lg border border-rose-400/20 bg-rose-400/[0.07] px-3 py-2 text-[10px] font-black uppercase tracking-[0.08em] text-rose-300 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Reject
            </button>
          </div>
        )}
      </td>
    </tr>
  );
}

function ServiceStatus({
  service,
}: {
  service: AdminServiceStatus;
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4">
      <div>
        <p className="text-xs font-black text-slate-300">
          {service.name}
        </p>

        {service.message ? (
          <p className="mt-1 text-[10px] text-slate-600">
            {service.message}
          </p>
        ) : null}
      </div>

      <span
        className={`rounded-lg border px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.1em] ${getStatusClasses(
          service.status,
        )}`}
      >
        {service.status}
      </span>
    </div>
  );
}

function AdminContent() {
  const [approvalFilter, setApprovalFilter] =
    useState<(typeof approvalFilters)[number]>(
      "Pending Approval",
    );

  const {
    user: currentUser,
  } = useCurrentUser();

  const {
    data,
    isLoading,
    action,
    error,
    lastUpdated,
    load,
    approveUser,
    rejectUser,
    clear,
  } = useAdmin();

  const currentRoles = Array.isArray(
    currentUser?.roles,
  )
    ? currentUser.roles
    : [];

  const isOwner =
    currentUser?.is_owner === true ||
    isOwnerRole(currentUser?.role) ||
    currentRoles.some(isOwnerRole);

  const isBusy =
    isLoading || action !== null;

  async function handleLoad() {
    await load(approvalFilter);
  }

  async function handleApprove(
    userId: string,
  ) {
    const confirmed =
      window.confirm(
        "Approve this user account?",
      );

    if (!confirmed) {
      return;
    }

    await approveUser(
      userId,
      approvalFilter,
    );
  }

  async function handleReject(
    userId: string,
  ) {
    const confirmed =
      window.confirm(
        "Reject this user account?",
      );

    if (!confirmed) {
      return;
    }

    await rejectUser(
      userId,
      approvalFilter,
    );
  }

  const cards = [
    {
      label: "Pending Users",
      value: data
        ? String(data.pendingUsers)
        : "—",
      note:
        "Awaiting administrative review",
    },
    {
      label: "Approved Users",
      value: data
        ? String(data.approvedUsers)
        : "—",
      note:
        "Active platform accounts",
    },
    {
      label: "Signals Today",
      value: data
        ? String(data.signalsToday)
        : "—",
      note:
        "Maximum allowed: 10",
    },
    {
      label: "System Health",
      value:
        data?.systemHealth || "—",
      note:
        "Backend and provider status",
    },
  ];

  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-[10px] font-black uppercase tracking-[0.22em] text-cyan-300">
            Administration
          </p>

          <h1 className="mt-2 text-3xl font-black tracking-tight text-white">
            Admin Control Center
          </h1>

          <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">
            Manage user approval, platform protection,
            service health, and administrative account
            controls for Blue-Trading-AI.
          </p>
        </div>

        <div className="flex items-center gap-3 rounded-2xl border border-emerald-400/15 bg-emerald-400/[0.05] px-4 py-3">
          <span className="midnight-status-dot h-2.5 w-2.5 rounded-full bg-emerald-400" />

          <div>
            <p className="text-xs font-black text-emerald-300">
              Admin Controls Ready
            </p>

            <p className="mt-1 text-[10px] uppercase tracking-[0.12em] text-slate-600">
              {isOwner
                ? "Owner access active"
                : "Administrator access active"}
            </p>
          </div>
        </div>
      </section>

      {error ? (
        <section className="rounded-2xl border border-rose-400/20 bg-rose-400/[0.05] p-4">
          <p className="text-xs font-black text-rose-300">
            Admin request failed
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
              Live Admin Data
            </p>

            <h2 className="mt-2 text-lg font-black text-white">
              Protected administration dashboard
            </h2>

            <p className="mt-2 text-xs leading-5 text-slate-600">
              Loads data from the protected
              <span className="font-mono text-cyan-200">
                {" "}/admin/dashboard/
              </span>{" "}
              endpoint.
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={clear}
              disabled={isBusy || !data}
              className="rounded-xl border border-blue-400/10 bg-blue-500/[0.04] px-4 py-2.5 text-xs font-black text-slate-400 disabled:opacity-40"
            >
              Clear
            </button>

            <button
              type="button"
              onClick={() =>
                void handleLoad()
              }
              disabled={isBusy}
              className="midnight-button rounded-xl px-5 py-2.5 text-xs font-black disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isLoading
                ? "Loading Admin Data..."
                : "Refresh Admin Data"}
            </button>
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <div className="midnight-panel overflow-hidden rounded-3xl">
          <div className="flex flex-col gap-4 border-b border-blue-400/10 p-5 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
                User Management
              </p>

              <h2 className="mt-2 text-lg font-black text-white">
                Account approval queue
              </h2>
            </div>

            <label className="block min-w-[220px]">
              <span className="text-xs font-black text-slate-300">
                Account Status
              </span>

              <select
                value={approvalFilter}
                onChange={(event) =>
                  setApprovalFilter(
                    event.target
                      .value as (typeof approvalFilters)[number],
                  )
                }
                disabled={isBusy}
                className="mt-2 w-full rounded-xl border border-blue-400/10 bg-[#091426] px-4 py-3 text-sm text-white disabled:opacity-60"
              >
                {approvalFilters.map(
                  (item) => (
                    <option key={item}>
                      {item}
                    </option>
                  ),
                )}
              </select>
            </label>
          </div>

          {data?.users.length ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1000px] text-left">
                <thead className="border-b border-blue-400/10 bg-blue-500/[0.025]">
                  <tr>
                    {[
                      "User",
                      "Email",
                      "Registered",
                      "Email Status",
                      "Account Status",
                      "Role",
                      "Actions",
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
                  {data.users.map(
                    (user) => (
                      <AdminUserRow
                        key={user.id}
                        user={user}
                        isBusy={isBusy}
                        onApprove={(
                          userId,
                        ) =>
                          void handleApprove(
                            userId,
                          )
                        }
                        onReject={(
                          userId,
                        ) =>
                          void handleReject(
                            userId,
                          )
                        }
                      />
                    ),
                  )}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="flex min-h-[360px] items-center justify-center p-6">
              <div className="max-w-md text-center">
                <div className="midnight-pulse mx-auto flex h-16 w-16 items-center justify-center rounded-2xl border border-cyan-300/20 bg-blue-500/[0.06] text-xl font-black text-cyan-200">
                  A
                </div>

                <h3 className="mt-5 text-lg font-black text-white">
                  {data
                    ? "No matching user accounts"
                    : "Ready for live user administration"}
                </h3>

                <p className="mt-3 text-sm leading-6 text-slate-500">
                  {data
                    ? "The backend returned no users for the selected account status."
                    : "Select an account status and refresh the protected admin dashboard."}
                </p>
              </div>
            </div>
          )}
        </div>

        <aside className="space-y-6">
          {isOwner ? (
            <section className="midnight-panel rounded-3xl p-5">
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-amber-300">
                Owner-Only Controls
              </p>

              <h2 className="mt-2 text-lg font-black text-white">
                Platform mode
              </h2>

              <div className="mt-5 rounded-2xl border border-amber-300/15 bg-amber-400/[0.04] p-4">
                <p className="text-xs font-black text-amber-300">
                  Backend endpoint not configured
                </p>

                <p className="mt-2 text-xs leading-5 text-slate-500">
                  The current backend does not expose a confirmed
                  system-mode route. This control remains disabled
                  to prevent a false or unsafe administrative action.
                </p>
              </div>

              <button
                type="button"
                disabled
                className="mt-4 w-full cursor-not-allowed rounded-xl border border-blue-400/10 bg-blue-500/[0.04] px-5 py-3 text-sm font-black text-slate-600 opacity-60"
              >
                System Mode Unavailable
              </button>
            </section>
          ) : (
            <section className="midnight-panel rounded-3xl p-5">
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
                Administrative Scope
              </p>

              <h2 className="mt-2 text-lg font-black text-white">
                Administrator permissions
              </h2>

              <p className="mt-4 text-xs leading-6 text-slate-500">
                Administrators can review users, approve or reject
                eligible accounts, and inspect service status.
                OWNER-only platform controls are intentionally hidden.
              </p>
            </section>
          )}

          <section className="midnight-panel rounded-3xl p-5">
            <div className="flex items-center justify-between gap-3">
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-slate-600">
                Backend Status
              </p>

              <span className="text-[10px] text-slate-700">
                {lastUpdated
                  ? lastUpdated.toLocaleTimeString()
                  : "Not updated"}
              </span>
            </div>

            <div className="mt-5 space-y-3">
              {data?.services.length ? (
                data.services.map(
                  (service) => (
                    <ServiceStatus
                      key={service.name}
                      service={service}
                    />
                  ),
                )
              ) : (
                <div className="rounded-2xl border border-blue-400/10 bg-blue-500/[0.035] p-4">
                  <p className="text-xs text-slate-500">
                    Refresh admin data to load verified service status.
                  </p>
                </div>
              )}
            </div>
          </section>
        </aside>
      </section>
    </div>
  );
}

export default function AdminPage() {
  return (
    <RoleGuard
      allowedRoles={
        ACCESS_ROLES.administration
      }
    >
      <AdminContent />
    </RoleGuard>
  );
}