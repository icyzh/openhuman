"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import {
  useOrganizationsCreateOrganization,
  useOrganizationsListOrganizations,
  useOrganizationsUpdateOrganization,
} from "@repo/api-client";
import { useAuthUpdateMe } from "@repo/api-client";
import { useOrgStore } from "@/stores/org";
import { Spinner } from "@/components/ui/spinner";
import { OrgSetupForm } from "./_components/org-setup-form";
import type { OrgSetupFormData } from "./_components/org-setup-form";

export default function SetupPage() {
  const router = useRouter();
  const { isSignedIn, isLoaded } = useAuth();
  const setOrg = useOrgStore((s) => s.setOrg);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const createOrgMutation = useOrganizationsCreateOrganization();
  const updateOrgMutation = useOrganizationsUpdateOrganization();
  const updateUserMutation = useAuthUpdateMe();

  const { data: orgs, isLoading: orgsLoading } = useOrganizationsListOrganizations({
    query: { enabled: isLoaded && isSignedIn },
  });

  const existingOrg = useMemo(() => orgs?.[0] ?? null, [orgs]);
  const shouldGoToDashboard = !orgsLoading && !!existingOrg;

  useEffect(() => {
    if (!shouldGoToDashboard || !existingOrg) {
      if (shouldGoToDashboard) {
        router.replace("/dashboard");
      }
      return;
    }

    setOrg(existingOrg.id, existingOrg.name);
    router.replace("/dashboard");
  }, [existingOrg, router, setOrg, shouldGoToDashboard]);

  const handleSubmit = useCallback(
    async (data: OrgSetupFormData) => {
      setIsSubmitting(true);
      setError(null);

      try {
        const org = existingOrg
          ? await updateOrgMutation.mutateAsync({
              orgId: existingOrg.id,
              data: {
                name: data.name,
                description: data.description || undefined,
                what_it_does: data.what_it_does || undefined,
                website_url: data.website_url || undefined,
              },
            })
          : await createOrgMutation.mutateAsync({
              data: {
                name: data.name,
                description: data.description || undefined,
                what_it_does: data.what_it_does || undefined,
                website_url: data.website_url || undefined,
              },
            });

        await updateUserMutation.mutateAsync({
          data: { onboarding_completed: true },
        });

        setOrg(org.id, org.name);
        router.replace("/dashboard");
      } catch {
        setError("Failed to set up your organization. Please try again.");
      } finally {
        setIsSubmitting(false);
      }
    },
    [
      createOrgMutation,
      existingOrg,
      router,
      setOrg,
      updateOrgMutation,
      updateUserMutation,
    ],
  );

  if (!isLoaded || orgsLoading) {
    return (
      <div className="flex justify-center">
        <Spinner />
      </div>
    );
  }

  if (shouldGoToDashboard) {
    return null;
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1.5 text-center">
        <h1 className="text-xl font-semibold tracking-tight text-foreground">
          Set up your workspace
        </h1>
        <p className="text-sm text-muted-foreground">
          Add your organization details to get started
        </p>
      </div>

      <OrgSetupForm
        onSubmit={handleSubmit}
        isSubmitting={isSubmitting}
        error={error}
      />
    </div>
  );
}
