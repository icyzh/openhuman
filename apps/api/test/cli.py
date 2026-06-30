#!/usr/bin/env python3
"""
CLI test tool for the OpenHuman AI agent orchestration.

Usage (from the apps/api directory)::

    # Interactive mode — pick an employee from a menu
    python -m test.cli

    # One-shot with a specific employee
    python -m test.cli --employee-id <uuid> --message "Hello!"

    # List seed employees without running the agent
    python -m test.cli --list

The tool creates a temporary SQLite database, seeds a test organisation with
four pre-configured employees (HR, Sales, Support, General), and invokes the
full LangGraph agent graph against your configured OpenAI LLM.

Requires ``OPENAI_API_KEY`` in the environment or a ``.env`` file.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path
from textwrap import dedent
from uuid import UUID

# ---------------------------------------------------------------------------
# Path setup — ensure `app` is importable and .env is loaded
# ---------------------------------------------------------------------------
_this_dir = Path(__file__).resolve().parent
_api_dir = _this_dir.parent
if str(_api_dir) not in sys.path:
    sys.path.insert(0, str(_api_dir))

# Explicitly load .env from apps/api/ before importing app.* (which reads
# settings at import time). This fixes environments where the CWD is not
# the project root (e.g. streamlit, or running from a different directory).
_env_path = _api_dir / ".env"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path)


from langchain_core.messages import HumanMessage  # noqa: E402

from app.agent.build import build_graph  # noqa: E402
from app.agent.tools import BUILT_IN_TOOLS  # noqa: E402
from test.fixtures import SEED_EMPLOYEES, print_banner, setup_test_db  # noqa: E402


# Compiled once at module load
agent_graph = build_graph(BUILT_IN_TOOLS)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _redact_key(key: str) -> str:
    """Show only the last 4 chars of an API key."""
    if not key:
        return "<not set>"
    if len(key) <= 8:
        return "*" * len(key)
    return "*" * (len(key) - 4) + key[-4:]


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


async def run_agent(
    employee_id: UUID,
    message: str,
    platform: str = "api",
    db_path: str | Path = ":memory:",
) -> None:
    """Set up DB, run the agent graph, and print the result."""

    # --- Setup ---------------------------------------------------------------
    print(f"🔧 Setting up test database ({db_path}) … ", end="", flush=True)
    _engine, session_factory, employee_ids = await setup_test_db(db_path)
    print("done.")

    # Resolve which employee to use
    if str(employee_id) not in {str(v) for v in employee_ids.values()}:
        print(f"\n⚠️  Employee {employee_id} not found in seed data. Using 'general' fallback.")
        employee_id = employee_ids.get("general", list(employee_ids.values())[0])

    print_banner()
    print(f"🎯 Using employee : {employee_id}")
    print(f"📨 Message        : {message!r}")
    print(f"📡 Platform       : {platform}")
    print(f"🔑 OpenAI key : {_redact_key(os.getenv('OPENAI_API_KEY', ''))}")
    print(f"🤖 Model      : {os.getenv('OPENAI_MODEL', 'gpt-4o-mini')}")
    print()

    # --- Invoke agent --------------------------------------------------------
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

        print("⏳ Running agent graph …\n")
        t0 = time.monotonic()

        try:
            result = await agent_graph.ainvoke(initial_state, config=config)
        except Exception as exc:
            print(f"\n❌ Agent execution failed: {exc!r}")
            raise

        elapsed = time.monotonic() - t0

    # --- Print results -------------------------------------------------------
    response_text = result.get("response", "")
    tool_rounds = result.get("tool_round", 0)
    error = result.get("error")
    input_blocked = result.get("input_blocked", False)
    block_reason = result.get("block_reason")
    output_guardrail_passed = result.get("output_guardrail_passed", True)
    citations = result.get("citations", [])
    messages = result.get("messages", [])

    # Count tool calls from AIMessages
    tool_call_names: list[str] = []
    for msg in messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_call_names.append(tc.get("name", "?"))

    print("─" * 60)
    print("📊 RESULTS")
    print("─" * 60)
    print(f"  ⏱️  Wall time         : {elapsed:.2f}s")
    print(f"  🔧 Tool rounds       : {tool_rounds}")
    print(f"  🛠️  Tool calls        : {tool_call_names if tool_call_names else 'none'}")
    print(f"  🛡️  Input blocked     : {input_blocked}")
    if block_reason:
        print(f"     Block reason      : {block_reason}")
    print(f"  ✅ Output guardrail  : {'passed' if output_guardrail_passed else 'FAILED'}")
    print(f"  📎 Citations         : {len(citations)}")
    if citations:
        for c in citations:
            print(f"     - [{c.get('source', '?')}] {c.get('content', '')[:120]}")
    if error:
        print(f"  ⚠️  Error             : {error}")

    print()
    print("─" * 60)
    print("💬 RESPONSE")
    print("─" * 60)
    print(response_text or "<no response produced>")
    print("─" * 60)

    # Show message trace if verbose
    if os.getenv("VERBOSE"):
        print("\n📜 FULL MESSAGE TRACE\n")
        for i, msg in enumerate(messages):
            role = type(msg).__name__
            content = getattr(msg, "content", "")
            tool_calls = getattr(msg, "tool_calls", None)
            extra = ""
            if tool_calls:
                names = [tc.get("name", "?") for tc in tool_calls]
                extra = f"  🔧→ {names}"
            print(f"  [{i}] {role}{extra}")
            if content:
                for line in str(content)[:300].splitlines():
                    print(f"       {line}")
            print()

    # --- Cleanup -------------------------------------------------------------
    await _engine.dispose()


# ---------------------------------------------------------------------------
# Interactive mode
# ---------------------------------------------------------------------------


def _pick_employee() -> UUID | None:
    """Print a menu and return the chosen employee UUID."""
    print("\n📋 Seed employees:\n")
    for i, cfg in enumerate(SEED_EMPLOYEES, 1):
        from test.fixtures import SEED_EMPLOYEE_IDS

        eid = SEED_EMPLOYEE_IDS.get(cfg["specialization"])
        print(f"  {i}. {cfg['name']} ({cfg['specialization']})  id={eid}")

    print()
    choice = input("Pick an employee [1-4, default=4]: ").strip() or "4"

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(SEED_EMPLOYEES):
            from test.fixtures import SEED_EMPLOYEE_IDS

            return SEED_EMPLOYEE_IDS[SEED_EMPLOYEES[idx]["specialization"]]
    except (ValueError, IndexError):
        pass

    print("⚠️  Invalid choice, using General Assistant.")
    from test.fixtures import SEED_EMPLOYEE_IDS

    return SEED_EMPLOYEE_IDS.get("general")


async def _interactive() -> None:
    """Interactive chat loop with employee selection."""
    print("🤖 OpenHuman Agent Test CLI\n")

    # Seed the DB first (also sets fixtures.SEED_EMPLOYEE_IDS as a side effect)
    engine, session_factory, _ids = await setup_test_db(":memory:")

    employee_id = _pick_employee()
    if employee_id is None:
        return

    print(f"\n🎯 Employee: {employee_id}")
    print('Type your message (or "quit" to exit, "switch" to change employee).\n')

    try:
        while True:
            message = input("🧑 You → ").strip()
            if not message:
                continue
            if message.lower() in ("quit", "exit", "q"):
                print("👋 Goodbye!")
                break
            if message.lower() == "switch":
                employee_id = _pick_employee()
                if employee_id is None:
                    break
                print(f"🎯 Switched to: {employee_id}")
                continue

            initial_state = {
                "messages": [HumanMessage(content=message)],
                "platform": "api",
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
                try:
                    result = await agent_graph.ainvoke(initial_state, config=config)
                except Exception as exc:
                    print(f"❌ Error: {exc!r}\n")
                    continue
                elapsed = time.monotonic() - t0

            response = result.get("response", "<no response>")
            tool_rounds = result.get("tool_round", 0)
            error = result.get("error")

            print(f"🤖 Bot → ({tool_rounds} tool rounds, {elapsed:.1f}s)")
            print(f"{response}")
            if error:
                print(f"⚠️  Error: {error}")
            print()

    except (KeyboardInterrupt, EOFError):
        print("\n👋 Goodbye!")
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test the OpenHuman agent graph from the command line.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=dedent("""\
        Examples:
          python -m test.cli --list
          python -m test.cli --message "What is 2+2?"
          python -m test.cli --employee-id <uuid> --message "Search for AI news"
          VERBOSE=1 python -m test.cli --message "Hello!"
        """),
    )
    parser.add_argument(
        "--employee-id",
        type=str,
        default=None,
        help="UUID of a seed employee (default: general assistant)",
    )
    parser.add_argument(
        "--message", "-m",
        type=str,
        default=None,
        help="Message to send (omit for interactive mode)",
    )
    parser.add_argument(
        "--platform",
        type=str,
        default="api",
        choices=["api", "discord", "slack"],
        help="Platform context (default: api)",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=":memory:",
        help="SQLite database path (default: :memory:)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print seed employees and exit (no agent run)",
    )

    args = parser.parse_args()

    if args.list:
        async def _list() -> None:
            _e, _sf, _ids = await setup_test_db(":memory:")
            print_banner()
            await _e.dispose()

        asyncio.run(_list())
        return

    if args.message:
        # One-shot mode
        employee_id_str = args.employee_id
        if employee_id_str:
            employee_id = UUID(employee_id_str)
        else:
            # Default to general assistant — need to seed first
            async def _get_default() -> UUID:
                _e, _sf, ids = await setup_test_db(args.db_path)
                return ids.get("general", list(ids.values())[0])

            employee_id = asyncio.run(_get_default())

        asyncio.run(
            run_agent(
                employee_id=employee_id,
                message=args.message,
                platform=args.platform,
                db_path=args.db_path,
            )
        )
    else:
        # Interactive mode
        asyncio.run(_interactive())


if __name__ == "__main__":
    main()
