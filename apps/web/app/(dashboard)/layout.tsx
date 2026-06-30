import { Suspense } from "react";
import { DashboardShell } from "@/app/(dashboard)/_components/dashboard-shell";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <DashboardShell>
      <Suspense fallback={null}>{children}</Suspense>
    </DashboardShell>
  );
}
