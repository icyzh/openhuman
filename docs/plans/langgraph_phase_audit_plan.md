# LangGraph Workflow Phase Audit Plan

> Audit and implement the backend phase by phase against `docs/LANGGRAPH_WORKFLOW.md`.
> This plan treats `docs/plans/implementation_plan.md` as the revised implementation baseline and calls out where it intentionally defers parts of the full workflow.

## Audit Rules

- Check implementation against both the workflow doc and the revised implementation plan.
- Classify findings as `matches spec`, `intentional deferment`, `partial mismatch`, or `bug/risk`.
- Keep changes phase-scoped. Do not fix later phases while implementing an earlier phase unless a later issue blocks the current phase.
- Preserve current public API names and table names unless the workflow explicitly requires a change.
- Prefer forward-safe migrations and non-destructive changes.

## Phase 1: Database Foundation

### Goal

Provide the stable PostgreSQL/SQLAlchemy foundation for users, organizations, employees, channel assignments, documents, bot credentials, and deferred Cognee/MCP metadata.

### Required Decisions

- Migrations must be non-destructive.
- Organization deletion should cascade to employees and documents.
- Employee deletion should cascade to channel assignments and employee-linked documents.
- Duplicate channel assignments for the same employee/platform/channel should be blocked.
- Employee statuses should be restricted to `active`, `inactive`, and `suspended`.
- Document statuses should be restricted to `uploaded`, `processing`, `indexed`, and `failed`.

### Implementation Checklist

- Verify `core/database.py` defines async engine, session factory, declarative base, and `get_db`.
- Verify `core/config.py` exposes DB pool settings and database URL.
- Align models:
  - `User` owns organizations.
  - `Organization` owns employees and documents.
  - `Employee` has encrypted Discord/Slack token fields, JSONB config fields, Cognee IDs, status, channel assignments, and documents.
  - `ChannelAssignment` links employees to platform channels.
  - `Document` links to org and optionally employee, with storage and Cognee document metadata.
- Align Alembic migration:
  - Remove destructive `DROP TABLE ... CASCADE` setup from `upgrade()`.
  - Create tables in FK order.
  - Add indexes for `organizations.owner_id`, `employees.org_id`, `channel_assignments.employee_id`, `documents.org_id`, and `documents.employee_id`.
  - Add FK `ondelete` rules and status/uniqueness constraints.

### Verification

- `uv run ruff check` on changed model and migration files.
- `uv run python -m compileall app alembic`.
- `uv run python -c "import app.main"`.
- `uv run alembic upgrade head --sql`.
- Run live `alembic upgrade head` only when a reachable dev Postgres is configured.

### Current Status

Implemented in this branch. Live DB upgrade still needs a reachable configured database.

## Phase 2: Auth and Security

### Goal

Ensure registration, login, JWT auth, current-user dependency, password hashing, and bot-token encryption are secure and consistently applied.

### Audit Checklist

- Verify `auth/router.py` exposes register, login, and current user endpoints with correct response schemas.
- Verify `auth/service.py` rejects duplicate emails and never returns password hashes.
- Verify `core/security.py`:
  - Uses bcrypt for passwords.
  - Uses JWT `sub`, `iat`, and `exp`.
  - Requires a real production JWT secret.
  - Uses AES-256-GCM for bot token encryption.
  - Rejects missing or invalid encryption keys before token writes.
- Verify `core/dependencies.py`:
  - Rejects missing, expired, invalid, or deleted-user tokens.
  - Loads users by UUID safely.
- Verify all non-public routers depend on `get_current_user`.

### Expected Fixes

- Replace insecure production defaults with config validation or startup warnings.
- Ensure agent test endpoint policy is explicit: authenticated internal test route or intentionally public dev-only route.
- Add focused tests for register, login, `/me`, invalid token, and duplicate email.

### Verification

- Auth unit tests or API tests with an isolated test DB.
- Static import check for auth modules.
- Manual check that token encryption never leaks plaintext in API responses.

## Phase 3: CRUD APIs

### Goal

Implement and verify organization, employee, channel assignment, and document REST APIs with strict owner isolation.

### Audit Checklist

- Organizations:
  - `POST /api/organizations`
  - `GET /api/organizations`
  - `GET /api/organizations/{org_id}`
  - `PATCH /api/organizations/{org_id}`
  - `DELETE /api/organizations/{org_id}`
- Employees:
  - Nested under `/api/organizations/{org_id}/employees`.
  - Creation supports name, role, personality, specialization, duties, and memory policy.
  - Updates cannot cross organization ownership boundaries.
  - Discord token storage encrypts token and only returns `has_discord_token`.
  - Status endpoint allows only DB-approved statuses.
- Channel assignments:
  - Nested under employee route.
  - Prevent duplicate employee/platform/channel rows.
  - Enforce org ownership before create/list/delete.
- Documents:
  - Upload stores metadata and file path.
  - List/delete enforce org ownership.
  - Filename handling must prevent path traversal.
  - Cognee ingestion remains deferred unless Phase 5 changes scope.

### Expected Fixes

- Add missing ownership checks.
- Normalize or validate platform/status values.
- Harden document filename handling.
- Ensure delete behavior matches Phase 1 cascade decisions.

### Verification

- API tests for each CRUD route.
- Cross-user access tests for every org-scoped resource.
- OpenAPI export check.

## Phase 4: LangGraph Agent Core

### Goal

Verify the generic reusable LangGraph loop matches the documented graph shape and supports employee specialization through runtime prompt/tool config.

### Required Graph Shape

`input_guardrail -> build_prompt -> llm_call -> tools loop -> output_guardrail -> formatter -> END`

### Audit Checklist

- `AgentState` extends or cleanly implements message accumulation.
- `build_prompt`:
  - Loads employee and organization context.
  - Uses template specialization without changing graph topology.
  - Adds system prompt exactly once and preserves human message order.
- `llm_call`:
  - Binds only allowed tools for the employee.
  - Does not fall back to all tools if the employee/template intends a restricted set.
- Tool routing:
  - Uses native LLM tool calls.
  - Stops at max 5 tool rounds.
  - Returns a clear final answer when tool round limit is reached.
- Guardrails:
  - Input guardrail can block before LLM cost.
  - Output guardrail sets a safe response when blocked.
  - Template guardrail config is actually passed into checks.
- Formatter:
  - Applies platform length constraints.
  - Handles empty responses safely.
- Agent route:
  - Auth/public policy is explicit.
  - Returns response, tool count, and error consistently.

### Expected Fixes

- Fix any `MessagesState` ordering or duplicate system message issue.
- Remove unsafe all-tools fallback unless it is explicitly development-only.
- Pass employee guardrail config into input/output guardrails.
- Add deterministic tests with mocked LLM/tool calls.

### Verification

- Greeting path: 0 tools.
- Memory/tool path: 1+ tool round.
- Blocked input path: 0 LLM calls.
- Max tool loop path: stops after 5.
- Output blocked path: safe fallback response.

## Phase 5: Memory and Tools

### Goal

Verify built-in tools are safe, correctly named, employee-scoped, and aligned with the revised decision that Cognee and MCP are deferred for now.

### Audit Checklist

- Memory:
  - `memory_search` and `memory_ingest` stubs are clearly marked as mock/deferred.
  - Tool names match templates and prompt language.
  - Employee ID is passed through tool execution context.
- Built-in tools:
  - `search_web` handles provider/network failure gracefully.
  - `get_datetime` handles timezone honestly or documents UTC/default behavior.
  - `calculate` limits AST operations and rejects unsafe expressions.
  - `fetch_url` blocks internal/private/file URLs to avoid SSRF.
- MCP:
  - Stub is clearly isolated.
  - No prompt claims MCP tools are available when client returns none.

### Expected Fixes

- Rename tools or templates so naming is consistent.
- Remove tool access escalation from template fallback behavior.
- Add SSRF protections for URL fetching.
- Add tests for each built-in tool and memory stub behavior.

### Verification

- Unit tests for safe/unsafe calculator expressions.
- Unit tests for allowed and blocked URLs.
- Agent test proving employee-specific tool allowlist is enforced.
- Manual web-search test only when network is intentionally available.

## Phase 6: Bot Gateway and Integrations

### Goal

Verify the Discord and Slack gateways discover active employees, start/stop clients safely, and route mentions/DMs into the LangGraph agent without spam.

### Audit Checklist

- Gateway manager:
  - Starts in FastAPI lifespan only when intended for the environment.
  - Polls active employees with tokens.
  - Starts missing bots and stops inactive/deleted bots.
  - Handles bad tokens without killing the loop.
- Discord:
  - Responds only to DMs or mentions.
  - Removes bot mention from prompt.
  - Uses fresh DB session for each graph run.
  - Chunks responses for Discord limits.
- Slack:
  - Responds to `app_mention` and DMs only.
  - Replies in thread.
  - Uses Socket Mode only when required app token exists.
- Security:
  - Decrypts tokens only inside gateway runtime.
  - Does not log tokens.
  - Does not expose raw integration errors to public channels in production.

### Expected Fixes

- Gate gateway startup behind environment/config if local API startup should not open bot connections.
- Add retry/backoff and bad-token handling.
- Add channel assignment filtering if employees should only respond in assigned channels.
- Normalize error messages sent to Discord/Slack.

### Verification

- Unit tests for manager start/stop decisions with mocked employee rows.
- Unit tests for Discord mention/DM filters.
- Unit tests for Slack mention/DM filters.
- Manual integration test with real Discord/Slack tokens only in a safe dev workspace.

## Final Acceptance Criteria

- Phase 1 through Phase 6 each have a status: complete, deferred by plan, or needs fix.
- All deviations from `LANGGRAPH_WORKFLOW.md` are documented with a reason.
- All security-sensitive behavior has tests or a manual verification note.
- OpenAPI export succeeds.
- Backend imports cleanly.
- No destructive migrations remain in forward migration paths.
