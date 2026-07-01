# Cognee Memory Integration

## Context

Replace mock memory stubs with real Cognee SDK integration. Cognee tenants, users, and datasets are provisioned automatically during org/employee creation. Memory search/ingest is exposed through the API router and agent tools. Slack messages are auto-ingested into org knowledge.

**Stack**: FastAPI backend, **SQLAlchemy 2.0 ORM** (async, `Mapped[]` + `mapped_column()`), **Alembic** for migrations, PostgreSQL for application data. Cognee is embedded (SQLite + LanceDB + Kuzu) and stores its own data separately in `./cognee_data`. The Cognee ID columns on `organizations` and `employees` tables were added in the initial Alembic migration — no new migration needed.

Fixes known issues from the old repo:
- Dataset IDs were created then discarded — only names were used
- Dataset names like `"company-knowledge"` weren't tenant-unique
- Memory review pipeline used auto-created datasets with no permissions

This implementation: UUID-based dataset names, IDs stored in ORM columns, all datasets explicitly created with permissions.

## Embedded vs Remote (Why No Docker Service)

The old repo tried to run Cognee as a **separate Docker service** with a REST API (`docker-compose.cognee.yml`). That was heavy — separate container, networking, health checks.

We use Cognee **embedded** — it runs inside the Python backend process. Cognee stores data as local files (SQLite + LanceDB + Kuzu) in `./cognee_data`. No separate server, no extra Docker service, no REST API. Just `import cognee` and use the SDK directly.

Docker deployment stays at 3 services (frontend, backend, postgres). When a docker-compose setup is added, include a volume mount for `./cognee_data` so memory survives container restarts.

## Two-Step Ingest: Bucket → Cognee

Document upload uses a **two-step pattern** to prevent data loss. If Cognee ingest fails, the file is still safe in the bucket.

### Step 1: Storage Backend (the "Bucket")

`app/storage/` provides a pluggable `StorageBackend` abstraction:

- **`LocalStorageBackend`**: saves to `./uploads/{org_id}/{filename}` (default)
- **`S3StorageBackend`**: saves to `s3://{bucket}/{org_id}/{uuid8}_{filename}`

The backend is configured via `storage_backend` setting (`"local"` or `"s3"`). All backends implement the same interface: `save()`, `read()`, `read_stream()`, `delete()`, `get_presigned_url()`.

When a file is uploaded, `save_document()` writes it to the configured backend first. Only after the file is durably stored does it create the `Document` DB row.

```
POST /api/documents/upload
  → backend.save(org_id, filename, content)  ← durable, synchronous
  → INSERT INTO documents (...)               ← metadata in PG
  → [best-effort] remember(content, org_dataset, system_user)  ← Cognee, async
```

### Step 2: Cognee Ingest (Best-Effort Memory)

After the file is safely in the bucket and the DB row exists, we attempt Cognee ingestion. This step is:

- **Best-effort**: failure is logged, never blocks the upload response
- **Background**: `run_in_background=True` — the Cognee pipeline (chunk → embed → graph) runs async
- **Text-only for v1**: txt, md, csv, json, xml files. PDF/Office deferred.
- **Into org dataset**: ingested as the system user so all employees can search

If Cognee is down or the ingest fails, the document still exists in the bucket and the DB row shows `status="uploaded"`. It can be re-ingested later.

### Why Decoupled?

- **Resilience**: Cognee pipeline failures don't lose files
- **Speed**: upload response returns immediately, Cognee processes in background
- **Replay-ability**: files in the bucket can be re-ingested if Cognee is reprovisioned
- **Backend flexibility**: same pattern works whether files are on local disk or S3

## Architecture

### Dataset Topology

```
Admin (superuser: admin@openhuman.internal)
└── Tenant: Acme Corp (cognee tenant)
    ├── System user: system+{tenantId}@openhuman.internal
    │   └── Dataset: company-{cogneeTenantId}
    │       ├── Contains: org config, uploaded documents, Slack messages
    │       └── Access: tenant-wide read (all employees inherit)
    │
    ├── AI Employee "Alice"
    │   ├── Cognee user: ai-alice+{tenantId}@openhuman.internal
    │   └── Dataset: employee-{alicePgUuid}
    │       ├── Contains: employee profile, agent-learned facts
    │       └── Access: tenant-wide read (via grant)
    │
    └── AI Employee "Bob"
        └── (same pattern)
```

### What Goes Where

| Content source | Dataset | Cognee user | Trigger |
|---|---|---|---|
| Org config | `company-{tenantId}` | System user | Org creation |
| Employee profile | `employee-{empUuid}` | Employee user | Employee create/update |
| Uploaded documents | `company-{tenantId}` | System user | File upload (after storage backend save) |
| Slack messages | `company-{tenantId}` | System user | Gateway (every incoming msg, auto) |
| Agent-decided facts | `employee-{empUuid}` | Employee user | Agent calls `ingest_memory` tool |
| API ingest | `employee-{empUuid}` | Employee user | `POST /api/memory/ingest` |

Two-step ingest for documents: 1) file → `StorageBackend` (durable bucket, prevents data loss), 2) content → Cognee `remember()` (best-effort memory, non-blocking).

### ORM Columns (already in migration)

| Table | Cognee Columns |
|---|---|
| organizations | `cognee_tenant_id`, `cognee_tenant_name`, `cognee_system_user_id`, `cognee_system_user_name`, `cognee_dataset_id`, `cognee_dataset_name` |
| employees | `cognee_user_id`, `cognee_user_name`, `cognee_dataset_id`, `cognee_dataset_name` |
| documents | `cognee_document_id` (reserved for future per-document tracking; not used in v1) |

Names alongside IDs for debugging only. All `remember()`/`recall()` calls target by UUID.

### Dataset Naming

`company-{cogneeTenantId}` for orgs, `employee-{employeePgUuid}` for employees. UUID-based, deterministic, unique.

---

## How Identity Works

The agent always carries its `employee_id` (PG UUID) through the LangGraph config. From that single ID, all Cognee credentials are resolved via the ORM.

### Provisioning (one-time, org/employee creation)

```
POST /api/organizations {name: "Acme"}
→ INSERT INTO organizations (id=org-uuid-1, name="Acme")
→ Cognee: create_tenant("Acme", admin)        → tenant_id = "abc-123"
→ Cognee: create_system_user("abc-123", admin)  → user_id = "sys-456"
→ Cognee: create_dataset("company-abc-123")     → dataset_id = "ds-789"
→ Cognee: grant_tenant_read(ds-789, abc-123)
→ UPDATE organizations SET cognee_tenant_id='abc-123', cognee_system_user_id='sys-456',
    cognee_dataset_id='ds-789', cognee_dataset_name='company-abc-123'

POST /api/organizations/org-uuid-1/employees {name: "Alice"}
→ INSERT INTO employees (id=emp-uuid-1, org_id=org-uuid-1)
→ Cognee: create_employee_user("abc-123", "Alice")  → user_id = "ai-111"
→ Cognee: add_user_to_tenant("ai-111", "abc-123")
→ Cognee: create_dataset("employee-emp-uuid-1")       → dataset_id = "ds-222"
→ Cognee: grant_tenant_read(ds-222, abc-123)
→ UPDATE employees SET cognee_user_id='ai-111', cognee_dataset_id='ds-222',
    cognee_dataset_name='employee-emp-uuid-1'
```

### Runtime (every agent invocation)

```
Slack message → gateway resolves employee "Alice" (emp-uuid-1)
→ get_graph_for_employee(db, emp-uuid-1)
→ config = {"configurable": {"db": db, "employee_id": "emp-uuid-1", "all_tools": [...]}}
→ graph.ainvoke(initial_state, config=config)

Agent calls search_memory("what's our refund policy?")
→ tool receives config.configurable
→ emp_id = "emp-uuid-1"
→ db = config["configurable"]["db"]

Inside search_memory:
  SELECT cognee_user_id, cognee_dataset_name, org_id
  FROM employees WHERE id = 'emp-uuid-1'
  → user_id = "ai-111", emp_dataset = "employee-emp-uuid-1", org_id = "org-uuid-1"

  SELECT cognee_dataset_name
  FROM organizations WHERE id = 'org-uuid-1'
  → org_dataset = "company-abc-123"

  recall("refund policy", user_id="ai-111",
         datasets=["employee-emp-uuid-1", "company-abc-123"])
  → Cognee checks: can user "ai-111" read these datasets? Yes.
  → Returns results from BOTH datasets, each tagged with dataset_name
```

**Key point**: PostgreSQL is the identity bridge. `employee_id` (PG UUID) → ORM lookup → Cognee IDs → SDK calls. Cognee's own access control (tenant read grants) ensures the user can only access authorized datasets.

### Agent Memory Tools

- **`search_memory(query)`** — searches `[employee-{empUuid}, company-{tenantId}]`. Results include `dataset_name` so the LLM can distinguish sources. Single tool, both datasets, no scope parameter for v1.
- **`ingest_memory(content)`** — writes to `employee-{empUuid}` only. The employee's personal notebook. Org knowledge comes through documents/Slack paths, not through the agent tool.

---

## Cognee SDK Reference

### Key Gotchas

```python
# create_tenant() returns UUID directly, not an object
tenant_id = await create_tenant(tenant_name=name, user_id=UUID(owner_id))

# create_user() does NOT accept tenant_id — use add_user_to_tenant() after
user = await create_user(email=email, password=pw, parent_user_id=UUID(admin_id))
await add_user_to_tenant(user_id=user.id, tenant_id=tenant_id, owner_id=owner_id)

# get_user() takes UUID, not email — use get_user_by_email() for email lookup
user = await get_user_by_email("admin@example.com")  # → User or None
user = await get_user(UUID(user_id))                  # → User

# create_authorized_dataset() takes User OBJECT, not UUID
user = await get_user(UUID(owner_user_id))
dataset = await create_authorized_dataset(name, user)  # → Dataset with .id, .name

# Permissions use the authorized variant (takes UUIDs)
await authorized_give_permission_on_datasets(
    UUID(recipient_id), [UUID(dataset_id)], "read", UUID(granter_id)
)

# remember() user parameter lives in RememberKwargs
await cognee.remember(data, dataset_name="kb", user=user_obj)

# recall() takes user=, returns graph_completion format
results = await cognee.recall("query", user=user_obj, datasets=["kb"])

# forget() — use memory_only=True to avoid SQLite UNIQUE constraint
await cognee.forget(dataset="kb", memory_only=True)

# improve() takes dataset= (string), not dataset_name=
await cognee.improve(dataset="kb")

# Background remember() — data isn't instantly searchable
await cognee.remember(data, dataset_name="kb", user=user_obj)
```

### v1 API Surface

Cognee v1 exposes these top-level functions:
- `cognee.remember(data, dataset_name, user=, dataset_id=, run_in_background=True)`
- `cognee.recall(query, user=, datasets=[...], dataset_ids=[...])` — returns `RecallResponse` list
- `cognee.forget(dataset=, memory_only=True)`
- `cognee.improve(dataset=)`
- `cognee.run_migrations()`
- `cognee.datasets.list_datasets(user=)`

v1 does NOT expose tenant/user/permission management. For those we use `cognee.modules.*` internal imports (same pattern as the old repo):
- `cognee.modules.users.tenants.methods` → `create_tenant`, `add_user_to_tenant`
- `cognee.modules.users.methods` → `create_user`, `get_user`, `get_user_by_email`
- `cognee.modules.data.methods` → `create_authorized_dataset`
- `cognee.modules.users.permissions.methods` → `authorized_give_permission_on_datasets`

### Env Var Bootstrap (import-order critical)

Cognee reads config from `os.environ` at **import time**. If any `app.*` module does `import cognee` before env vars are set, Cognee initializes with wrong config.

Solution: `app/core/cognee.py` — a tiny module that sets `os.environ` but does NOT `import cognee`. Imported and called in `main.py` BEFORE any `app.*` import.

```python
# app/core/cognee.py — NO import cognee here!
import os
from app.core.config import settings

def apply_cognee_config():
    os.environ.setdefault("LLM_PROVIDER", settings.cognee_llm_provider)
    if settings.cognee_llm_endpoint:
        os.environ["LLM_ENDPOINT"] = settings.cognee_llm_endpoint
    if settings.cognee_llm_api_key:
        os.environ["LLM_API_KEY"] = settings.cognee_llm_api_key
    os.environ.setdefault("LLM_MODEL", settings.cognee_llm_model)
    os.environ.setdefault("EMBEDDING_PROVIDER", settings.cognee_embedding_provider)
    if settings.cognee_embedding_endpoint:
        os.environ["EMBEDDING_ENDPOINT"] = settings.cognee_embedding_endpoint
    os.environ.setdefault("EMBEDDING_MODEL", settings.cognee_embedding_model)
    os.environ.setdefault("COGNEE_SKIP_CONNECTION_TEST",
                          str(settings.cognee_skip_connection_test).lower())
    os.environ.setdefault("COGNEE_DATA_DIR", settings.cognee_data_dir)
```

```python
# main.py — import order matters!
from app.core.cognee import apply_cognee_config
apply_cognee_config()  # ← MUST run before any import cognee

# Now safe: these may transitively import cognee
import app.auth.models  # noqa: F401
...
from app.memory.service import init_cognee
```

### Env Vars Required

```env
LLM_PROVIDER=openai
LLM_ENDPOINT=https://openrouter.ai/api/v1
LLM_API_KEY=sk-or-v1-...
LLM_MODEL=openai/gpt-4o-mini
EMBEDDING_PROVIDER=openai
EMBEDDING_ENDPOINT=https://openrouter.ai/api/v1
EMBEDDING_MODEL=openai/text-embedding-3-small
COGNEE_SKIP_CONNECTION_TEST=true
```

---

## Implementation Plan Summary

See `/home/sno/.claude/plans/fizzy-hatching-shore.md` for the full plan. Quick summary of files to change:

| # | File | Change |
|---|---|---|
| 1 | `pyproject.toml` | Add `cognee`, move `aiosqlite` to main deps |
| 2 | `app/core/config.py` | Add 8 Cognee env var fields |
| 3 | `app/core/cognee.py` | **NEW** bootstrap (sets `os.environ` before `import cognee`) |
| 4 | `app/memory/service.py` | Full rewrite — port all wrappers from old `cognee_service/` |
| 5 | `app/memory/router.py` | Wire search/ingest to real `recall()`/`remember()` calls |
| 6 | `app/organizations/service.py` | Cognee provisioning in `create_org()`, cleanup in `delete_org()` |
| 7 | `app/employees/service.py` | Cognee provisioning in `create_employee()`, re-seed in `update_employee()`, cleanup in `delete_employee()` |
| 8 | `app/documents/service.py` | Cognee ingest after `backend.save()`, no forget on delete |
| 9 | `app/agent/tools/executor.py` | Real `search_memory`/`ingest_memory` implementations |
| 10 | `app/main.py` | Bootstrap import + `init_cognee()` in lifespan |
| 11 | `app/gateway/slack_bot.py` | Auto-ingest Slack messages into org dataset |

---

## Risks & Notes

1. **Embedded, no Docker**: Cognee runs in-process (SQLite + LanceDB + Kuzu). No separate service. Volume-mount `./cognee_data` in docker-compose for persistence.
2. **Background remember()**: Data isn't instantly searchable. Profile seed and document/Slack ingest use `background=True` (fire-and-forget). Agent `ingest_memory` uses `background=False` for immediate availability.
3. **Best-effort everywhere**: Cognee failures never block org/employee creation. IDs are nullable. If provisioning fails, the org exists without memory — can be fixed later.
4. **No abstraction layer**: `app/memory/service.py` is the thin wrapper. Agent tools call it directly.
5. **Import order critical**: `apply_cognee_config()` must set `os.environ` BEFORE any `import cognee`.
6. **Cognee is a hard dependency**: `cognee>=1.2,<2.0` in pyproject.toml. Internal `cognee.modules.*` APIs (tenant/user/permission) are pinned to avoid breakage across major versions. If Cognee is not installed, the server won't start — not a soft dependency.
7. **Service wrappers are NOT redundant**: v1 exposes memory ops but not tenant/user/permission management. We wrap both — adding UUID conversion, domain naming conventions, and best-effort error handling.
8. **Slack deduplication handled by architecture**: one `WorkspaceSlackBot` per token, one employee per message via `_resolve_employee()`. No `event_ts`-based dedup — acceptable for v1.
9. **Two-step document ingest**: file → storage backend (durable), then content → Cognee (best-effort). Decoupled for resilience. No file size guard for v1 — very large text files could OOM.
10. **Single-worker recommended**: Cognee uses SQLite internally. Multiple uvicorn workers may cause `database is locked` errors. Use `--workers 1` or a single worker for the Cognee process.
11. **Cross-employee memory not in v1**: `search_memory` searches the calling employee's dataset + org dataset, not other employees' datasets.
12. **Org delete iterates employees**: `delete_org()` cleans up each employee's Cognee dataset before the cascade delete. Best-effort — if any forget fails, the remaining are still attempted.

## Deferred

- `search_memory` scope parameter (personal/org/all) — v1 searches both
- Cross-employee memory search (`search_team_memory`) 
- Slack message retention/forget policies
- Per-channel Slack datasets for large orgs
- Dashboard setup flows (API endpoints already exist; Cognee hooks into them)
