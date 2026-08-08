"use client";

import type { ReactNode } from "react";

import { DashboardAuthGuard } from "@/components/auth/dashboard-auth-guard";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";

type ProtectedAppShellProps = {
  children: ReactNode;
};

export function ProtectedAppShell({
  children,
}: ProtectedAppShellProps) {
  return (
    <DashboardAuthGuard>
      <div className="midnight-page flex min-h-screen text-white">
        <Sidebar />

        <div className="min-w-0 flex-1">
          <Topbar />

          <main className="mx-auto w-full max-w-[1600px] px-4 pb-8 pt-4 sm:px-6 lg:px-8">
            {children}
          </main>
        </div>
      </div>
    </DashboardAuthGuard>
  );
}