"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeftIcon,
  DownloadIcon,
  ExternalLinkIcon,
  FileTextIcon,
  GitGraphIcon,
  MailIcon,
  PlusIcon,
  Trash2Icon,
  UploadIcon,
  XIcon,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  useEmployeesGetEmployeeRoute,
  useEmployeesUpdateEmployeeRoute,
  useEmployeesDeleteEmployeeRoute,
  useEmployeesSetStatus,
  getEmployeesListEmployeesRouteQueryKey,
  getEmployeesGetEmployeeRouteQueryKey,
  useDocumentsListOrgDocuments,
  getDocumentsListOrgDocumentsQueryKey,
  useDocumentsUploadDocument,
  useDocumentsDeleteDocumentRoute,
  useMcpListMcpConnectors,
  useMcpListEmployeeMcpConnections,
  useMcpDeleteMcpConnection,
  getMcpListEmployeeMcpConnectionsQueryKey,
} from "@repo/api-client";
import type { UpdateEmployeeRequest } from "@repo/api-client";
import { useOrgStore } from "@/stores/org";
import { getStatusConfig, EMPLOYEE_TYPE_LABELS } from "@/types/employee";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { cn } from "@/lib/utils";

import { useAuth } from "@clerk/nextjs";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function slackInstallUrl(employeeId: string, orgId: string): string {
  return `${API_URL}/api/slack/install?employee_id=${encodeURIComponent(employeeId)}&org_id=${encodeURIComponent(orgId)}`;
}

function formatSize(bytes: number | null | undefined): string {
  if (bytes == null) return "—";
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1,
  );
  const size = bytes / 1024 ** i;
  return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

async function downloadDocument(
  docId: string,
  filename: string,
  token: string | null,
) {
  const response = await fetch(`${API_URL}/api/documents/${docId}/download`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error("Download failed");
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function InfoRow({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span
        className={cn(
          "text-sm font-medium text-foreground",
          mono && "font-mono",
        )}
      >
        {value}
      </span>
    </div>
  );
}

type EditableField = "name" | "role";

export default function EmployeeDetailPage() {
  const { id: empId } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const orgId = useOrgStore((s) => s.orgId);
  const { getToken } = useAuth();

  const {
    data: apiEmployee,
    isLoading,
    isError,
    error,
  } = useEmployeesGetEmployeeRoute(orgId ?? "", empId, {
    query: { enabled: !!(orgId && empId) },
  });

  const employee = apiEmployee
    ? {
        id: apiEmployee.id,
        orgId: apiEmployee.org_id,
        name: apiEmployee.name,
        employeeType: apiEmployee.employee_type ?? null,
        role: apiEmployee.role ?? "",
        specialization: apiEmployee.specialization ?? "",
        duties: (apiEmployee.duties ?? []) as string[],
        status: apiEmployee.status,
        hasDiscord: apiEmployee.has_discord_token,
        hasSlack: apiEmployee.has_slack_token,
        slackTeamName: apiEmployee.slack_team_name ?? null,
        deployedAt: apiEmployee.created_at,
      }
    : null;

  const updateMutation = useEmployeesUpdateEmployeeRoute();
  const deleteMutation = useEmployeesDeleteEmployeeRoute();
  const statusMutation = useEmployeesSetStatus();

  const invalidate = useCallback(() => {
    if (!orgId) return;
    queryClient.invalidateQueries({
      queryKey: getEmployeesListEmployeesRouteQueryKey(orgId),
    });
    queryClient.invalidateQueries({
      queryKey: getEmployeesGetEmployeeRouteQueryKey(orgId, empId),
    });
  }, [orgId, empId, queryClient]);

  const doUpdate = useCallback(
    (data: UpdateEmployeeRequest) => {
      if (!orgId) return;
      updateMutation.mutate(
        { orgId, empId, data },
        { onSuccess: () => invalidate() },
      );
    },
    [orgId, empId, updateMutation, invalidate],
  );

  const searchParams = useSearchParams();

  useEffect(() => {
    const slack = searchParams.get("slack");
    if (slack === "connected") {
      toast.success("Slack workspace connected successfully!");
    } else if (slack === "error") {
      const reason = searchParams.get("reason") || "unknown error";
      toast.error(`Slack connection failed: ${reason}`);
    }
    if (slack) {
      const next = new URL(window.location.href);
      next.searchParams.delete("slack");
      next.searchParams.delete("reason");
      window.history.replaceState({}, "", next.toString());
    }
  }, [searchParams]);

  useEffect(() => {
    const mcpOauth = searchParams.get("mcp_oauth");
    const connector = searchParams.get("connector");
    if (mcpOauth === "connected") {
      toast.success(`${connector === "gmail" ? "Gmail" : connector || "MCP"} connected successfully!`);
      if (orgId && empId) {
        queryClient.invalidateQueries({
          queryKey: getMcpListEmployeeMcpConnectionsQueryKey(orgId, empId),
        });
      }
    } else if (mcpOauth === "error") {
      const reason = searchParams.get("reason") || "unknown error";
      toast.error(`Connection failed: ${reason}`);
    }
    if (mcpOauth) {
      const next = new URL(window.location.href);
      next.searchParams.delete("mcp_oauth");
      next.searchParams.delete("connector");
      next.searchParams.delete("reason");
      next.searchParams.delete("employee_id");
      window.history.replaceState({}, "", next.toString());
    }
  }, [searchParams, orgId, empId, queryClient]);

  const [editingField, setEditingField] = useState<EditableField | null>(null);
  const [draftValue, setDraftValue] = useState("");
  const [dutyInput, setDutyInput] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Config card local state (save on blur, not on every keystroke)
  const [localName, setLocalName] = useState("");
  const [localRole, setLocalRole] = useState("");
  const [localSpecialization, setLocalSpecialization] = useState("");

  // Slack credentials config state removed — fixed mode uses env-based credentials

  // Document management
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadDocMutation = useDocumentsUploadDocument();
  const deleteDocMutation = useDocumentsDeleteDocumentRoute();
  const [isUploading, setIsUploading] = useState(false);
  const [deletingDocId, setDeletingDocId] = useState<string | null>(null);
  const [deleteDocDialogOpen, setDeleteDocDialogOpen] = useState(false);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [graphHtml, setGraphHtml] = useState<string | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphError, setGraphError] = useState<string | null>(null);

  const {
    data: documents,
    isLoading: docsLoading,
    isError: docsError,
    refetch: refetchDocs,
  } = useDocumentsListOrgDocuments(
    { organization_id: orgId!, employee_id: empId },
    { query: { enabled: !!(orgId && empId) } },
  );

  const {
    data: connectors,
    isLoading: connectorsLoading,
  } = useMcpListMcpConnectors(orgId ?? "", { query: { enabled: !!orgId } });

  const {
    data: mcpConnectionsData,
    isLoading: mcpConnectionsLoading,
    refetch: refetchMcpConnections,
  } = useMcpListEmployeeMcpConnections(orgId ?? "", empId, { query: { enabled: !!(orgId && empId) } });

  const deleteMcpConnectionMutation = useMcpDeleteMcpConnection();

  const handleDisconnectMcp = useCallback(
    async (slug: string) => {
      if (!orgId || !empId) return;
      try {
        await deleteMcpConnectionMutation.mutateAsync({
          orgId,
          empId,
          slug,
        });
        toast.success(`${slug === "gmail" ? "Gmail" : slug} disconnected successfully!`);
        queryClient.invalidateQueries({
          queryKey: getMcpListEmployeeMcpConnectionsQueryKey(orgId, empId),
        });
      } catch {
        toast.error(`Failed to disconnect ${slug}.`);
      }
    },
    [orgId, empId, deleteMcpConnectionMutation, queryClient]
  );

  const invalidateDocs = useCallback(() => {
    if (!orgId || !empId) return;
    queryClient.invalidateQueries({
      queryKey: getDocumentsListOrgDocumentsQueryKey({
        organization_id: orgId,
        employee_id: empId,
      }),
    });
  }, [orgId, empId, queryClient]);

  const handleFileUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const fileList = e.target.files;
      if (!fileList || fileList.length === 0) return;
      setIsUploading(true);
      for (const file of Array.from(fileList)) {
        try {
          await uploadDocMutation.mutateAsync({
            data: {
              file: file as unknown as string,
              organization_id: orgId!,
              employee_id: empId as unknown as string,
            },
          });
        } catch {
          toast.error(`Failed to upload ${file.name}`);
        }
      }
      invalidateDocs();
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
    [orgId, empId, uploadDocMutation, invalidateDocs],
  );

  const handleDeleteDoc = useCallback(async () => {
    if (!deletingDocId) return;
    try {
      await deleteDocMutation.mutateAsync({ docId: deletingDocId });
      toast.success("Document deleted");
      invalidateDocs();
    } catch {
      toast.error("Failed to delete document");
    } finally {
      setDeleteDocDialogOpen(false);
      setDeletingDocId(null);
    }
  }, [deleteDocMutation, deletingDocId, invalidateDocs]);

  const handleDownload = useCallback(
    async (docId: string, filename: string) => {
      setDownloadingId(docId);
      try {
        const token = await getToken();
        if (!token) {
          toast.error("Session expired. Please sign in again.");
          return;
        }
        await downloadDocument(docId, filename, token);
      } catch {
        toast.error("Failed to download file");
      } finally {
        setDownloadingId(null);
      }
    },
    [getToken],
  );

  useEffect(() => {
    if (employee) {
      setLocalName(employee.name);
      setLocalRole(employee.role);
      setLocalSpecialization(employee.specialization);
    }
  }, [employee?.id]);

  useEffect(() => {
    let cancelled = false;

    async function loadKnowledgeGraph() {
      if (!orgId || !empId) return;

      setGraphLoading(true);
      setGraphError(null);

      try {
        const token = await getToken();
        if (!token) {
          throw new Error("Session expired. Please sign in again.");
        }

        const response = await fetch(
          `${API_URL}/api/organizations/${encodeURIComponent(orgId)}/employees/${encodeURIComponent(empId)}/knowledge-graph`,
          {
            headers: { Authorization: `Bearer ${token}` },
          },
        );

        if (!response.ok) {
          if (response.status === 404) {
            throw new Error("No knowledge graph is available for this agent yet.");
          }
          throw new Error("Failed to load knowledge graph.");
        }

        const html = await response.text();
        if (!cancelled) {
          setGraphHtml(html);
        }
      } catch (err) {
        if (!cancelled) {
          setGraphHtml(null);
          setGraphError(
            err instanceof Error ? err.message : "Failed to load knowledge graph.",
          );
        }
      } finally {
        if (!cancelled) {
          setGraphLoading(false);
        }
      }
    }

    void loadKnowledgeGraph();

    return () => {
      cancelled = true;
    };
  }, [empId, getToken, orgId]);

  const startEdit = useCallback((field: EditableField, value: string) => {
    setDraftValue(value);
    setEditingField(field);
    requestAnimationFrame(() => inputRef.current?.focus());
  }, []);

  const commitEdit = useCallback(() => {
    if (!editingField || !employee) return;
    const trimmed = draftValue.trim();
    const current = String(employee[editingField] ?? "");
    if (trimmed && trimmed !== current) {
      doUpdate({ [editingField]: trimmed } as UpdateEmployeeRequest);
    }
    setEditingField(null);
    setDraftValue("");
  }, [editingField, draftValue, employee, doUpdate]);

  // Loading state
  if (isLoading) {
    return (
      <div className="flex flex-1 flex-col gap-8 px-6 py-6">
        <Skeleton className="h-9 w-32" />
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-6 w-48" />
        <Separator />
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-80 rounded-xl" />
          <Skeleton className="h-80 rounded-xl" />
        </div>
      </div>
    );
  }

  // Error state
  if (isError || !employee) {
    const is404 = error instanceof Error && error.message.includes("404");
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 py-32">
        <p className="text-sm text-muted-foreground">
          {is404 ? "Employee not found." : "Failed to load employee."}
        </p>
        <Button variant="link" onClick={() => router.push("/dashboard")}>
          Back to Team
        </Button>
      </div>
    );
  }

  const statusConfig = getStatusConfig(employee.status);

  const handleAddDuty = () => {
    const trimmed = dutyInput.trim();
    if (!trimmed) return;
    const next = [...employee.duties, trimmed];
    doUpdate({ duties: next });
    setDutyInput("");
  };

  const handleRemoveDuty = (index: number) => {
    const next = employee.duties.filter((_, i) => i !== index);
    doUpdate({ duties: next });
  };

  const handleDelete = () => {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    if (!orgId) return;
    invalidate();
    deleteMutation.mutate(
      { orgId, empId },
      { onSuccess: () => router.push("/dashboard") },
    );
  };

  return (
    <div className="flex flex-1 flex-col gap-8 px-6 py-6">
      <div className="flex items-center justify-between gap-4">
        <Link href="/dashboard">
          <Button variant="ghost" size="sm" className="w-fit">
            <ArrowLeftIcon />
            Back to Team
          </Button>
        </Link>

        <Button
          variant={confirmDelete ? "destructive" : "ghost"}
          size="sm"
          onClick={handleDelete}
          onBlur={() => setConfirmDelete(false)}
          disabled={deleteMutation.isPending}
        >
          <Trash2Icon />
          {confirmDelete ? "Click again to confirm" : "Delete"}
        </Button>
      </div>

      <div className="flex flex-col gap-1">
        {editingField === "name" ? (
          <Input
            ref={inputRef}
            value={draftValue}
            onChange={(e) => setDraftValue(e.target.value)}
            onBlur={commitEdit}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitEdit();
              if (e.key === "Escape") {
                setEditingField(null);
                setDraftValue("");
              }
            }}
            className="text-2xl font-semibold tracking-tight h-auto py-1"
          />
        ) : (
          <h1
            className="cursor-pointer rounded-md px-1 -mx-1 hover:bg-muted/50 transition-colors border border-transparent hover:border-border text-2xl font-semibold tracking-tight text-foreground"
            onClick={() => startEdit("name", employee.name)}
            title="Click to edit"
          >
            {employee.name}
          </h1>
        )}
        {editingField === "role" ? (
          <Input
            ref={inputRef}
            value={draftValue}
            onChange={(e) => setDraftValue(e.target.value)}
            onBlur={commitEdit}
            onKeyDown={(e) => {
              if (e.key === "Enter") commitEdit();
              if (e.key === "Escape") {
                setEditingField(null);
                setDraftValue("");
              }
            }}
            className="text-base text-muted-foreground h-auto py-1"
          />
        ) : (
          <span
            className="cursor-pointer rounded-md px-1 -mx-1 hover:bg-muted/50 transition-colors border border-transparent hover:border-border text-base text-muted-foreground"
            onClick={() => startEdit("role", employee.role)}
            title="Click to edit"
          >
            {employee.role}
          </span>
        )}
      </div>

      <Separator />

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Info Card */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "inline-block size-2 shrink-0 rounded-full",
                  statusConfig.dotColor,
                )}
              />
              <h3 className="text-base font-semibold text-foreground">Info</h3>
              {employee.specialization && (
                <span className="ml-auto inline-flex items-center gap-1 rounded-md bg-muted px-1.5 py-0.5 text-xs font-medium text-muted-foreground">
                  {employee.specialization}
                </span>
              )}
            </div>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <InfoRow label="Name" value={employee.name} />
            <InfoRow label="Role" value={employee.role || "—"} />
            <InfoRow
              label="Employee Type"
              value={
                employee.employeeType
                  ? (EMPLOYEE_TYPE_LABELS[employee.employeeType] ??
                    employee.employeeType)
                  : "—"
              }
            />
            <InfoRow
              label="Specialization"
              value={employee.specialization || "—"}
            />
            <InfoRow label="Status" value={statusConfig.label} />
            <InfoRow
              label="Deployed"
              value={new Date(employee.deployedAt).toLocaleDateString()}
            />
            <InfoRow
              label="Discord"
              value={employee.hasDiscord ? "Connected" : "Not connected"}
            />
            <InfoRow
              label="Slack"
              value={
                employee.hasSlack && employee.slackTeamName
                  ? `Connected (${employee.slackTeamName})`
                  : employee.hasSlack
                    ? "Connected"
                    : "Not connected"
              }
            />
            {orgId && (
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Slack Bot</span>
                {employee.hasSlack && employee.slackTeamName ? (
                  <span className="text-sm font-medium text-green-600 dark:text-green-400">
                    Connected ({employee.slackTeamName})
                  </span>
                ) : (
                  <a
                    href={slackInstallUrl(employee.id, orgId)}
                    className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
                  >
                    <ExternalLinkIcon className="size-3.5" />
                    Add {employee.name} to Slack
                  </a>
                )}
              </div>
            )}
            <InfoRow label="Employee ID" value={employee.id} mono />
          </CardContent>
        </Card>

        {/* Configuration Card */}
        <div className="flex flex-col gap-6">
          <Card>
            <CardHeader>
              <h3 className="text-base font-semibold text-foreground">
                Configuration
              </h3>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <Label>Name</Label>
                <Input
                  value={localName}
                  onChange={(e) => setLocalName(e.target.value)}
                  onBlur={() => {
                    if (localName.trim() && localName !== employee.name) {
                      doUpdate({ name: localName.trim() });
                    }
                  }}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>Role</Label>
                <Input
                  value={localRole}
                  onChange={(e) => setLocalRole(e.target.value)}
                  onBlur={() => {
                    if (localRole !== employee.role) {
                      doUpdate({ role: localRole.trim() || undefined });
                    }
                  }}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>Specialization</Label>
                <Input
                  value={localSpecialization}
                  placeholder="e.g. Technical billing & refunds"
                  onChange={(e) => setLocalSpecialization(e.target.value)}
                  onBlur={() => {
                    if (localSpecialization !== employee.specialization) {
                      doUpdate({
                        specialization: localSpecialization.trim() || undefined,
                      });
                    }
                  }}
                />
              </div>

              <Separator />

              {/* Discord / Slack integration status */}
              <div className="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-4 py-3">
                <div className="flex flex-col gap-0.5">
                  <span className="text-sm font-medium text-foreground">
                    Discord
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {employee.hasDiscord
                      ? "Bot token configured"
                      : "No bot token configured"}
                  </span>
                </div>
                <span
                  className={cn(
                    "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
                    employee.hasDiscord
                      ? "bg-green-500/10 text-green-700"
                      : "bg-muted text-muted-foreground",
                  )}
                >
                  {employee.hasDiscord ? "Connected" : "Inactive"}
                </span>
              </div>

              {orgId && (
                <div className="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-4 py-3">
                  <div className="flex flex-col gap-0.5">
                    <span className="text-sm font-medium text-foreground">
                      Connect Slack Bot
                    </span>
                    {employee.hasSlack && employee.slackTeamName ? (
                      <span className="text-xs text-green-600 dark:text-green-400">
                        Connected to {employee.slackTeamName}
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">
                        Install {employee.name}&apos;s Slack app so it can
                        respond to @mentions and DMs.
                      </span>
                    )}
                  </div>
                  {employee.hasSlack ? (
                    <span className="inline-flex shrink-0 items-center gap-1.5 rounded-md bg-green-100 px-3 py-1.5 text-sm font-medium text-green-700 dark:bg-green-900/30 dark:text-green-400">
                      Connected
                    </span>
                  ) : (
                    <a
                      href={slackInstallUrl(employee.id, orgId)}
                      className="inline-flex shrink-0 items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
                    >
                      <ExternalLinkIcon className="size-3.5" />
                      Connect
                    </a>
                  )}
                </div>
              )}

              <Separator />

              <div className="flex flex-col gap-1.5">
                <Label>Status</Label>
                <Select
                  value={employee.status}
                  onValueChange={(value) => {
                    if (!orgId || !value) return;
                    statusMutation.mutate(
                      { orgId, empId, data: { status: value } },
                      { onSuccess: () => invalidate() },
                    );
                  }}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {["active", "inactive", "suspended"].map((status) => (
                        <SelectItem key={status} value={status}>
                          {status}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          {/* Duties Card */}
          <Card>
            <CardHeader>
              <h3 className="text-base font-semibold text-foreground">
                Duties
              </h3>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {employee.duties.length > 0 && (
                <div className="flex flex-col gap-2">
                  {employee.duties.map((duty, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2.5"
                    >
                      <span className="min-w-0 flex-1 text-sm text-foreground">
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
              <div className="flex gap-2">
                <Input
                  placeholder="Add a responsibility..."
                  value={dutyInput}
                  onChange={(e) => setDutyInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleAddDuty();
                    }
                  }}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  onClick={handleAddDuty}
                  className="shrink-0"
                >
                  <PlusIcon />
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* MCP Integrations Card */}
          <Card>
            <CardHeader>
              <h3 className="text-base font-semibold text-foreground">
                MCP Integrations
              </h3>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <div className="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-4 py-3">
                <div className="flex items-center gap-3">
                  <div className="flex size-10 items-center justify-center rounded-lg border border-border bg-background">
                    <MailIcon className="size-5 text-primary" />
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <span className="text-sm font-medium text-foreground">
                      Gmail / Google Workspace
                    </span>
                    {mcpConnectionsData?.connections?.some(
                      (c) => c.connector_slug === "gmail" && c.status === "connected"
                    ) ? (
                      <span className="text-xs text-green-600 dark:text-green-400 font-medium">
                        Connected
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">
                        Let {employee.name} send, draft, and read emails.
                      </span>
                    )}
                  </div>
                </div>
                {mcpConnectionsData?.connections?.some(
                  (c) => c.connector_slug === "gmail" && c.status === "connected"
                ) ? (
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-destructive hover:bg-destructive/10 hover:text-destructive shrink-0"
                    onClick={() => handleDisconnectMcp("gmail")}
                    disabled={deleteMcpConnectionMutation.isPending}
                  >
                    Disconnect
                  </Button>
                ) : (
                  <a
                    href={`${API_URL}/api/organizations/${orgId}/employees/${empId}/mcp-connections/gmail/install?redirect_to=${encodeURIComponent(
                      window.location.origin + window.location.pathname
                    )}`}
                    className="inline-flex shrink-0 items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
                  >
                    <ExternalLinkIcon className="size-3.5" />
                    Connect
                  </a>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      <Separator />

      {/* Knowledge Base */}
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileTextIcon className="size-5 text-muted-foreground" />
            <h3 className="text-base font-semibold text-foreground">
              Knowledge Base
            </h3>
            {documents && documents.length > 0 && (
              <Badge variant="secondary" className="text-xs font-medium">
                {documents.length} file{documents.length !== 1 ? "s" : ""}
              </Badge>
            )}
          </div>
          <Button
            variant="outline"
            size="sm"
            disabled={isUploading}
            onClick={() => fileInputRef.current?.click()}
          >
            {isUploading ? (
              <>
                <Spinner className="mr-1.5 size-3.5" />
                Uploading…
              </>
            ) : (
              <>
                <PlusIcon className="mr-1.5 size-3.5" />
                Add files
              </>
            )}
          </Button>
        </div>

        {docsLoading ? (
          <div className="flex justify-center py-8">
            <Spinner />
          </div>
        ) : docsError ? (
          <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border py-12">
            <p className="text-sm text-destructive">
              Failed to load documents.
            </p>
            <Button
              variant="outline"
              size="sm"
              className="mt-3"
              onClick={() => refetchDocs()}
            >
              Retry
            </Button>
          </div>
        ) : documents && documents.length > 0 ? (
          <div className="space-y-2">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="flex items-center gap-3 rounded-lg border border-border px-3 py-2.5"
              >
                <FileTextIcon className="size-4 shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1 truncate text-sm">
                  {doc.filename}
                </span>
                <span className="hidden text-xs text-muted-foreground sm:inline">
                  {formatSize(doc.size_bytes)}
                </span>
                <Badge variant="secondary" className="text-xs">
                  {doc.status}
                </Badge>
                <button
                  type="button"
                  onClick={() => handleDownload(doc.id, doc.filename)}
                  disabled={downloadingId === doc.id}
                  className="rounded p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                  aria-label={`Download ${doc.filename}`}
                >
                  {downloadingId === doc.id ? (
                    <Spinner className="size-3.5" />
                  ) : (
                    <DownloadIcon className="size-3.5" />
                  )}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setDeletingDocId(doc.id);
                    setDeleteDocDialogOpen(true);
                  }}
                  className="rounded p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-destructive"
                  aria-label={`Delete ${doc.filename}`}
                >
                  <Trash2Icon className="size-3.5" />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border py-12">
            <UploadIcon className="size-8 text-muted-foreground/40" />
            <p className="mt-2 text-sm text-muted-foreground">
              No documents for this agent yet.
            </p>
            <Button
              variant="outline"
              size="sm"
              className="mt-3"
              onClick={() => fileInputRef.current?.click()}
            >
              Upload files
            </Button>
          </div>
        )}
      </div>

      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-2">
          <GitGraphIcon className="size-5 text-muted-foreground" />
          <h3 className="text-base font-semibold text-foreground">
            Knowledge Graph
          </h3>
        </div>

        {graphLoading ? (
          <div className="flex justify-center rounded-lg border border-dashed border-border py-12">
            <Spinner />
          </div>
        ) : graphError ? (
          <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border py-12 text-center">
            <p className="text-sm text-muted-foreground">{graphError}</p>
          </div>
        ) : graphHtml ? (
          <div className="overflow-hidden rounded-xl border border-border bg-background">
            <iframe
              title={`${employee.name} knowledge graph`}
              srcDoc={graphHtml}
              sandbox="allow-scripts allow-same-origin"
              className="h-[720px] w-full bg-background"
            />
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border py-12 text-center">
            <p className="text-sm text-muted-foreground">
              No knowledge graph is available for this agent yet.
            </p>
          </div>
        )}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".pdf,.md,.txt,.csv,.json,.html,.docx,.pptx,.xlsx,.doc,.xls,.ppt,.odt,.rtf"
        className="hidden"
        onChange={handleFileUpload}
      />

      <AlertDialog
        open={deleteDocDialogOpen}
        onOpenChange={setDeleteDocDialogOpen}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete document?</AlertDialogTitle>
            <AlertDialogDescription>
              This document will be permanently removed from this agent's
              knowledge base.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setDeletingDocId(null)}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={handleDeleteDoc}
              disabled={deleteDocMutation.isPending}
            >
              {deleteDocMutation.isPending ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
