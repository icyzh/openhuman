import type { EmployeeResponse } from "@repo/api-client";

export interface EmployeeDisplay {
  id: string;
  orgId: string;
  name: string;
  employeeType: string | null;
  role: string;
  specialization: string;
  duties: string[];
  status: string;
  hasDiscord: boolean;
  hasSlack: boolean;
  hasClickup?: boolean;
  deployedAt: string;
  currentTask: string | null;
  mcpConnectionSlugs: string[];
}

function castDuties(duties: unknown[] | null | undefined): string[] {
  if (!duties) return [];
  return duties.filter((d): d is string => typeof d === "string");
}

const MOCK_TASKS: Record<string, string[]> = {
  "Customer Support": [
    "Responding to 3 open support tickets from enterprise customers",
    "Drafting a knowledge base article on common billing questions",
    "Triaging priority queue — 7 tickets awaiting first response",
    "Following up on a refund request escalated from the finance team",
  ],
  "HR Specialist": [
    "Reviewing 12 new candidate applications for the engineering role",
    "Scheduling onboarding sessions for 2 new hires starting next week",
    "Updating the employee handbook with the new remote work policy",
    "Processing quarterly benefits enrollment for the APAC team",
  ],
  "Legal & Compliance": [
    "Auditing vendor contracts for GDPR compliance gaps",
    "Reviewing the new data retention policy draft",
    "Preparing compliance report for the Q3 regulatory filing",
    "Assessing third-party tool risk before procurement approval",
  ],
  "General Assistant": [
    "Summarizing meeting notes from the weekly product sync",
    "Organizing the company all-hands slide deck for Friday",
    "Drafting internal announcement about the new office policy",
    "Compiling competitive research from recent market reports",
  ],
  "Sales Representative": [
    "Preparing a custom proposal for a high-value enterprise lead",
    "Following up on 5 cold outreach emails sent last week",
    "Updating the CRM pipeline for the end-of-quarter review",
    "Researching prospect accounts before the Monday discovery call",
  ],
};

const ALL_TASKS = Object.values(MOCK_TASKS).flat();

const MOCK_MCP_POOLS: Record<string, string[]> = {
  "Customer Support": ["gmail", "slack", "zendesk", "twilio", "hubspot"],
  "HR Specialist": ["gmail", "notion", "google-calendar", "zoom", "trello"],
  "Legal & Compliance": ["gmail", "github", "notion", "google-calendar"],
  "General Assistant": [
    "gmail",
    "slack",
    "notion",
    "github",
    "figma",
    "linear",
  ],
  "Sales Representative": [
    "gmail",
    "slack",
    "salesforce",
    "hubspot",
    "google-calendar",
  ],
};

function hashString(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = (hash * 31 + char) | 0;
  }
  return Math.abs(hash);
}

function pickMockTask(role: string, id: string): string | null {
  const pool = MOCK_TASKS[role] ?? ALL_TASKS;
  const idx = hashString(id) % pool.length;
  return pool[idx] ?? null;
}

function pickMockMcpSlugs(
  role: string,
  id: string,
  mcpConnections: unknown[] | null | undefined,
): string[] {
  // If real MCP connections exist, extract connector_slug from them
  if (mcpConnections && mcpConnections.length > 0) {
    const slugs: string[] = [];
    for (const conn of mcpConnections) {
      if (
        conn &&
        typeof conn === "object" &&
        "connector_slug" in conn &&
        typeof (conn as Record<string, unknown>).connector_slug === "string"
      ) {
        slugs.push((conn as Record<string, unknown>).connector_slug as string);
      }
    }
    if (slugs.length > 0) return slugs;
  }

  // Otherwise generate mock MCPs deterministically
  const pool = MOCK_MCP_POOLS[role] ?? ["gmail", "slack"];
  const idx = hashString(id);
  const count = 2 + (idx % (pool.length - 1)); // 2 to pool.length connections
  const selected: string[] = [];
  const shuffled = [...pool];
  for (let i = 0; i < count && i < shuffled.length; i++) {
    const pickIdx = (hashString(`${id}-mcp-${i}`) + idx) % shuffled.length;
    const slug = shuffled.splice(pickIdx, 1)[0];
    if (slug && !selected.includes(slug)) {
      selected.push(slug);
    }
  }
  return selected;
}

export function apiToEmployeeDisplay(api: EmployeeResponse): EmployeeDisplay {
  return {
    id: api.id,
    orgId: api.org_id,
    name: api.name,
    employeeType: api.employee_type ?? null,
    role: api.role ?? "",
    specialization: api.specialization ?? "",
    duties: castDuties(api.duties),
    status: api.status,
    hasDiscord: api.has_discord_token,
    hasSlack: api.has_slack_token,
    hasClickup: false,
    deployedAt: api.created_at,
    currentTask: pickMockTask(api.role ?? "", api.id),
    mcpConnectionSlugs: pickMockMcpSlugs(
      api.role ?? "",
      api.id,
      api.mcp_connections,
    ),
  };
}

const STATUS_DISPLAY: Record<string, { label: string; dotColor: string }> = {
  active: { label: "Working", dotColor: "bg-green-500" },
  training: { label: "Working", dotColor: "bg-green-500" },
  idle: { label: "Idle", dotColor: "bg-amber-400" },
  inactive: { label: "Inactive", dotColor: "bg-muted-foreground/30" },
  suspended: { label: "Suspended", dotColor: "bg-red-500" },
};

const FALLBACK_STATUS = {
  label: "Unknown",
  dotColor: "bg-muted-foreground/30",
};

export function getStatusConfig(status: string) {
  return STATUS_DISPLAY[status] ?? FALLBACK_STATUS;
}

export const EMPLOYEE_TYPE_LABELS: Record<string, string> = {
  "legal-compliance": "Legal & Compliance",
  support: "Customer Support",
  hr: "HR Specialist",
  general: "General Assistant",
  sales: "Sales Representative",
};
