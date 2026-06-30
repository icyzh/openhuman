export interface EmployeeDocument {
  name: string;
  size: number;
}

export interface HelpContact {
  name: string;
  discordTag: string;
  expertise: string;
}

export interface Employee {
  id: string;
  name: string;
  role: string;
  specialization: string;
  department: string;
  model: string;
  status: "active" | "training" | "idle" | "offline";
  duties: string[];
  discordTag: string;
  slackTag: string;
  documents: EmployeeDocument[];
  helpContacts: HelpContact[];
  deployedAt: string;
}

const MOCK_EMPLOYEES: Employee[] = [
  {
    id: "emp-1",
    name: "Aria",
    role: "Customer Support Agent",
    specialization: "Technical billing & refunds",
    department: "Support",
    model: "Claude Opus 4",
    status: "active",
    duties: [
      "Respond to customer support tickets within 2 hours",
      "Escalate bug reports to the engineering team",
      "Maintain and update the internal knowledge base",
    ],
    discordTag: "aria_support",
    slackTag: "aria.support",
    documents: [],
    helpContacts: [],
    deployedAt: "2026-01-15",
  },
  {
    id: "emp-2",
    name: "Nova",
    role: "Content Strategist",
    specialization: "SEO & long-form blog content",
    department: "Marketing",
    model: "Claude Sonnet 4.6",
    status: "active",
    duties: [
      "Draft weekly blog posts and newsletter content",
      "Optimize existing content for SEO",
      "Analyze content performance metrics monthly",
    ],
    discordTag: "nova_content",
    slackTag: "nova.content",
    documents: [],
    helpContacts: [],
    deployedAt: "2026-03-02",
  },
  {
    id: "emp-3",
    name: "Sterling",
    role: "Code Review Specialist",
    specialization: "Security & performance reviews",
    department: "Engineering",
    model: "Claude Opus 4",
    status: "active",
    duties: [
      "Review all PRs for security vulnerabilities",
      "Flag performance regressions in critical paths",
      "Generate weekly code quality reports",
    ],
    discordTag: "sterling_review",
    slackTag: "sterling.review",
    documents: [],
    helpContacts: [],
    deployedAt: "2025-11-20",
  },
  {
    id: "emp-4",
    name: "Cipher",
    role: "Data Analyst",
    specialization: "Product analytics & dashboards",
    department: "Data",
    model: "Claude Opus 4",
    status: "training",
    duties: [
      "Build and maintain Looker dashboards",
      "Run weekly retention and churn analyses",
    ],
    discordTag: "cipher_data",
    slackTag: "cipher.data",
    documents: [],
    helpContacts: [],
    deployedAt: "2026-06-10",
  },
  {
    id: "emp-5",
    name: "Lumen",
    role: "Brand Designer",
    specialization: "Social media assets & pitch decks",
    department: "Design",
    model: "Claude Fable 5",
    status: "active",
    duties: [
      "Create social media graphics for product launches",
      "Design pitch decks for the sales team",
    ],
    discordTag: "lumen_design",
    slackTag: "lumen.design",
    documents: [],
    helpContacts: [],
    deployedAt: "2026-04-18",
  },
  {
    id: "emp-6",
    name: "Sage",
    role: "Legal Document Reviewer",
    specialization: "Contract & compliance review",
    department: "Data",
    model: "Claude Opus 4",
    status: "idle",
    duties: [
      "Review vendor contracts for compliance risks",
      "Summarize regulatory changes for the legal team",
    ],
    discordTag: "sage_legal",
    slackTag: "sage.legal",
    documents: [],
    helpContacts: [],
    deployedAt: "2026-02-08",
  },
  {
    id: "emp-7",
    name: "Echo",
    role: "Social Media Manager",
    specialization: "Twitter & LinkedIn growth",
    department: "Marketing",
    model: "Claude Haiku 4.5",
    status: "active",
    duties: [
      "Schedule and publish daily social posts",
      "Respond to mentions and DMs within 1 hour",
      "Track engagement metrics and report weekly",
    ],
    discordTag: "echo_social",
    slackTag: "echo.social",
    documents: [],
    helpContacts: [],
    deployedAt: "2025-12-01",
  },
  {
    id: "emp-8",
    name: "Atlas",
    role: "Infrastructure Monitor",
    specialization: "Cloud cost & uptime monitoring",
    department: "Engineering",
    model: "Claude Sonnet 4.6",
    status: "offline",
    duties: [
      "Monitor server uptime and alert on incidents",
      "Track cloud spend and flag anomalies",
    ],
    discordTag: "atlas_infra",
    slackTag: "atlas.infra",
    documents: [],
    helpContacts: [],
    deployedAt: "2026-01-30",
  },
];

export async function fetchEmployees(): Promise<Employee[]> {
  return MOCK_EMPLOYEES;
}

export function getInitials(name: string): string {
  return name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase();
}

export const DEPARTMENTS = [
  "Engineering",
  "Design",
  "Marketing",
  "Data",
  "Support",
] as const;

export const DEPARTMENT_COLORS: Record<string, string> = {
  Engineering: "#3b82f6",
  Design: "#8b5cf6",
  Marketing: "#ef4444",
  Data: "#10b981",
  Support: "#f59e0b",
};

export const MODEL_OPTIONS = [
  "Claude Opus 4",
  "Claude Sonnet 4.6",
  "Claude Haiku 4.5",
  "Claude Fable 5",
] as const;
