#!/usr/bin/env python3
"""
Configure a Slack App slot with real credentials in the database.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from uuid import UUID

# Path setup
_this_dir = Path(__file__).resolve().parent
_api_dir = _this_dir.parent
if str(_api_dir) not in sys.path:
    sys.path.insert(0, str(_api_dir))

# Load .env
_env_path = _api_dir / ".env"
if _env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_path)

# Register models
import app.auth.models
import app.organizations.models
import app.employees.models
import app.gateway.models
import app.channel_assignments.models
import app.documents.models
import app.agent.tools.mcp.models

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings
from app.core.security import encrypt_token
from app.gateway.models import SlackAppSlot

async def main():
    parser = argparse.ArgumentParser(description="Configure a Slack App slot with real credentials.")
    parser.add_argument("--db-path", type=str, default=settings.database_url, help="Database connection URL")
    parser.add_argument("--slot-id", type=str, help="UUID of the slot to configure")
    parser.add_argument("--slack-app-id", type=str, help="Slack App ID (e.g. A012345)")
    parser.add_argument("--client-id", type=str, help="Slack Client ID")
    parser.add_argument("--client-secret", type=str, help="Slack Client Secret")
    parser.add_argument("--app-token", type=str, help="Slack App-level Token (xapp-...)")
    args = parser.parse_args()

    encryption_key = os.getenv("ENCRYPTION_KEY", settings.encryption_key)
    if not encryption_key or len(encryption_key) != 64:
        print("ERROR: ENCRYPTION_KEY must be a 64-character hex string in the environment or .env.", file=sys.stderr)
        sys.exit(1)

    url = args.db_path
    connect_args = {}
    if url.startswith("postgresql+asyncpg"):
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_cache_size"] = 0

    engine = create_async_engine(url, connect_args=connect_args)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        # If slot_id is not provided, list all slots and let the user select
        if not args.slot_id:
            res = await session.execute(select(SlackAppSlot))
            slots = res.scalars().all()
            if not slots:
                print("No slots found in database. Provision slots first using test CLI.")
                await engine.dispose()
                return

            print("Available Slots:")
            for i, slot in enumerate(slots):
                employee_name = "None"
                if slot.employee_id:
                    from app.employees.models import Employee
                    emp = await session.get(Employee, slot.employee_id)
                    employee_name = emp.name if emp else "Unknown"
                print(f"[{i}] ID: {slot.id} | App ID: {slot.slack_app_id} | Status: {slot.status} | Assigned to: {employee_name}")
            
            try:
                choice = int(input("\nSelect slot index to configure: "))
                selected_slot = slots[choice]
            except (ValueError, IndexError):
                print("Invalid selection.")
                await engine.dispose()
                return
        else:
            try:
                slot_uuid = UUID(args.slot_id)
            except ValueError:
                print(f"Invalid slot UUID: {args.slot_id}")
                await engine.dispose()
                return
            selected_slot = await session.get(SlackAppSlot, slot_uuid)
            if not selected_slot:
                print(f"Slot {args.slot_id} not found.")
                await engine.dispose()
                return

        print(f"\nConfiguring Slot {selected_slot.id}...")
        slack_app_id = args.slack_app_id or input(f"Slack App ID [{selected_slot.slack_app_id}]: ").strip() or selected_slot.slack_app_id
        client_id = args.client_id or input(f"Client ID [{selected_slot.client_id}]: ").strip() or selected_slot.client_id
        
        client_secret = args.client_secret or input("Client Secret (leave empty to keep existing): ").strip()
        app_token = args.app_token or input("App Token (xapp-...) (leave empty to keep existing): ").strip()

        selected_slot.slack_app_id = slack_app_id
        selected_slot.client_id = client_id
        
        if client_secret:
            selected_slot.client_secret_enc = encrypt_token(client_secret)
        if app_token:
            selected_slot.app_token_enc = encrypt_token(app_token)

        await session.commit()
        print(f"✓ Slot {selected_slot.id} updated successfully!")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
