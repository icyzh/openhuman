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
from app.agent.tools.mcp.connectors import REGISTRY as MCP_REGISTRY  # noqa: E402
from app.employees.templates import get_template  # noqa: E402
from test.fixtures import (  # noqa: E402
    SEED_EMPLOYEES,
    clear_slack_token,
    get_slack_token_status,
    print_banner,
    set_slack_token,
    setup_test_db,
)
from test.mcp_helpers import (  # noqa: E402
    add_mcp_connection,
    list_mcp_connectors,
    remove_mcp_connection,
    resolve_mcp_tools,
)


# ---------------------------------------------------------------------------
# Lazy graph builder (resolves MCP tools at invocation time)
# ---------------------------------------------------------------------------
async def _get_or_build_graph(session, employee_id):
    """Resolve MCP tools + built-in tools and return (graph, all_tools)."""
    from sqlalchemy import select as sa_select

    from app.employees.models import Employee

    emp = await session.scalar(
        sa_select(Employee).where(Employee.id == employee_id)
    )
    if emp is None:
        return build_graph(BUILT_IN_TOOLS), list(BUILT_IN_TOOLS)

    template = get_template(emp.specialization or "general")
    mcp_tools: list = []
    if template.allowed_mcp_servers and emp.org_id:
        mcp_tools = await resolve_mcp_tools(
            session, emp.org_id, employee_id, template.allowed_mcp_servers
        )

    all_tools = list(BUILT_IN_TOOLS) + mcp_tools
    return build_graph(all_tools), all_tools


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
        # Build graph with MCP tools resolved for this employee
        graph, all_tools = await _get_or_build_graph(session, employee_id)
        mcp_tool_count = sum(1 for t in all_tools if t.name.startswith("mcp__"))

        config = {
            "configurable": {
                "db": session,
                "employee_id": str(employee_id),
                "all_tools": all_tools,
            }
        }

        print("⏳ Running agent graph …\n")
        t0 = time.monotonic()

        try:
            result = await graph.ainvoke(initial_state, config=config)
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
    print(f"  🔌 MCP tools loaded  : {mcp_tool_count}")
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
                graph, all_tools = await _get_or_build_graph(session, employee_id)

                config = {
                    "configurable": {
                        "db": session,
                        "employee_id": str(employee_id),
                        "all_tools": all_tools,
                    }
                }

                t0 = time.monotonic()
                try:
                    result = await graph.ainvoke(initial_state, config=config)
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
        default="/tmp/openhuman_test.db",
        help="SQLite database path (default: /tmp/openhuman_test.db). Use ':memory:' for ephemeral.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print seed employees and exit (no agent run)",
    )
    parser.add_argument(
        "--set-slack-token",
        type=str,
        default=None,
        metavar="TOKEN",
        help="Store an encrypted Slack bot token for the given employee (use with --employee-id). "
             "The token is encrypted at rest with AES-256-GCM.",
    )
    parser.add_argument(
        "--clear-slack-token",
        action="store_true",
        help="Remove the Slack bot token from the given employee (use with --employee-id).",
    )
    parser.add_argument(
        "--slack-status",
        action="store_true",
        help="Print whether the given employee has a Slack token stored.",
    )
    parser.add_argument(
        "--test-routing",
        action="store_true",
        help="Seed 3 employees sharing one Slack token with channel assignments, "
             "then test channel→employee routing logic (no real Slack connection needed).",
    )

    # ---- MCP management flags ------------------------------------------------
    parser.add_argument(
        "--list-mcp",
        action="store_true",
        help="List registered MCP connectors and connection status for an employee "
             "(use with --employee-id). Without --employee-id, shows org-wide status only.",
    )
    parser.add_argument(
        "--set-mcp-connection",
        type=str,
        default=None,
        metavar="SLUG:CREDENTIAL",
        help="Store an API key / PAT for an MCP connector. "
             "Format: SLUG:CREDENTIAL (e.g. 'github:ghp_xxx'). "
             "Use with --employee-id. The credential is encrypted at rest.",
    )
    parser.add_argument(
        "--clear-mcp-connection",
        type=str,
        default=None,
        metavar="SLUG",
        help="Remove (revoke) an MCP connection for the given employee "
             "(use with --employee-id).",
    )
    parser.add_argument(
        "--mcp-status",
        action="store_true",
        help="Show detailed MCP connection status for an employee "
             "(use with --employee-id).",
    )

    args = parser.parse_args()

    # ---- List mode ----------------------------------------------------------
    if args.list:
        async def _list() -> None:
            _e, sf, _ids = await setup_test_db(args.db_path)
            print_banner()
            # Show Slack token status for each employee
            print("🔑 Slack token status:\n")
            for cfg in SEED_EMPLOYEES:
                eid = _ids.get(cfg["specialization"])
                if eid:
                    has = await get_slack_token_status(sf, eid)
                    print(f"  {cfg['name']:<20s}  {'✅ token set' if has else '❌ no token'}")
            print()
            await _e.dispose()

        asyncio.run(_list())
        return

    # ---- Slack token operations --------------------------------------------
    if args.set_slack_token is not None or args.clear_slack_token or args.slack_status:
        if not args.employee_id:
            print("❌ --employee-id is required for Slack token operations.")
            sys.exit(1)

        employee_id = UUID(args.employee_id)
        db_path = args.db_path

        async def _slack_op() -> None:
            engine, sf, ids = await setup_test_db(db_path)

            if args.set_slack_token is not None:
                ok = await set_slack_token(sf, employee_id, args.set_slack_token)
                if ok:
                    print(f"✅ Slack token stored (encrypted) for employee {employee_id}")
                else:
                    print(f"❌ Employee {employee_id} not found.")

            elif args.clear_slack_token:
                ok = await clear_slack_token(sf, employee_id)
                if ok:
                    print(f"🗑️  Slack token removed for employee {employee_id}")
                else:
                    print(f"❌ Employee {employee_id} not found.")

            elif args.slack_status:
                has = await get_slack_token_status(sf, employee_id)
                print(f"🔑 Employee {employee_id}: {'✅ Slack token set' if has else '❌ no Slack token'}")

            await engine.dispose()

        asyncio.run(_slack_op())
        return

    # ---- Routing test -------------------------------------------------------
    if args.test_routing:
        async def _test_routing() -> None:
            from sqlalchemy import select

            from app.channel_assignments.models import ChannelAssignment

            # Use an ephemeral DB so we don't pollute the persistent one
            engine, sf, ids = await setup_test_db(":memory:")

            # Give all 4 seed employees the SAME Slack token (simulating one workspace)
            shared_token = "xoxb-shared-workspace-token"
            for emp_id in ids.values():
                await set_slack_token(sf, emp_id, shared_token)

            # Create channel assignments:
            #   Alex (HR)      → #hr-announcements
            #   Blake (Sales)   → #deals, #sales-leads
            #   Casey (Support) → #support, #bugs
            #   Drew (General)  → NO assignments (unrestricted)
            assignments = [
                ("hr_specialist", "C001", "#hr-announcements"),
                ("sales_rep", "C002", "#deals"),
                ("sales_rep", "C003", "#sales-leads"),
                ("support_agent", "C004", "#support"),
                ("support_agent", "C005", "#bugs"),
            ]
            async with sf() as session:
                for spec, channel_id, channel_name in assignments:
                    session.add(ChannelAssignment(
                        employee_id=ids[spec],
                        platform="slack",
                        channel_id=channel_id,
                        channel_name=channel_name,
                    ))
                await session.commit()

            emp_ids_list = list(ids.values())
            emp_id_set = frozenset(emp_ids_list)

            # Resolve helper — mirrors WorkspaceSlackBot._resolve_employee
            async def resolve(channel_id: str | None) -> UUID | None:
                async with sf() as session:
                    if channel_id is not None:
                        # 1. Explicit assignment
                        ca = (await session.execute(
                            select(ChannelAssignment).where(
                                ChannelAssignment.platform == "slack",
                                ChannelAssignment.channel_id == channel_id,
                                ChannelAssignment.employee_id.in_(emp_id_set),
                            )
                        )).scalars().first()
                        if ca is not None:
                            return ca.employee_id

                        # 2. Any assignments? → unassigned channel
                        any_ca = (await session.execute(
                            select(ChannelAssignment).where(
                                ChannelAssignment.platform == "slack",
                                ChannelAssignment.employee_id.in_(emp_id_set),
                            ).limit(1)
                        )).scalars().first()
                        if any_ca is not None:
                            return None

                    # 3. Unrestricted fallback (or DM)
                    rows = (await session.execute(
                        select(ChannelAssignment.employee_id).where(
                            ChannelAssignment.platform == "slack",
                            ChannelAssignment.employee_id.in_(emp_id_set),
                        ).distinct()
                    )).all()
                    assigned = {r[0] for r in rows}
                    for eid in emp_ids_list:
                        if eid not in assigned:
                            return eid
                    return emp_ids_list[0] if emp_ids_list else None

            # Resolve employee name
            spec_by_id = {v: k for k, v in ids.items()}
            cfg_by_spec = {c["specialization"]: c for c in SEED_EMPLOYEES}

            def describe(eid: UUID | None) -> str:
                if eid is None:
                    return "IGNORE (no one assigned)"
                spec = spec_by_id.get(eid, "?")
                name = cfg_by_spec.get(spec, {}).get("name", str(eid))
                return f"{name} ({spec})"

            # ── Test cases ────────────────────────────────────────────────
            print()
            print("═" * 60)
            print("🧪 CHANNEL → EMPLOYEE ROUTING TEST")
            print("═" * 60)
            print()
            print("Setup: 4 employees share token xoxb-shared-workspace-token")
            print()
            print("  Alex (HR)       → C001 (#hr-announcements)")
            print("  Blake (Sales)    → C002 (#deals), C003 (#sales-leads)")
            print("  Casey (Support)  → C004 (#support), C005 (#bugs)")
            print("  Drew (General)   → UNRESTRICTED (no assignments)")
            print()
            print("─" * 60)

            test_cases = [
                ("C004", "Support channel → Casey (Support)"),
                ("C002", "Deals channel → Blake (Sales)"),
                ("C001", "HR channel → Alex (HR)"),
                ("C999", "Unassigned channel (others restricted) → IGNORE"),
                (None,   "DM → Drew (General, unrestricted)"),
            ]

            all_ok = True
            for channel_id, description in test_cases:
                result = await resolve(channel_id)
                label = "DM" if channel_id is None else channel_id
                who = describe(result)

                # Expected results
                if channel_id == "C004":
                    expected_spec = "support_agent"
                elif channel_id in ("C002", "C003"):
                    expected_spec = "sales_rep"
                elif channel_id == "C001":
                    expected_spec = "hr_specialist"
                elif channel_id == "C999":
                    expected_spec = None
                elif channel_id is None:
                    expected_spec = "general"

                ok = (result is None and expected_spec is None) or \
                     (result is not None and spec_by_id.get(result) == expected_spec)

                status = "✅" if ok else "❌ FAIL"
                if not ok:
                    all_ok = False

                print(f"  {status}  {label:<20s} → {who}")
                print(f"          {description}")

            print("─" * 60)
            if all_ok:
                print("\n✅ All routing tests passed.\n")
            else:
                print("\n❌ Some routing tests FAILED.\n")

            await engine.dispose()

        asyncio.run(_test_routing())
        return

    # ---- List MCP connectors -------------------------------------------------
    if args.list_mcp:
        async def _list_mcp() -> None:
            engine, sf, ids = await setup_test_db(args.db_path)

            employee_id = None
            org_id = None
            emp_spec = "general"
            if args.employee_id:
                employee_id = UUID(args.employee_id)
            else:
                # Default to general assistant
                employee_id = ids.get("general", list(ids.values())[0])

            # Resolve org_id from an employee
            async with sf() as session:
                from sqlalchemy import select as sa_select
                from app.employees.models import Employee
                emp = await session.scalar(
                    sa_select(Employee).where(Employee.id == employee_id)
                )
                if emp is None:
                    print(f"❌ Employee {employee_id} not found.")
                    await engine.dispose()
                    return
                org_id = emp.org_id

                connectors = await list_mcp_connectors(session, org_id, employee_id)

            print_banner()
            print("🔌 MCP Connectors\n")
            print(f"   Org: {org_id}")
            print(f"   Employee: {employee_id}")
            print()

            if not connectors:
                print("   (no connectors registered)\n")
            else:
                for c in connectors:
                    icon = "✅" if c["is_connected"] else "⬜"
                    print(f"  {icon} {c['name']} ({c['slug']})")
                    print(f"     Auth: {c['auth_type']}")
                    print(f"     Status: {c['connection_status']}")
                    if c.get("scopes"):
                        print(f"     Scopes: {', '.join(c['scopes'])}")
                    if c.get("requires_manual_approval"):
                        print(f"     ⚠️  Requires vendor approval")
                    print()

            await engine.dispose()

        asyncio.run(_list_mcp())
        return

    # ---- Set / Clear / Status MCP connection ---------------------------------
    if args.set_mcp_connection is not None or args.clear_mcp_connection or args.mcp_status:
        if not args.employee_id:
            print("❌ --employee-id is required for MCP connection operations.")
            sys.exit(1)

        employee_id = UUID(args.employee_id)

        async def _mcp_op() -> None:
            engine, sf, ids = await setup_test_db(args.db_path)

            try:
                async with sf() as session:
                    from sqlalchemy import select as sa_select
                    from app.employees.models import Employee
                    emp = await session.scalar(
                        sa_select(Employee).where(Employee.id == employee_id)
                    )
                    if emp is None:
                        print(f"❌ Employee {employee_id} not found.")
                        return
                    org_id = emp.org_id

                    if args.set_mcp_connection is not None:
                        raw = args.set_mcp_connection
                        if ":" not in raw:
                            print("❌ Format: --set-mcp-connection SLUG:CREDENTIAL")
                            print("   Example: --set-mcp-connection github:ghp_xxxx")
                            return
                        slug, credential = raw.split(":", 1)
                        slug = slug.strip()
                        credential = credential.strip()

                        if slug not in MCP_REGISTRY:
                            print(f"❌ Unknown connector slug: {slug}")
                            print(f"   Available: {', '.join(MCP_REGISTRY)}")
                            return

                        spec = MCP_REGISTRY[slug]
                        if spec.auth_type not in ("pat_bearer", "api_key_header"):
                            print(f"❌ '{slug}' uses OAuth — cannot set a key directly.")
                            print(f"   Use the web UI or API for OAuth connectors.")
                            return

                        try:
                            conn = await add_mcp_connection(
                                session, org_id, employee_id, slug, credential
                            )
                            print(f"✅ MCP connection stored (encrypted) for '{slug}'")
                            print(f"   Connection ID: {conn.id}")
                        except Exception as exc:
                            print(f"❌ Failed: {exc}")

                    elif args.clear_mcp_connection:
                        slug = args.clear_mcp_connection.strip()
                        ok = await remove_mcp_connection(session, org_id, employee_id, slug)
                        if ok:
                            print(f"🗑️  MCP connection '{slug}' revoked.")
                        else:
                            print(f"⚠️  No active connection found for '{slug}'.")

                    elif args.mcp_status:
                        connectors = await list_mcp_connectors(session, org_id, employee_id)
                        print(f"\n🔌 MCP Connection Status for employee {employee_id}\n")
                        if not connectors:
                            print("   (no connectors registered)\n")
                        else:
                            for c in connectors:
                                icon = "✅" if c["is_connected"] else "⬜"
                                print(f"  {icon} {c['name']} ({c['slug']})")
                                print(f"     Auth type     : {c['auth_type']}")
                                print(f"     Connected     : {c['is_connected']}")
                                print(f"     Status        : {c['connection_status']}")
                                if c.get("connection_id"):
                                    print(f"     Connection ID : {c['connection_id']}")
                                if c.get("scopes"):
                                    print(f"     OAuth scopes  : {', '.join(c['scopes'])}")
                                if c.get("requires_manual_approval"):
                                    print(f"     ⚠️  Requires vendor approval")
                                print()
            finally:
                await engine.dispose()

        asyncio.run(_mcp_op())
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
