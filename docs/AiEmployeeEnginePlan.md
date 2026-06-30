# AI Employee Engine — Phase Plan

## Overview

A platform that deploys AI employees (HR, Legal, Sales, Support, etc.) that live 24/7 in Slack. Each employee has its own tools, memory, personality, and schedule — but they all run on a single shared LangGraph.

---

## Architecture Principles (carried through every phase)

- **One graph, many configs.** The agent loop is defined once. Everything that varies (tools, prompts, memory, schedule, ingestion) lives in per-employee configs.
- **Tools are dynamically injected.** The graph never imports a tool. Tools arrive at runtime in a dict. Memory tools sit alongside domain tools — same interface.
- **Company isolation by design.** `company_id` is the root key in every lookup. Tools are hydrated with that company's credentials. Memory is namespaced by `company_id:employee_type`. Cross-contamination is architecturally impossible.
- **The graph is the dumbest piece.** It just loops: reason → act → reason → respond. All intelligence lives in the LLM, the tools, and the config.

---

## Phase 1: Core Engine (no Slack, no memory, no multi-tenancy)

**Goal:** One employee type, one company, runs locally from a CLI or script. Prove the graph + config + dynamic tools pattern works.

### What gets built

- `graph.py` — the shared agent loop (load_task → reason → act → respond)
- `config/hr.py` — one employee config: system prompt + tool names
- `tools/` — a registry of tools, each implementing a standard interface
- `hydrate_tools()` — resolves tool names → instantiated tools with credentials
- A CLI entrypoint: `python run.py --employee hr --task "Review this resume"`

### What gets validated

- The LLM correctly decides when to call tools vs. respond
- Tools execute and results feed back into the loop
- The graph terminates properly (no infinite loops)
- Config switching works — same graph, different config, different behavior

### What stays hardcoded

- Company ID is a constant
- Tools are stubs or mock APIs
- Tasks come from the CLI, not Slack
- No memory between runs

### Exit criteria

- HR employee can receive a resume file path, call `parse_pdf → rate_resume → categorize_resume`, and return a structured review. Legal employee can do the same with a different config and different tools. Same graph, no code changes.

---

## Phase 2: Memory Layer (cognee integration)

**Goal:** Employees remember. A candidate reviewed today is recalled when they apply again in three weeks.

### What gets built

- cognee integration via `get_sessionized_cognee_tools(session_id=f"{company_id}:{employee_type}")`
- Memory tools (`remember`, `recall`) injected into the dynamic tool dict alongside domain tools
- Graph-enforced recall: a `recall` node runs memory retrieval *before* reasoning, so the LLM always has context without having to ask for it
- Manual pre-seeding: call `cognee.add()` + `cognee.cognify()` on company documents before the employee ever runs

### What gets validated

- Memory is scoped to `company_id:employee_type` — HR can't see Legal's memory
- After reviewing Sarah Chen's resume, a second review of the same candidate includes prior context automatically
- Pre-seeded documents (handbooks, policies) are retrievable in relevant queries

### Exit criteria

- Two separate conversations about the same candidate, days apart, produce context-aware responses. "This candidate previously applied for backend role, scored 87. Rejected due to salary expectations — but this new role has a higher band."

---

## Phase 3: Slack Integration — Active (real-time @mentions)

**Goal:** The employee lives in Slack and responds when directly mentioned. First taste of real-world deployment.

### What gets built

- Slack Events API webhook handler
- `@mention` event parsing → resolve company_id + employee_type → enqueue job
- Queue (in-process `asyncio.Queue` — no Redis yet)
- Worker process that dequeues, hydrates tools + memory, runs the graph, posts response back to Slack thread
- Basic Slack surface: bot user, OAuth scopes, event subscription

### What gets validated

- `@HR review this resume` triggers the full agent loop and posts a response in-thread
- Multiple @mentions in quick succession queue properly and don't collide
- Errors surface gracefully (employee replies "I ran into an issue processing that" rather than silent failure)

### Exit criteria

- HR and Legal employees respond to @mentions in their respective Slack channels. Each uses its own tools and memory. Works for a single company.

---

## Phase 4: Passive Ingestion (batch observation)

**Goal:** Employees absorb knowledge from channels without being mentioned. This is what makes them feel like they've been working there for months.

### What gets built

- Per-employee ingestion config: channels to watch, domain keywords, extraction prompt, cadence
- Batch ingestion pipeline (runs every N minutes per employee type):
  1. Fetch all new messages in monitored channels since last tick
  2. Relevance filter (keyword + embedding similarity against domain profile)
  3. Batch summarization: one LLM call extracts all relevant facts from the batch
  4. `cognee.remember()` stores the extracted knowledge
- Separate lightweight codepath from the main graph — this is a summarizer, not the full agent

### What gets validated

- A policy update posted in #general gets absorbed by HR employee's memory without being @mentioned
- Three people discussing the Berlin office opening in #general produces one consolidated memory, not three near-identical entries
- Irrelevant chatter (deploy pipeline, lunch plans) costs nothing — filtered before any LLM call
- Different employees extract different things from the same #general channel based on their domain profiles

### Exit criteria

- After a week of passive observation, asking HR "What do you know about our hiring plans?" returns knowledge absorbed from channels HR was watching — without anyone ever explicitly telling HR anything.

---

## Phase 5: Proactive Engagement

**Goal:** Employees speak unprompted — but only when it's genuinely helpful, never when it's invasive.

### What gets built

- Per-employee `proactive` config section defining allowed unprompted behaviors
- Extension of the ingestion pipeline: after filtering and summarizing, also check "should we act on this?"
- Supported proactive patterns:
  - **Scheduled digests.** Monday 9am: "Here's what happened last week in hiring."
  - **Unanswered questions.** Nobody replied to "What's our parental leave policy?" in 30 minutes → employee answers in-thread.
  - **Threshold-based alerts.** Known risky contract mentioned → Legal flags it.
- Guardrails: the LLM is the final filter — even if triggered, it can decide "this doesn't warrant a response"

### What gets validated

- HR posts a Monday digest in #hr-updates without being asked
- An unanswered policy question in #general gets a helpful, threaded response after the configured delay
- Legal flags a contract with known problematic clauses, but stays silent on casual legal hypotheticals
- No employee ever replies "I noticed you're discussing X and I think you're wrong" — the prompt guardrail holds

### Exit criteria

- Employees proactively contribute value once or twice a week. Zero complaints about intrusiveness. The team starts to trust them.

---

## Phase 6: Scheduled Duties

**Goal:** Employees have recurring responsibilities — daily standup posts, weekly digests, morning triage. They track time and execute on schedule.

### What gets built

- Per-employee `scheduled` config section: cron expression + task description + target channel
- Scheduler process (singleton): wakes every ~30 seconds, checks all company × employee configs, enqueues any due duties
- Integration with the same queue — scheduled duties are just another job type to the worker
- Missed-duty handling: if the worker was down at 9am, the scheduler enqueues the missed duty when it comes back

### What gets validated

- HR posts "Good morning — here's the current hiring pipeline" every weekday at 9am in #general
- Legal posts a weekly compliance digest every Monday at 9am
- Schedule changes take effect without restart — just update the config
- If 9am fires while the worker is briefly down, the duty runs when the worker recovers (within reason)

### Exit criteria

- Three different employees, each with different scheduled duties, different cadences, different channels. Zero cross-interference. A schedule config change propagates within 60 seconds.

---

## Phase 7: Multi-Tenancy at Scale

**Goal:** Multiple companies, each with their own set of employees, their own credentials, their own memory. The platform works for paying customers.

### What gets built

- Company onboarding flow: sign up → connect Slack → configure employees → seed knowledge
- Per-company credential vault (API keys for their tools — BambooHR, Salesforce, etc.)
- Redis-backed queue (BullMQ or similar) replacing in-process `asyncio.Queue`
- Queue-per-employee-type pattern: `hr-queue`, `legal-queue`, `sales-queue` — so one company's HR backlog doesn't starve Legal
- Per-company rate limiting on LLM calls and Slack API calls
- Worker horizontal scaling: `docker-compose` with `replicas: 2-10` per queue
- LangGraph checkpointing (SQLite → Postgres) so a crash mid-task resumes cleanly
- Admin dashboard: queue depth, worker count, error rates, LLM spend per company

### What gets validated

- Acme Corp's HR employee and Globex's HR employee run concurrently with zero data leakage
- One company submitting 500 resume reviews doesn't slow down other companies
- A worker crashes mid-review → new worker picks up the checkpoint and continues
- LLM spend is attributable per company

### Exit criteria

- 10 companies, 40+ employees across all types, running concurrently. System auto-scales workers based on queue depth. Any employee can be queried about its own memory and returns only that company's data.

---

## Phase 8: Production Hardening

**Goal:** The platform is reliable enough that companies depend on it.

### What gets built

- Observability: OpenTelemetry tracing across graph nodes, tool calls, and LLM calls. Tagged by `company_id` and `employee_type`.
- Alerting: queue depth spikes, worker crash loops, LLM error rate thresholds, per-company spend anomalies
- Slack rate limit handling: per-workspace token bucket, graceful backoff
- Employee health heartbeat: if an employee misses its scheduled duty twice in a row, alert the company admin
- Feedback loop: after every employee response, a "Was this helpful? 👍👎" reaction. Low scores flag the interaction for review.
- Cost optimization: cache frequent LLM calls (same resume reviewed twice → cached result), batch similar tasks
- Security audit: tool execution sandboxing, prompt injection guards, PII redaction in logs

### Exit criteria

- 99%+ uptime over a 30-day period. Mean time to detect issues under 5 minutes. Per-company LLM costs within 20% of estimates. Zero cross-company data incidents.

---

## What's Deliberately Deferred

- **Custom graphs per employee type.** Start extracting subgraphs only when a real employee genuinely needs different node structure. Hasn't happened yet in this design — config handles all observed variance.
- **Multi-platform.** Slack only until there's proven demand for Teams or Discord. The architecture supports it (swap the webhook handler and reply adapter) but don't build it until someone pays for it.
- **Inter-employee collaboration.** HR and Legal coordinating on a hire. Powerful product feature, but requires a routing layer between employees that's its own design discussion. Phase 8+.
- **Custom tool builder.** Letting companies define their own tools in a UI. Phase 9. Start with a fixed tool catalog and expand based on demand.

---

## Config Shape (evolves through phases, target end state)

```
employee_config:
  id: "hr-specialist"
  display_name: "HR Specialist"
  description: "Screen resumes, manage onboarding, answer policy questions"

  system_prompt: "You are an HR specialist..."

  tools:
    domain: [rate_resume, categorize_resume, lookup_employee, parse_pdf]
    universal: [send_slack_message, send_email]
    memory: [remember, recall]          # cognee, injected automatically

  integrations: [bamboo_hr, greenhouse, workday]

  task_types: [screen_candidates, schedule_interviews, answer_policy, send_communications]

  ingestion:
    cadence: "5 minutes"
    channels: [#general, #announcements, #hr-internal, #engineering]
    domain_keywords: [hiring, role, compensation, benefits, interview, onboarding, departure]
    extraction_prompt: "Extract anything relevant to HR: hiring plans, role changes, ..."

  proactive:
    digest:
      enabled: true
      schedule: "Monday 9am"
      channel: "#hr-updates"
    unanswered_questions:
      enabled: true
      delay: "30 minutes"
      confidence_min: 0.8
    policy_violation:
      enabled: false

  scheduled:
    - cron: "0 9 * * mon-fri"
      task: "Post current hiring pipeline summary in #general"
    - cron: "0 17 * * fri"
      task: "Compile weekly HR digest in #hr"
    - cron: "0 8 * * *"
      task: "Triage overnight resume submissions"
```

---

## Infrastructure Progression

| Phase | Queue | Memory | State | Workers | Companies |
|---|---|---|---|---|---|
| 1-2 | None (direct call) | cognee (local) | None | 1 (manual) | 1 (hardcoded) |
| 3 | asyncio.Queue | cognee | None | 1 | 1 |
| 4-6 | asyncio.Queue | cognee | None | 1-2 | 1 |
| 7 | Redis + BullMQ | cognee | Postgres checkpointing | N (per queue) | 10+ |
| 8 | Redis + BullMQ | cognee | Postgres | N (auto-scaled) | 50+ |
