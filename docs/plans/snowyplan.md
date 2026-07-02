# Snow's Plan — Final Integration & Cleanup

> **Created:** 2026-07-02
> **Context:** Post-ai-v0.2 merge. Backend Cognee flow is wired. Frontend setup/onboard works. Gaps remain in the document→Cognee pipeline, org website scraping, and cleanup.

---

## Current State Audit

### ✅ Working

| Component | Detail |
|-----------|--------|
| Cognee bootstrap | `app/core/cognee.py` — env vars set before any `import cognee` |
| Cognee startup | `init_cognee()` called in FastAPI lifespan (runs migrations) |
| Admin Cognee user | `get_or_create_admin()` — lazy, persisted in Cognee's SQLite |
| Org create | Creates tenant → system user → dataset → seeds org info → persists Cognee IDs on org row |
| Employee create | Creates employee user → dataset → seeds profile → persists Cognee IDs |
| Document upload (text) | Storage backend + text ingest to **org** Cognee dataset |
| Org delete | Forgets all datasets (org + all employees) before CASCADE |
| Employee delete | Forgets employee dataset before CASCADE |
| Employee update | Re-seeds Cognee profile on identity field changes |
| Slack bot → agent | `employee_id` + `db` passed in `RunnableConfig` → memory tools work |
| Slack auto-ingest | Incoming messages ingested to org Cognee dataset |
| `search_memory` tool | Searches employee + org datasets via `recall()` |
| `ingest_memory` tool | Writes to employee dataset via `remember()` |
| Agent graph | `get_graph_for_employee()` — per-employee tool resolution, cached graphs |
| Frontend setup wizard | Create org → upload docs |
| Frontend onboard | Create employee → upload docs |
| Frontend detail page | Edit fields, manage docs, Slack OAuth, status |

### 🔴 Gaps

| # | Gap | Severity |
|---|-----|----------|
| 1 | **Employee documents go to org dataset, not employee dataset** — `documents/service.py` always ingests into `org.cognee_dataset_name` even when `employee_id` is provided | High |
| 2 | **Document delete doesn't remove from Cognee** — `delete_document()` only removes from storage + DB, stale knowledge persists in graph | Medium |
| 3 | **Only text files ingested into Cognee** — PDFs, docx, xlsx, pptx etc. are stored in bucket but never reach Cognee memory. Cognee supports all these formats natively. Slack attachments (PDFs etc.) also need handling. | High |
| 4 | **No organization website scraping** — Org has no `website_url` field. ScrapeGraphAI integration (https://docs.cognee.ai/integrations/scrapegraphai-integration) should crawl the org's website and add to company dataset during onboarding. | Medium |
| 5 | **Discord code dormant but present** — Discord code is half-built and should be left in place but must not cause runtime errors when no Discord tokens exist | Low |
| 6 | **Unused/legacy endpoints** — Code audit needed to identify dead routes and stale code | Low |

---

## Phase 1: Fix Document → Cognee Pipeline (Gaps 1, 2, 3)

### 1a. Route employee documents to the correct Cognee dataset

**File:** `apps/api/app/documents/service.py`

**Change:** In `save_document()`, when `employee_id` is provided:
1. Look up the employee's Cognee info (`cognee_user_id`, `cognee_dataset_name`, `cognee_dataset_id`)
2. Ingest into the **employee's** dataset instead of the org's dataset
3. If employee has no Cognee provisioning yet, fall back to org dataset with a warning log

**Logic:**

```
if employee_id is provided:
    emp = await db.get(Employee, employee_id)
    if emp and emp.cognee_dataset_name and emp.cognee_user_id:
        target_dataset = emp.cognee_dataset_name
        target_user_id = emp.cognee_user_id
        target_dataset_id = emp.cognee_dataset_id
    else:
        # Fallback to org dataset
        logger.warning("Employee %s has no Cognee provisioning, falling back to org dataset", employee_id)
        target_dataset = org.cognee_dataset_name
        target_user_id = org.cognee_system_user_id
        target_dataset_id = org.cognee_dataset_id
else:
    target_dataset = org.cognee_dataset_name
    target_user_id = org.cognee_system_user_id
    target_dataset_id = org.cognee_dataset_id
```

### 1b. Support all file formats for Cognee ingest

**Problem:** Currently only `text/plain`, `text/markdown`, `text/csv`, `application/json`, `application/xml` are ingested. PDFs, docx, xlsx, pptx etc. are stored in bucket but skipped.

**Cognee's `remember()`** accepts file paths natively — it handles parsing internally. Instead of decoding text ourselves, we should save the file to a temp location (or use the storage backend path) and pass it to Cognee.

**Change:**
1. After saving to storage backend, write the file bytes to a temp file
2. Call `cognee.remember(temp_file_path, dataset_name=..., user=..., dataset_id=..., run_in_background=True)` with the file path
3. Remove the `TEXT_TYPES` whitelist — all files go to Cognee
4. Keep the size limit check (500KB) for now
5. Clean up temp file after Cognee returns

**File:** `apps/api/app/documents/service.py`

**Note:** Cognee's `remember()` data parameter can be:
- A string (raw text)
- A file path (Cognee detects format and parses)
- Binary content

We'll use file paths. The storage backend already has the bytes; we can write to a temp file, pass the path to Cognee, then clean up.

### 1c. Forget on document delete (best-effort note)

**Change in `delete_document()`:**
- Add a comment noting that individual document deletion from Cognee is not supported (Cognee's `forget()` works at the dataset level, not per-document)
- This is an accepted limitation for now — tracked in [[cognee-per-doc-delete-limitation]]

**File:** `apps/api/app/documents/service.py`

---

## Phase 2: Organization Website + ScrapeGraphAI (Gap 4)

### 2a. Add `website_url` to Organization model

**Files to change:**
1. `apps/api/app/organizations/models.py` — add column `website_url: Mapped[str | None]`
2. `apps/api/app/organizations/schemas.py` — add `website_url` to `CreateOrganizationRequest`, `UpdateOrganizationRequest`, `OrganizationResponse`
3. `apps/api/alembic/versions/` — new migration: `ALTER TABLE organizations ADD COLUMN website_url VARCHAR(2048)`

### 2b. Integrate ScrapeGraphAI during org creation

**Dependency:** `cognee-community-tasks-scrapegraph` (add to `pyproject.toml`)

**Env vars needed:** `SGAI_API_KEY` (ScrapeGraphAI API key) — add to `Settings` in `config.py`

**Change in `organizations/service.py` — `create_org()`:**

After Cognee dataset is created and seeded with org info, if `data.website_url` is provided:
1. Import `scrape_and_add` from `cognee_community_tasks_scrapegraph`
2. Call `await scrape_and_add(urls=[data.website_url], user_prompt="Extract the company description, products/services, mission, key features, target audience, and any other relevant business information", dataset_name=f"company-{tenant['id']}")`
3. Best-effort, non-blocking — log but don't fail org creation if scrape fails

### 2c. Re-scrape on website URL update

**Change in `organizations/service.py` — `update_org()`:**

If `website_url` changed:
1. Forget the old scrape (optional — accepted limitation)
2. Re-run `scrape_and_add()` with the new URL

### 2d. Frontend changes

**Files to change:**
1. `apps/web/app/setup/_components/org-setup-form.tsx` — add URL input field
2. `apps/web/app/(dashboard)/organization/page.tsx` — add URL field to org settings
3. `packages/api-client/` — re-generate after schema changes (orval)

---

## Phase 3: Discord Safety Check (Gap 5)

**Goal:** Ensure zero Discord tokens = zero issues. Don't remove Discord code.

**Checklist:**
- [ ] `gateway/manager.py` — verify the refresh loop gracefully handles employees with only `slack_token_enc` (no `discord_token_enc`)
- [ ] `gateway/discord_bot.py` — verify it doesn't import anything that fails at module level
- [ ] `employees/router.py` — Discord token endpoint should remain but return clear errors if Discord is not configured
- [ ] `employees/service.py` — `get_active_employees_with_tokens()` already handles OR condition (discord OR slack) ✅
- [ ] Frontend — `hasDiscord` should gracefully show "Not connected" when no token
- [ ] `test_gateway.py` — Discord tests should be skippable when `DISCORD_TOKEN` env var is unset

---

## Phase 4: Code Cleanup (Gap 6)

### 4a. Audit API endpoints

Identify and flag (don't delete yet — just document):
- Endpoints with no frontend consumer
- Stub/todo endpoints that don't work
- Duplicate or near-duplicate routes

### 4b. Remove dead code

- Unused imports
- Commented-out code blocks
- Debug print statements (replace with `logger.debug`)
- Duplicate doc files (`BigPicture.md` ≈ `LANGGRAPH_WORKFLOW.md` — keep one, redirect the other)

### 4c. Config hygiene

- Audit `Settings` class for unused env vars
- Verify `.env.example` matches actual required vars
- Remove any hardcoded defaults that should be env vars

---

## Phase 5: End-to-End Verification

### 5a. Full flow test

1. User registers → JWT token
2. Create org with website URL → tenant + dataset + ScrapeGraphAI
3. Upload PDFs/docs → bucket + Cognee (all formats)
4. Create employee → Cognee employee user + dataset
5. Upload employee docs → employee Cognee dataset
6. Connect Slack → OAuth → token stored
7. Bot gateway starts → Slack bot online
8. @mention in Slack → agent responds
9. Agent uses `search_memory` → finds org + employee knowledge
10. Agent uses `ingest_memory` → writes to employee dataset
11. Update employee profile → Cognee re-seeded
12. Delete employee → dataset forgotten
13. Delete org → all datasets forgotten

### 5b. Edge cases

- Org created without website URL → no scrape, no error
- Org created by user who already has an org → handled by frontend guard
- Employee created when Cognee is down → employee still created, Cognee fields left null, logged
- Document uploaded when Cognee is down → still stored in bucket, Cognee ingest skipped, logged
- ScrapeGraphAI API key not set → scrape skipped, logged
- No Slack token → bot not started for that employee

---

## Implementation Order

```
Phase 1a (employee doc routing)  ───  1 file, straightforward
Phase 1b (all format support)    ───  1 file, changes ingest logic
Phase 1c (doc delete note)       ───  1 file, comment only
Phase 2a (website_url model)     ───  3 files + migration
Phase 2b (ScrapeGraphAI)         ───  2 files + dep
Phase 2c (re-scrape on update)   ───  1 file
Phase 2d (frontend)              ───  3 files + orval regen
Phase 3  (Discord safety)        ───  read-only audit + minor fixes
Phase 4  (cleanup)               ───  audit + remove
Phase 5  (verification)          ───  manual test run
```

**Suggested order:** 1a → 1b → 1c → 2a → 2b → 2c → 2d → 3 → 4 → 5

Phases 1 and 2 are the critical path. Phase 3 is a safety net. Phase 4 is polish. Phase 5 is the final gate.

---

## Decisions & Accepted Limitations

1. **Per-document Cognee deletion is not supported** — Cognee's `forget()` works at the dataset level. Deleting a single document from the knowledge graph is not currently possible via the Cognee SDK. Documents deleted from storage/DB will leave stale entries in the graph until the entire dataset is forgotten (org/employee deletion). This is acceptable for v1.

2. **ScrapeGraphAI runs in the foreground during org creation** — this blocks the HTTP response for a few seconds but simplifies error handling. Can be moved to background job later.

3. **Discord code left in place** — Discord integration is half-built. We keep all Discord files, columns, and endpoints but ensure nothing breaks when no Discord tokens are configured.

4. **Admin Cognee user stored in Cognee's SQLite** — survives restarts, only lost if `cognee_data/` directory is wiped. Acceptable for now.

5. **Org website scraping is best-effort** — if ScrapeGraphAI is unavailable or the API key is missing, org creation proceeds normally. The scrape is an enrichment, not a requirement.

---

## Files Affected (summary)

| File | Phase | Change |
|------|-------|--------|
| `apps/api/app/documents/service.py` | 1a, 1b, 1c | Employee dataset routing, all-format ingest, delete note |
| `apps/api/app/organizations/models.py` | 2a | Add `website_url` column |
| `apps/api/app/organizations/schemas.py` | 2a | Add `website_url` to request/response schemas |
| `apps/api/app/organizations/service.py` | 2b, 2c | ScrapeGraphAI on create/update |
| `apps/api/app/core/config.py` | 2b | Add `sgai_api_key` setting |
| `apps/api/pyproject.toml` | 2b | Add `cognee-community-tasks-scrapegraph` dep |
| `apps/api/alembic/versions/` | 2a | New migration for `website_url` |
| `apps/web/app/setup/_components/org-setup-form.tsx` | 2d | Add URL input |
| `apps/web/app/(dashboard)/organization/page.tsx` | 2d | Add URL field |
| `packages/api-client/` | 2d | Orval re-generation |
| `apps/api/app/gateway/manager.py` | 3 | Discord safety audit |
| `apps/api/tests/test_gateway.py` | 3 | Discord test skip logic |
| `.env.example` | 2b, 4c | Document `SGAI_API_KEY` |
| `docs/Cognee.md` | — | Update with decisions & accepted limitations |
