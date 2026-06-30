import asyncio
import logging
from uuid import UUID

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from app.core.config import settings
from app.core.database import async_session_factory
from app.employees.models import Employee
from app.employees.service import (
    decrypt_discord_token,
    decrypt_slack_token,
    get_active_employees_with_tokens,
)
from app.gateway.discord_bot import EmployeeDiscordBot
from app.gateway.slack_bot import EmployeeSlackBot

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
        self.discord_bots: dict[UUID, tuple[EmployeeDiscordBot, asyncio.Task[None]]] = {}
        self.slack_bots: dict[UUID, tuple[EmployeeSlackBot, AsyncSocketModeHandler]] = {}
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

        # Shut down active Discord bot tasks
        for emp_id in list(self.discord_bots.keys()):
            await self._stop_discord_bot(emp_id)

        # Shut down active Slack bot websocket connections
        for emp_id in list(self.slack_bots.keys()):
            await self._stop_slack_bot(emp_id)

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

        active_emp_ids = {emp.id for emp in active_employees}

        # Stop bots for employees that are no longer active / present
        for emp_id in list(self.discord_bots.keys()):
            if emp_id not in active_emp_ids:
                await self._stop_discord_bot(emp_id)

        for emp_id in list(self.slack_bots.keys()):
            if emp_id not in active_emp_ids:
                await self._stop_slack_bot(emp_id)

        # Provision / update bots for active employees
        for emp in active_employees:
            await self._reconcile_discord_bot(emp)
            await self._reconcile_slack_bot(emp)

    # ------------------------------------------------------------------
    # Per-employee reconciliation
    # ------------------------------------------------------------------

    async def _reconcile_discord_bot(self, emp: Employee) -> None:
        """Start, stop, or leave alone the Discord bot for *emp*.

        Handles bad / revoked tokens gracefully so one broken employee
        cannot crash the refresh loop or prevent other bots from running.
        """
        try:
            token = decrypt_discord_token(emp)
        except Exception:
            logger.exception("Failed to decrypt Discord token for employee %s", emp.id)
            # If we can't decrypt, make sure no bot is running for this employee
            if emp.id in self.discord_bots:
                await self._stop_discord_bot(emp.id)
            return

        if token:
            if emp.id not in self.discord_bots:
                await self._start_discord_bot(emp.id, token)
        else:
            if emp.id in self.discord_bots:
                await self._stop_discord_bot(emp.id)

    async def _reconcile_slack_bot(self, emp: Employee) -> None:
        """Start, stop, or leave alone the Slack bot for *emp*.

        Socket Mode requires the global ``SLACK_APP_TOKEN`` in addition to
        the per-employee bot token.
        """
        try:
            token = decrypt_slack_token(emp)
        except Exception:
            logger.exception("Failed to decrypt Slack token for employee %s", emp.id)
            if emp.id in self.slack_bots:
                await self._stop_slack_bot(emp.id)
            return

        if token and settings.slack_app_token:
            if emp.id not in self.slack_bots:
                await self._start_slack_bot(emp.id, token)
        else:
            if emp.id in self.slack_bots:
                await self._stop_slack_bot(emp.id)

    # ------------------------------------------------------------------
    # Discord bot start / stop (with retry)
    # ------------------------------------------------------------------

    async def _start_discord_bot(self, emp_id: UUID, token: str) -> None:
        """Create and launch a Discord client for *emp_id*.

        Retries with exponential backoff on ``LoginFailure`` (bad token)
        and transient network errors.  Gives up after ``_MAX_RETRIES``
        attempts so that a permanently-bad token doesn't spin forever.
        """
        for attempt in range(1, _MAX_RETRIES + 1):
            bot = EmployeeDiscordBot(employee_id=emp_id)
            task = asyncio.create_task(bot.start(token))
            self.discord_bots[emp_id] = (bot, task)
            logger.info(
                "Started Discord bot for employee %s (attempt %d/%d)",
                emp_id, attempt, _MAX_RETRIES,
            )

            # Wait a short time to see if the login succeeds or fails fast
            try:
                done, _ = await asyncio.wait([task], timeout=15)
            except Exception:
                done = set()

            if done:
                # Task finished — check for exceptions
                exc = task.exception()
                if exc is None:
                    # Login succeeded and the client is running (task only
                    # completes on shutdown, so this is unusual unless the
                    # client exits immediately after login — treat as
                    # transient).
                    logger.info("Discord bot for employee %s logged in successfully", emp_id)
                    return
                else:
                    logger.error(
                        "Discord bot for employee %s failed: %s", emp_id, exc,
                    )
            else:
                # Still running after timeout — login probably succeeded
                # (discord.Client.start blocks until disconnection).
                logger.info(
                    "Discord bot for employee %s appears healthy (attempt %d)",
                    emp_id, attempt,
                )
                return

            # Clean up failed attempt before retrying
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
    # Slack bot start / stop
    # ------------------------------------------------------------------

    async def _start_slack_bot(self, emp_id: UUID, token: str) -> None:
        """Create and connect a Slack Socket Mode handler for *emp_id*."""
        bot = EmployeeSlackBot(employee_id=emp_id, bot_token=token)
        handler = AsyncSocketModeHandler(bot.app, settings.slack_app_token)
        try:
            await handler.connect_async()
        except Exception:
            logger.exception("Failed to connect Slack Socket Mode for employee %s", emp_id)
            return
        self.slack_bots[emp_id] = (bot, handler)
        logger.info("Started Slack Socket Mode connection for employee %s", emp_id)

    async def _stop_slack_bot(self, emp_id: UUID) -> None:
        entry = self.slack_bots.pop(emp_id, None)
        if entry is None:
            return
        _bot, handler = entry
        try:
            await handler.close_async()
        except Exception:
            logger.exception(
                "Error closing Slack Socket Mode connection for employee %s", emp_id
            )
        logger.info("Stopped Slack Socket Mode connection for employee %s", emp_id)
