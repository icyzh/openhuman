# MCP Integration — Adding a New Connector

A step-by-step guide for adding a new MCP (Model Context Protocol) server to
OpenHuman's agent runtime.  The architecture is **config-driven**: the
`MCPClientManager`, OAuth router, and graph wiring are written once against
the `ConnectorSpec` model — adding connector #*N* means adding **one
declarative module** in `connectors/` and (for OAuth servers) two env vars.

---

## 3-Step Recipe

### Step 1 — Create a connector module

Add a new file under `apps/api/app/agent/tools/mcp/connectors/`, e.g.
`salesforce.py`:

```python
"""Salesforce MCP connector."""

from app.agent.tools.mcp.connectors.spec import ConnectorSpec

SALESFORCE_CONNECTOR = ConnectorSpec(
    slug="salesforce",
    name="Salesforce",
    description="Read/write Salesforce records, reports, and dashboards",
    base_url="https://mcp.salesforce.com/mcp",       # <-- real endpoint
    transport="streamable_http",
    auth_type="oauth2",                               # none | api_key_header | pat_bearer | oauth2
    authorize_url="https://login.salesforce.com/services/oauth2/authorize",
    token_url="https://login.salesforce.com/services/oauth2/token",
    default_scopes=["api", "refresh_token"],
    docs_url="https://help.salesforce.com/s/mcp",
    # ── optional hardening overrides (Phase 4) ─────────────────────
    request_timeout_seconds=45.0,                     # default: 30
    rate_limit_per_minute=120,                        # default: 60
)
```

Key fields (see `ConnectorSpec` in `spec.py` for the full model):

| Field | Required | Notes |
|---|---|---|
| `slug` | **yes** | Unique key — used in DB, URLs, and the `mcp__{slug}__` tool prefix |
| `name` | **yes** | Human-readable label shown in dashboards |
| `description` | **yes** | One sentence — displayed in the connector catalog |
| `base_url` | **yes** | MCP server endpoint (Streamable HTTP or SSE) |
| `auth_type` | **yes** | `none`, `api_key_header`, `pat_bearer`, or `oauth2` |
| `authorize_url` | OAuth only | OAuth 2.x authorization endpoint |
| `token_url` | OAuth only | OAuth token-exchange endpoint |
| `default_scopes` | OAuth only | Scopes requested during OAuth consent |
| `request_timeout_seconds` | no | Per-call timeout (default 30 s) |
| `rate_limit_per_minute` | no | Max calls/min to this server (default 60; 0 = unlimited) |

### Step 2 — Register the connector

Open `apps/api/app/agent/tools/mcp/connectors/registry.py` and add two lines:

```python
from app.agent.tools.mcp.connectors.salesforce import SALESFORCE_CONNECTOR  # 1. import

REGISTRY: dict[str, ConnectorSpec] = {
    "web_search": WEB_SEARCH_CONNECTOR,
    "github":    GITHUB_CONNECTOR,
    "notion":    NOTION_CONNECTOR,
    "vercel":    VERCEL_CONNECTOR,
    "salesforce": SALESFORCE_CONNECTOR,                # 2. register
}
```

Also re-export from `apps/api/app/agent/tools/mcp/connectors/__init__.py` if
you want it importable directly (optional — only `REGISTRY` is required).

That's it for the code.  The management API (`GET /mcp-connectors`),
OAuth flow (`/api/mcp/{slug}/install`), graph compilation, and tool
prefixing all work **automatically** from the registry.

### Step 3 — (OAuth only) Add environment variables

For `auth_type="oauth2"` connectors, the OAuth helper reads client
credentials from `Settings` via the naming convention
`{slug}_client_id` / `{slug}_client_secret`.

Add to `apps/api/app/core/config.py`:

```python
salesforce_client_id: str = ""
salesforce_client_secret: str = ""
```

And populate them in your deployment environment:

```bash
export SALESFORCE_CLIENT_ID="3MVG9..."
export SALESFORCE_CLIENT_SECRET="..."
```

For `auth_type="api_key_header"` or `"pat_bearer"` connectors **no env
vars are needed** — the org admin pastes the key through the management
API, and it is stored AES-256-GCM encrypted in the `mcp_connections` table.

---

## How Everything Wires Together

```
connectors/salesforce.py          ← you write this
        │
        ▼
connectors/registry.py            ← register in REGISTRY dict
        │
        ├──▶ MCPClientManager      ← reads base_url, auth_type, timeout
        │    (client.py)             builds transport config, loads tools,
        │                            wraps with circuit breaker + rate limiter
        │
        ├──▶ app/mcp/router.py     ← lists connector in GET /mcp-connectors
        │                            handles key-paste & OAuth install flows
        │
        ├──▶ app/mcp/oauth.py       ← reads authorize_url, token_url, scopes
        │                            exchanges codes, refreshes tokens
        │
        └──▶ app/agent/router.py   ← resolves MCP tools per employee at
                                     request time, merges with built-in tools
```

---

## Auth Type Quick Reference

| `auth_type` | Credential | Env vars needed | Install flow |
|---|---|---|---|
| `none` | — | none | None (always available) |
| `api_key_header` | API key → `X-API-Key` header | none | Key-paste form |
| `pat_bearer` | PAT → `Authorization: Bearer` | none | Key-paste form |
| `oauth2` | OAuth access + refresh token | `{slug}_client_id`, `{slug}_client_secret` | OAuth redirect dance |

---

## Hardening (Phase 4) — Resilience Defaults

Every connector gets these guards automatically — no extra code needed:

| Guard | Default | Where configured |
|---|---|---|
| **Circuit breaker** | 3 consecutive failures → 30 s cooldown | Module-level in `client.py` |
| **Rate limiter** | 60 calls/min sliding window | `ConnectorSpec.rate_limit_per_minute` |
| **Per-call timeout** | 30 s | `ConnectorSpec.request_timeout_seconds` |
| **Structured logging** | `mcp_server`, `mcp_tool`, `latency_ms`, `success`, `error` | Automatic — `log_mcp_call()` |

When a circuit breaker opens, the connector is skipped at **connect time**
(no tools are loaded for that server) and any in-flight wrapped tools
raise a clear `RuntimeError`.  The agent turn continues with the remaining
healthy connectors.

---

## Testing Your Connector

1. **Smoke-test the registry** — start the API and hit
   `GET /api/organizations/{org}/mcp-connectors`.  Your connector should
   appear in the list with `is_connected: false`.

2. **Add a connection** — use the key-paste or OAuth install endpoint to
   create a row in `mcp_connections`.

3. **Run the agent** — `POST /api/agent/run` with an employee whose
   template includes the new slug in `allowed_mcp_servers`.  Check the
   structured logs for `mcp_server=<slug>` entries.

4. **Verify circuit breaker** — temporarily point `base_url` at a
   non-existent endpoint, run 3 failing agent turns, then check that the
   4th turn logs "Circuit breaker open for '<slug>' — skipping".

---

## Checklist

- [ ] Connector module created in `connectors/`
- [ ] `ConnectorSpec` fields populated (at minimum: slug, name, description, base_url, auth_type)
- [ ] Registered in `REGISTRY` dict
- [ ] OAuth env vars added to `config.py` (OAuth connectors only)
- [ ] Deployed env vars set (OAuth connectors only)
- [ ] Smoke-tested via `GET /mcp-connectors`
- [ ] Agent run confirmed with structured logs
- [ ] Circuit breaker / timeout verified
