# Phase 4 — Cognee Memory Integration — Implementation Plan

> Design reference: `docs/Cognee.md` (architecture, identity model, SDK gotchas)

## Overview

11 files. Best-effort everywhere — Cognee failures never block CRUD. PG is the identity bridge. Cognee embedded (no Docker service).

---

## Step 1: Dependencies

**`apps/api/pyproject.toml`**

```toml
# Add to [project] dependencies:
"cognee>=1.2,<2.0",
```

Why pinned: we use `cognee.modules.*` internal APIs (tenant/user/permission management) which are not part of the public v1 surface and could change across major versions.

---

## Step 2: Config — Cognee Env Vars

**`apps/api/app/core/config.py`** — add after `cognee_data_dir` (line ~39):

```python
# Cognee LLM / embedding (read via os.environ at import time)
cognee_llm_provider: str = "openai"
cognee_llm_endpoint: str = ""
cognee_llm_api_key: str = ""
cognee_llm_model: str = "openai/gpt-4o-mini"
cognee_embedding_provider: str = "openai"
cognee_embedding_endpoint: str = ""
cognee_embedding_model: str = "openai/text-embedding-3-small"
cognee_skip_connection_test: bool = True
```

Cognee reads these from `os.environ` at `import cognee` time. We do NOT set `os.environ` here (Pydantic Settings doesn't do that). The bootstrap module handles that.

---

## Step 3: Bootstrap Module (NEW)

**`apps/api/app/core/cognee.py`** — critical: does NOT `import cognee`.

```python
"""Cognee bootstrap — must be imported before any module that imports cognee."""

import os


def apply_cognee_config() -> None:
    """Set Cognee env vars from settings BEFORE cognee SDK is imported.

    Cognee reads os.environ at import time. If this isn't called first,
    Cognee initializes with empty/wrong config and won't work.
    """
    from app.core.config import settings

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
    os.environ.setdefault(
        "COGNEE_SKIP_CONNECTION_TEST",
        str(settings.cognee_skip_connection_test).lower(),
    )
    os.environ.setdefault("COGNEE_DATA_DIR", settings.cognee_data_dir)
```

---

## Step 4: Memory Service — Full Rewrite

**`apps/api/app/memory/service.py`** — ~250 lines. This is the core file. Everything else imports from here.

### Imports and setup

```python
import logging
import re
import secrets
from uuid import UUID

import cognee
from cognee.modules.users.methods import (
    create_user as _cognee_create_user,
    get_user as _cognee_get_user,
    get_user_by_email as _cognee_get_user_by_email,
)
from cognee.modules.users.tenants.methods import (
    add_user_to_tenant as _cognee_add_user_to_tenant,
    create_tenant as _cognee_create_tenant,
)
from cognee.modules.data.methods import (
    create_authorized_dataset as _cognee_create_authorized_dataset,
)
from cognee.modules.users.permissions.methods import (
    authorized_give_permission_on_datasets as _cognee_authorized_give_permission_on_datasets,
)

logger = logging.getLogger(__name__)
```

### Admin

```python
_ADMIN_EMAIL = "admin@openhuman.internal"

async def init_cognee() -> None:
    """Run Cognee migrations at startup. Call once in FastAPI lifespan."""
    await cognee.run_migrations()

async def get_or_create_admin() -> dict:
    """Idempotent: returns {id, email} for the app-wide admin Cognee user."""
    user = await _cognee_get_user_by_email(_ADMIN_EMAIL)
    if user is None:
        user = await _cognee_create_user(
            email=_ADMIN_EMAIL,
            password=secrets.token_urlsafe(32),
            is_superuser=True,
        )
    return {"id": str(user.id), "email": user.email}
```

### Tenants

```python
async def create_tenant(name: str, owner_id: str) -> dict:
    """Create a Cognee tenant. owner_id = admin Cognee user UUID."""
    tenant_id = await _cognee_create_tenant(
        tenant_name=name, user_id=UUID(owner_id)
    )
    return {"id": str(tenant_id), "name": name}

async def add_user_to_tenant(
    user_id: str, tenant_id: str, owner_id: str
) -> None:
    """Add a user to a tenant. owner_id must be the tenant owner."""
    await _cognee_add_user_to_tenant(
        user_id=UUID(user_id),
        tenant_id=UUID(tenant_id),
        owner_id=UUID(owner_id),
    )
```

### Users

```python
async def create_system_user(tenant_id: str, admin_id: str) -> dict:
    """Create org system user. parent_user_id=admin so admin inherits perms.
    Caller must call add_user_to_tenant() afterwards."""
    email = f"system+{tenant_id}@openhuman.internal"
    user = await _cognee_create_user(
        email=email,
        password=secrets.token_urlsafe(32),
        parent_user_id=UUID(admin_id),
    )
    return {"id": str(user.id), "email": user.email}

async def create_employee_user(tenant_id: str, employee_name: str) -> dict:
    """Create Cognee user for an AI employee. No parent_user_id.
    Caller must call add_user_to_tenant() afterwards."""
    safe_name = re.sub(
        r"[^a-z0-9-]", "-", employee_name.lower().replace(" ", "-")
    )[:64]
    email = f"ai-{safe_name}+{tenant_id}@openhuman.internal"
    user = await _cognee_create_user(
        email=email,
        password=secrets.token_urlsafe(32),
    )
    return {"id": str(user.id), "email": user.email}
```

### Datasets

```python
async def create_dataset(name: str, owner_id: str) -> dict:
    """Create a dataset owned by a Cognee user. Returns {id, name}."""
    user = await _cognee_get_user(UUID(owner_id))
    dataset = await _cognee_create_authorized_dataset(name, user)
    return {"id": str(dataset.id), "name": dataset.name}

async def grant_tenant_read(
    dataset_id: str, tenant_id: str, owner_id: str
) -> None:
    """Grant tenant-wide read permission on a dataset.
    All tenant members inherit this permission."""
    await _cognee_authorized_give_permission_on_datasets(
        UUID(tenant_id), [UUID(dataset_id)], "read", UUID(owner_id)
    )
```

### Memory Operations (cognee v1 top-level API)

```python
async def remember(
    data: str,
    dataset_name: str,
    user_id: str,
    dataset_id: str | None = None,
    background: bool = True,
) -> dict:
    """Store data in Cognee. Pass dataset_id for direct UUID targeting.
    Set background=False to wait for full pipeline (slower but immediate)."""
    user = await _cognee_get_user(UUID(user_id))
    kwargs: dict = {"dataset_name": dataset_name, "user": user}
    if dataset_id:
        kwargs["dataset_id"] = UUID(dataset_id)
    await cognee.remember(data, **kwargs, run_in_background=background)
    return {"status": "ok"}


async def recall(
    query: str,
    user_id: str,
    datasets: list[str] | None = None,
) -> list[dict]:
    """Search Cognee memory as a specific user.
    If datasets is None, searches all datasets the user can access.
    Returns list of {"text", "dataset_name", "source", "score"}."""
    user = await _cognee_get_user(UUID(user_id))
    results = await cognee.recall(query, user=user, datasets=datasets)
    # Normalize RecallResponse objects to plain dicts
    return [
        {
            "text": getattr(r, "text", str(r)),
            "dataset_name": getattr(r, "dataset_name", ""),
            "source": getattr(r, "source", "graph"),
            "score": getattr(r, "score", None),
        }
        for r in results
    ]


async def forget_dataset(dataset_name: str) -> dict:
    """Delete a dataset from Cognee. memory_only=True avoids SQLite
    UNIQUE constraint issues."""
    await cognee.forget(dataset=dataset_name, memory_only=True)
    return {"status": "ok"}


async def improve_dataset(dataset_name: str) -> dict:
    """Refresh embeddings and re-index a dataset."""
    await cognee.improve(dataset=dataset_name)
    return {"status": "ok"}
```

### Listing (deferred — not needed for v1)

The `list_datasets()`, `list_tenants()`, and `list_tenant_users()` functions from the old repo are not ported in v1. Cognee's built-in `cognee.datasets.list_datasets(user=...)` can be used for debugging if needed. Direct SQLite queries against Cognee's internal database are fragile (schema changes across versions) and the path varies by `COGNEE_DATA_DIR` configuration.

**Remove**: existing `MemoryResult` dataclass and `memory_search`/`memory_ingest` stubs. Router will import `recall`/`remember` directly and use `MemoryResultSchema` from schemas.

---

## Step 5: Memory Router — Wire Real Calls

**`apps/api/app/memory/router.py`**

Change imports and update `_verify_employee_ownership` to return the Employee:
```python
# Remove:
from app.memory.service import memory_ingest, memory_search
# Add:
import logging
from app.memory.service import recall, remember

logger = logging.getLogger(__name__)

# Refactor helper to return Employee instead of None:
async def _verify_employee_ownership(
    db: AsyncSession, employee_id: UUID, user_id: UUID
) -> Employee:
    """Return Employee if it belongs to an org owned by user_id, else 404."""
    emp = await db.scalar(
        select(Employee)
        .join(Organization, Employee.org_id == Organization.id)
        .where(
            Employee.id == employee_id,
            Organization.owner_id == user_id,
        )
    )
    if emp is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )
    return emp
```

**`search` endpoint** — replace body:

```python
@router.post("/search", response_model=MemorySearchResponse)
async def search(
    data: MemorySearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MemorySearchResponse:
    emp = await _verify_employee_ownership(
        db, data.employee_id, current_user.id
    )
    # _verify_employee_ownership now returns the Employee object
    # (refactored from returning None — see helper below)

    org = await db.scalar(
        select(Organization).where(Organization.id == emp.org_id)
    )

    # Build dataset list: employee dataset + org dataset
    datasets: list[str] = []
    if emp.cognee_dataset_name:
        datasets.append(emp.cognee_dataset_name)
    if org and org.cognee_dataset_name:
        datasets.append(org.cognee_dataset_name)

    user_id = emp.cognee_user_id or (
        org.cognee_system_user_id if org else None
    )
    if not user_id or not datasets:
        return MemorySearchResponse(results=[], query=data.query)

    try:
        results = await recall(data.query, user_id, datasets=datasets)
    except Exception:
        logger.exception("Cognee recall failed for employee %s", data.employee_id)
        results = []

    schemas = [
        MemoryResultSchema(
            text=r.get("text", ""),
            dataset_name=r.get("dataset_name", ""),
            source=r.get("source", "graph"),
            score=r.get("score"),
        )
        for r in results
    ]
    return MemorySearchResponse(results=schemas, query=data.query)
```

**`ingest` endpoint** — replace body:

```python
@router.post("/ingest", response_model=MemoryIngestResponse)
async def ingest(
    data: MemoryIngestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MemoryIngestResponse:
    emp = await _verify_employee_ownership(
        db, data.employee_id, current_user.id
    )
    if not emp.cognee_user_id or not emp.cognee_dataset_name:
        raise HTTPException(
            status_code=400,
            detail="Employee Cognee not provisioned yet",
        )

    try:
        await remember(
            data.content,
            emp.cognee_dataset_name,
            emp.cognee_user_id,
            dataset_id=emp.cognee_dataset_id,
            background=True,
        )
    except Exception:
        logger.exception(
            "Cognee remember failed for employee %s", data.employee_id
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to ingest memory content",
        )

    return MemoryIngestResponse(status="success")
```

---

## Step 6: Org Service — Cognee Provisioning

**`apps/api/app/organizations/service.py`**

Add imports:
```python
import logging
from app.memory.service import (
    get_or_create_admin, create_tenant, create_system_user,
    add_user_to_tenant, create_dataset, grant_tenant_read,
    remember, forget_dataset,
)
logger = logging.getLogger(__name__)
```

**`create_org()`** — add after `await db.refresh(org)`:

```python
    # ── Cognee provisioning (best-effort, non-blocking) ──────────
    try:
        admin = await get_or_create_admin()
        tenant = await create_tenant(org.name, admin["id"])
        sys_user = await create_system_user(tenant["id"], admin["id"])
        await add_user_to_tenant(
            sys_user["id"], tenant["id"], admin["id"]
        )
        dataset = await create_dataset(
            f"company-{tenant['id']}", sys_user["id"]
        )
        await grant_tenant_read(
            dataset["id"], tenant["id"], sys_user["id"]
        )

        # Seed org info as a memory fact
        seed_text = f"Organization: {org.name}"
        if org.description:
            seed_text += f"\nDescription: {org.description}"
        if org.what_it_does:
            seed_text += f"\nWhat it does: {org.what_it_does}"
        await remember(
            seed_text,
            f"company-{tenant['id']}",
            sys_user["id"],
            dataset_id=dataset["id"],
            background=True,
        )

        # Persist Cognee IDs on org row
        org.cognee_tenant_id = tenant["id"]
        org.cognee_tenant_name = tenant["name"]
        org.cognee_system_user_id = sys_user["id"]
        org.cognee_system_user_name = sys_user["email"]
        org.cognee_dataset_id = dataset["id"]
        org.cognee_dataset_name = dataset["name"]
        await db.commit()
        await db.refresh(org)
    except Exception:
        logger.exception(
            "Cognee org provisioning failed for org %s (non-blocking)",
            org.id,
        )
    # ── End Cognee ──────────────────────────────────────────────

    return org
```

**`delete_org()`** — add before `await db.delete(org)`:

```python
    # ── Best-effort Cognee cleanup ──────────────────────────────
    # Must fetch employees with Cognee datasets BEFORE cascade delete
    employees_with_cognee = [
        e for e in org.employees if e.cognee_dataset_name
    ]
    for emp in employees_with_cognee:
        try:
            await forget_dataset(emp.cognee_dataset_name)
        except Exception:
            logger.exception(
                "Cognee forget_dataset failed during org delete "
                "for employee %s",
                emp.id,
            )
    if org.cognee_dataset_name:
        try:
            await forget_dataset(org.cognee_dataset_name)
        except Exception:
            logger.exception(
                "Cognee forget_dataset failed during org delete %s",
                org.id,
            )
    # ─────────────────────────────────────────────────────────────

    await db.delete(org)
    await db.commit()
    return True
```

---

## Step 7: Employee Service — Cognee Provisioning

**`apps/api/app/employees/service.py`**

Add imports:
```python
import json
import logging
from app.memory.service import (
    get_or_create_admin, create_employee_user, add_user_to_tenant,
    create_dataset, grant_tenant_read, remember, forget_dataset,
)
logger = logging.getLogger(__name__)
```

**`create_employee()`** — add after `await db.commit()` and before `emp = await _get_employee_with_assignments(...)`:

```python
    # ── Cognee provisioning (best-effort, only if org has tenant) ─
    if org.cognee_tenant_id:
        try:
            admin = await get_or_create_admin()
            cognee_user = await create_employee_user(
                org.cognee_tenant_id, emp.name
            )
            await add_user_to_tenant(
                cognee_user["id"],
                org.cognee_tenant_id,
                admin["id"],
            )
            dataset = await create_dataset(
                f"employee-{emp.id}", cognee_user["id"]
            )
            await grant_tenant_read(
                dataset["id"],
                org.cognee_tenant_id,
                cognee_user["id"],
            )

            # Seed employee profile
            profile = json.dumps({
                "name": emp.name,
                "role": emp.role,
                "employee_type": emp.employee_type,
                "personality": emp.personality,
                "specialization": emp.specialization,
            })
            await remember(
                profile,
                f"employee-{emp.id}",
                cognee_user["id"],
                dataset_id=dataset["id"],
                background=True,
            )

            # Persist Cognee IDs on employee row
            emp.cognee_user_id = cognee_user["id"]
            emp.cognee_user_name = cognee_user["email"]
            emp.cognee_dataset_id = dataset["id"]
            emp.cognee_dataset_name = dataset["name"]
            await db.commit()
        except Exception:
            logger.exception(
                "Cognee employee provisioning failed for emp %s "
                "(non-blocking)",
                emp.id,
            )
    # ── End Cognee ──────────────────────────────────────────────
```

**`update_employee()`** — add after the existing `await db.commit()` (in the success path, before re-fetch):

```python
    # ── Re-seed Cognee profile if identity fields changed ────────
    cognee_changed = any(
        field in data.model_dump(exclude_none=True)
        for field in (
            "name", "role", "employee_type",
            "personality", "specialization",
        )
    )
    if cognee_changed and emp.cognee_user_id and emp.cognee_dataset_name:
        try:
            profile = json.dumps({
                "name": emp.name,
                "role": emp.role,
                "employee_type": emp.employee_type,
                "personality": emp.personality,
                "specialization": emp.specialization,
            })
            await remember(
                profile,
                emp.cognee_dataset_name,
                emp.cognee_user_id,
                dataset_id=emp.cognee_dataset_id,
                background=True,
            )
        except Exception:
            logger.exception(
                "Cognee profile re-seed failed for emp %s "
                "(non-blocking)",
                emp.id,
            )
    # ── End Cognee ──────────────────────────────────────────────
```

**`delete_employee()`** — add before `await db.delete(emp)`:

```python
    # ── Best-effort Cognee cleanup ──────────────────────────────
    if emp.cognee_dataset_name:
        try:
            await forget_dataset(emp.cognee_dataset_name)
        except Exception:
            logger.exception(
                "Cognee forget_dataset failed during employee "
                "delete %s",
                emp.id,
            )
    # ─────────────────────────────────────────────────────────────

    await db.delete(emp)
    await db.commit()
    return True
```

---

## Step 8: Document Service — Cognee Ingest

**`apps/api/app/documents/service.py`**

Add imports:
```python
import logging
from app.memory.service import remember

logger = logging.getLogger(__name__)
```

**`save_document()`** — add after `await db.refresh(doc)` and before `return doc`:

```python
    # ── Cognee ingest for text files (best-effort, non-blocking) ─
    safe_name = sanitize_filename(file.filename)
    TEXT_TYPES = {
        "text/plain", "text/markdown", "text/csv",
        "application/json", "application/xml",
    }
    is_text = (
        file.content_type in TEXT_TYPES
        or safe_name.endswith((".txt", ".md", ".csv", ".json", ".xml"))
    )
    if is_text and org.cognee_dataset_name and org.cognee_system_user_id:
        try:
            text_content = content.decode("utf-8", errors="replace")
            await remember(
                f"Document: {safe_name}\n\n{text_content}",
                org.cognee_dataset_name,
                org.cognee_system_user_id,
                dataset_id=org.cognee_dataset_id,
                background=True,
            )
        except Exception:
            logger.exception(
                "Cognee document ingest failed for doc %s "
                "(non-blocking)",
                doc.id,
            )
    # ── End Cognee ──────────────────────────────────────────────

    return doc
```

Note: `content` is already available as a local variable (the raw bytes from `await file.read()`). The `safe_name` variable is computed above before the Cognee block.

**`delete_document()`** — NO Cognee changes. Docs share the org dataset, so we can't `forget_dataset()` on individual doc deletes (it would wipe all org knowledge). File cleanup is handled by `_backend_for(doc).delete()`.

---

## Step 9: Agent Tools — Real Memory

**`apps/api/app/agent/tools/executor.py`**

Add imports at top:
```python
import logging
from uuid import UUID
from sqlalchemy import select
from app.employees.models import Employee
from app.organizations.models import Organization
from app.memory.service import recall, remember

logger = logging.getLogger(__name__)
```

**Replace `search_memory` stub:**

```python
@tool
async def search_memory(query: str, config: RunnableConfig = None) -> str:
    """Search team memory for past decisions, facts, and knowledge.
    Searches both your personal memory and shared org knowledge."""
    emp_id = None
    db = None
    if config and "configurable" in config:
        emp_id = config["configurable"].get("employee_id")
        db = config["configurable"].get("db")

    if not emp_id or not db:
        return "Memory search unavailable (no employee context)."

    try:
        emp = await db.scalar(
            select(Employee).where(Employee.id == UUID(emp_id))
        )
        if not emp:
            return "Employee not found."

        org = await db.scalar(
            select(Organization).where(Organization.id == emp.org_id)
        )

        datasets: list[str] = []
        if emp.cognee_dataset_name:
            datasets.append(emp.cognee_dataset_name)
        if org and org.cognee_dataset_name:
            datasets.append(org.cognee_dataset_name)

        user_id = emp.cognee_user_id or (
            org.cognee_system_user_id if org else None
        )
        if not user_id or not datasets:
            return "Memory not yet provisioned for this employee."

        results = await recall(query, user_id, datasets=datasets)
        if not results:
            return f"No relevant memory found for '{query}'."

        lines = []
        for r in results:
            src = r.get("source", "unknown")
            ds = r.get("dataset_name", "")
            text = r.get("text", "")
            lines.append(f"- [{ds}] {text}")
        return (
            f"Found {len(results)} memory result(s):\n\n"
            + "\n".join(lines)
        )
    except Exception as e:
        logger.exception("search_memory tool failed")
        return f"Error searching memory: {e}"
```

**Replace `ingest_memory` stub:**

```python
@tool
async def ingest_memory(content: str, config: RunnableConfig = None) -> str:
    """Store an important fact or decision in your personal memory
    for future reference. Use this to remember things you've learned."""
    emp_id = None
    db = None
    if config and "configurable" in config:
        emp_id = config["configurable"].get("employee_id")
        db = config["configurable"].get("db")

    if not emp_id or not db:
        return "Cannot store memory (no employee context)."

    try:
        emp = await db.scalar(
            select(Employee).where(Employee.id == UUID(emp_id))
        )
        if (
            not emp
            or not emp.cognee_user_id
            or not emp.cognee_dataset_name
        ):
            return "Memory not yet provisioned for this employee."

        await remember(
            content,
            emp.cognee_dataset_name,
            emp.cognee_user_id,
            dataset_id=emp.cognee_dataset_id,
            background=False,  # immediate availability for agent use
        )
        return (
            f"Successfully remembered: {content[:200]}"
            + ("..." if len(content) > 200 else "")
        )
    except Exception as e:
        logger.exception("ingest_memory tool failed")
        return f"Error storing memory: {e}"
```

Why `background=False` for agent ingest: the agent might `ingest_memory` then immediately `search_memory` in the next turn. We need the data to be immediately available. The tradeoff is higher latency on the ingest call, but this is acceptable for agent-driven facts (typically small text snippets).

---

## Step 10: Main.py — Lifespan Init

**`apps/api/app/main.py`**

Import bootstrap BEFORE all `import app.*` lines:

```python
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

# ── Cognee bootstrap: MUST run before any import app.* ──────────
from app.core.cognee import apply_cognee_config
apply_cognee_config()
# ─────────────────────────────────────────────────────────────────

import logging
from fastapi import FastAPI
...

logger = logging.getLogger(__name__)
```

Add `init_cognee()` to lifespan:

```python
@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    # ── Cognee startup ──────────────────────────────────────────
    try:
        from app.memory.service import init_cognee
        await init_cognee()
        logger.info("Cognee initialized successfully")
    except Exception:
        logger.exception(
            "Cognee initialization failed — continuing without memory"
        )
    # ── Gateway ──────────────────────────────────────────────────
    gateway_manager = BotGatewayManager()
    if settings.gateway_enabled:
        await gateway_manager.start()
    try:
        yield
    finally:
        if settings.gateway_enabled:
            await gateway_manager.stop()
```

Why lazy import `from app.memory.service import init_cognee` inside the try block: if Cognee fails to import entirely (missing package, wrong version), we don't crash before the lifespan even starts. The server comes up without memory.

---

## Step 11: Slack Gateway — Auto-Ingest Messages

**`apps/api/app/gateway/slack_bot.py`**

Add imports:
```python
import logging
from sqlalchemy import select
from app.organizations.models import Organization
from app.memory.service import remember

logger = logging.getLogger(__name__)
```

In `_process_slack_message()`, add after resolving `employee_id` and before `_run_agent()`:

```python
        # ── Auto-ingest Slack message into org memory ────────────
        try:
            emp = await session.get(Employee, employee_id)
            if emp:
                org = await session.scalar(
                    select(Organization).where(
                        Organization.id == emp.org_id
                    )
                )
                if (
                    org
                    and org.cognee_dataset_name
                    and org.cognee_system_user_id
                ):
                    speaker = event.get("user", "unknown")
                    channel = event.get("channel", "unknown")
                    ts = event.get("ts", "")
                    ingest_text = (
                        f"Slack message from <@{speaker}> "
                        f"in <#{channel}> at {ts}:\n{text}"
                    )
                    await remember(
                        ingest_text,
                        org.cognee_dataset_name,
                        org.cognee_system_user_id,
                        dataset_id=org.cognee_dataset_id,
                        background=True,
                    )
        except Exception:
            pass  # silent — never block the Slack response
        # ── End auto-ingest ──────────────────────────────────────
```

But wait — we need a `session` variable. Looking at the existing code, `_process_slack_message` creates sessions via `async_session_factory()` in `_resolve_employee()` and `_run_agent()`. The cleanest approach: add a small helper or inline a session just for the Cognee lookup. Alternatively, use the employee's cached org info.

Simpler approach — use the `employee_id` to look up the org in a dedicated session:

```python
        # ── Auto-ingest Slack message into org memory ────────────
        try:
            async with async_session_factory() as ingest_session:
                from app.employees.models import Employee as EmpModel
                emp = await ingest_session.get(EmpModel, employee_id)
                if emp and emp.cognee_user_id:
                    org = await ingest_session.scalar(
                        select(Organization).where(
                            Organization.id == emp.org_id
                        )
                    )
                    if (
                        org
                        and org.cognee_dataset_name
                        and org.cognee_system_user_id
                    ):
                        speaker = event.get("user", "unknown")
                        ch = event.get("channel", "unknown")
                        ts = event.get("ts", "")
                        ingest_text = (
                            f"Slack message from <@{speaker}> "
                            f"in <#{ch}> at {ts}:\n{text}"
                        )
                        from app.memory.service import remember as cog_rem
                        await cog_rem(
                            ingest_text,
                            org.cognee_dataset_name,
                            org.cognee_system_user_id,
                            dataset_id=org.cognee_dataset_id,
                            background=True,
                        )
        except Exception:
            logger.debug(
                "Slack message Cognee ingest skipped for employee %s",
                employee_id, exc_info=True,
            )
        # ── End auto-ingest ──────────────────────────────────────
```

Place this right after employee resolution succeeds and before `_run_agent()`.

---

## Edge Cases Handled

| Scenario | Behavior |
|---|---|
| Cognee package not installed | `init_cognee()` fails in lifespan, server starts without memory, logs error |
| Cognee migrations fail | Caught in lifespan, server continues |
| Org created, Cognee provisioning fails | Org exists without Cognee IDs. Memory endpoints return empty/400. Can retry later. |
| Employee created, org has no Cognee tenant | Skip provisioning (checked: `if org.cognee_tenant_id`) |
| Employee created, provisioning fails mid-way | Partial Cognee state (tenant/user created but no dataset). Cleaned up on org delete. Best-effort — won't block. |
| Memory search with unprovisioned employee | Returns empty results or "not provisioned" message |
| Slack message ingest fails | Silent catch — never blocks Slack response |
| Document uploaded, Cognee ingest fails | File still saved to bucket. Document exists without memory index. |
| Employee deleted, forget fails | Employee row still deleted. Orphaned Cognee dataset (harmless, can be cleaned up later). |
| Org deleted with cascading employees | `delete_org()` iterates employees to forget their Cognee datasets first, then forgets the org dataset, then cascade-deletes DB rows. Best-effort — individual failures don't block the rest. |
| Two employees share same bot token (same Slack workspace) | One `WorkspaceSlackBot`, `_resolve_employee()` picks one per message. No double-ingestion. |

---

## Verification

```bash
# 1. Start server
cd apps/api && uv run uvicorn app.main:app --reload
# → logs: "Cognee initialized successfully"

# 2. Create org
TOKEN=$(curl -s localhost:8000/api/auth/register \
  -d '{"email":"test@test.com","password":"test123","name":"Test"}' | jq -r .access_token)

ORG=$(curl -s localhost:8000/api/organizations \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"TestCorp","description":"A test org"}')
ORG_ID=$(echo $ORG | jq -r .id)

# Check Cognee IDs in DB
psql -c "SELECT name, cognee_tenant_id, cognee_dataset_name FROM organizations;"
# → should show non-null values

# 3. Create employee
EMP=$(curl -s localhost:8000/api/organizations/$ORG_ID/employees \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"Alice","employee_type":"general"}')
EMP_ID=$(echo $EMP | jq -r .id)

psql -c "SELECT name, cognee_user_id, cognee_dataset_name FROM employees;"
# → should show non-null values

# 4. Ingest a fact
curl -s localhost:8000/api/memory/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"content\":\"The sky is blue\",\"employee_id\":\"$EMP_ID\"}"
# → {"status":"success"}

# 5. Search memory
curl -s localhost:8000/api/memory/search \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"query\":\"sky\",\"employee_id\":\"$EMP_ID\"}"
# → {"results":[{"text":"The sky is blue",...}], "query":"sky"}

# 6. Upload document
echo "OpenHuman uses REST APIs" > /tmp/test.txt
curl -s localhost:8000/api/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/test.txt" -F "organization_id=$ORG_ID"
# → DocumentResponse with storage_backend="local"

# 7. Delete employee
curl -s -X DELETE localhost:8000/api/organizations/$ORG_ID/employees/$EMP_ID \
  -H "Authorization: Bearer $TOKEN"
# → 204

# 8. Delete org
curl -s -X DELETE localhost:8000/api/organizations/$ORG_ID \
  -H "Authorization: Bearer $TOKEN"
# → 204

# 9. Run tests
uv run pytest tests/test_tools_and_memory.py -v
# → memory stub tests will need updating (stubs replaced by real tools)
```

---

## Test Updates Needed

**`tests/test_tools_and_memory.py`**: The `TestSearchMemory` and `TestIngestMemory` classes test the stub behavior (expecting "No relevant memory found" and "Fact successfully remembered"). These need updating to match the new real implementations, or to mock `recall`/`remember` from the memory service.
