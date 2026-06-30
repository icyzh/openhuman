# Cognee Memory Integration — Phase 4 (fork from main)

## Context

Port the Cognee service from the old repo (`/home/sno/Work/hackathon/oldhuman/openhuman/services/ai/app/cognee_service/`). Wire it into org/employee creation so Cognee tenants, users, and datasets are provisioned automatically. Expose memory search/ingest endpoints for the dashboard and agent.

The old implementation has known issues (from `snowork.md`):
- Dataset IDs were created then discarded — only names were used
- Dataset names like `"company-knowledge"` weren't tenant-unique
- Memory review pipeline used auto-created datasets with no permissions

This implementation fixes those: UUID-based dataset names, IDs stored in ORM, all datasets explicitly created with permissions.

## Cognee SDK Reference (from `TO_REMEMBER.md`)

Key gotchas from the old codebase:

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
# Results: [{"text": "...", "dataset_name": "kb", "source": "graph", "score": None}]

# forget() — use memory_only=True to avoid SQLite UNIQUE constraint
await cognee.forget(dataset="kb", memory_only=True)

# improve() takes dataset= (string), not dataset_name=
await cognee.improve(dataset="kb")

# Background remember() means data isn't instantly searchable
# Use run_in_background=False for immediate recall
await cognee.remember(data, dataset_name="kb", user=user_obj)
```

## Cognee Env Vars (set in Config or .env)

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

These are already in `app/core/config.py` from Phase 1.

## Architecture

### Admin User Pattern
Single app-wide admin (`admin@openhuman.internal`, `is_superuser=True`) created once at startup. The admin owns all tenants. System users and AI employees are created with `parent_user_id=admin` so the admin inherits full permissions.

```
Admin (superuser)
├── Tenant: Acme Corp
│   ├── System user: system+{tenantId}@openhuman.internal
│   │   └── Dataset: company-{tenantId}  (tenant-wide read)
│   ├── AI Employee: ai-alice+{tenantId}@openhuman.internal
│   │   └── Dataset: employee-{empPgUuid}  (tenant-wide read)
│   └── AI Employee: ai-bob+{tenantId}@openhuman.internal
│       └── Dataset: employee-{empPgUuid}  (tenant-wide read)
```

### Dataset Naming (deterministic, unique)
| Dataset | Name pattern | Owned by | Created at |
|---------|-------------|----------|------------|
| Org knowledge | `company-{cogneeTenantId}` | System user | Org onboarding |
| Employee brain | `employee-{employeePgUuid}` | Employee user | Employee onboarding |

### What Gets Stored in ORM
| Table | Cognee Columns |
|-------|---------------|
| organizations | `cognee_tenant_id`, `cognee_tenant_name`, `cognee_system_user_id`, `cognee_system_user_name`, `cognee_dataset_id`, `cognee_dataset_name` |
| employees | `cognee_user_id`, `cognee_user_name`, `cognee_dataset_id`, `cognee_dataset_name` |

Names are stored alongside IDs for debugging (`SELECT cognee_dataset_name FROM employees WHERE id = '...'` is immediately readable). They are NOT used in code paths — all `remember()`/`recall()` calls target by UUID.

---

## Files to Create

### `app/memory/service.py` — Cognee wrapper (port + clean from old repo)

This is the core file. Port from `services/ai/app/cognee_service/` with cleanup.

```python
# ---- Admin ----
async def init_cognee() -> None:
    """Run Cognee migrations at startup. Call once in FastAPI lifespan."""
    await cognee.run_migrations()

async def get_or_create_admin() -> dict:
    """Return {id, email} for the app-wide admin Cognee user."""
    ...

# ---- Tenants ----
async def create_tenant(name: str, owner_id: str) -> dict:
    """Create Cognee tenant. Returns {id, name}."""
    tenant_id = await create_tenant(tenant_name=name, user_id=UUID(owner_id))
    return {"id": str(tenant_id), "name": name}

async def add_user_to_tenant(user_id: str, tenant_id: str, owner_id: str) -> None:
    await add_user_to_tenant(user_id=UUID(user_id), tenant_id=UUID(tenant_id), owner_id=UUID(owner_id))

# ---- Users ----
async def create_system_user(tenant_id: str, admin_id: str) -> dict:
    """Create org system user. Returns {id, email}."""
    email = f"system+{tenant_id}@openhuman.internal"
    user = await create_user(email=email, password=secrets.token_urlsafe(32), parent_user_id=UUID(admin_id))
    return {"id": str(user.id), "email": user.email}

async def create_employee_user(tenant_id: str, employee_name: str) -> dict:
    """Create Cognee user for an AI employee. Returns {id, email}."""
    safe_name = employee_name.lower().replace(" ", "-")
    email = f"ai-{safe_name}+{tenant_id}@openhuman.internal"
    user = await create_user(email=email, password=secrets.token_urlsafe(32))
    return {"id": str(user.id), "email": user.email}

# ---- Datasets ----
async def create_dataset(name: str, owner_id: str) -> dict:
    """Create a dataset. Returns {id, name}."""
    user = await get_user(UUID(owner_id))
    dataset = await create_authorized_dataset(name, user)
    return {"id": str(dataset.id), "name": dataset.name}

async def grant_tenant_read(dataset_id: str, tenant_id: str, owner_id: str) -> None:
    """Grant tenant-wide read on a dataset."""
    await authorized_give_permission_on_datasets(
        UUID(tenant_id), [UUID(dataset_id)], "read", UUID(owner_id)
    )

# ---- Memory Operations ----
async def remember(data: str, dataset_name: str, user_id: str,
                   dataset_id: str | None = None, background: bool = True) -> dict:
    """Store data in Cognee. Pass dataset_id for direct UUID targeting."""
    user = await get_user(UUID(user_id))
    kwargs = {"dataset_name": dataset_name, "user": user}
    if dataset_id:
        kwargs["dataset_id"] = UUID(dataset_id)
    await cognee.remember(data, **kwargs, run_in_background=background)
    return {"status": "ok"}

async def recall(query: str, user_id: str, datasets: list[str] | None = None) -> list[dict]:
    """Search Cognee memory. Returns list of result dicts."""
    user = await get_user(UUID(user_id))
    results = await cognee.recall(query, user=user, datasets=datasets)
    return results  # list of {"text":..., "dataset_name":..., "source":..., "score":...}

async def forget_dataset(dataset_name: str) -> dict:
    """Delete a dataset from memory."""
    await cognee.forget(dataset=dataset_name, memory_only=True)
    return {"status": "ok"}

# ---- Listing (direct SQLite queries — Cognee's built-in listing is scoped) ----
async def list_datasets(user_id: str | None = None) -> list[dict]: ...
async def list_tenants() -> list[dict]: ...
```

### `app/memory/router.py` — Memory API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/memory/search` | Search employee + org memory |
| POST | `/api/memory/ingest` | Ingest a fact |

Router: `prefix="/api/memory"`, `tags=["memory"]`.

**`POST /api/memory/search`**:
```json
// Request
{"query": "what did we decide about the API?", "employee_id": "uuid"}
// Response
{"results": [{"text": "...", "dataset_name": "employee-{uuid}", "source": "graph", "score": null}], "query": "..."}
```

Implementation: look up `employee.cognee_user_id` + `employee.cognee_dataset_name` + `org.cognee_dataset_name`. Call `recall(query, cognee_user_id, datasets=[employee_dataset, org_dataset])`.

**`POST /api/memory/ingest`**:
```json
// Request
{"content": "Team decided REST over GraphQL", "employee_id": "uuid"}
// Response
{"status": "ok"}
```

Implementation: look up `employee.cognee_user_id` + `employee.cognee_dataset_name` + `employee.cognee_dataset_id`. Call `remember(content, dataset_name, user_id, dataset_id=dataset_id)`.

### `app/memory/schemas.py`
- `MemorySearchRequest(query: str, employee_id: str)`
- `MemoryResult(text: str, dataset_name: str, source: str, score: float | None)`
- `MemorySearchResponse(results: list[MemoryResult], query: str)`
- `MemoryIngestRequest(content: str, employee_id: str)`
- `MemoryIngestResponse(status: str)`

### `app/documents/service.py` — File upload + Cognee ingest
- Save uploaded file to disk (`storage_path` from config)
- Create Document row in DB
- For text files (txt, md): call `remember(file_content, org_dataset_name, system_user_id, dataset_id=org_dataset_id)`
- PDF ingest deferred (needs PDF parser — follow-up)

### `app/documents/router.py` — Updated with real implementation

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/documents/upload` | Upload file, store metadata, ingest to Cognee |
| GET | `/api/documents` | List docs for org |
| GET | `/api/documents/{doc_id}` | Get doc metadata |
| DELETE | `/api/documents/{doc_id}` | Delete file + forget from Cognee |

Router: `prefix="/api/documents"`, `tags=["documents"]`.

---

## Integration Hooks (modify Phase 3 routes)

### `POST /api/organizations` — after DB insert

```python
# After: org = await create_org(db, user_id, data)
try:
    admin = await get_or_create_admin()
    tenant = await create_tenant(org.name, admin["id"])
    sys_user = await create_system_user(tenant["id"], admin["id"])
    await add_user_to_tenant(sys_user["id"], tenant["id"], admin["id"])
    dataset = await create_dataset(f"company-{tenant['id']}", sys_user["id"])
    await grant_tenant_read(dataset["id"], tenant["id"], sys_user["id"])
    # Seed org config as a memory fact
    await remember(
        f"Organization: {org.name}", f"company-{tenant['id']}",
        sys_user["id"], dataset_id=dataset["id"], background=True
    )
    # Update org with Cognee IDs
    org.cognee_tenant_id = tenant["id"]
    org.cognee_tenant_name = tenant["name"]
    org.cognee_system_user_id = sys_user["id"]
    org.cognee_system_user_name = sys_user["email"]
    org.cognee_dataset_id = dataset["id"]
    org.cognee_dataset_name = dataset["name"]
    await db.commit()
except Exception:
    # Best-effort: org exists, Cognee can be provisioned later
    logger.exception("Cognee org provisioning failed")
```

### `POST /api/organizations/{org_id}/employees` — after DB insert

```python
# After: emp = await create_employee(db, org_id, user_id, data)
try:
    org = await get_org_with_cognee(db, org_id)
    if org and org.cognee_tenant_id:
        admin = await get_or_create_admin()
        cognee_user = await create_employee_user(org.cognee_tenant_id, emp.name)
        await add_user_to_tenant(cognee_user["id"], org.cognee_tenant_id, admin["id"])
        dataset = await create_dataset(f"employee-{emp.id}", cognee_user["id"])
        await grant_tenant_read(dataset["id"], org.cognee_tenant_id, cognee_user["id"])
        # Seed employee profile
        profile = json.dumps({"name": emp.name, "role": emp.role, "personality": emp.personality})
        await remember(profile, f"employee-{emp.id}", cognee_user["id"], dataset_id=dataset["id"], background=True)
        # Update employee with Cognee IDs
        emp.cognee_user_id = cognee_user["id"]
        emp.cognee_user_name = cognee_user["email"]
        emp.cognee_dataset_id = dataset["id"]
        emp.cognee_dataset_name = dataset["name"]
        await db.commit()
except Exception:
    logger.exception("Cognee employee provisioning failed")
```

### On employee update (PATCH)
Re-seed profile if name/role/personality changed. Best-effort, fire-forget, logged on failure.

### On employee delete
Call `forget_dataset(f"employee-{emp.id}")` before deleting the DB row. Best-effort.

### On org delete
Call `forget_dataset(f"company-{org.cognee_tenant_id}")` before cascading delete. Best-effort.

---

## `app/main.py` — Lifespan Update

```python
@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup
    await init_cognee()
    yield
    # Shutdown (nothing needed — Cognee is embedded)
```

Register memory and documents routers:
```python
from app.memory.router import router as memory_router
from app.documents.router import router as documents_router
app.include_router(memory_router)
app.include_router(documents_router)
```

---

## Verification

```bash
# 1. Create org → Cognee tenant + system user + dataset created
curl -X POST localhost:8000/api/organizations ...

# Check DB: cognee_tenant_id, cognee_dataset_name populated
psql -c "SELECT name, cognee_tenant_id, cognee_dataset_name FROM organizations;"

# 2. Create employee → Cognee user + dataset created
curl -X POST localhost:8000/api/organizations/$ORG_ID/employees ...

# Check DB: cognee_user_id, cognee_dataset_name populated
psql -c "SELECT name, cognee_user_id, cognee_dataset_name FROM employees;"

# 3. Search memory
curl -X POST localhost:8000/api/memory/search \
  -d '{"query":"test","employee_id":"$EMP_ID"}'
# → {"results": [...], "query": "test"}

# 4. Ingest a fact
curl -X POST localhost:8000/api/memory/ingest \
  -d '{"content":"the sky is blue","employee_id":"$EMP_ID"}'

# 5. Upload document
curl -X POST localhost:8000/api/documents/upload \
  -F "file=@test.txt" -F "organization_id=$ORG_ID"

# 6. Delete employee → forget called
curl -X DELETE localhost:8000/api/organizations/$ORG_ID/employees/$EMP_ID

# 7. OpenAPI spec
uv run python scripts/export_openapi.py
cd ../../packages/api-client && bun run generate
```

---

## Risks & Notes

1. **Cognee is embedded** (SQLite + LanceDB + Kuzu). No cloud Cognee needed. Data lives in `cognee_data_dir`.
2. **Background remember()** means data isn't instantly searchable. The profile seed is fire-and-forget — expected to appear within seconds.
3. **best-effort provisioning**: Cognee failures never block org/employee creation. Cognee IDs are nullable. If Cognee is down at creation time, the org/employee exists without memory — can be fixed later.
4. **Direct SQLite queries** for listing (datasets, tenants, users). Cognee's built-in `list_datasets()` is access-control-scoped and won't return everything. The direct approach from the old repo works — keep it.
5. **No abstraction layer**. The `app/memory/service.py` is the thin wrapper. Agent tools call it directly. No interfaces, no providers, no dependency injection frameworks.
