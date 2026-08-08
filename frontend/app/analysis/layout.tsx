import type { ReactNode } from "react";

import { ProtectedAppShell } from "@/components/layout/protected-app-shell";

type AnalysisLayoutProps = {
  children: ReactNode;
};

export default function AnalysisLayout({
  children,
}: AnalysisLayoutProps) {
  return (
    <ProtectedAppShell>
      {children}
    </ProtectedAppShell>
  );
}