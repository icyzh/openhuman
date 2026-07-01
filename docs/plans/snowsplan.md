# Snow's Plan — Final Integration & Cleanup

> **Created:** 2026-07-02 | **Updated:** 2026-07-02 (reviewer feedback incorporated)
> **Reviewers:** code-reviewer, consistency-auditor, qa-expert
> **Context:** Post-ai-v0.2 merge. Backend Cognee flow is wired. Frontend setup/onboard works. Gaps remain in the document→Cognee pipeline, Slack attachment handling, org website scraping, and cleanup.
> **Deep audit:** 2026-07-02 — traced all three critical paths (document upload, Slack→agent, config propagation). No structural breaks found. 5 additional minor gaps identified.

---

## Current State Audit

### ✅ Working (verified by deep trace)

| Component | Detail |
|-----------|--------|
| Cognee bootstrap | `app/core/cognee.py` — `apply_cognee_config()` sets env vars before any `import cognee` |
| Cognee startup | `init_cognee()` (in `app/memory/service.py`) called in FastAPI lifespan, runs Cognee migrations |
| Admin Cognee user | `get_or_create_admin()` (in `app/memory/service.py`) — lazy, persisted in Cognee's SQLite, recreated if wiped |
| Org create | Creates tenant → system user → dataset → seeds org info → persists Cognee IDs on org row |
| Employee create | Creates employee user → dataset → seeds profile → persists Cognee IDs |
| Bucket-first document upload | `StorageBackend` (local or S3/Railway) saves BEFORE Cognee ingest — two-step pattern |
| Org delete | Forgets all datasets (org + all employees) before CASCADE |
| Employee delete | Forgets employee dataset before CASCADE |
| Employee update | Re-seeds Cognee profile on identity field changes |
| Slack bot → agent config | `employee_id` + `db` + `all_tools` passed in `RunnableConfig` — flows through ALL 6 graph nodes → ToolNode → each tool's `ainvoke` |
| Slack auto-ingest (text) | Incoming message text ingested to org Cognee dataset |
| `search_memory` tool | Extracts `config["configurable"]["employee_id"]` + `["db"]`, searches employee + org datasets |
| `ingest_memory` tool | Same extraction, writes to employee dataset with `background=False` (immediate) |
| Agent graph per employee | `get_graph_for_employee()` — template-gated tool filtering, graph cached by tool-name frozenset |
| All 4 templates | Include `search_memory` + `ingest_memory` in `allowed_tools` |
| MCP tool config passthrough | `guarded_ainvoke` preserves and forwards config |
| Frontend setup wizard | Create org → upload docs (Step 1 → Step 2) |
| Frontend onboard | Create employee → upload docs |
| Frontend detail page | Edit fields, manage docs, Slack OAuth, status |
| Error safety | All error paths return safe fallback messages, never leak internals |
| Discord safety | Zero Discord imports in `slack_bot.py`, `gateway/manager.py` handles Slack-only employees |

### 🔴 Gaps

| # | Gap | Severity | Found By |
|---|-----|----------|----------|
| 1 | **Employee documents go to org dataset, not employee dataset** — `documents/service.py` always ingests into `org.cognee_dataset_name` even when `employee_id` is provided | High | Initial audit |
| 2 | **Document delete doesn't remove from Cognee** — `delete_document()` only removes from storage + DB, stale knowledge persists in graph | Medium | Initial audit |
| 3 | **Only text files ingested into Cognee** — PDFs, docx, xlsx, pptx etc. stored in bucket but never reach Cognee. Cognee natively parses all these when given a file path. | High | Initial audit |
| 4 | **No organization website scraping** — Org has no `website_url` field. ScrapeGraphAI integration should crawl org website into company dataset. | Medium | Initial audit |
| 5 | **Slack file attachments completely unhandled** — Bot never inspects `event.files`. When a PDF/image is dropped in Slack, only the text caption is ingested. The file content is lost. | High | Deep trace |
| 6 | **Discord code dormant but present** — Keep as-is, must not cause runtime errors when no Discord tokens exist. Verified safe. | Low | Initial audit |
| 7 | **Unused/legacy endpoints** — Code audit needed to identify dead routes and stale code | Low | Initial audit |
| 8 | **Dead `cognee_document_id` field** — Exists on Document model + migration, never written, never exposed in schema. | Low | Deep trace |
| 9 | **Local storage filename collision** — S3 backend adds UUID prefix (`{uuid8}_{filename}`), local backend stores as `{org_id}/{filename}` without prefix. Same-name files in same org silently overwrite. | Low | Deep trace |
| 10 | **Cognee ingest silently skipped when org not provisioned** — No log, no warning, just skips the `elif` block. | Low | Deep trace |
| 11 | **`status` column never progresses past "uploaded"** — Check constraint allows `uploaded/processing/indexed/failed`. No code updates it after creation. | Low | Deep trace |

### 🔴 Pre-existing test debt (not caused by this plan, but relevant)

| Issue | Detail |
|-------|--------|
| 14 test failures in `tests/` | Stale assertions from guardrail changes, memory stub→real upgrade, BUILT_IN_TOOLS expansion |
| 30 errors in `test/` (integration) | Async fixture config issue — `asyncio_mode = "auto"` not honored in `test/` directory |
| `documents/service.py` | Zero test coverage |
| `organizations/service.py` | Zero test coverage |
| `storage/local.py` + `s3.py` | Zero test coverage |

---

## Phase 0: Test Baseline (before any implementation)

Before touching any production code, stabilize the test suite so we can verify changes don't break things.

### 0a. Fix pre-existing test failures

**14 failures in `tests/`:**
- `test_agent.py`: 2 output guardrail tests assert old behavior ("As an AI..." no longer blocked) → update assertions to match current guardrail patterns
- `test_tools_and_memory.py`: 6 memory tool tests assert stub-like strings → update to match real `recall()`/`remember()` behavior
- `test_tools_and_memory.py`: 2 tool count/ordering tests (BUILT_IN_TOOLS expanded from 6 to 10) → update counts
- `test_gateway.py`: 2 gateway manager start/stop tests (event loop collision) → fix mock
- `test_slack_oauth.py`: 1 redirect URL comparison mismatch → fix assertion
- `test_tools_and_memory.py`: 1 general template test (escalation tools intentionally excluded) → update assertion

### 0b. Fix integration test async fixture issue

The `test/` directory's 30 errors are all `"requested an async fixture 'test_db', with no plugin or hook that handled it"`. The `asyncio_mode = "auto"` in `pyproject.toml` isn't being picked up by the `test/` directory.

**Fix:** Add `pytest.ini` or `conftest.py` in `test/` with `asyncio_mode = "auto"`, or move integration tests under `tests/` where the config works.

### 0c. Write baseline tests for files we're changing

Before modifying `documents/service.py` and related files, write tests that pin current behavior:

**New file:** `apps/api/tests/test_documents.py`
- `test_save_document_without_employee_id` — verify ingests into org dataset
- `test_save_document_with_employee_id` — verify document linked to employee (even though Cognee goes to org — this is current buggy behavior we're about to change)
- `test_save_document_text_file` — verify text content decoded and remembered
- `test_save_document_binary_file` — verify binary files stored but NOT Cognee-ingested (current gap)
- `test_delete_document` — verify removes from storage + DB
- `test_document_status_is_uploaded` — verify status stays "uploaded"

**New file:** `apps/api/tests/test_organizations_service.py`
- `test_create_org` — verify org created, no website_url
- `test_create_org_with_cognee` — verify Cognee IDs persisted
- `test_update_org` — verify fields update
- `test_delete_org` — verify cascade + Cognee cleanup

---

## Phase 1: Fix Document → Cognee Pipeline (Gaps 1, 2, 3, 10, 11)

### 1a. Route employee documents to the correct Cognee dataset

**File:** `apps/api/app/documents/service.py` — `save_document()`

**Change:** Replace the current Cognee ingest block (lines 74-103) which always uses `org.cognee_dataset_name`/`org.cognee_system_user_id`. Instead, determine the target based on whether `employee_id` was provided:

```python
# Determine Cognee target
if employee_id:
    emp = await db.get(Employee, employee_id)
    if emp and emp.cognee_dataset_name and emp.cognee_user_id and emp.cognee_dataset_id:
        target_dataset = emp.cognee_dataset_name
        target_user_id = emp.cognee_user_id
        target_dataset_id = emp.cognee_dataset_id
        target_label = f"employee-{employee_id}"
    else:
        missing = []
        if not emp:
            missing.append("employee not found")
        else:
            if not emp.cognee_user_id: missing.append("cognee_user_id")
            if not emp.cognee_dataset_name: missing.append("cognee_dataset_name")
            if not emp.cognee_dataset_id: missing.append("cognee_dataset_id")
        logger.warning(
            "Employee %s has incomplete Cognee provisioning (%s), falling back to org dataset",
            employee_id, ", ".join(missing) if missing else "unknown",
        )
        target_dataset = org.cognee_dataset_name
        target_user_id = org.cognee_system_user_id
        target_dataset_id = org.cognee_dataset_id
        target_label = f"org-{org.id} (fallback from employee)"
else:
    target_dataset = org.cognee_dataset_name
    target_user_id = org.cognee_system_user_id
    target_dataset_id = org.cognee_dataset_id
    target_label = f"org-{org.id}"
```

**Tests to add/update:**
- Update `test_save_document_with_employee_id` → now asserts Cognee target is employee dataset
- Add `test_save_document_employee_no_cognee` → asserts fallback to org dataset with warning log
- Add `test_save_document_employee_partial_cognee` → e.g. has user but no dataset → fallback

### 1b. Support all file formats for Cognee ingest

**Problem:** Currently only `text/plain`, `text/markdown`, `text/csv`, `application/json`, `application/xml` are ingested via `content.decode("utf-8")`. All other formats are silently skipped.

**Approach:** Cognee's `remember()` accepts file paths and handles parsing internally. Instead of decoding text ourselves, write the uploaded bytes to a temp file and pass the path to `remember()`.

**Important verification (from code-reviewer B2):** Before implementing, verify that Cognee's `remember(data, ...)` actually detects file paths vs. plain text strings. If Cognee treats the path string as literal text content, we need to read the file bytes ourselves and pass them appropriately. The safe fallback is:
- For text formats → decode and pass as string (current behavior, known to work)
- For binary formats → pass temp file path (assumes Cognee handles it)
- Add an integration test that uploads a known PDF and verifies it's searchable

**Change in `save_document()`:** Replace the entire `TEXT_TYPES` / `is_text` block (lines 75-103) with:

```python
# Cognee ingest — all file formats, path-based (best-effort, non-blocking)
_COGNEE_MAX_SIZE = 500_000  # bytes; can be raised later

if not target_dataset or not target_user_id:
    logger.warning(
        "Cognee ingest skipped for doc %s — %s not provisioned",
        doc.filename, target_label,
    )
elif size > _COGNEE_MAX_SIZE:
    logger.debug(
        "Cognee ingest skipped for %s (%d bytes exceeds %d limit)",
        doc.filename, size, _COGNEE_MAX_SIZE,
    )
else:
    try:
        import tempfile, os
        suffix = Path(doc.filename).suffix
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            await remember(
                tmp_path,
                target_dataset,
                target_user_id,
                dataset_id=target_dataset_id,
                background=True,
            )
            doc.status = "indexed"
        except Exception:
            doc.status = "failed"
            raise
        finally:
            os.unlink(tmp_path)
    except Exception:
        logger.exception(
            "Cognee ingest failed for doc %s (%s, %d bytes, target=%s)",
            doc.id, doc.filename, size, target_label,
        )
        doc.status = "failed"

# Persist status update
await db.commit()
```

**Key changes from current code:**
- No `TEXT_TYPES` whitelist — all files go to Cognee
- Uses `tempfile.NamedTemporaryFile` for clean temp file management
- Passes file **path** to `remember()` instead of decoded text
- `doc.status` updated to `"indexed"` on success, `"failed"` on error
- `logger.warning` when Cognee is skipped because org/employee isn't provisioned (Gap 10 fix)
- Temp file cleanup in `finally` block (prevents disk leaks — addresses code-reviewer concern)

**Tests to add:**
- `test_save_document_pdf` → verify stored in bucket, Cognee ingest attempted
- `test_save_document_over_size_limit` → verify stored but Cognee skipped with log
- `test_save_document_cognee_down` → verify stored with status="failed", no crash
- `test_save_document_temp_file_cleanup` → verify no leftover temp files after success AND failure
- `test_save_document_status_progresses_to_indexed` → verify status updated on success
- `test_save_document_no_extension` → verify handled gracefully

### 1c. Forget on document delete (accepted limitation)

**Change in `delete_document()`:**
Add a comment block explaining the limitation. No functional change — Cognee's `forget()` is dataset-level, not per-document.

**File:** `apps/api/app/documents/service.py`

---

## Phase 2: Slack Attachment Handling (Gap 5)

### 2a. Download Slack files → bucket → Cognee

**Problem:** Slack bot never inspects `event.files`. File content is lost.

**⚠️ Security (code-reviewer B1):** Validate `url_private` domain before downloading to prevent SSRF.

**⚠️ Resource (code-reviewer B3):** Check file size before downloading to prevent OOM.

**Slack event structure:**
```json
{
  "files": [{
    "id": "F123ABC", "name": "report.pdf", "mimetype": "application/pdf",
    "url_private": "https://files.slack.com/files-pri/...", "size": 123456
  }]
}
```

**Change in `EmployeeSlackBot._process_slack_message()`:**

After the existing text auto-ingest block (and before `_run_agent`), insert:

```python
# Handle file attachments — download → bucket → Cognee
files = event.get("files", [])
_MAX_SLACK_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

if files and org and org.cognee_dataset_name and org.cognee_system_user_id:
    import tempfile, os, httpx
    from pathlib import Path
    from app.storage import get_storage_backend
    from app.documents.models import Document

    backend = get_storage_backend()

    async with httpx.AsyncClient(timeout=30) as http_client:
        for file_info in files:
            try:
                file_url = file_info.get("url_private")
                if not file_url:
                    continue

                # ── SSRF guard: only download from Slack's CDN ──
                if not file_url.startswith("https://files.slack.com/"):
                    logger.warning(
                        "Rejected non-Slack file URL for employee %s: %s",
                        self.employee_id, file_url,
                    )
                    continue

                file_size = file_info.get("size", 0)
                if file_size > _MAX_SLACK_FILE_SIZE:
                    logger.debug(
                        "Slack file %s (%d bytes) exceeds size limit — skipping",
                        file_info.get("name"), file_size,
                    )
                    continue

                # 1. Download from Slack
                headers = {"Authorization": f"Bearer {self.bot_token}"}
                resp = await http_client.get(file_url, headers=headers)
                resp.raise_for_status()
                file_bytes = resp.content

                # 2. Save to bucket
                storage_path = await backend.save(
                    org_id=emp.org_id,
                    filename=file_info.get("name", "slack_file"),
                    content=file_bytes,
                    content_type=file_info.get("mimetype"),
                )

                # 3. Create Document DB row
                doc = Document(
                    org_id=emp.org_id,
                    employee_id=self.employee_id,
                    filename=file_info.get("name", "slack_file"),
                    content_type=file_info.get("mimetype"),
                    size_bytes=len(file_bytes),
                    storage_path=storage_path,
                    storage_backend=settings.storage_backend,
                    status="uploaded",
                )
                async with async_session_factory() as ingest_session:
                    ingest_session.add(doc)
                    await ingest_session.commit()

                # 4. Cognee ingest via file path
                suffix = Path(doc.filename).suffix
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    tmp.write(file_bytes)
                    tmp_path = tmp.name
                try:
                    await remember(
                        tmp_path,
                        org.cognee_dataset_name,
                        org.cognee_system_user_id,
                        dataset_id=org.cognee_dataset_id,
                        background=True,
                    )
                finally:
                    os.unlink(tmp_path)

            except Exception:
                logger.debug(
                    "Slack file attachment ingest skipped (employee=%s, file=%s)",
                    self.employee_id,
                    file_info.get("name", "unknown"),
                    exc_info=True,
                )
```

**Change in `WorkspaceSlackBot._process_slack_message()`:**

Same logic, but adapted for WorkspaceSlackBot's variable names:
- Uses the **local** `employee_id` variable (resolved by `_resolve_employee()` at the top of `_process_slack_message`), NOT `self.employee_id`
- The `org` and `emp` variables are already available from the existing text auto-ingest block (lines 595-626) — insert the file handling block AFTER that block
- `employee_id` on the Document row = the local `employee_id` variable

**⚠️ Consistency note (code-reviewer S4):** Slack files go to **org dataset** (not employee dataset). This is consistent with the existing Slack text auto-ingest behavior — Slack conversations are organizational knowledge shared across all employees. Dashboard uploads with `employee_id` go to the employee's personal dataset (Phase 1a). This split is intentional.

**Tests to add (in `tests/test_gateway.py`):**
- New test class `TestSlackFileAttachments`:
  - `test_file_attachment_downloaded_and_stored` — mock Slack HTTP response, verify `backend.save()` called
  - `test_file_attachment_cognee_ingested` — verify `remember()` called with temp file path
  - `test_file_attachment_non_slack_url_rejected` — SSRF guard: non-`files.slack.com` URL → skipped
  - `test_file_attachment_over_size_limit` — oversized file → skipped
  - `test_file_attachment_download_error` — Slack returns 403 → caught, no crash
  - `test_file_attachment_temp_file_cleaned_up` — verify `os.unlink()` called in finally
  - `test_multiple_attachments` — 3 files in one message → all processed
  - `test_message_with_files_and_text` — both text ingest AND file ingest run

---

## Phase 3: Organization Website + ScrapeGraphAI (Gap 4)

### 3a. Add `website_url` to Organization model

**Migration file** (generate with `alembic revision -m "add_website_url_to_organizations"`):
```python
def upgrade():
    op.add_column("organizations", sa.Column("website_url", sa.String(2048), nullable=True))

def downgrade():
    op.drop_column("organizations", "website_url")
```

**Files to change:**
1. `apps/api/app/organizations/models.py` — add:
   ```python
   website_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
   ```
2. `apps/api/app/organizations/schemas.py`:
   - `CreateOrganizationRequest` — add `website_url: str | None = None`
   - `UpdateOrganizationRequest` — add `website_url: str | None = None`
   - `OrganizationResponse` — add `website_url: str | None = None`
3. `apps/api/app/organizations/service.py`:
   - `create_org()` — add `website_url=data.website_url` to the `Organization(...)` constructor (line 30-35)
   - `update_org()` — add `if data.website_url is not None: org.website_url = data.website_url` (line 108-113 area)

### 3b. Integrate ScrapeGraphAI during org creation

**Dependency:** `cognee-community-tasks-scrapegraph` (add to `pyproject.toml`)

**Config:** Add to `app/core/config.py`:
```python
sgai_api_key: str = ""
```

**`.env.example`:** Add `SGAI_API_KEY=your-scrapegraphai-key` in a new ScrapeGraphAI section.

**Change in `organizations/service.py` — `create_org()`:**

After the existing Cognee provisioning + seed block (line 57-72 area), add:

```python
# ── ScrapeGraphAI website crawl (best-effort, non-blocking) ──
if data.website_url:
    try:
        from cognee_community_tasks_scrapegraph import scrape_and_add
        await scrape_and_add(
            urls=[data.website_url],
            user_prompt=(
                "Extract the company description, products/services, "
                "mission, key features, target audience, and any other "
                "relevant business information"
            ),
            dataset_name=f"company-{tenant['id']}",
        )
    except ImportError:
        logger.warning(
            "ScrapeGraphAI not available — skipping website scrape for org %s. "
            "Install cognee-community-tasks-scrapegraph and set SGAI_API_KEY.",
            org.id,
        )
    except Exception:
        logger.exception(
            "Website scrape failed for org %s (non-blocking)", org.id
        )
# ── End ScrapeGraphAI ──────────────────────────────────────────
```

**⚠️ ImportError handling (code-reviewer S3):** The lazy `import` inside the `try` block prevents org creation from crashing when the package is not installed. Two exception layers: `ImportError` for missing package/API key, general `Exception` for runtime scrape failures.

### 3c. Re-scrape on website URL update

**Change in `organizations/service.py` — `update_org()`:**

After the field updates (line 108-113 area), if `website_url` changed:

```python
if data.website_url is not None and data.website_url != org.website_url:
    org.website_url = data.website_url
    # Best-effort re-scrape
    if org.cognee_dataset_name:
        try:
            from cognee_community_tasks_scrapegraph import scrape_and_add
            await scrape_and_add(
                urls=[data.website_url],
                user_prompt="Extract the company description, products/services, mission, key features, target audience, and any other relevant business information",
                dataset_name=org.cognee_dataset_name,
            )
        except ImportError:
            logger.warning("ScrapeGraphAI not available — skipping re-scrape")
        except Exception:
            logger.exception("Website re-scrape failed for org %s (non-blocking)", org.id)
```

### 3d. Frontend changes

**Files:**
1. `apps/web/app/setup/_components/org-setup-form.tsx`:
   - Add `website_url` to `OrgSetupFormData` interface
   - Add URL input field: `<Input id="website_url" type="url" placeholder="https://acme.com" ...>`
2. `apps/web/app/(dashboard)/organization/page.tsx`:
   - Add `website_url` to the org settings form
3. `packages/api-client/` — run `bun run generate` (orval) after schema changes. **Note:** requires the API server to be running with updated schemas so orval can read `openapi.json`. Run: `cd apps/api && uv run uvicorn app.main:app` then `cd packages/api-client && bun run generate`.

---

## Phase 4: Discord Safety Check (Gap 6)

**Goal:** Ensure zero Discord tokens = zero issues. Don't remove Discord code.

**Verified safe by deep trace:**
- [x] `gateway/slack_bot.py` — zero Discord imports, no module-level Discord dependency
- [x] `employees/service.py` — `get_active_employees_with_tokens()` handles OR condition (discord OR slack)

**Manual checks:**
- [ ] `gateway/manager.py` — verify refresh loop handles employees with only `slack_token_enc` (no `discord_token_enc`)
- [ ] `gateway/discord_bot.py` — verify `discord.py` import doesn't fail at module level when package is installed
- [ ] Frontend — `hasDiscord` already shows "Not connected" when no token
- [ ] `test_gateway.py` — add `@pytest.mark.skipif(not os.getenv("DISCORD_TOKEN"), reason="No Discord token configured")` to Discord test classes

---

## Phase 5: Code Cleanup (Gaps 7, 8, 9, 10, 11)

### 5a. Dead `cognee_document_id` field (Gap 8)
- **Decision:** Leave in place. Add comment on the model: `# Reserved for future per-document Cognee tracking. Not currently populated.`
- **File:** `apps/api/app/documents/models.py`

### 5b. Local storage filename collision (Gap 9)
- Add UUID prefix to local backend's `save()` to match S3 behavior
- Change from `{org_id}/{sanitized_filename}` to `{org_id}/{uuid8}_{sanitized_filename}`
- **File:** `apps/api/app/storage/local.py`
- **Note:** Old files with the flat format remain readable (storage_path is in DB). Only new uploads get the UUID prefix.

### 5c. Cognee skip logging (Gap 10)
- Fixed in Phase 1b (added `logger.warning` when target dataset/user_id is None)

### 5d. Status progression (Gap 11)
- Fixed in Phase 1b (`doc.status = "indexed"` on success, `"failed"` on error)
- **Note on `background=True`:** When `remember()` is called with `background=True`, the Cognee pipeline runs async. Setting `status = "indexed"` after `remember()` returns means the data has been *queued* for indexing, not necessarily *finished*. For v1, "indexed" means "successfully submitted to Cognee." If strict indexing confirmation is needed in the future, switch to `background=False` at the cost of slower upload response times.

### 5e. `.env.example` audit
- Currently missing 22 of 52 Settings fields. Add all missing sections:
  - Cognee LLM/embedding settings (8 fields: `COGNEE_LLM_PROVIDER`, `COGNEE_LLM_ENDPOINT`, `COGNEE_LLM_API_KEY`, `COGNEE_LLM_MODEL`, `COGNEE_EMBEDDING_PROVIDER`, `COGNEE_EMBEDDING_ENDPOINT`, `COGNEE_EMBEDDING_MODEL`, `COGNEE_SKIP_CONNECTION_TEST`)
  - Slack OAuth settings (`SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_OAUTH_REDIRECT_URI`, `SLACK_IDENTITY_MODE`)
  - MCP OAuth settings (6 fields: Notion, Vercel, GitHub client IDs + secrets)
  - `FRONTEND_URL`, `AGENT_WORKER_CONCURRENCY`, `AGENT_JOB_POLL_INTERVAL_SECONDS`
  - `SGAI_API_KEY` (new, from Phase 3b)
  - Update Cognee section comment (currently says "deferred — Phase 5", should say "active")

### 5f. General cleanup
- Audit API endpoints for unused routes: check each router's endpoints against frontend consumers
- Remove/mark duplicate doc: `BigPicture.md` ≈ `LANGGRAPH_WORKFLOW.md` (keep `BigPicture.md`, add redirect note in `LANGGRAPH_WORKFLOW.md`)
- Remove dead Settings fields: `api_host`, `api_port` are never referenced
- Update stale docs: `Work.md`, `Backend.md`, `AgentMemoryGuide.md` (remove mock/placeholder references, note Cognee is live)

---

## Phase 6: End-to-End Verification

### 6a. Full flow test (see QA expert's manual verification script)

1. User registers → JWT token
2. Create org with website URL → tenant + dataset + ScrapeGraphAI scrape
3. Upload PDFs/docs via dashboard → bucket (S3) + Cognee ingest (all formats, path-based)
4. Upload employee-specific docs → bucket + employee Cognee dataset
5. Create employee → Cognee employee user + dataset + profile seed
6. Connect Slack → OAuth → token stored
7. Bot gateway starts → Slack bot online
8. @mention in Slack → agent responds
9. Send PDF in Slack → downloaded → bucket → Cognee org dataset (SSRF validated, size checked)
10. Agent uses `search_memory` → finds org + employee knowledge from all ingested sources
11. Agent uses `ingest_memory` → writes to employee dataset
12. Update employee profile → Cognee re-seeded
13. Delete employee → dataset forgotten
14. Delete org → all datasets forgotten

### 6b. Edge cases

- Org created without website URL → no scrape, no error
- Org created with website URL but no `SGAI_API_KEY` → scrape skipped, logged, org created normally
- Org created with website URL but `cognee-community-tasks-scrapegraph` not installed → ImportError caught, logged, org created normally
- Employee created when Cognee is down → employee still created, Cognee fields left null, logged
- Document uploaded when Cognee is down → still stored in bucket, status set to "failed", logged with warning
- Document uploaded without `employee_id` → goes to org dataset
- Document uploaded with `employee_id` but employee has no Cognee → falls back to org dataset with detailed warning
- ScrapeGraphAI API key not set → scrape skipped, logged
- No Slack token → bot not started for that employee
- Slack message with files but no text → files ingested, agent still runs
- Slack message with files + text → both ingested (text + files), agent runs with full context
- Slack file URL not from `files.slack.com` → SSRF guard rejects, logged, no download
- Slack file over 10MB → skipped with log
- Local storage: same-name files → no collision (UUID prefix added in Phase 5b)
- Temp file cleanup: process crash between creation and unlink → files in `/tmp` accumulate (accepted risk, documented)

---

## Implementation Order

```
Phase 0a (fix pre-existing test failures)   ───  ~6 test files, assertion updates
Phase 0b (fix integration test fixtures)    ───  1 conftest/pytest.ini
Phase 0c (baseline tests)                   ───  2 new test files
Phase 1a (employee doc routing)             ───  1 file + test updates
Phase 1b (all format support)               ───  1 file + new tests
Phase 1c (doc delete note)                  ───  1 file, comment only
Phase 2  (Slack attachments)                ───  1 file + new test class
Phase 3a (website_url model + migration)    ───  4 files
Phase 3b (ScrapeGraphAI create)             ───  2 files + new dep
Phase 3c (re-scrape on update)              ───  1 file
Phase 3d (frontend website_url)             ───  3 files + orval regen
Phase 4  (Discord safety verify)            ───  read-only, test skip decorators
Phase 5a (dead field comment)               ───  1 file, comment
Phase 5b (local UUID prefix)                ───  1 file
Phase 5d (status progression)               ───  already covered in 1b
Phase 5e (.env.example audit)              ───  1 file, add 22+ vars
Phase 5f (general cleanup)                  ───  audit + remove stale docs
Phase 6  (verification)                     ───  manual test run
```

**Order:** 0a → 0b → 0c → 1a → 1b → 1c → 2 → 3a → 3b → 3c → 3d → 4 → 5a → 5b → 5e → 5f → 6

---

## Decisions & Accepted Limitations

1. **Per-document Cognee deletion is not supported** — Cognee's `forget()` works at the dataset level. Documents deleted from storage/DB leave stale entries in the knowledge graph until the entire dataset is forgotten. Acceptable for v1.

2. **ScrapeGraphAI runs in the foreground during org creation** — blocks the HTTP response for a few seconds. Can be moved to a background job later.

3. **Discord code left in place** — half-built, verified safe by deep audit (zero Discord imports in critical paths).

4. **Admin Cognee user stored in Cognee's SQLite** — survives restarts, recreated if `cognee_data/` is wiped.

5. **Org website scraping is best-effort** — if `SGAI_API_KEY` is missing or the package isn't installed, org creation proceeds normally.

6. **Website re-scrape on update does not forget old content** — Cognee forget is dataset-level, not worth the complexity for v1.

7. **`cognee_document_id` left as reserved** — column exists but never populated. Kept for future Cognee per-document tracking support.

8. **Temp files for Cognee ingest** — files written to `tempfile.NamedTemporaryFile`, passed to Cognee by path, cleaned up in `finally`. Risk of orphaned files on process crash is accepted.

9. **`status = "indexed"` with `background=True`** — "indexed" means "successfully submitted to Cognee's background pipeline," not "fully indexed and searchable." Switching to `background=False` would give accurate status at the cost of slower uploads. Tracked for future improvement.

10. **Slack files go to org dataset, dashboard employee uploads go to employee dataset** — Slack conversations are shared organizational knowledge; dashboard uploads with `employee_id` are personal agent knowledge. This split is intentional.

11. **SSRF guard on Slack file URLs** — only `https://files.slack.com/` URLs are accepted for download. Other domains are logged and rejected.

12. **10MB Slack file size limit** — files larger than 10MB are skipped. This guards against OOM from large attachments. Can be raised when streaming download is implemented.

---

## Files Affected (complete summary)

| File | Phase | Change |
|------|-------|--------|
| `apps/api/tests/test_documents.py` | 0c | **NEW** — baseline tests for document CRUD |
| `apps/api/tests/test_organizations_service.py` | 0c | **NEW** — baseline tests for org CRUD |
| `apps/api/tests/test_agent.py` | 0a | Fix 2 stale guardrail assertions |
| `apps/api/tests/test_tools_and_memory.py` | 0a | Fix 9 stale assertions (counts, memory stubs) |
| `apps/api/tests/test_gateway.py` | 0a, 2, 4 | Fix 2 event loop assertions + add Slack file tests + Discord skip decorators |
| `apps/api/tests/test_slack_oauth.py` | 0a | Fix 1 redirect comparison |
| `apps/api/test/conftest.py` | 0b | Fix async fixture config |
| `apps/api/app/documents/service.py` | 1a, 1b, 1c | Employee dataset routing, path-based ingest, status progression, delete note |
| `apps/api/app/gateway/slack_bot.py` | 2 | Slack file download → bucket → Cognee (both bot classes, with SSRF + size guards) |
| `apps/api/app/organizations/models.py` | 3a | Add `website_url` column |
| `apps/api/app/organizations/schemas.py` | 3a | Add `website_url` to all 3 schemas |
| `apps/api/app/organizations/service.py` | 3a, 3b, 3c | Set `website_url` in create/update, ScrapeGraphAI calls |
| `apps/api/app/core/config.py` | 3b | Add `sgai_api_key` setting |
| `apps/api/pyproject.toml` | 3b | Add `cognee-community-tasks-scrapegraph` dep |
| `apps/api/alembic/versions/` | 3a | New migration: `ALTER TABLE organizations ADD COLUMN website_url VARCHAR(2048)` |
| `apps/web/app/setup/_components/org-setup-form.tsx` | 3d | Add website URL input |
| `apps/web/app/(dashboard)/organization/page.tsx` | 3d | Add website URL field |
| `packages/api-client/` | 3d | Orval re-generation |
| `apps/api/app/storage/local.py` | 5b | Add UUID prefix to avoid filename collisions |
| `apps/api/app/documents/models.py` | 5a | Add comment on `cognee_document_id` (reserved) |
| `apps/api/.env.example` | 5e | Add 22+ missing env vars + `SGAI_API_KEY` |
| `docs/Cognee.md` | — | Updated with new decisions, limitations, file handling, Slack attachments |
| `docs/Work.md` | 5f | Update stale Cognee references |
| `docs/Backend.md` | 5f | Update stale memory/docs references |
| `docs/AgentMemoryGuide.md` | 5f | Remove mock/placeholder references |
