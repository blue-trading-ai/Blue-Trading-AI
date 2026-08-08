import type { ReactNode } from "react";

import { ProtectedAppShell } from "@/components/layout/protected-app-shell";

type SignalsLayoutProps = {
  children: ReactNode;
};

export default function SignalsLayout({
  children,
}: SignalsLayoutProps) {
  return (
    <ProtectedAppShell>
      {children}
    </ProtectedAppShell>
  );
}