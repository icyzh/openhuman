# Agent Memory Guide — For the LangGraph Developer

This doc defines the memory tool contract. Your agent's tool executor calls these two functions. The actual Cognee implementation lives in `app/memory/service.py` (being built on the `cognee` fork). Until that fork is merged, use the mock implementations below.

## The Two Memory Tools

### `memory_search`

```python
# Signature your tool executor should call:
async def memory_search(query: str, employee_id: str) -> list[MemoryResult]:
    """
    Search the employee's memory for relevant facts.

    Searches BOTH the employee's private dataset AND the org-level dataset.
    Returns results sorted by relevance (if Cognee provides scores).

    Args:
        query: Natural language search query (e.g. "what's our API decision?")
        employee_id: PostgreSQL UUID of the employee (from MessageInput/AgentState)

    Returns:
        List of MemoryResult objects. Empty list if no results or Cognee unavailable.
        Never raises — errors are logged, empty list returned.
    """
```

```python
# The MemoryResult type:
class MemoryResult:
    text: str              # The matched content
    dataset_name: str      # Which dataset it came from ("employee-{uuid}" or "company-{uuid}")
    source: str            # "graph" for graph completion, "chunk" for raw chunks
    score: float | None    # Relevance score (may be None from Cognee)
```

### `memory_ingest`

```python
# Signature your tool executor should call:
async def memory_ingest(content: str, employee_id: str) -> bool:
    """
    Store a fact in the employee's private dataset.

    Fire-and-forget: the caller doesn't wait for indexing to complete.
    Returns True if the ingest call succeeded, False if Cognee was unavailable.

    Args:
        content: The text to store (fact, conversation snippet, decision, etc.)
        employee_id: PostgreSQL UUID of the employee

    Returns:
        True if ingestion was accepted, False on error.
        Never raises — errors are logged, False returned.
    """
```

---

## How the Tools Work Internally

Your tool executor doesn't need to know this — the implementation in `app/memory/service.py` handles it. Documented here for transparency:

1. Given `employee_id`, look up the employee row:
   ```sql
   SELECT cognee_user_id, cognee_dataset_name, organization.cognee_dataset_name
   FROM employees JOIN organizations ON employees.org_id = organizations.id
   WHERE employees.id = $employee_id
   ```

2. **For search**: call `cognee.recall(query, user=cognee_user, datasets=[employee_dataset, org_dataset])`

3. **For ingest**: call `cognee.remember(content, dataset_name=employee_dataset, user=cognee_user, dataset_id=employee_dataset_id)`

---

## How `employee_id` Reaches Your Agent

The agent's `AgentState` / `MessageInput` must carry `employee_id`. When the bot gateway (or HTTP endpoint) invokes the agent, it passes the employee's PostgreSQL UUID.

In the agent graph, thread it through:
```
MessageInput.employee_id → AgentState.employee_id → ToolContext.employee_id
```

Your `tool_executor` node reads `employee_id` from state and passes it to the tool implementation.

---

## What NOT To Do

1. **Don't create your own datasets**. Each employee already has a Cognee dataset (`employee-{employeePgUuid}`) created at onboarding. Don't call `create_dataset()` from agent code.

2. **Don't hardcode dataset names**. Don't construct names like `"org-{orgId}-memory"` or `"company-knowledge"`. Always resolve via the employee's stored `cognee_dataset_name` and `cognee_dataset_id`.

3. **Don't call Cognee SDK directly**. Go through `app/memory/service.py`. The service handles user context, multi-tenancy, and error handling.

4. **Don't store conversation history in Cognee**. Cognee is for facts and knowledge, not raw chat logs. The frontend manages conversation history.

5. **Don't block on ingest**. Always use `background=True` for `remember()` — the agent response should not wait for Cognee's indexing pipeline.

---

## Mock Implementations

Use these until the `cognee` fork is merged. They behave correctly (no-op for ingest, empty for search) so your agent's control flow works end-to-end:

```python
# Placeholder in app/memory/service.py until Cognee is wired:

from dataclasses import dataclass

@dataclass
class MemoryResult:
    text: str
    dataset_name: str
    source: str
    score: float | None


async def memory_search(query: str, employee_id: str) -> list[MemoryResult]:
    """Mock: returns empty results. Agent falls back to "I don't know"."""
    import logging
    logging.getLogger(__name__).info(
        "memory_search mock called: query=%s employee_id=%s", query, employee_id
    )
    return []


async def memory_ingest(content: str, employee_id: str) -> bool:
    """Mock: always succeeds. Content is silently accepted."""
    import logging
    logging.getLogger(__name__).info(
        "memory_ingest mock called: content_len=%d employee_id=%s",
        len(content), employee_id,
    )
    return True
```

When the `cognee` fork merges, these get replaced with real Cognee calls. The function signatures don't change — your tool executor code doesn't need any updates.

---

## Tool Definition for the LLM

When registering these tools with the LLM (in `build_prompt` node), use these JSON Schema definitions:

```python
MEMORY_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "memory_search",
        "description": "Search the team's memory for facts, decisions, and knowledge related to a query. Use this when asked about past discussions, decisions, or documented information.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query — be specific and use keywords",
                },
            },
            "required": ["query"],
        },
    },
}

MEMORY_INGEST_TOOL = {
    "type": "function",
    "function": {
        "name": "memory_ingest",
        "description": "Store an important fact or decision in the team's memory for future reference. Use this when someone explicitly asks to remember something, or when an important decision is made.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The fact or decision to remember, written clearly for future retrieval",
                },
            },
            "required": ["content"],
        },
    },
}
```

Note: the LLM doesn't see `employee_id` — the tool executor injects it from agent state automatically.

---

## Summary

| Your concern | Our contract |
|-------------|-------------|
| Tool signatures | `memory_search(query, employee_id) → list[MemoryResult]` and `memory_ingest(content, employee_id) → bool` |
| Where does `employee_id` come from? | AgentState — thread it from MessageInput through to ToolContext |
| What datasets exist? | One per employee (`employee-{pgUuid}`) + one per org (`company-{tenantId}`) |
| Do I need to create datasets? | No — provisioned at employee onboarding |
| What if Cognee is down? | Tools return empty/False, never raise |
| Can I test without Cognee? | Yes — use the mock implementations above |
| When do the real implementations arrive? | When the `cognee` fork merges into main |
