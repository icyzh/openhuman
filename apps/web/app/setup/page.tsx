"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import {
  useOrganizationsCreateOrganization,
  useOrganizationsListOrganizations,
  useOrganizationsUpdateOrganization,
} from "@repo/api-client";
import { useAuthMe, useAuthUpdateMe } from "@repo/api-client";
import { useOrgStore } from "@/stores/org";
import { Spinner } from "@/components/ui/spinner";
import { OrgSetupForm } from "./_components/org-setup-form";
import type { OrgSetupFormData } from "./_components/org-setup-form";
import { KnowledgeUpload } from "./_components/knowledge-upload";

type Step = "form" | "upload";

export default function SetupPage() {
  const router = useRouter();
  const { isSignedIn, isLoaded } = useAuth();
  const { setOrg, orgId } = useOrgStore();
  const [step, setStep] = useState<Step>("form");
  const [createdOrgId, setCreatedOrgId] = useState<string | null>(null);
  const [orgName, setOrgName] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const createMutation = useOrganizationsCreateOrganization();
  const updateOrgMutation = useOrganizationsUpdateOrganization();
  const updateUserMutation = useAuthUpdateMe();

  const { data: orgs, isLoading: listLoading } =
    useOrganizationsListOrganizations({
      query: { enabled: isLoaded && isSignedIn && !orgId },
    });

  const { data: currentUser, isLoading: userLoading } = useAuthMe({
    query: { enabled: isLoaded && isSignedIn },
  });

  const handleOrgDetailsSaved = useCallback(
    async (data: OrgSetupFormData) => {
      if (!createdOrgId) return;
      setIsCreating(true);
      setError(null);
      try {
        await updateOrgMutation.mutateAsync({
          orgId: createdOrgId,
          data: {
            name: data.name,
            description: data.description || undefined,
            what_it_does: data.what_it_does || undefined,
            website_url: data.website_url || undefined,
          },
        });
        setOrgName(data.name);
        setStep("upload");
      } catch {
        setError("Failed to update organization. Please try again.");
      } finally {
        setIsCreating(false);
      }
    },
    [createdOrgId, updateOrgMutation],
  );

  const completeSetup = useCallback(async () => {
    if (!createdOrgId) return;
    try {
      await updateUserMutation.mutateAsync({ data: { onboarding_completed: true } });
    } catch {
      // Non-blocking — the dashboard guard will redirect back if needed
    }
    setOrg(createdOrgId, orgName);
    router.replace("/onboard");
  }, [createdOrgId, orgName, setOrg, router, updateUserMutation]);

  const handleUploadComplete = useCallback(() => {
    completeSetup();
  }, [completeSetup]);

  const handleSkipUpload = useCallback(() => {
    completeSetup();
  }, [completeSetup]);

  // Guard: if already onboarded, redirect to dashboard
  useEffect(() => {
    if (currentUser?.onboarding_completed) {
      router.replace("/dashboard");
      return;
    }
    // Store the existing org ID for PATCH (org is auto-created by backend)
    if (orgs && orgs.length > 0 && !createdOrgId) {
      const first = orgs[0];
      if (!first) return;
      setCreatedOrgId(first.id);
      setOrgName(first.name);
    }
  }, [orgs, currentUser, router, createdOrgId]);

  // Still loading Clerk auth state or user profile
  if (!isLoaded || userLoading) {
    return (
      <div className="flex justify-center">
        <Spinner />
      </div>
    );
  }

  // Already onboarded — redirect guard
  if (currentUser?.onboarding_completed) {
    return null;
  }

  if (listLoading) {
    return (
      <div className="flex justify-center">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {step === "form" && (
        <>
          <div className="space-y-1.5 text-center">
            <h1 className="text-xl font-semibold tracking-tight text-foreground">
              Set up your workspace
            </h1>
            <p className="text-sm text-muted-foreground">
              Tell us about your company to get started
            </p>
          </div>
          <OrgSetupForm
            onSubmit={handleOrgDetailsSaved}
            isSubmitting={isCreating}
            error={error}
          />
        </>
      )}

      {step === "upload" && createdOrgId && (
        <>
          <div className="space-y-1.5 text-center">
            <h1 className="text-xl font-semibold tracking-tight text-foreground">
              Add your knowledge base
            </h1>
            <p className="text-sm text-muted-foreground">
              Upload PDFs or markdown files about your company.
              <br />
              You can always add more later.
            </p>
          </div>
          <KnowledgeUpload
            orgId={createdOrgId}
            onComplete={handleUploadComplete}
            onSkip={handleSkipUpload}
          />
        </>
      )}
    </div>
  );
}
