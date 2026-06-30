# Work Log — What's Been Done

## Phase 1: Database Foundation ✅

**Completed**: 2026-06-30

### Files created/modified

| File | What |
|------|------|
| `app/core/config.py` | All settings: database_url, JWT secret/algorithm/expiry, AES encryption key, OpenRouter API key/URL, Cognee LLM/embedding config |
| `app/core/database.py` | Async SQLAlchemy engine (asyncpg), `async_session_factory`, `Base` declarative base, `get_db()` dependency |
| `app/auth/models.py` | `User` — id (UUID PK), email (unique, indexed), password_hash, name, is_active, created_at, updated_at |
| `app/organizations/models.py` | `Organization` — id (UUID PK), owner_id (FK→users), name, 6 Cognee ID columns (all nullable), created_at. Relationships: owner, employees, documents |
| `app/employees/models.py` | `Employee` — id (UUID PK), org_id (FK→organizations, indexed), name, role, personality (JSONB), specialization, duties (JSONB), discord_token_enc (Text), slack_token_enc (Text), mcp_connections (JSONB), memory_policy (JSONB), 4 Cognee ID columns (all nullable), status, created_at, updated_at. Relationships: organization, channel_assignments, documents |
| `app/channel_assignments/models.py` | `ChannelAssignment` — id (UUID PK), employee_id (FK→employees, indexed), platform, channel_id, channel_name. Relationship: employee |
| `app/documents/models.py` | `Document` — id (UUID PK), org_id (FK→organizations), employee_id (FK→employees, nullable), filename, content_type, size_bytes, storage_path, cognee_document_id, status, uploaded_at. Relationships: organization, employee |
| `alembic/env.py` | Wired to `Base.metadata` + `settings.database_url`. Imports all model modules so autogenerate detects them |
| `alembic/versions/3b3f34b263c7_initial_schema.py` | Clean initial migration: drops old TS-schema tables with CASCADE, creates 5 new tables in FK order |
| `pyproject.toml` | Added deps: `asyncpg`, `bcrypt`, `python-jose[cryptography]`, `cryptography` |

### Verified

- [x] All 5 models import and register with `Base.metadata`
- [x] Alembic autogenerate produces clean migration
- [x] Migration applies successfully — 5 tables in PostgreSQL
- [x] User, Organization, Employee, ChannelAssignment, Document all insert correctly
- [x] JSONB columns (personality, duties, memory_policy, mcp_connections) round-trip
- [x] Relationships resolve: `User.organizations`, `Organization.employees`
- [x] Cognee ID columns are all nullable and default to NULL
- [x] UUID PKs generated via `gen_random_uuid()`
- [x] Foreign key constraints enforced
- [x] Indexes on `users.email` (unique), `employees.org_id`, `channel_assignments.employee_id`

### Design decisions

- **Domain-driven structure**: Each domain (auth, organizations, employees, etc.) owns its models, schemas, router, and service in one directory
- **SQLAlchemy 2.0 Mapped syntax**: Using `Mapped[]` + `mapped_column()` throughout
- **UUID primary keys**: All tables use UUID with `gen_random_uuid()` server default — no auto-increment integers
- **Cognee columns day 1**: All Cognee ID columns exist from the start as nullable — no migration needed later when Cognee is wired
- **JSONB for flexible fields**: personality, duties, memory_policy, mcp_connections use PostgreSQL JSONB
- **Encrypted tokens**: discord_token_enc and slack_token_enc are Text (not String) for AES-256-GCM ciphertext
- **Clean-slate migration**: Old TypeScript-schema tables dropped with CASCADE before creating new tables

---

## Phase 2: Auth ✅

**Completed**: 2026-06-30

### Files created/modified

| File | What |
|------|------|
| `app/core/security.py` | `hash_password()` / `verify_password()` (bcrypt), `create_access_token()` / `decode_access_token()` (JWT HS256), `encrypt_token()` / `decrypt_token()` (AES-256-GCM for bot tokens) |
| `app/core/dependencies.py` | `get_current_user` — FastAPI dependency: extracts `Bearer <token>`, decodes JWT, fetches User, raises 401 |
| `app/auth/schemas.py` | `RegisterRequest`, `LoginRequest`, `TokenResponse`, `UserResponse` (Pydantic v2, `from_attributes=True`) |
| `app/auth/service.py` | `register()` — checks duplicate email, hashes password, creates user. `authenticate()` — finds by email, verifies password. `get_user_by_id()`, `make_token_response()` |
| `app/auth/router.py` | `POST /api/auth/register` (201), `POST /api/auth/login` (200), `GET /api/auth/me` (200). Tags: `auth` |
| `app/main.py` | Registers auth router. Imports all model modules before routers to resolve SQLAlchemy relationship strings |
| `pyproject.toml` | Replaced `passlib[bcrypt]` with `bcrypt>=4.0.0` (passlib incompatible with bcrypt 5.x) |

### API Contract

| Method | Path | Request | Response | Errors |
|--------|------|---------|----------|--------|
| POST | `/api/auth/register` | `{email, password, name}` | `{access_token, token_type: "bearer"}` | 409 duplicate |
| POST | `/api/auth/login` | `{email, password}` | `{access_token, token_type: "bearer"}` | 401 bad creds |
| GET | `/api/auth/me` | `Authorization: Bearer <token>` | `{id, email, name, is_active, created_at}` | 401 invalid/missing |

### Verified

- [x] bcrypt password hashing: `$2b$12$...` format, correct password verifies, wrong password rejected
- [x] JWT: HS256, `sub` claim = user UUID, `exp` claim = configurable expiry
- [x] Register: creates user with hashed password, returns valid JWT
- [x] Login: correct creds → JWT, wrong creds → 401
- [x] Duplicate email: returns 409
- [x] `/me`: returns user when token valid, 401 when missing/invalid
- [x] OpenAPI spec exports with all 3 auth paths

### Design decisions

- **bcrypt directly**: No passlib abstraction — bcrypt 5.x is incompatible with passlib, and bcrypt's API is simple enough
- **Single access token**: 1-hour expiry, no refresh token complexity in v1
- **`get_db` in `database.py`**: Not in `dependencies.py` — it's a database utility, not an auth concern
- **Model imports in `main.py`**: All model modules imported before router registration (avoids SQLAlchemy string resolution errors)
- **HTTPBearer scheme**: Standard `Authorization: Bearer <token>` header, no custom middleware needed
