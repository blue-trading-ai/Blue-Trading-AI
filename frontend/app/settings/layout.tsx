import type { ReactNode } from "react";

import { ProtectedAppShell } from "@/components/layout/protected-app-shell";

type SettingsLayoutProps = {
  children: ReactNode;
};

export default function SettingsLayout({
  children,
}: SettingsLayoutProps) {
  return (
    <ProtectedAppShell>
      {children}
    </ProtectedAppShell>
  );
}