# Comprehensive Vercel & Cloud Deployment Guide

This guide describes how to deploy the entire OpenHuman monorepo (Next.js frontend + FastAPI backend + integrations) to production, including all required database setups, storage backends, Slack OAuth configs, and third-party MCP connector API keys.

---

## Prerequisites & Accounts Required

To enable all features of the OpenHuman platform, you will need:
1.  **Vercel** — For frontend and serverless API hosting.
2.  **GitHub** — For source control and automated CI/CD.
3.  **Supabase** (or Neon) — For managed Postgres + pgvector.
4.  **Neo4j Aura** — For hosting the Cognee knowledge graph.
5.  **OpenAI** — Developer account for model endpoints.
6.  **Slack Developer Portal** — For Slack bot integrations.
7.  **Cloudflare R2** (or AWS S3) — For document file uploads.
8.  **OAuth Apps** — Credentials from Notion, GitHub, and Vercel (optional, for MCP connectors).

---

## Step 1: Set Up Cloud Infrastructure

### A. Managed PostgreSQL (Supabase)
1.  Create a project on Supabase.
2.  Open the **SQL Editor** and run:
    ```sql
    CREATE EXTENSION IF NOT EXISTS vector;
    ```
3.  Copy the connection string (URI) from **Project Settings > Database**. Choose the pooler mode (port `5432` or `6543`).

### B. Graph Database (Neo4j Aura)
1.  Create a free database instance on Neo4j Aura.
2.  Save the **Connection URL** (`neo4j+s://...`), **Username** (`neo4j`), and **Password**.

### C. Cloud Storage Bucket (Cloudflare R2 or AWS S3)
To store documents uploaded by users:
1.  Create a bucket named `openhuman-uploads` on AWS S3 or Cloudflare R2.
2.  Generate an **Access Key ID** and **Secret Access Key** with read/write access to the bucket.
3.  Save the S3 API endpoint URL (for Cloudflare R2, it looks like `https://<account-id>.r2.cloudflarestorage.com`).

---

## Step 2: Deploy the Backend API (`apps/api`) to Vercel

1.  In Vercel, click **Add New > Project**, and import your GitHub repository.
2.  Set the **Root Directory** to `apps/api`. Set **Framework Preset** to **Other** (Vercel will build it as a Python project).
3.  Configure **every single API key** in the Vercel **Environment Variables** panel:

### 1. Core Security & Databases
| Key | Example Value | Description |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `production` | Triggers production constraints. |
| `DATABASE_URL` | `postgresql+asyncpg://<your-supabase-user>:<your-supabase-password>@<your-supabase-host>:6543/postgres` | Connection URI to Supabase Postgres. |
| `RELATIONAL_DATABASE_URL` | `postgresql://<your-supabase-user>:<your-supabase-password>@<your-supabase-host>:6543/postgres` | Sync connection string for Cognee metadata. |
| `JWT_SECRET_KEY` | `your-long-secure-random-jwt-key` | Token signing secret ($\ge$ 32 chars). |
| `ENCRYPTION_KEY` | `your-64-character-hex-aes-key` | Key for encrypting user Discord/Slack tokens in DB. |

### 2. Cognee Graph & Vector Engine
| Key | Example Value | Description |
| :--- | :--- | :--- |
| `COGNEE_DATA_DIR` | `/tmp/cognee_data` | Temp directory for Cognee local runtime files. |
| `GRAPH_DATABASE_PROVIDER` | `neo4j` | Explicitly targets Neo4j Aura. |
| `GRAPH_DATABASE_URL` | `neo4j+s://<your-neo4j-id>.databases.neo4j.io` | Your Neo4j Aura endpoint. |
| `GRAPH_DATABASE_NAME` | `<your-neo4j-id>` | Aura database name. |
| `GRAPH_DATABASE_USERNAME` | `<your-neo4j-id>` | Aura username. |
| `GRAPH_DATABASE_PASSWORD` | `<your-neo4j-password>` | Aura password. |
| `VECTOR_DB_PROVIDER` | `pgvector` | Explicitly targets PostgreSQL vector search. |
| `VECTOR_DB_HOST` | `<your-supabase-host>` | Supabase host. |
| `VECTOR_DB_PORT` | `6543` | Postgres port. |
| `VECTOR_DB_NAME` | `postgres` | Database name. |
| `VECTOR_DB_USERNAME` | `<your-supabase-user>` | Database user. |
| `VECTOR_DB_PASSWORD` | `<your-supabase-password>` | Database password. |

### 3. AI Providers
| Key | Example Value | Description |
| :--- | :--- | :--- |
| `OPENAI_API_KEY` | `sk-proj-...` | Used by LangGraph agent and Cognee indexer. |
| `OPENAI_MODEL` | `gpt-4o-mini` | Main LLM model for agents. |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Leave empty or set to custom API gateway. |
| `COGNEE_LLM_PROVIDER` | `openai` | LLM provider for Cognee. |
| `COGNEE_LLM_API_KEY` | `sk-proj-...` | If different from standard OpenAI key. |
| `COGNEE_EMBEDDING_PROVIDER` | `openai` | Vector embedding provider. |
| `COGNEE_EMBEDDING_MODEL` | `openai/text-embedding-3-small`| Model for memory generation. |

### 4. S3 Document Uploads
| Key | Example Value | Description |
| :--- | :--- | :--- |
| `STORAGE_BACKEND` | `s3` | Bypasses local uploads directory. |
| `S3_ENDPOINT_URL` | `https://...` | R2/S3 API Endpoint (leave blank for native AWS S3). |
| `S3_ACCESS_KEY_ID` | `your-access-key` | Access key credentials. |
| `S3_SECRET_ACCESS_KEY` | `your-secret-key` | Secret key credentials. |
| `S3_BUCKET_NAME` | `openhuman-uploads` | S3 bucket name. |
| `S3_REGION` | `auto` | Bucket region. |

### 5. Slack Integration & Gateway Configs
| Key | Example Value | Description |
| :--- | :--- | :--- |
| `GATEWAY_ENABLED` | `false` | Must be `false` on Vercel (bots won't run). |
| `SLACK_IDENTITY_MODE` | `per_employee` | Controls Slack workspace behavior. |
| `SLACK_CLIENT_ID` | `your-slack-client-id` | Slack app client ID. |
| `SLACK_CLIENT_SECRET` | `your-slack-client-secret` | Slack app client secret. |
| `SLACK_OAUTH_REDIRECT_URI` | `https://openhuman-api.vercel.app/api/slack/oauth/callback`| Your public backend OAuth redirect path. |
| `SLACK_CONFIG_TOKEN` | `xoxe-config-token` | Slack API manifest automation. |
| `SLACK_CONFIG_REFRESH_TOKEN` | `refresh-token` | Refreshes the manifest token. |

### 6. MCP Connector Credentials (OAuth Mode)
Required to authorize AI agents with third-party productivity tools:
| Key | Example Value | Description |
| :--- | :--- | :--- |
| `NOTION_CLIENT_ID` | `notion-client-id` | Notion integration client ID. |
| `NOTION_CLIENT_SECRET` | `notion-client-secret` | Notion integration client secret. |
| `GITHUB_CLIENT_ID` | `github-client-id` | GitHub OAuth App client ID. |
| `GITHUB_CLIENT_SECRET` | `github-client-secret` | GitHub OAuth App client secret. |
| `VERCEL_CLIENT_ID` | `vercel-client-id` | Vercel Integration client ID. |
| `VERCEL_CLIENT_SECRET` | `vercel-client-secret` | Vercel Integration client secret. |
| `MCP_OAUTH_REDIRECT_URI` | `https://openhuman-api.vercel.app/api/mcp/oauth/callback`| The endpoint matching your public API. |

4.  Click **Deploy**. Copy your API production URL: `https://openhuman-api.vercel.app`.

---

## Step 3: Run Database and Cognee Schema Migrations

Execute these migrations from your local development machine targeting your remote database before building the frontend.

From your local terminal inside `apps/api/`:

### A. Postgres SQL Migrations (Alembic)
```bash
DATABASE_URL="postgresql+asyncpg://<your-supabase-user>:<your-supabase-password>@<your-supabase-host>:6543/postgres" uv run alembic upgrade head
```

### B. Cognee Memory Graph & Table Migrations
```bash
GRAPH_DATABASE_PROVIDER="neo4j" \
GRAPH_DATABASE_URL="neo4j+s://<your-neo4j-id>.databases.neo4j.io" \
GRAPH_DATABASE_USERNAME="<your-neo4j-id>" \
GRAPH_DATABASE_PASSWORD="<your-neo4j-password>" \
RELATIONAL_DATABASE_URL="postgresql://<your-supabase-user>:<your-supabase-password>@<your-supabase-host>:6543/postgres" \
VECTOR_DB_PROVIDER="pgvector" \
VECTOR_DB_HOST="<your-supabase-host>" \
VECTOR_DB_NAME="postgres" \
VECTOR_DB_USERNAME="<your-supabase-user>" \
VECTOR_DB_PASSWORD="<your-supabase-password>" \
uv run python -c "import cognee; import asyncio; asyncio.run(cognee.prune_data()); asyncio.run(cognee.run_migrations())"
```

---

## Step 4: Deploy the Frontend (`apps/web`) to Vercel

1.  In Vercel, import the same repository again for the frontend app.
2.  Set the **Root Directory** to `apps/web`.
3.  Set the **Framework Preset** to **Next.js**.
4.  Add the following **Environment Variable**:
    *   `NEXT_PUBLIC_API_URL`: `https://openhuman-api.vercel.app`
5.  Click **Deploy**.
