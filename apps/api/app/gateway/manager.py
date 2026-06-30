"""
Bot Gateway Manager — lifecycle for Discord and Slack bot connections.

Runs a background refresh loop that polls the database for active employees
and reconciles the set of running bot clients.

**Slack:** One :class:`WorkspaceSlackBot` per unique bot token, not per
employee.  Multiple employees in the same Slack workspace share one token
(and therefore one Socket Mode connection).  The bot routes each incoming
message to the correct employee via ``channel_assignments``.
"""

import asyncio
import logging
from collections import defaultdict
from uuid import UUID

from app.core.config import settings
from app.core.database import async_session_factory
from app.employees.models import Employee
from app.employees.service import (
    decrypt_discord_token,
    decrypt_slack_token,
    get_active_employees_with_tokens,
)
from app.gateway.discord_bot import EmployeeDiscordBot
from app.gateway.slack_bot import WorkspaceSlackBot

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retry / backoff constants
# ---------------------------------------------------------------------------

_MAX_RETRIES = 3
_BASE_DELAY = 10  # seconds — exponential backoff: 10, 20, 40


class BotGatewayManager:
    """Manages continuous background lifecycle of Discord/Slack bots for
    active AI employees.

    The refresh loop polls the database every 60 seconds and reconciles the
    set of running bot clients with the active employee rows.
    """

    def __init__(self) -> None:
        # Discord: one client per employee (each has their own token)
        self.discord_bots: dict[UUID, tuple[EmployeeDiscordBot, asyncio.Task[None]]] = {}

        # Slack: one WorkspaceSlackBot per unique bot token
        # Keyed by bot token string so duplicate tokens share one connection.
        self.slack_bots: dict[str, WorkspaceSlackBot] = {}

        self.refresh_task: asyncio.Task[None] | None = None
        self.running: bool = False

    # ------------------------------------------------------------------
    # Public lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the background refresh loop to poll active employee bots."""
        self.running = True
        self.refresh_task = asyncio.create_task(self._refresh_loop())
        logger.info("Bot Gateway Manager started.")

    async def stop(self) -> None:
        """Stop all running bots and cancel the refresh loop."""
        self.running = False
        if self.refresh_task:
            self.refresh_task.cancel()
            try:
                await self.refresh_task
            except asyncio.CancelledError:
                pass

        # Shut down Discord bots
        for emp_id in list(self.discord_bots.keys()):
            await self._stop_discord_bot(emp_id)

        # Shut down Slack bots
        for token in list(self.slack_bots.keys()):
            await self._stop_slack_bot(token)

        logger.info("Bot Gateway Manager stopped.")

    # ------------------------------------------------------------------
    # Refresh loop
    # ------------------------------------------------------------------

    async def _refresh_loop(self) -> None:
        while self.running:
            try:
                await self.refresh_bots()
            except Exception:
                logger.exception("Unhandled error in gateway refresh loop")
            await asyncio.sleep(60)

    async def refresh_bots(self) -> None:
        """Poll database and synchronize running bots with active DB rows."""
        async with async_session_factory() as db:
            active_employees = await get_active_employees_with_tokens(db)

        # --- Discord (unchanged: one bot per employee) ------------------------
        active_emp_ids = {emp.id for emp in active_employees}

        for emp_id in list(self.discord_bots.keys()):
            if emp_id not in active_emp_ids:
                await self._stop_discord_bot(emp_id)

        for emp in active_employees:
            await self._reconcile_discord_bot(emp)

        # --- Slack (new: group by token, one bot per unique token) ------------
        await self._reconcile_slack_bots(active_employees)

    # ------------------------------------------------------------------
    # Discord — per-employee (unchanged)
    # ------------------------------------------------------------------

    async def _reconcile_discord_bot(self, emp: Employee) -> None:
        """Start, stop, or leave alone the Discord bot for *emp*."""
        try:
            token = decrypt_discord_token(emp)
        except Exception:
            logger.exception("Failed to decrypt Discord token for employee %s", emp.id)
            if emp.id in self.discord_bots:
                await self._stop_discord_bot(emp.id)
            return

        if token:
            if emp.id not in self.discord_bots:
                await self._start_discord_bot(emp.id, token)
        else:
            if emp.id in self.discord_bots:
                await self._stop_discord_bot(emp.id)

    async def _start_discord_bot(self, emp_id: UUID, token: str) -> None:
        """Create and launch a Discord client for *emp_id*.

        Retries with exponential backoff on transient errors.
        """
        for attempt in range(1, _MAX_RETRIES + 1):
            bot = EmployeeDiscordBot(employee_id=emp_id)
            task = asyncio.create_task(bot.start(token))
            self.discord_bots[emp_id] = (bot, task)
            logger.info(
                "Started Discord bot for employee %s (attempt %d/%d)",
                emp_id, attempt, _MAX_RETRIES,
            )

            try:
                done, _ = await asyncio.wait([task], timeout=15)
            except Exception:
                done = set()

            if done:
                exc = task.exception()
                if exc is None:
                    logger.info("Discord bot for employee %s logged in successfully", emp_id)
                    return
                else:
                    logger.error(
                        "Discord bot for employee %s failed: %s", emp_id, exc,
                    )
            else:
                logger.info(
                    "Discord bot for employee %s appears healthy (attempt %d)",
                    emp_id, attempt,
                )
                return

            await self._stop_discord_bot(emp_id)
            if attempt < _MAX_RETRIES:
                delay = _BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "Retrying Discord bot for employee %s in %ds", emp_id, delay,
                )
                await asyncio.sleep(delay)

        logger.error(
            "Giving up on Discord bot for employee %s after %d attempts",
            emp_id, _MAX_RETRIES,
        )

    async def _stop_discord_bot(self, emp_id: UUID) -> None:
        entry = self.discord_bots.pop(emp_id, None)
        if entry is None:
            return
        bot, task = entry
        try:
            await bot.close()
        except Exception:
            logger.exception("Error closing Discord client for employee %s", emp_id)
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Discord task error during shutdown for employee %s", emp_id)
        logger.info("Stopped Discord bot for employee %s", emp_id)

    # ------------------------------------------------------------------
    # Slack — one bot per unique token (refactored)
    # ------------------------------------------------------------------

    async def _reconcile_slack_bots(self, active_employees: list[Employee]) -> None:
        """Group active employees by decrypted Slack token and ensure exactly
        one :class:`WorkspaceSlackBot` is running per unique token.

        Employees whose token cannot be decrypted are silently skipped
        (and any existing bot for their *old* token is unaffected — it will
        be torn down when the token is no longer in use by anyone).
        """
        if not settings.slack_app_token:
            # No app-level token configured → shut down all Slack bots
            for token in list(self.slack_bots.keys()):
                await self._stop_slack_bot(token)
            return

        # Group employees by decrypted bot token
        token_to_employees: dict[str, list[UUID]] = defaultdict(list)
        for emp in active_employees:
            try:
                token = decrypt_slack_token(emp)
            except Exception:
                logger.exception(
                    "Failed to decrypt Slack token for employee %s — skipping", emp.id,
                )
                continue
            if token:
                token_to_employees[token].append(emp.id)

        active_tokens = set(token_to_employees.keys())

        # Stop bots for tokens that are no longer present
        for token in list(self.slack_bots.keys()):
            if token not in active_tokens:
                await self._stop_slack_bot(token)

        # Start / update bots for current tokens
        for token, emp_ids in token_to_employees.items():
            if token in self.slack_bots:
                # Bot already running — update its employee list in case
                # employees were added/removed for this token
                existing = self.slack_bots[token]
                existing.employee_ids = emp_ids
                existing._employee_id_set = frozenset(emp_ids)
            else:
                await self._start_slack_bot(token, emp_ids)

    async def _start_slack_bot(
        self, token: str, employee_ids: list[UUID],
    ) -> None:
        """Create and connect a single Socket Mode connection for *token*.

        All *employee_ids* share this token (they are in the same Slack
        workspace).  The bot will route messages to the correct employee
        based on channel assignments.
        """
        if not settings.slack_app_token:
            logger.warning("Cannot start Slack bot — SLACK_APP_TOKEN is not set.")
            return

        bot = WorkspaceSlackBot(
            bot_token=token,
            app_token=settings.slack_app_token,
            employee_ids=employee_ids,
        )
        try:
            await bot.connect()
        except Exception:
            logger.exception(
                "Failed to connect Slack Socket Mode (token=...%s)", token[-8:],
            )
            return

        self.slack_bots[token] = bot
        logger.info(
            "Started Slack bot for token ...%s (%d employees)",
            token[-8:], len(employee_ids),
        )

    async def _stop_slack_bot(self, token: str) -> None:
        """Disconnect and remove the Slack bot for *token*."""
        bot = self.slack_bots.pop(token, None)
        if bot is None:
            return
        await bot.disconnect()
        logger.info("Stopped Slack bot for token ...%s", token[-8:])
