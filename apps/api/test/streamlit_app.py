#!/usr/bin/env python3
"""
Streamlit test UI for the OpenHuman AI agent orchestration.

Launch from ``apps/api``::

    streamlit run test/streamlit_app.py

Or from the repo root::

    streamlit run apps/api/test/streamlit_app.py

The UI creates an in-memory SQLite database seeded with four test employees
(HR, Sales, Support, General) and lets you chat with any of them through
the full LangGraph agent graph — including tool calls, guardrails, and
response formatting.

Requires ``OPENAI_API_KEY`` in the environment or a ``.env`` file.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING
from uuid import UUID

# ---------------------------------------------------------------------------
# Path setup — ensure `app` is importable and .env is loaded
# ---------------------------------------------------------------------------
_this_dir = Path(__file__).resolve().parent
_api_dir = _this_dir.parent
if str(_api_dir) not in sys.path:
    sys.path.insert(0, str(_api_dir))

# Explicitly load .env from apps/api/ before importing app.* (pydantic-settings
# reads env_file=".env" relative to CWD, but Streamlit changes CWD to the
# script's directory, so it would look for test/.env instead of apps/api/.env).
_env_path = _api_dir / ".env"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path)

import streamlit as st
from langchain_core.messages import AIMessage as LCAIMessage
from langchain_core.messages import HumanMessage, ToolMessage

from app.agent.build import build_graph
from app.agent.tools import BUILT_IN_TOOLS
from test.fixtures import SEED_EMPLOYEES, print_banner, setup_test_db

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="OpenHuman — Agent Tester",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Compiled agent graph (cached once per process)
# ---------------------------------------------------------------------------
if "agent_graph" not in st.session_state:
    st.session_state.agent_graph = build_graph(BUILT_IN_TOOLS)

agent_graph = st.session_state.agent_graph


# ---------------------------------------------------------------------------
# Async runner helper
# ---------------------------------------------------------------------------
def _run_async(coro):
    """Run an async coroutine and cache the event loop policy."""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        # Already inside a running event loop (rare with Streamlit)
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro)


# ---------------------------------------------------------------------------
# DB lifecycle (cached in session state)
# ---------------------------------------------------------------------------
def _init_db():
    """One-shot DB setup — only called when not already in session state."""
    if "db_engine" in st.session_state:
        return

    with st.spinner("Setting up test database …"):
        engine, session_factory, employee_ids = _run_async(
            setup_test_db(":memory:")
        )

    st.session_state.db_engine = engine
    st.session_state.db_session_factory = session_factory
    st.session_state.employee_ids = employee_ids  # specialization → UUID
    st.session_state.db_ready = True


# ---------------------------------------------------------------------------
# Session-state defaults
# ---------------------------------------------------------------------------
def _init_state():
    """Initialise all session_state keys on first run."""
    defaults: dict[str, object] = {
        "chat_history": [],  # list of dicts: {role, content, meta}
        "selected_employee_spec": "general",
        "platform": "api",
        "db_ready": False,
        "message_counter": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ---------------------------------------------------------------------------
# Agent invocation
# ---------------------------------------------------------------------------
async def _invoke_agent(employee_id: UUID, message: str, platform: str, session_factory):
    """Run the agent graph and return (result_state, elapsed_seconds)."""
    initial_state = {
        "messages": [HumanMessage(content=message)],
        "platform": platform,
        "employee_id": str(employee_id),
        "tool_round": 0,
    }

    async with session_factory() as session:
        config = {
            "configurable": {
                "db": session,
                "employee_id": str(employee_id),
            }
        }
        t0 = time.monotonic()
        result = await agent_graph.ainvoke(initial_state, config=config)
        elapsed = time.monotonic() - t0

    return result, elapsed


# ---------------------------------------------------------------------------
# Message rendering helpers
# ---------------------------------------------------------------------------
def _extract_tool_calls(messages: list) -> list[dict]:
    """Pull tool-call details from the message trace."""
    calls: list[dict] = []
    for msg in messages:
        if isinstance(msg, LCAIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                calls.append({
                    "name": tc.get("name", "?"),
                    "args": tc.get("args", {}),
                    "id": tc.get("id", ""),
                })
    return calls


def _extract_tool_results(messages: list) -> dict[str, str]:
    """Map tool_call_id → content from ToolMessages."""
    results: dict[str, str] = {}
    for msg in messages:
        if isinstance(msg, ToolMessage):
            results[msg.tool_call_id] = str(msg.content)
    return results


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
def _render_sidebar():
    st.sidebar.title("🤖 OpenHuman Agent Tester")
    st.sidebar.caption("Test your AI employee orchestration in real time.")

    # --- Employee picker -----------------------------------------------------
    st.sidebar.header("👤 Employee")

    spec_labels = {
        cfg["specialization"]: f"{cfg['name']} — {cfg['role']}"
        for cfg in SEED_EMPLOYEES
    }
    specs = list(spec_labels)

    current_spec = st.session_state.selected_employee_spec
    current_index = specs.index(current_spec) if current_spec in specs else 3

    selected_label = st.sidebar.selectbox(
        "Select employee",
        options=specs,
        format_func=lambda s: spec_labels[s],
        index=current_index,
        key="employee_selector",
    )
    # Map label back to spec slug
    selected_spec = selected_label
    st.session_state.selected_employee_spec = selected_spec

    employee_ids: dict = st.session_state.get("employee_ids", {})
    employee_id = employee_ids.get(selected_spec)

    # Show details for selected employee
    from app.employees.templates import TEMPLATES

    if selected_spec in TEMPLATES:
        t = TEMPLATES[selected_spec]
        st.sidebar.markdown(f"**Tools allowed:**")
        for tool in t.allowed_tools:
            st.sidebar.markdown(f"- `{tool}`")
        st.sidebar.markdown(f"**Guardrails:** PII={t.guardrail_config.get('block_pii', False)}, Citations={t.guardrail_config.get('require_citations', False)}")

    # --- Platform ------------------------------------------------------------
    st.sidebar.header("📡 Platform")
    platform = st.sidebar.selectbox(
        "Context",
        options=["api", "discord", "slack"],
        index=["api", "discord", "slack"].index(st.session_state.platform),
        key="platform_selector",
    )
    st.session_state.platform = platform

    # --- Model info ----------------------------------------------------------
    st.sidebar.header("🔧 Configuration")
    st.sidebar.markdown(
        f"""\
**Model:** `{os.getenv('OPENAI_MODEL', 'gpt-4o-mini')}`
**API key:** `{_mask_key(os.getenv('OPENAI_API_KEY', ''))}`
"""
    )

    # --- Actions -------------------------------------------------------------
    st.sidebar.header("⚡ Actions")
    if st.sidebar.button("🗑️  Clear chat", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.message_counter = 0
        st.rerun()

    if st.sidebar.button("🔄 Reset database", use_container_width=True):
        _teardown_db()
        st.session_state.db_ready = False
        st.session_state.chat_history = []
        _init_db()
        st.rerun()

    # --- Status --------------------------------------------------------------
    st.sidebar.divider()
    st.sidebar.caption(
        f"Messages: {len(st.session_state.chat_history)} | "
        f"DB: {'✅' if st.session_state.db_ready else '❌'}"
    )

    return employee_id


def _mask_key(key: str) -> str:
    if not key:
        return "⚠️ not set"
    if len(key) <= 8:
        return "*" * len(key)
    return "*" * (len(key) - 4) + key[-4:]


# ---------------------------------------------------------------------------
# Teardown
# ---------------------------------------------------------------------------
def _teardown_db():
    engine: AsyncEngine | None = st.session_state.pop("db_engine", None)
    if engine:
        _run_async(engine.dispose())
    st.session_state.pop("db_session_factory", None)
    st.session_state.pop("employee_ids", None)


# ---------------------------------------------------------------------------
# Main UI
# ---------------------------------------------------------------------------
def main():
    _init_state()
    _init_db()

    if not st.session_state.db_ready:
        st.error("Database not ready. Refresh the page.")
        return

    employee_id = _render_sidebar()

    # --- Main column ---------------------------------------------------------
    st.title("🤖 Agent Test Console")
    st.caption(
        "Messages go through the full LangGraph pipeline: "
        "**input guardrail → prompt build → LLM + tools → output guardrail → format**."
    )

    if employee_id is None:
        st.warning("No employee selected. Pick one from the sidebar.")
        return

    employee_id_str = str(employee_id)
    session_factory = st.session_state.db_session_factory

    # --- Render existing chat history -----------------------------------------
    for entry in st.session_state.chat_history:
        with st.chat_message(entry["role"]):
            st.markdown(entry["content"])
            _render_message_meta(entry.get("meta"))

    # --- Chat input -----------------------------------------------------------
    message_key = f"chat_input_{st.session_state.message_counter}"
    user_input = st.chat_input(
        "Type a message to test the agent …",
        key=message_key,
    )

    if user_input:
        # Append user message
        st.session_state.chat_history.append({
            "role": "user",
            "content": user_input,
            "meta": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        st.session_state.message_counter += 1

        # Run agent
        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("⏳ *Running agent graph …*")

            try:
                result, elapsed = _run_async(
                    _invoke_agent(
                        UUID(employee_id_str),
                        user_input,
                        st.session_state.platform,
                        session_factory,
                    )
                )
            except Exception as exc:
                placeholder.error(f"Agent execution failed:\n\n```\n{traceback.format_exc()}\n```")
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": f"❌ Error: {exc}",
                    "meta": {"error": str(exc)},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                st.rerun()

            # Parse results
            response_text = result.get("response", "") or "<no response>"
            error = result.get("error")
            tool_rounds = result.get("tool_round", 0)
            input_blocked = result.get("input_blocked", False)
            block_reason = result.get("block_reason")
            output_guardrail_passed = result.get("output_guardrail_passed", True)
            citations = result.get("citations", [])
            messages = result.get("messages", [])
            tool_calls = _extract_tool_calls(messages)
            tool_results = _extract_tool_results(messages)
            system_prompt = result.get("system_prompt", "")

            # Build meta for the chat entry
            meta = {
                "elapsed": elapsed,
                "tool_rounds": tool_rounds,
                "tool_calls": tool_calls,
                "tool_results": tool_results,
                "input_blocked": input_blocked,
                "block_reason": block_reason,
                "output_guardrail_passed": output_guardrail_passed,
                "citations": citations,
                "error": error,
                "system_prompt": system_prompt,
                "messages": messages,
            }

            # Display the final response
            placeholder.markdown(response_text)
            _render_message_meta(meta)

            # Append to history
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": response_text,
                "meta": meta,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            st.rerun()


# ---------------------------------------------------------------------------
# Message metadata expander
# ---------------------------------------------------------------------------
def _render_message_meta(meta: dict | None):
    """Render expandable metadata below an assistant message."""
    if meta is None:
        return

    with st.expander("🔍 Agent trace", expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("⏱️ Latency", f"{meta.get('elapsed', 0):.2f}s")
        col2.metric("🔧 Tool rounds", meta.get("tool_rounds", 0))
        col3.metric(
            "🛡️ Input guard",
            "🚫 Blocked" if meta.get("input_blocked") else "✅ Pass",
        )
        col4.metric(
            "✅ Output guard",
            "✅ Pass" if meta.get("output_guardrail_passed") else "❌ Fail",
        )

        # Block reason
        if meta.get("block_reason"):
            st.warning(f"Input blocked: {meta['block_reason']}")

        # Error
        if meta.get("error"):
            st.error(f"Agent error: {meta['error']}")

        # Tool calls
        tool_calls = meta.get("tool_calls", [])
        tool_results = meta.get("tool_results", {})
        if tool_calls:
            st.subheader("🛠️ Tool Calls")
            for tc in tool_calls:
                tc_id = tc.get("id", "")
                result_text = tool_results.get(tc_id, "<no result>")
                with st.container(border=True):
                    st.markdown(f"**`{tc['name']}`**")
                    with st.expander("Args", expanded=False):
                        st.json(tc.get("args", {}))
                    with st.expander("Result", expanded=False):
                        st.text(str(result_text)[:2000])

        # Citations
        citations = meta.get("citations", [])
        if citations:
            st.subheader("📎 Citations")
            for c in citations:
                st.caption(f"[{c.get('source', '?')}] {c.get('content', '')[:200]}")

        # System prompt
        system_prompt = meta.get("system_prompt", "")
        if system_prompt:
            with st.expander("📜 System Prompt", expanded=False):
                st.text(system_prompt)

        # Full message trace
        messages = meta.get("messages", [])
        if messages:
            with st.expander("📨 Full Message Trace", expanded=False):
                for i, msg in enumerate(messages):
                    role = type(msg).__name__
                    content = getattr(msg, "content", "")
                    tool_calls = getattr(msg, "tool_calls", None)
                    extra = ""
                    if tool_calls:
                        names = [tc.get("name", "?") for tc in tool_calls]
                        extra = f"  🔧→ {names}"
                    st.caption(f"**[{i}] {role}{extra}**")
                    if content:
                        st.text(str(content)[:500])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()
