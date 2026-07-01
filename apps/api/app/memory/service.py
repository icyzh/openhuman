"""Cognee memory service — thin wrappers around the Cognee SDK.

Cognee v1 top-level API:
  cognee.remember()  cognee.recall()  cognee.forget()  cognee.improve()
  cognee.run_migrations()

Cognee internal modules (v1 does not expose tenant/user/permission management):
  cognee.modules.users.methods          → create_user, get_user, get_user_by_email
  cognee.modules.users.tenants.methods  → create_tenant, add_user_to_tenant
  cognee.modules.data.methods           → create_authorized_dataset
  cognee.modules.users.permissions.methods → authorized_give_permission_on_datasets
"""

from __future__ import annotations

import logging
import re
import secrets
from uuid import UUID

import cognee
from cognee.modules.data.methods import (
    create_authorized_dataset as _cognee_create_authorized_dataset,
)
from cognee.modules.users.methods import (
    create_user as _cognee_create_user,
    get_user as _cognee_get_user,
    get_user_by_email as _cognee_get_user_by_email,
)
from cognee.modules.users.permissions.methods import (
    authorized_give_permission_on_datasets as _cognee_authorized_give_permission_on_datasets,
)
from cognee.modules.users.tenants.methods import (
    add_user_to_tenant as _cognee_add_user_to_tenant,
    create_tenant as _cognee_create_tenant,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

_ADMIN_EMAIL = "admin@openhuman.internal"


async def init_cognee() -> None:
    """Run Cognee migrations at startup. Call once in FastAPI lifespan."""
    await cognee.run_migrations()


_admin_cache: dict | None = None


async def get_or_create_admin() -> dict:
    """Idempotent: returns {id, email} for the app-wide admin Cognee user.

    Cached in-process after first resolution — the admin is immutable.
    """
    global _admin_cache
    if _admin_cache is not None:
        return _admin_cache
    user = await _cognee_get_user_by_email(_ADMIN_EMAIL)
    if user is None:
        user = await _cognee_create_user(
            email=_ADMIN_EMAIL,
            password=secrets.token_urlsafe(32),
            is_superuser=True,
        )
    _admin_cache = {"id": str(user.id), "email": user.email}
    return _admin_cache


# ---------------------------------------------------------------------------
# Tenants
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


async def create_system_user(tenant_id: str, admin_id: str) -> dict:
    """Create org system user. parent_user_id=admin so admin inherits perms.

    Caller must call add_user_to_tenant() afterwards.
    """
    email = f"system+{tenant_id}@openhuman.internal"
    user = await _cognee_create_user(
        email=email,
        password=secrets.token_urlsafe(32),
        parent_user_id=UUID(admin_id),
    )
    return {"id": str(user.id), "email": user.email}


async def create_employee_user(tenant_id: str, employee_name: str) -> dict:
    """Create Cognee user for an AI employee. No parent_user_id.

    Caller must call add_user_to_tenant() afterwards.
    """
    safe_name = re.sub(
        r"[^a-z0-9-]", "-", employee_name.lower().replace(" ", "-")
    )[:64]
    email = f"ai-{safe_name}+{tenant_id}@openhuman.internal"
    user = await _cognee_create_user(
        email=email,
        password=secrets.token_urlsafe(32),
    )
    return {"id": str(user.id), "email": user.email}


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------


async def create_dataset(name: str, owner_id: str) -> dict:
    """Create a dataset owned by a Cognee user. Returns {id, name}."""
    user = await _cognee_get_user(UUID(owner_id))
    dataset = await _cognee_create_authorized_dataset(name, user)
    return {"id": str(dataset.id), "name": dataset.name}


async def grant_tenant_read(
    dataset_id: str, tenant_id: str, owner_id: str
) -> None:
    """Grant tenant-wide read permission on a dataset.

    All tenant members inherit this permission.
    """
    await _cognee_authorized_give_permission_on_datasets(
        UUID(tenant_id), [UUID(dataset_id)], "read", UUID(owner_id)
    )


# ---------------------------------------------------------------------------
# Memory Operations (cognee v1 top-level API)
# ---------------------------------------------------------------------------


async def remember(
    data: str,
    dataset_name: str,
    user_id: str,
    dataset_id: str | None = None,
    background: bool = True,
) -> dict:
    """Store data in Cognee.

    Pass dataset_id for direct UUID targeting (avoids name resolution).
    Set background=False to wait for full pipeline (slower but immediate recall).
    """
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
    Returns list of {"text", "dataset_name", "source", "score"}.
    """
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
    """Delete a dataset from Cognee.

    Uses memory_only=True to avoid SQLite UNIQUE constraint issues.
    """
    await cognee.forget(dataset=dataset_name, memory_only=True)
    return {"status": "ok"}


