import type { ReactNode } from "react";

import { ProtectedAppShell } from "@/components/layout/protected-app-shell";

type PerformanceLayoutProps = {
  children: ReactNode;
};

export default function PerformanceLayout({
  children,
}: PerformanceLayoutProps) {
  return (
    <ProtectedAppShell>
      {children}
    </ProtectedAppShell>
  );
}