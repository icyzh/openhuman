# Deployment Readiness Implementation Plan

This plan outlines the architecture, configuration, and workflows required to transition the OpenHuman monorepo from a local development setup to a production-grade, deployment-ready state.

---

## 1. Production Architecture Overview

The OpenHuman application consists of a decoupled frontend and backend. In production, these should be hosted in environments optimized for their respective workloads:

```mermaid
graph TD
    Client[Web Browser / Client]
    
    subgraph Frontend Environment (e.g., Vercel / CDN)
        Web[Next.js Frontend]
    end
    
    subgraph Backend Environment (e.g., Railway / VPS / Docker Engine)
        API[FastAPI Backend / App Engine]
        DB[(PostgreSQL + pgvector)]
        Cognee[(Cognee Memory / SQLite + Kuzu)]
        Storage[(Local / S3 Document Storage)]
    end
    
    Client -->|HTTPS / Next.js SSR| Web
    Client -->|REST API Requests / WS| API
    Web -->|Server-Side Fetch / SSR| API
    API -->|Async Connections| DB
    API -->|SQLite Graph DB / Local Disk| Cognee
    API -->|Read/Write Uploads| Storage
```

### Hosting Strategy Recommendation
1.  **Next.js Frontend (`apps/web`)**: Deploy to **Vercel** or a similar serverless platform. This yields excellent globally distributed SSR performance, automatic preview environments, and instant static file serving.
2.  **FastAPI Backend & Services (`apps/api`)**: Deploy to a container hosting service like **Railway** or a **VPS running Docker**. This allows persistent state handling (needed by Cognee SQLite/Kuzu graph databases and local file uploads) and long-running background tasks.
3.  **Database**: Managed PostgreSQL instance (supporting **pgvector**), or containerized PostgreSQL in self-hosted setups.

---

## 2. Done: Dockerization Improvements

We have successfully implemented the necessary configurations to support production Docker containerization:

### A. Next.js Standalone Mode (`apps/web/next.config.ts`)
Next.js has been configured to build in `standalone` mode.
*   **Why**: Standalone mode extracts only the required dependencies (`node_modules` subset, Next.js server files, and app code) into a single `.next/standalone` folder. This reduces the Docker image size from ~1.5GB to under 200MB.

### B. Production Multi-Stage Frontend Dockerfile (`apps/web/Dockerfile`)
We created a multi-stage `Dockerfile` tailored for Next.js and Turborepo using **Bun**:
1.  **Prune Stage**: Uses Turborepo's `prune` feature to extract only `@openhuman/web` and its workspace dependencies (such as `@repo/api-client`), ignoring other unrelated packages.
2.  **Install & Build Stage**: Installs the exact dependency tree using `bun install --frozen-lockfile` and runs the production build, outputting the standalone server bundle.
3.  **Runner Stage**: Employs a slim Alpine image, sets up a non-root system user (`nextjs:nodejs`), and runs `node apps/web/server.js`.

### C. Self-Hosted Orchestration (`docker-compose.yml`)
A root-level `docker-compose.yml` has been added. It wires up:
1.  `postgres` using `pgvector/pgvector:16-pgdg`.
2.  `backend` (FastAPI) built from `apps/api/Dockerfile`, depending on PostgreSQL being healthy.
3.  `frontend` (Next.js) built using the root monorepo context, depending on the Backend API being healthy.
4.  Healthcheck steps on the database and API to enforce safe initialization ordering.

---

## 3. Production Environment Variables Reference

Ensure these variables are configured correctly in the deployment environments:

### Backend API Variables (`apps/api`)

| Variable | Recommended Production Value | Description |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `production` | Enables strict production settings and optimizations. |
| `API_HOST` | `0.0.0.0` | IP to bind the server to. |
| `API_PORT` | `8000` | Port to expose the FastAPI server. |
| `DATABASE_URL` | `postgresql+asyncpg://<user>:<password>@<host>:<port>/<db>` | Connection string for Postgres (must support pgvector). |
| `JWT_SECRET_KEY` | *[Secure Random String]* | Key for signing JWTs. Must be $\ge$ 32 chars. |
| `ENCRYPTION_KEY` | *[Secure 64-character Hex]* | AES-256 key for storing Discord/Slack credentials. |
| `OPENAI_API_KEY` | `sk-proj-...` | API Key for the AI core engine. |
| `COGNEE_DATA_DIR` | `/app/cognee_data` | Persistent path for Cognee memory vector files. |
| `STORAGE_BACKEND` | `s3` (or `local` with persistent mounts) | Selects upload backend (`s3` is recommended for serverless/distributed setups). |
| `S3_BUCKET_NAME` | `openhuman-uploads` | AWS S3 or MinIO bucket name. |
| `GATEWAY_ENABLED` | `true` | Set to `true` if you wish to run the Slack/Discord bots. |

### Frontend Variables (`apps/web`)

| Variable | Recommended Production Value | Description |
| :--- | :--- | :--- |
| `NEXT_PUBLIC_API_URL` | `https://api.yourdomain.com` | Publicly reachable domain of the FastAPI backend. Used by client browser requests. |
| `PORT` | `3000` | Internally mapped port inside the container. |

> [!IMPORTANT]  
> Since Next.js bakes client-side `NEXT_PUBLIC_` environment variables into the static bundle at **build time**, `NEXT_PUBLIC_API_URL` must be passed as a build argument (`ARG`) when compiling the Docker image.

---

## 4. Production Deployment Guidelines

### Option A: Cloud Deployment (Vercel + Railway)

#### Step 1: Deploy PostgreSQL + API Backend on Railway
1.  Create a new project on Railway.
2.  Add a **Postgres** database service. Note: Make sure it supports `pgvector`.
3.  Deploy the backend from GitHub. Set the root directory to `apps/api`.
4.  Configure the environment variables listed in the Reference table. Set `DATABASE_URL` to point to your Postgres database.
5.  Set up a persistent volume mount on `/app/cognee_data` to ensure Cognee's graphs are saved.
6.  Generate a public domain for the Backend (e.g. `https://api.example.com`).

#### Step 2: Deploy Next.js Frontend on Vercel
1.  Import your GitHub repository into Vercel.
2.  Choose **Next.js** as the framework template.
3.  In the project configuration, set **Root Directory** to `apps/web`.
4.  Configure **Build Command** to: `bun run build`. Vercel automatically understands Turborepo workspace configurations.
5.  Add the environment variable `NEXT_PUBLIC_API_URL` pointing to the public URL of the backend (e.g., `https://api.example.com`).
6.  Trigger the deploy.

---

### Option B: Self-Hosted Stack (Docker Compose)
To launch the entire stack on a single server:
1.  Clone the repository on the target server.
2.  Create a `.env` file in the root directory to hold secrets (like `OPENAI_API_KEY`, `JWT_SECRET_KEY`, and `ENCRYPTION_KEY`).
3.  Build and run the containers in detached mode:
    ```bash
    docker compose up -d --build
    ```
4.  Verify that all services started correctly:
    ```bash
    docker compose ps
    ```
5.  Access the dashboard at `http://localhost:3000` and Swagger docs at `http://localhost:8000/docs`.

---

## 5. Database Migration & Maintenance

Applying database schemas in production must be done carefully to avoid downtime:

### Run Migrations on Startup (Docker Compose/VPS)
For single-instance VPS or Docker deployments, you can run migrations before the backend starts by modifying the Docker CMD or adding a startup script:
```bash
# Run migrations, then start uvicorn
uv run alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Run Migrations via CI/CD / Release Phase (Railway/Heroku/Vercel)
If deploying to a platform supporting release hooks:
1.  Configure a **Pre-Deploy / Release Command**:
    ```bash
    uv run alembic upgrade head
    ```
2.  This command runs in a temporary container before the new container starts routing traffic, ensuring schema safety.

---

## 6. Critical Production Considerations

> [!WARNING]  
> **Cognee Database Locks**: Cognee uses SQLite and Kuzu under the hood, which creates local files on disk. SQLite can experience `database is locked` errors if multiple processes or threads try to write concurrently.
> *   *Mitigation*: Ensure the backend container runs with a **single worker instance** (do not scale backend containers horizontally beyond 1 replica if they share the same SQLite database volume, and limit Uvicorn to a single worker process in high-write environments).

> [!NOTE]  
> **CORS Configurations**: In production, secure your API endpoints by updating the CORS origins. In `apps/api/app/main.py` or `.env`, set `CORS_ORIGINS` to target only your exact frontend domain (e.g. `["https://www.yourdomain.com"]`), rather than `*` or localhosts.
