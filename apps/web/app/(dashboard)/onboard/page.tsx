"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeftIcon,
  BotIcon,
  CheckCircle2Icon,
  Loader2Icon,
  ShieldCheckIcon,
  HeadphonesIcon,
  TrendingUpIcon,
  SparklesIcon,
  ScaleIcon,
} from "lucide-react";

import {
  ApiError,
  useEmployeesCreateEmployeeRoute,
  useEmployeesListEmployeesRoute,
  getEmployeesListEmployeesRouteQueryKey,
} from "@repo/api-client";
import { useOrgStore } from "@/stores/org";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Fixed bot definitions (mirrors the API registry) ─────────────────────
// We define these client-side for instant rendering; the API is the source
// of truth for credential availability.

interface FixedBot {
  name: string;
  role: string;
  employee_type: string;
  description: string;
  icon: React.ElementType;
  gradient: string;
  accentColor: string;
}

const FIXED_BOTS: FixedBot[] = [
  {
    name: "Alison",
    role: "HR Specialist",
    employee_type: "hr",
    description:
      "Manages onboarding, benefits, policies, and employee questions",
    icon: ShieldCheckIcon,
    gradient: "from-rose-500/10 to-pink-500/10",
    accentColor: "text-rose-500",
  },
  {
    name: "Alex",
    role: "Customer Support",
    employee_type: "support",
    description:
      "Handles customer inquiries, support tickets, and troubleshooting",
    icon: HeadphonesIcon,
    gradient: "from-blue-500/10 to-cyan-500/10",
    accentColor: "text-blue-500",
  },
  {
    name: "Marcus",
    role: "Sales Representative",
    employee_type: "sales",
    description:
      "Qualifies leads, researches prospects, and tracks pipeline metrics",
    icon: TrendingUpIcon,
    gradient: "from-emerald-500/10 to-green-500/10",
    accentColor: "text-emerald-500",
  },
  {
    name: "Jordan",
    role: "General Assistant",
    employee_type: "general",
    description:
      "Versatile assistant for research, calculations, and general tasks",
    icon: SparklesIcon,
    gradient: "from-violet-500/10 to-purple-500/10",
    accentColor: "text-violet-500",
  },
  {
    name: "Taylor",
    role: "Legal & Compliance",
    employee_type: "legal-compliance",
    description: "Reviews contracts, policies, and regulatory documents",
    icon: ScaleIcon,
    gradient: "from-amber-500/10 to-orange-500/10",
    accentColor: "text-amber-500",
  },
];

export default function OnboardPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const orgId = useOrgStore((s) => s.orgId);
  const createMutation = useEmployeesCreateEmployeeRoute();

  const [addingType, setAddingType] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  const handleAddBot = useCallback(
    async (bot: FixedBot) => {
      if (!orgId || addingType) return;

      setAddingType(bot.employee_type);
      setError(null);

      try {
        // 1. Create the employee with the fixed bot name/role
        const result = await createMutation.mutateAsync({
          orgId: orgId,
          data: {
            name: bot.name,
            employee_type: bot.employee_type,
            role: bot.role,
          },
        });

        // Invalidate the employee list cache
        queryClient.invalidateQueries({
          queryKey: getEmployeesListEmployeesRouteQueryKey(orgId),
        });

        // 2. Redirect to Slack OAuth install
        const installUrl = `${API_URL}/api/slack/install?employee_id=${result.id}&org_id=${orgId}`;
        window.location.href = installUrl;
      } catch (err) {
        setAddingType(null);
        if (err instanceof ApiError && err.status === 409) {
          setError(
            `${bot.name} is already deployed. Each bot type can only be added once.`,
          );
        } else if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("Failed to add bot. Please try again.");
        }
      }
    },
    [orgId, addingType, createMutation, queryClient],
  );

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

      <div className="mx-auto flex w-full max-w-3xl flex-col gap-8">
        {/* Header */}
        <div className="flex flex-col gap-3 text-center">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Add an AI employee to your team
          </h1>
          <p className="text-base text-muted-foreground">
            Pick a bot to add to your Slack workspace. Each bot has a fixed
            identity and specialization.
          </p>
        </div>

        {/* Error banner */}
        {error && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* Bot grid */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FIXED_BOTS.map((bot) => {
            const isTaken = takenTypes.has(bot.employee_type);
            const isAdding = addingType === bot.employee_type;
            const isDisabled = isTaken || !!addingType;
            const Icon = bot.icon;

            return (
              <button
                key={bot.employee_type}
                type="button"
                disabled={isDisabled}
                onClick={() => handleAddBot(bot)}
                className={`group relative flex flex-col gap-4 rounded-2xl border-2 p-5 text-left transition-all duration-200 ${
                  isTaken
                    ? "cursor-default border-border/50 bg-muted/20 opacity-60"
                    : isAdding
                      ? "border-primary bg-primary/5"
                      : addingType
                        ? "cursor-not-allowed border-border/50 opacity-50"
                        : "border-border hover:border-primary/50 hover:shadow-md hover:shadow-primary/5 hover:-translate-y-0.5"
                }`}
              >
                {/* Icon + Name */}
                <div className="flex items-start gap-3">
                  <div
                    className={`flex size-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${bot.gradient}`}
                  >
                    <Icon className={`size-5 ${bot.accentColor}`} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-base font-semibold text-foreground">
                        {bot.name}
                      </span>
                      {isTaken && (
                        <CheckCircle2Icon className="size-4 text-emerald-500" />
                      )}
                    </div>
                    <span className="text-sm text-muted-foreground">
                      {bot.role}
                    </span>
                  </div>
                </div>

                {/* Description */}
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {bot.description}
                </p>

                {/* Status */}
                <div className="mt-auto pt-1">
                  {isTaken ? (
                    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-600 dark:text-emerald-400">
                      <CheckCircle2Icon className="size-3.5" />
                      Active in your workspace
                    </span>
                  ) : isAdding ? (
                    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-primary">
                      <Loader2Icon className="size-3.5 animate-spin" />
                      Connecting to Slack…
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground/70 transition-colors group-hover:text-primary">
                      <BotIcon className="size-3.5" />
                      Click to add to Slack
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>

        {/* Footer hint */}
        <p className="text-center text-xs text-muted-foreground/60">
          Each bot will appear in your Slack workspace with its own identity.
          <br />
          You can manage them from your{" "}
          <Link href="/dashboard" className="underline">
            dashboard
          </Link>{" "}
          at any time.
        </p>
      </div>
    </div>
  );
}
