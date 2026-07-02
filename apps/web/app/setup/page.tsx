"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import {
  useOrganizationsCreateOrganization,
  useOrganizationsListOrganizations,
} from "@repo/api-client";
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

  const { data: orgs, isLoading: listLoading } =
    useOrganizationsListOrganizations({
      query: { enabled: isLoaded && isSignedIn && !orgId },
    });

  const handleOrgCreated = useCallback(
    async (data: OrgSetupFormData) => {
      setIsCreating(true);
      setError(null);
      try {
        const org = await createMutation.mutateAsync({
          data: {
            name: data.name,
            description: data.description || undefined,
            what_it_does: data.what_it_does || undefined,
          },
        });
        setCreatedOrgId(org.id);
        setOrgName(org.name);
        setStep("upload");
      } catch {
        setError("Failed to create organization. Please try again.");
      } finally {
        setIsCreating(false);
      }
    },
    [createMutation],
  );

  const handleUploadComplete = useCallback(() => {
    if (!createdOrgId) return;
    setOrg(createdOrgId, orgName);
    router.replace("/dashboard");
  }, [createdOrgId, orgName, setOrg, router]);

  const handleSkipUpload = useCallback(() => {
    if (!createdOrgId) return;
    setOrg(createdOrgId, orgName);
    router.replace("/dashboard");
  }, [createdOrgId, orgName, setOrg, router]);

  // Guard: if user already has an org (from store or API), redirect to dashboard
  useEffect(() => {
    if (orgId) {
      router.replace("/dashboard");
      return;
    }
    if (orgs && orgs.length > 0) {
      const first = orgs[0];
      if (!first) return;
      setOrg(first.id, first.name);
      router.replace("/dashboard");
    }
  }, [orgs, orgId, setOrg, router]);

  // Still loading Clerk auth state
  if (!isLoaded) {
    return (
      <div className="flex justify-center">
        <Spinner />
      </div>
    );
  }

  // Still loading org list or org already exists
  if (orgId || (orgs && orgs.length > 0)) {
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
            onSubmit={handleOrgCreated}
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
