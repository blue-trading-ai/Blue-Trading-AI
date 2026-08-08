import type { ReactNode } from "react";

import { RoleGuard } from "@/components/auth/role-guard";
import { ProtectedAppShell } from "@/components/layout/protected-app-shell";
import { ACCESS_ROLES } from "@/lib/access-control";

type AdminLayoutProps = {
  children: ReactNode;
};

export default function AdminLayout({
  children,
}: AdminLayoutProps) {
  return (
    <ProtectedAppShell>
      <RoleGuard
        allowedRoles={
          ACCESS_ROLES.administration
        }
      >
        {children}
      </RoleGuard>
    </ProtectedAppShell>
  );
}