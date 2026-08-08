import type { ReactNode } from "react";

import { ProtectedAppShell } from "@/components/layout/protected-app-shell";

type MarketStructureLayoutProps = {
  children: ReactNode;
};

export default function MarketStructureLayout({
  children,
}: MarketStructureLayoutProps) {
  return (
    <ProtectedAppShell>
      {children}
    </ProtectedAppShell>
  );
}