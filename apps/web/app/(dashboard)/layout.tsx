"use client";

import { Suspense, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { useOrganizationsListOrganizations, useAuthMe } from "@repo/api-client";
import { useOrgStore } from "@/stores/org";
import { DashboardShell } from "@/app/(dashboard)/_components/dashboard-shell";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

function OrgInitializer({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { isSignedIn, isLoaded } = useAuth();
  const { orgId, setOrg } = useOrgStore();

  const {
    data: orgs,
    isLoading: listLoading,
    isError,
    refetch,
  } = useOrganizationsListOrganizations({
    query: { enabled: isLoaded && isSignedIn && !orgId },
  });

  const {
    data: currentUser,
    isLoading: userLoading,
  } = useAuthMe({
    query: { enabled: isLoaded && isSignedIn },
  });

  useEffect(() => {
    if (orgId) return;
    if (listLoading || userLoading || !orgs) return;

    if (orgs.length > 0) {
      const first = orgs[0];
      if (!first) return;

      if (currentUser?.onboarding_completed) {
        // Existing user — set org and render dashboard
        setOrg(first.id, first.name);
      } else {
        // New user — send to org setup first
        router.replace("/setup");
      }
    } else {
      router.replace("/setup");
    }
  }, [orgs, listLoading, userLoading, currentUser, setOrg, router, orgId]);

  if (!isLoaded || listLoading || userLoading) {
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
