"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeftIcon,
  FileTextIcon,
  PlusIcon,
  UploadIcon,
  XIcon,
} from "lucide-react";

import {
  ApiError,
  useEmployeesCreateEmployeeRoute,
  useEmployeesListEmployeesRoute,
  getEmployeesListEmployeesRouteQueryKey,
  useDocumentsUploadDocument,
} from "@repo/api-client";
import { useOrgStore } from "@/stores/org";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/spinner";

const EMPLOYEE_TYPES = [
  {
    id: "legal-compliance",
    label: "Legal Compliance Officer",
    description: "Reviews contracts, policies, and regulatory documents",
  },
  {
    id: "support",
    label: "Support Employee",
    description: "Handles customer inquiries and support tickets",
  },
  {
    id: "hr",
    label: "HR Employee",
    description: "Manages onboarding, benefits, and employee questions",
  },
  {
    id: "general",
    label: "General",
    description: "Versatile assistant for any team need",
  },
] as const;

export default function OnboardPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const orgId = useOrgStore((s) => s.orgId);
  const createMutation = useEmployeesCreateEmployeeRoute();

  const [employeeType, setEmployeeType] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [specialization, setSpecialization] = useState("");
  const [duties, setDuties] = useState<string[]>([]);
  const [dutyInput, setDutyInput] = useState("");

  // File upload state
  const uploadInputRef = useRef<HTMLInputElement>(null);
  const uploadDocMutation = useDocumentsUploadDocument();
  const [uploadingFiles, setUploadingFiles] = useState<
    {
      file: File;
      status: "pending" | "uploading" | "done" | "error";
      error?: string;
    }[]
  >([]);
  const [isBulkUploading, setIsBulkUploading] = useState(false);

  // Fetch existing employees to determine which types are already deployed
  const { data: existingEmployees } = useEmployeesListEmployeesRoute(
    orgId ?? "",
    {
      query: { enabled: !!orgId },
    },
  );

  const takenTypes = useMemo(() => {
    if (!existingEmployees) return new Set<string>();
    return new Set(
      existingEmployees
        .map((e) => e.employee_type)
        .filter((t): t is string => t != null),
    );
  }, [existingEmployees]);

  const allTypesTaken = takenTypes.size >= EMPLOYEE_TYPES.length;

  const isValid = name.trim().length > 0 && !!orgId && !!employeeType;

  const handleAddDuty = () => {
    const trimmed = dutyInput.trim();
    if (!trimmed) return;
    setDuties((prev) => [...prev, trimmed]);
    setDutyInput("");
  };

  const handleRemoveDuty = (index: number) => {
    setDuties((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = async () => {
    if (!isValid) return;
    try {
      const result = await createMutation.mutateAsync({
        orgId: orgId!,
        data: {
          name: name.trim(),
          employee_type: employeeType!,
          role: role.trim() || undefined,
          specialization: specialization.trim() || undefined,
          duties: duties.length > 0 ? duties : undefined,
        },
      });
      if (orgId) {
        queryClient.invalidateQueries({
          queryKey: getEmployeesListEmployeesRouteQueryKey(orgId),
        });
      }

      // Upload queued files for the new employee
      const pending = uploadingFiles.filter((f) => f.status !== "done");
      if (pending.length > 0) {
        setIsBulkUploading(true);
        let hasErrors = false;
        for (let i = 0; i < uploadingFiles.length; i++) {
          const entry = uploadingFiles[i];
          if (!entry || entry.status === "done") continue;
          setUploadingFiles((prev) =>
            prev.map((f, idx) =>
              idx === i ? { ...f, status: "uploading" } : f,
            ),
          );
          try {
            await uploadDocMutation.mutateAsync({
              data: {
                file: entry.file as unknown as string,
                organization_id: orgId!,
                employee_id: result.id as unknown as string,
              },
            });
            setUploadingFiles((prev) =>
              prev.map((f, idx) => (idx === i ? { ...f, status: "done" } : f)),
            );
          } catch {
            hasErrors = true;
            setUploadingFiles((prev) =>
              prev.map((f, idx) =>
                idx === i
                  ? { ...f, status: "error", error: "Upload failed" }
                  : f,
              ),
            );
          }
        }
        setIsBulkUploading(false);
        if (!hasErrors) {
          router.push("/dashboard");
        }
        // If errors, stay on page so user can see failures and retry/continue
        return;
      }

      router.push("/dashboard");
    } catch {
      // Error rendered below via createMutation.error
    }
  };

  const addUploadFiles = useCallback((newFiles: FileList | null) => {
    if (!newFiles) return;
    setUploadingFiles((prev) => [
      ...prev,
      ...Array.from(newFiles).map((file) => ({
        file,
        status: "pending" as const,
      })),
    ]);
  }, []);

  const removeUploadFile = useCallback((index: number) => {
    setUploadingFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const fileKey = (f: File) => `${f.name}-${f.size}-${f.lastModified}`;

  const pendingCount = uploadingFiles.filter(
    (f) => f.status !== "done" && f.status !== "error",
  ).length;
  const errorCount = uploadingFiles.filter((f) => f.status === "error").length;

  return (
    <div className="flex flex-1 flex-col gap-8 px-6 py-6">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="sm"
          className="w-fit"
          onClick={() => router.push("/dashboard")}
        >
          <ArrowLeftIcon />
          Back to Team
        </Button>
      </div>

      <div className="mx-auto flex w-full max-w-2xl flex-col gap-10">
        <div className="flex flex-col gap-3">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Create your AI employee
          </h1>
          <p className="text-base text-muted-foreground">
            Give them a name and role. You can add one employee of each type.
          </p>
        </div>

        {/* Team complete banner */}
        {allTypesTaken && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-800/30 dark:bg-amber-900/20 dark:text-amber-300">
            Your team is complete. You&rsquo;ve deployed one employee of each
            type.{" "}
            <Link href="/dashboard" className="underline font-medium">
              View your team
            </Link>
          </div>
        )}

        {/* Employee type tiles */}
        <div className="flex flex-col gap-3">
          <Label className="text-base font-medium">Employee type</Label>
          <div className="grid grid-cols-2 gap-3">
            {EMPLOYEE_TYPES.map((type) => {
              const isSelected = employeeType === type.id;
              const isTaken = takenTypes.has(type.id);
              const isClickable = !isTaken || isSelected;
              return (
                <button
                  key={type.id}
                  type="button"
                  disabled={!isClickable}
                  onClick={() => {
                    if (!isClickable) return;
                    setEmployeeType(type.id);
                    setRole(type.label);
                  }}
                  className={`flex flex-col gap-1.5 rounded-xl border-2 p-4 text-left transition-colors ${
                    isSelected
                      ? "border-primary bg-primary/5"
                      : isTaken
                        ? "cursor-not-allowed border-border/50 bg-muted/30 opacity-50"
                        : "border-border hover:border-primary/40 hover:bg-muted/50"
                  }`}
                >
                  <span className="text-base font-medium text-foreground">
                    {type.label}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    {type.description}
                  </span>
                  {isTaken && !isSelected && (
                    <span className="mt-1 text-xs text-muted-foreground/60">
                      Already deployed
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Name */}
        <div className="flex flex-col gap-2">
          <Label htmlFor="name" className="text-base font-medium">
            Name <span className="text-destructive">*</span>
          </Label>
          <p className="text-sm text-muted-foreground">
            What should your team call them? e.g. Allison, Marcus, Alex.
          </p>
          <Input
            id="name"
            placeholder="Allison"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>

        {/* Role */}
        <div className="flex flex-col gap-2">
          <Label htmlFor="role" className="text-base font-medium">
            Role
          </Label>
          <p className="text-sm text-muted-foreground">
            What do they do? e.g. Backend Engineer, Product Manager, Support
            Lead.
          </p>
          <Input
            id="role"
            placeholder="Backend Engineer"
            value={role}
            onChange={(e) => setRole(e.target.value)}
          />
        </div>

        {/* Specialization */}
        <div className="flex flex-col gap-2">
          <Label htmlFor="specialization" className="text-base font-medium">
            Specialization
          </Label>
          <p className="text-sm text-muted-foreground">
            What are they especially good at? e.g. Technical billing, SEO
            content, security audits.
          </p>
          <Input
            id="specialization"
            placeholder="Technical billing & refunds"
            value={specialization}
            onChange={(e) => setSpecialization(e.target.value)}
          />
        </div>

        {/* Duties */}
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <Label className="text-base font-medium">Duties</Label>
            <p className="text-sm text-muted-foreground">
              What are this employee&rsquo;s responsibilities? Add each duty one
              at a time.
            </p>
          </div>
          {duties.length > 0 && (
            <div className="flex flex-col gap-2">
              {duties.map((duty, i) => (
                <div
                  key={i}
                  className="flex items-start gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2.5"
                >
                  <span className="min-w-0 flex-1 text-base text-foreground">
                    {duty}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleRemoveDuty(i)}
                    className="mt-0.5 shrink-0 rounded-sm text-muted-foreground hover:text-foreground"
                  >
                    <XIcon className="size-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
          <div className="flex flex-col gap-2">
            <Textarea
              placeholder="e.g. Read all PDFs shared in #legal and review them for compliance risks..."
              value={dutyInput}
              onChange={(e) => setDutyInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                  e.preventDefault();
                  handleAddDuty();
                }
              }}
              rows={3}
            />
            <Button
              type="button"
              variant="outline"
              onClick={handleAddDuty}
              className="shrink-0 w-fit"
            >
              <PlusIcon />
              Add duty
            </Button>
          </div>
        </div>

        {/* Knowledge upload */}
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1">
            <Label className="text-base font-medium">Knowledge files</Label>
            <p className="text-sm text-muted-foreground">
              Upload PDFs, documents, or markdown files this agent should know
              about. You can always add more later.
            </p>
          </div>

          <div
            onClick={() => uploadInputRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ")
                uploadInputRef.current?.click();
            }}
            role="button"
            tabIndex={0}
            className="flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed border-border p-6 text-center transition-colors hover:border-primary/40"
          >
            <UploadIcon className="size-6 text-muted-foreground/60" />
            <p className="text-sm font-medium text-foreground">
              Click to upload files
            </p>
            <p className="text-xs text-muted-foreground">
              PDF, Word, Excel, Markdown, text, HTML &middot; no size limit
            </p>
            <input
              ref={uploadInputRef}
              type="file"
              accept=".pdf,.md,.txt,.csv,.json,.html,.docx,.pptx,.xlsx,.doc,.xls,.ppt,.odt,.rtf"
              multiple
              className="hidden"
              onChange={(e) => addUploadFiles(e.target.files)}
            />
          </div>

          {uploadingFiles.length > 0 && (
            <div className="space-y-2">
              {uploadingFiles.map((entry, i) => (
                <div
                  key={fileKey(entry.file)}
                  className="flex items-center gap-3 rounded-lg border border-border px-3 py-2.5"
                >
                  <FileTextIcon className="size-4 shrink-0 text-muted-foreground" />
                  <span className="min-w-0 flex-1 truncate text-sm">
                    {entry.file.name}
                  </span>
                  {entry.status === "uploading" && (
                    <Spinner className="size-4" />
                  )}
                  {entry.status === "done" && (
                    <span className="text-xs text-emerald-600">Uploaded</span>
                  )}
                  {entry.status === "error" && (
                    <span className="text-xs text-destructive">
                      {entry.error ?? "Error"}
                    </span>
                  )}
                  {entry.status !== "uploading" && entry.status !== "done" && (
                    <button
                      type="button"
                      onClick={() => removeUploadFile(i)}
                      className="text-muted-foreground hover:text-foreground"
                      aria-label={`Remove ${entry.file.name}`}
                    >
                      <XIcon className="size-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {errorCount > 0 && (
            <p className="text-sm text-destructive">
              {errorCount} file{errorCount !== 1 ? "s" : ""} failed to upload.
              Remove them and try again, or continue.
            </p>
          )}
        </div>

        {/* Submit */}
        <div className="flex flex-col gap-3 border-t border-border pt-6">
          {createMutation.isError && (
            <p className="text-sm text-destructive">
              {createMutation.error instanceof ApiError &&
              createMutation.error.status === 409
                ? "This employee type is already deployed. Each type can only be added once."
                : createMutation.error instanceof Error
                  ? createMutation.error.message
                  : "Failed to create employee. Please try again."}
            </p>
          )}
          <div className="flex items-center justify-end gap-3">
            <Button
              variant="outline"
              size="lg"
              onClick={() => router.push("/dashboard")}
              disabled={isBulkUploading}
            >
              Cancel
            </Button>
            {errorCount > 0 ? (
              <Button
                size="lg"
                onClick={() => router.push("/dashboard")}
                variant="secondary"
              >
                Continue anyway
              </Button>
            ) : (
              <Button
                size="lg"
                onClick={handleSubmit}
                disabled={
                  !isValid ||
                  createMutation.isPending ||
                  isBulkUploading ||
                  (!!employeeType && takenTypes.has(employeeType))
                }
              >
                {createMutation.isPending
                  ? "Creating…"
                  : isBulkUploading
                    ? "Uploading…"
                    : "Onboard"}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
