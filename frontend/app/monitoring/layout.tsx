import type { ReactNode } from "react";

import { RoleGuard } from "@/components/auth/role-guard";
import { ProtectedAppShell } from "@/components/layout/protected-app-shell";
import { ACCESS_ROLES } from "@/lib/access-control";

type MonitoringLayoutProps = {
  children: ReactNode;
};

export default function MonitoringLayout({
  children,
}: MonitoringLayoutProps) {
  return (
    <ProtectedAppShell>
      <RoleGuard
        allowedRoles={
          ACCESS_ROLES.monitoring
        }
      >
        {children}
      </RoleGuard>
    </ProtectedAppShell>
  );
}