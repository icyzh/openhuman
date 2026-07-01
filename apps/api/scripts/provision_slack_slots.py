"""Provision Slack app slots for the per-employee identity pool (Pattern A).

Creates *N* Slack app slots with encrypted credentials ready for employee
assignment.  The script supports two modes:

**Manual mode (default):** Prompts the operator for each slot's credentials
after they create the app in the Slack UI / manifest wizard.

**Automated mode:**  Uses ``SLACK_CONFIG_TOKEN`` from the environment to call
Slack's ``apps.manifest.create`` API directly.  Respects the ~1/min rate limit.

Usage::

    python scripts/provision_slack_slots.py --count 10
    python scripts/provision_slack_slots.py --count 5 --auto

Environment variables required in all modes:

    DATABASE_URL         — asyncpg connection string
    ENCRYPTION_KEY       — 64-hex-char AES-256 key

Automated mode also needs:

    SLACK_CONFIG_TOKEN   — xoxe-... config token with apps:write scope
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

# Ensure the api app package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings
from app.gateway.slack_app_provisioning import insert_slot


def _make_session_factory():
    database_url = os.getenv("DATABASE_URL", settings.database_url)
    engine = create_async_engine(database_url)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _manual_provision(count: int, session_factory) -> None:
    """Prompt the operator for each slot's credentials."""
    print(f"Provisioning {count} slot(s) in manual mode.\n")
    for i in range(1, count + 1):
        print(f"--- Slot {i}/{count} ---")
        print("1. Go to https://api.slack.com/apps and create a new app from")
        print("   the manifest at apps/api/slack_manifest.json")
        print("2. Enable Socket Mode, generate an app-level token (connections:write)")
        print()
        slack_app_id = input("  Slack App ID (e.g. A012ABCD): ").strip()
        client_id = input("  Client ID: ").strip()
        client_secret = input("  Client Secret (xoxb-...): ").strip()
        app_token = input("  App Token (xapp-...): ").strip()

        if not all([slack_app_id, client_id, client_secret, app_token]):
            print("  ⚠  Skipping — all fields required.\n")
            continue

        async with session_factory() as db:
            slot = await insert_slot(
                db,
                slack_app_id=slack_app_id,
                client_id=client_id,
                client_secret=client_secret,
                app_token=app_token,
            )
            await db.commit()
            print(f"  ✓  Slot {slot.id} created ({slack_app_id})\n")


async def _auto_provision(count: int, session_factory) -> None:
    """Create apps via Slack's manifest API (Phase 2 path).

    Respects the ~1/min rate limit by sleeping 65 seconds between calls.
    Requires ``SLACK_CONFIG_TOKEN`` to be set.
    """
    config_token = os.getenv("SLACK_CONFIG_TOKEN", settings.slack_config_token)
    if not config_token:
        print("ERROR: SLACK_CONFIG_TOKEN must be set for automated mode.", file=sys.stderr)
        sys.exit(1)

    print(f"Provisioning {count} slot(s) via Slack manifest API.\n")
    print("⚠  Note: Manifest API returns client_id + client_secret only.")
    print("   You must still manually generate app-level tokens (xapp-)")
    print("   in the Slack app settings for each created app.\n")

    # Lazy import — only needed in auto mode
    from slack_sdk.web.async_client import AsyncWebClient

    client = AsyncWebClient(token=config_token)

    for i in range(1, count + 1):
        print(f"--- Slot {i}/{count} ---")
        app_name = f"OpenHuman Agent {i}"
        try:
            # Load and parameterize the manifest
            from app.gateway.slack_app_provisioning import build_manifest
            manifest = build_manifest(app_name)

            response = await client.apps_manifest_create(manifest=manifest)
            if not response.get("ok"):
                print(f"  ✗  Slack API error: {response.get('error', 'unknown')}")
                continue

            slack_app_id = response["app_id"]
            client_id = response["credentials"]["client_id"]
            client_secret = response["credentials"]["client_secret"]

            print(f"  App created: {slack_app_id}")
            print(f"  → Go to https://api.slack.com/apps/{slack_app_id}/general")
            print(f"    and generate an app-level token (connections:write) for Socket Mode.")

            app_token = input("  App Token (xapp-...): ").strip()
            if not app_token:
                print("  ⚠  Skipping — app token required.\n")
                continue

            async with session_factory() as db:
                slot = await insert_slot(
                    db,
                    slack_app_id=slack_app_id,
                    client_id=client_id,
                    client_secret=client_secret,
                    app_token=app_token,
                )
                await db.commit()
                print(f"  ✓  Slot {slot.id} created ({slack_app_id})\n")

        except Exception as exc:
            print(f"  ✗  Error: {exc}")
            continue

        # Respect 1/min rate limit with a generous 65s delay
        if i < count:
            print("  … waiting 65s for rate limit …")
            time.sleep(65)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Provision Slack app slots for per-employee identity pool."
    )
    parser.add_argument(
        "--count", type=int, default=1, help="Number of slots to provision (default: 1)"
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Use Slack manifest API instead of full manual entry",
    )
    args = parser.parse_args()

    if args.count < 1:
        print("ERROR: --count must be >= 1", file=sys.stderr)
        sys.exit(1)

    session_factory = _make_session_factory()

    if args.auto:
        await _auto_provision(args.count, session_factory)
    else:
        await _manual_provision(args.count, session_factory)

    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
