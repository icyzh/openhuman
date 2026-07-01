"use client";

import { Suspense, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useOrganizationsListOrganizations } from "@repo/api-client";
import { useAuthStore } from "@/stores/auth";
import { useOrgStore } from "@/stores/org";
import { DashboardShell } from "@/app/(dashboard)/_components/dashboard-shell";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

function OrgInitializer({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const token = useAuthStore((s) => s.token);
  const isLoadingAuth = useAuthStore((s) => s.isLoading);
  const { orgId, setOrg } = useOrgStore();

  const {
    data: orgs,
    isLoading: listLoading,
    isError,
    refetch,
  } = useOrganizationsListOrganizations({
    query: { enabled: !isLoadingAuth && !!token && !orgId },
  });

  useEffect(() => {
    if (listLoading || !orgs) return;
    if (orgs.length > 0) {
      const first = orgs[0];
      if (first) setOrg(first.id, first.name);
    } else {
      router.replace("/setup");
    }
  }, [orgs, listLoading, setOrg, router]);

  if (isLoadingAuth || listLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-center">
          <p className="text-sm text-muted-foreground">
            Unable to load your workspace.
          </p>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            Try again
          </Button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <DashboardShell>
      <Suspense fallback={null}>
        <OrgInitializer>{children}</OrgInitializer>
      </Suspense>
    </DashboardShell>
  );
}
