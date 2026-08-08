import type { ReactNode } from "react";

import { ProtectedAppShell } from "@/components/layout/protected-app-shell";

type HistoryLayoutProps = {
  children: ReactNode;
};

export default function HistoryLayout({
  children,
}: HistoryLayoutProps) {
  return (
    <ProtectedAppShell>
      {children}
    </ProtectedAppShell>
  );
}