import type { ReactNode } from "react";

import { ProtectedAppShell } from "@/components/layout/protected-app-shell";

type NewsLayoutProps = {
  children: ReactNode;
};

export default function NewsLayout({
  children,
}: NewsLayoutProps) {
  return (
    <ProtectedAppShell>
      {children}
    </ProtectedAppShell>
  );
}