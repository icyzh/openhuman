# Backend Plan — Phases 1–3 (main branch)

## Current State

Domain-driven skeleton exists with empty stubs. Files with real content:
- `app/main.py` — FastAPI app, only health router registered
- `app/core/config.py` — minimal settings
- `app/health/` — working health endpoint
- `alembic/env.py` — Alembic configured but `target_metadata = None`
- `pyproject.toml` — deps: fastapi, pydantic-settings, sqlalchemy[asyncio], alembic

Everything else (`app/auth/`, `app/organizations/`, `app/employees/`, `app/core/database.py`, `app/core/security.py`, `app/core/dependencies.py`, etc.) is empty files.

## Architecture

```
app/
├── main.py              # App factory, router registration, lifespan
├── core/
│   ├── config.py        # pydantic-settings (all env vars)
│   ├── database.py      # AsyncEngine, async_session_factory, Base
│   ├── security.py      # Password hashing, JWT, AES-256-GCM encrypt/decrypt
│   └── dependencies.py  # get_db, get_current_user
├── health/              # ✅ Done
├── auth/                # User model, register/login/me routes
├── organizations/       # Org model, CRUD routes
├── employees/           # Employee model, CRUD + token management routes
├── channel_assignments/ # Channel assignment model + sub-routes
├── documents/           # Document model (no Cognee yet, just file metadata)
├── memory/              # Placeholder (filled in Phase 4 Cognee fork)
├── agent/               # Other dev's domain (don't touch)
└── gateway/             # Deferred (don't touch)
```

Each domain module contains its own `models.py`, `schemas.py`, `router.py`, `service.py` (co-located, not split across top-level directories).

---

## Phase 1: Database Foundation

### Goal
Working database connection, ORM models for all domains, Alembic wired up for autogenerate.

### 1a. Config — `app/core/config.py`

Add to existing `Settings`:
```python
# Database
database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/openhuman"
db_pool_size: int = 5
db_max_overflow: int = 10

# Auth
jwt_secret_key: str = "change-me-in-production"
jwt_algorithm: str = "HS256"
jwt_expire_minutes: int = 60

# Encryption (for bot tokens — AES-256-GCM)
encryption_key: str = ""  # 32-byte hex string

# OpenRouter (for agent team — we just provide the config)
openrouter_api_key: str = ""
openrouter_base_url: str = "https://openrouter.ai/api/v1"

# Cognee (for Phase 4 fork)
cognee_data_dir: str = "./cognee_data"
llm_provider: str = "openai"
llm_endpoint: str = "https://openrouter.ai/api/v1"
llm_api_key: str = ""
llm_model: str = "openai/gpt-4o-mini"
embedding_provider: str = "openai"
embedding_endpoint: str = "https://openrouter.ai/api/v1"
embedding_model: str = "openai/text-embedding-3-small"
cognee_skip_connection_test: bool = True
```

### 1b. Database Engine — `app/core/database.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
```

### 1c. Models

**Pattern**: UUID PKs via `server_default=func.gen_random_uuid()`. Timestamps via `func.now()`. JSONB via `sqlalchemy.dialects.postgresql.JSONB`. All Cognee columns nullable (populated in Phase 4 fork).

**`app/auth/models.py`** — `User`:
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | gen_random_uuid() |
| email | String(255) | unique, indexed, not null |
| password_hash | String(255) | not null |
| name | String(255) | not null |
| is_active | Boolean | default True |
| created_at | DateTime | server_default=func.now() |
| updated_at | DateTime | onupdate=func.now() |

**`app/organizations/models.py`** — `Organization`:
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | gen_random_uuid() |
| owner_id | UUID FK→users.id | not null |
| name | String(255) | not null |
| cognee_tenant_id | String(255) | nullable (Phase 4) |
| cognee_tenant_name | String(255) | nullable |
| cognee_system_user_id | String(255) | nullable |
| cognee_system_user_name | String(255) | nullable |
| cognee_dataset_id | String(255) | nullable |
| cognee_dataset_name | String(255) | nullable |
| created_at | DateTime | server_default=func.now() |

Relationships: `owner` (User), `employees` (list[Employee])

**`app/employees/models.py`** — `Employee`:
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | gen_random_uuid() |
| org_id | UUID FK→organizations.id | not null, indexed |
| name | String(255) | not null |
| role | String(255) | e.g. "Customer Support" |
| personality | JSONB | dict: {tone, traits, etc.} |
| specialization | String(255) | e.g. "support_agent" |
| duties | JSONB | list of duty definitions |
| discord_token_enc | Text | nullable, AES-256-GCM encrypted |
| slack_token_enc | Text | nullable |
| mcp_connections | JSONB | list of MCP server configs |
| memory_policy | JSONB | dict: {mentions_bot, auto_remember, etc.} |
| cognee_user_id | String(255) | nullable (Phase 4) |
| cognee_user_name | String(255) | nullable |
| cognee_dataset_id | String(255) | nullable |
| cognee_dataset_name | String(255) | nullable |
| status | String(50) | default "inactive" |
| created_at | DateTime | server_default=func.now() |
| updated_at | DateTime | onupdate=func.now() |

Relationships: `organization` (Organization), `channel_assignments` (list[ChannelAssignment])

**`app/channel_assignments/models.py`** — `ChannelAssignment`:
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | gen_random_uuid() |
| employee_id | UUID FK→employees.id | not null, indexed |
| platform | String(50) | "discord" or "slack" |
| channel_id | String(255) | not null |
| channel_name | String(255) | |

**`app/documents/models.py`** — `Document`:
| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | gen_random_uuid() |
| org_id | UUID FK→organizations.id | not null |
| employee_id | UUID FK→employees.id | nullable |
| filename | String(255) | not null |
| content_type | String(100) | |
| size_bytes | Integer | |
| storage_path | String(500) | |
| cognee_document_id | String(255) | nullable (Phase 4) |
| status | String(50) | default "uploaded" |
| uploaded_at | DateTime | server_default=func.now() |

### 1d. Alembic Wiring

Update `alembic/env.py`:
```python
from app.core.database import Base
from app.core.config import settings

# Import all models so Base.metadata knows about them
import app.auth.models        # noqa: F401
import app.organizations.models  # noqa: F401
import app.employees.models   # noqa: F401
import app.channel_assignments.models  # noqa: F401
import app.documents.models   # noqa: F401

target_metadata = Base.metadata
config.set_main_option("sqlalchemy.url", settings.database_url)
```

Also create `alembic.ini` if missing (standard Alembic init).

### 1e. Dependencies

Add to `pyproject.toml` deps: `asyncpg>=0.30`, `passlib[bcrypt]>=1.7`, `python-jose[cryptography]>=3.3`, `cryptography>=43.0`.

### Verification
```bash
uv run alembic revision --autogenerate -m "initial"
uv run alembic upgrade head
# → All tables created in PostgreSQL
uv run python -c "from app.core.database import engine; print('OK')"
```

---

## Phase 2: Auth

### Goal
User registration, login, JWT sessions, auth dependency.

### 2a. Security — `app/core/security.py`

```python
# Password hashing
def hash_password(password: str) -> str: ...
def verify_password(plain: str, hashed: str) -> bool: ...

# JWT
def create_access_token(user_id: str) -> str: ...
def decode_access_token(token: str) -> dict: ...

# AES-256-GCM (for bot tokens)
def encrypt_token(plaintext: str) -> str: ...
def decrypt_token(ciphertext: str) -> str: ...
```

Use `passlib.context.CryptContext` for bcrypt. Use `python-jose` for JWT. Use `cryptography.hazmat` for AES-256-GCM.

### 2b. Dependencies — `app/core/dependencies.py`

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db  # re-export
from app.core.security import decode_access_token

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate JWT, return User or 401."""
    ...
```

### 2c. Auth Module

**`app/auth/schemas.py`**:
- `RegisterRequest(email, password, name)`
- `LoginRequest(email, password)`
- `TokenResponse(access_token, token_type="bearer")`
- `UserResponse(id, email, name, is_active, created_at)` — `from_attributes=True`

**`app/auth/service.py`**:
- `register(db, data: RegisterRequest) → User` — check email uniqueness, hash password, create user
- `authenticate(db, email, password) → User` — verify credentials
- `get_user_by_id(db, user_id) → User | None`

**`app/auth/router.py`**:
| Method | Path | Handler | Response |
|--------|------|---------|----------|
| POST | `/api/auth/register` | `register` | 201 + TokenResponse |
| POST | `/api/auth/login` | `login` | 200 + TokenResponse |
| GET | `/api/auth/me` | `me` | 200 + UserResponse |

Router: `prefix="/api/auth"`, `tags=["auth"]`.

### 2d. Register router in `app/main.py`

```python
from app.auth.router import router as auth_router
app.include_router(auth_router)
```

### Verification
```bash
curl -X POST localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"secret123","name":"Test"}'
# → 201 + {"access_token": "...", "token_type": "bearer"}

curl localhost:8000/api/auth/me -H "Authorization: Bearer <token>"
# → 200 + {"id":"...","email":"test@test.com","name":"Test"}
```

---

## Phase 3: Organizations + Employees CRUD

### Goal
Full CRUD for orgs and employees. Bot token encryption. Channel assignments. Authorization: users can only access their own orgs.

### 3a. Organizations Module

**`app/organizations/schemas.py`**:
- `CreateOrganizationRequest(name)`
- `UpdateOrganizationRequest(name)`
- `OrganizationResponse(id, name, owner_id, cognee_tenant_id, cognee_dataset_name, employee_count, created_at)`

**`app/organizations/service.py`**:
- `create_org(db, user_id, data) → Organization`
- `get_org(db, org_id, user_id) → Organization | None` (ownership check)
- `list_orgs(db, user_id) → list[Organization]`
- `update_org(db, org_id, user_id, data) → Organization`
- `delete_org(db, org_id, user_id) → bool`

**`app/organizations/router.py`**:
| Method | Path | Handler | Auth |
|--------|------|---------|------|
| POST | `/api/organizations` | create | ✅ |
| GET | `/api/organizations` | list | ✅ |
| GET | `/api/organizations/{org_id}` | get | ✅ |
| PATCH | `/api/organizations/{org_id}` | update | ✅ |
| DELETE | `/api/organizations/{org_id}` | delete | ✅ |

Router: `prefix="/api/organizations"`, `tags=["organizations"]`.

### 3b. Employees Module

**`app/employees/schemas.py`**:
- `CreateEmployeeRequest(name, role, personality?, specialization?, duties?, memory_policy?)`
- `UpdateEmployeeRequest(name?, role?, personality?, specialization?, duties?, memory_policy?, status?)`
- `EmployeeResponse(id, org_id, name, role, personality, specialization, duties, memory_policy, mcp_connections, status, cognee_user_id, cognee_dataset_name, channel_assignments, created_at)`

**`app/employees/service.py`**:
- `create_employee(db, org_id, user_id, data) → Employee`
- `get_employee(db, org_id, emp_id, user_id) → Employee | None`
- `list_employees(db, org_id, user_id) → list[Employee]`
- `update_employee(db, org_id, emp_id, user_id, data) → Employee`
- `delete_employee(db, org_id, emp_id, user_id) → bool`
- `store_discord_token(db, org_id, emp_id, user_id, token) → None` (encrypts token)
- `activate/deactivate(db, org_id, emp_id, user_id) → Employee`

**`app/employees/router.py`**:
| Method | Path | Auth |
|--------|------|------|
| POST | `/api/organizations/{org_id}/employees` | ✅ |
| GET | `/api/organizations/{org_id}/employees` | ✅ |
| GET | `/api/organizations/{org_id}/employees/{emp_id}` | ✅ |
| PATCH | `/api/organizations/{org_id}/employees/{emp_id}` | ✅ |
| DELETE | `/api/organizations/{org_id}/employees/{emp_id}` | ✅ |
| PUT | `/api/organizations/{org_id}/employees/{emp_id}/discord` | ✅ |
| PUT | `/api/organizations/{org_id}/employees/{emp_id}/status` | ✅ |

Router: `prefix="/api/organizations/{org_id}/employees"`, `tags=["employees"]`.

### 3c. Channel Assignments (sub-route under employees)

**`app/channel_assignments/schemas.py`**:
- `CreateChannelAssignmentRequest(platform: "discord"|"slack", channel_id, channel_name)`
- `ChannelAssignmentResponse(id, platform, channel_id, channel_name)`

**`app/channel_assignments/router.py`**:
| Method | Path | Auth |
|--------|------|------|
| POST | `/api/organizations/{org_id}/employees/{emp_id}/channel-assignments` | ✅ |
| DELETE | `/api/organizations/{org_id}/employees/{emp_id}/channel-assignments/{ca_id}` | ✅ |

Router: `prefix="/api/organizations/{org_id}/employees/{emp_id}/channel-assignments"`, `tags=["channel-assignments"]`.

### 3d. Documents Module (file metadata only, no Cognee yet)

**`app/documents/schemas.py`**:
- `DocumentResponse(id, filename, content_type, size_bytes, status, uploaded_at)`

**`app/documents/router.py`**:
| Method | Path | Auth |
|--------|------|------|
| POST | `/api/documents/upload` | ✅ |
| GET | `/api/documents` | ✅ |
| DELETE | `/api/documents/{doc_id}` | ✅ |

Router: `prefix="/api/documents"`, `tags=["documents"]`.

### 3e. Register all routers in `app/main.py`

```python
from app.auth.router import router as auth_router
from app.organizations.router import router as org_router
from app.employees.router import router as emp_router
from app.channel_assignments.router import router as ca_router
from app.documents.router import router as doc_router

app.include_router(auth_router)
app.include_router(org_router)
app.include_router(emp_router)
app.include_router(ca_router)
app.include_router(doc_router)
```

### Verification
```bash
# Create org
curl -X POST localhost:8000/api/organizations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Acme Corp"}'

# Create employee
curl -X POST localhost:8000/api/organizations/$ORG_ID/employees \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Aria","role":"PM","specialization":"hr_specialist"}'

# Add Discord token (encrypted at rest)
curl -X PUT localhost:8000/api/organizations/$ORG_ID/employees/$EMP_ID/discord \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"token":"discord-bot-token-here"}'

# Activate
curl -X PUT localhost:8000/api/organizations/$ORG_ID/employees/$EMP_ID/status \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status":"active"}'

# Verify OpenAPI spec
uv run python scripts/export_openapi.py
# Open api.json → all endpoints present

# Verify Orval generation
cd ../../packages/api-client && bun run generate
# → No errors, typed client generated
```

---

## Summary — Files to Write Per Phase

### Phase 1 (8 files with real content)
- `app/core/config.py` — expand
- `app/core/database.py` — engine + Base + get_db
- `app/auth/models.py` — User
- `app/organizations/models.py` — Organization
- `app/employees/models.py` — Employee
- `app/channel_assignments/models.py` — ChannelAssignment
- `app/documents/models.py` — Document
- `alembic/env.py` — wire target_metadata
- (+ `alembic.ini` if missing)
- (+ `pyproject.toml` — add deps)

### Phase 2 (4 files)
- `app/core/security.py` — hash/verify, JWT, AES encrypt/decrypt
- `app/core/dependencies.py` — get_current_user
- `app/auth/schemas.py`
- `app/auth/service.py`
- `app/auth/router.py`
- `app/main.py` — register auth router

### Phase 3 (10+ files)
- `app/organizations/schemas.py`, `service.py`, `router.py`
- `app/employees/schemas.py`, `service.py`, `router.py`
- `app/channel_assignments/schemas.py`, `router.py`
- `app/documents/schemas.py`, `router.py`
- `app/main.py` — register all routers
