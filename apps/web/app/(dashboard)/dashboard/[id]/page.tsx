"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeftIcon,
  ExternalLinkIcon,
  FileTextIcon,
  PlusIcon,
  Trash2Icon,
  XIcon,
} from "lucide-react";

import type { Employee } from "@/data/employees";
import { DEPARTMENT_COLORS, MODEL_OPTIONS } from "@/data/employees";
import { useEmployeesStore } from "@/stores/employees";
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
import { cn } from "@/lib/utils";

const STATUS_CONFIG: Record<
  Employee["status"],
  { label: string; dotColor: string }
> = {
  active: { label: "Working", dotColor: "bg-green-500" },
  training: { label: "Working", dotColor: "bg-green-500" },
  idle: { label: "Idle", dotColor: "bg-amber-400" },
  offline: { label: "Idle", dotColor: "bg-muted-foreground/30" },
};

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function slackInstallUrl(employeeId: string, orgId: string): string {
  return `${API_URL}/api/slack/install?employee_id=${encodeURIComponent(employeeId)}&org_id=${encodeURIComponent(orgId)}`;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
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

export default function EmployeeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const employee = useEmployeesStore((s) =>
    s.employees.find((e) => e.id === id),
  );
  const updateEmployee = useEmployeesStore((s) => s.updateEmployee);
  const deleteEmployee = useEmployeesStore((s) => s.deleteEmployee);

  const searchParams = useSearchParams();
  const [slackBanner, setSlackBanner] = useState<
    { ok: boolean; message: string } | null
  >(null);

  useEffect(() => {
    const slack = searchParams.get("slack");
    if (slack === "connected") {
      setSlackBanner({
        ok: true,
        message: "Slack workspace connected successfully! 🎉",
      });
    } else if (slack === "error") {
      const reason = searchParams.get("reason") || "unknown error";
      setSlackBanner({
        ok: false,
        message: `Slack connection failed: ${reason}`,
      });
    }
    // Clean the URL without a full page reload
    if (slack) {
      const next = new URL(window.location.href);
      next.searchParams.delete("slack");
      next.searchParams.delete("reason");
      window.history.replaceState({}, "", next.toString());
    }
  }, [searchParams]);

  const [editingField, setEditingField] = useState<string | null>(null);
  const [draftValue, setDraftValue] = useState("");
  const [dutyInput, setDutyInput] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const startEdit = useCallback(
    (field: string, value: string) => {
      setDraftValue(value);
      setEditingField(field);
      requestAnimationFrame(() => inputRef.current?.focus());
    },
    [],
  );

  const commitEdit = useCallback(() => {
    if (!editingField || !employee) return;
    const trimmed = draftValue.trim();
    const current = employee[editingField as keyof Employee];
    if (trimmed && trimmed !== String(current ?? "")) {
      updateEmployee(id, { [editingField]: trimmed } as Partial<Employee>);
    }
    setEditingField(null);
    setDraftValue("");
  }, [editingField, draftValue, employee, id, updateEmployee]);

  if (!employee) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 px-6 py-32">
        <p className="text-sm text-muted-foreground">Employee not found.</p>
        <Button variant="link" onClick={() => router.push("/dashboard")}>
          Back to Team
        </Button>
      </div>
    );
  }

  const deptColor = DEPARTMENT_COLORS[employee.department] ?? "#6b7280";
  const statusConfig = STATUS_CONFIG[employee.status];

  const handleAddDuty = () => {
    const trimmed = dutyInput.trim();
    if (!trimmed) return;
    updateEmployee(id, { duties: [...employee.duties, trimmed] });
    setDutyInput("");
  };

  const handleRemoveDuty = (index: number) => {
    updateEmployee(id, {
      duties: employee.duties.filter((_, i) => i !== index),
    });
  };

  const handleDelete = () => {
    if (!confirmDelete) {
      setConfirmDelete(true);
      return;
    }
    deleteEmployee(id);
    router.push("/dashboard");
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
        >
          <Trash2Icon />
          {confirmDelete ? "Click again to confirm" : "Delete"}
        </Button>
      </div>

      {slackBanner && (
        <div
          className={`rounded-lg border px-4 py-3 text-sm font-medium ${
            slackBanner.ok
              ? "border-green-500/30 bg-green-500/10 text-green-700 dark:text-green-400"
              : "border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-400"
          }`}
        >
          {slackBanner.message}
          <button
            className="ml-3 underline hover:no-underline"
            onClick={() => setSlackBanner(null)}
          >
            Dismiss
          </button>
        </div>
      )}

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
              <h3 className="text-base font-semibold text-foreground">
                Info
              </h3>
              <Badge
                className="ml-auto"
                style={{
                  backgroundColor: `${deptColor}12`,
                  color: deptColor,
                }}
              >
                {employee.department}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <InfoRow label="Name" value={employee.name} />
            <InfoRow label="Role" value={employee.role} />
            <InfoRow label="Specialization" value={employee.specialization || "—"} />
            <InfoRow label="Model" value={employee.model || "—"} />
            <InfoRow label="Status" value={statusConfig.label} />
            <InfoRow label="Deployed" value={employee.deployedAt} />
            <InfoRow label="Discord" value={employee.discordTag ? `@${employee.discordTag}` : "—"} mono />
            <InfoRow label="Slack" value={employee.slackTag ? `@${employee.slackTag}` : "—"} mono />
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">
                Slack Bot
              </span>
              <a
                href={slackInstallUrl(employee.id, "demo-org")}
                className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
              >
                <ExternalLinkIcon className="size-3.5" />
                Connect Slack
              </a>
            </div>
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
                  value={employee.name}
                  onChange={(e) =>
                    updateEmployee(id, { name: e.target.value })
                  }
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>Role</Label>
                <Input
                  value={employee.role}
                  onChange={(e) =>
                    updateEmployee(id, { role: e.target.value })
                  }
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>Specialization</Label>
                <Input
                  value={employee.specialization}
                  placeholder="e.g. Technical billing & refunds"
                  onChange={(e) =>
                    updateEmployee(id, { specialization: e.target.value })
                  }
                />
              </div>

              <Separator />

              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1.5">
                  <Label>Discord</Label>
                  <Input
                    value={employee.discordTag}
                    placeholder="aria_support"
                    onChange={(e) =>
                      updateEmployee(id, { discordTag: e.target.value })
                    }
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label>Slack</Label>
                  <Input
                    value={employee.slackTag}
                    placeholder="aria.support"
                    onChange={(e) =>
                      updateEmployee(id, { slackTag: e.target.value })
                    }
                  />
                </div>
              </div>

              <div className="flex items-center justify-between rounded-lg border border-border bg-muted/30 px-4 py-3">
                <div className="flex flex-col gap-0.5">
                  <span className="text-sm font-medium text-foreground">
                    Connect Slack Bot
                  </span>
                  <span className="text-xs text-muted-foreground">
                    Install the Slack app to your workspace so this employee
                    can respond to @mentions and DMs.
                  </span>
                </div>
                <a
                  href={slackInstallUrl(employee.id, "demo-org")}
                  className="inline-flex shrink-0 items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
                >
                  <ExternalLinkIcon className="size-3.5" />
                  Connect
                </a>
              </div>

              <Separator />

              <div className="flex flex-col gap-1.5">
                <Label>Model</Label>
                <Select
                  value={employee.model}
                  onValueChange={(value) =>
                    updateEmployee(id, { model: value ?? "" })
                  }
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {MODEL_OPTIONS.map((model) => (
                        <SelectItem key={model} value={model}>
                          {model}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex flex-col gap-1.5">
                <Label>Status</Label>
                <Select
                  value={employee.status}
                  onValueChange={(value) =>
                    updateEmployee(id, {
                      status: value as Employee["status"],
                    })
                  }
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {(
                        ["active", "training", "idle", "offline"] as const
                      ).map((status) => (
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
        </div>
      </div>

      {/* Help Contacts */}
      {employee.helpContacts.length > 0 && (
        <Card>
          <CardHeader>
            <h3 className="text-base font-semibold text-foreground">
              Help Contacts
            </h3>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-2">
              {employee.helpContacts.map((contact, i) => (
                <div
                  key={i}
                  className="flex items-start gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2.5"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-foreground">
                      {contact.name}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      @{contact.discordTag}
                      {contact.expertise && ` · ${contact.expertise}`}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Documents */}
      <Card>
        <CardHeader>
          <h3 className="text-base font-semibold text-foreground">
            Documents
          </h3>
        </CardHeader>
        <CardContent>
          {employee.documents.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No documents uploaded yet.
            </p>
          ) : (
            <div className="flex flex-col gap-1.5">
              {employee.documents.map((doc, i) => (
                <div
                  key={`${doc.name}-${i}`}
                  className="flex items-center gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2"
                >
                  <FileTextIcon className="size-4 shrink-0 text-muted-foreground" />
                  <span className="min-w-0 flex-1 truncate text-sm">
                    {doc.name}
                  </span>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {formatFileSize(doc.size)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
