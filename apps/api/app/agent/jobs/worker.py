"""Background worker pool that polls ``agent_jobs`` and executes work.

This reuses the same asyncio background-task pattern as the gateway manager's
60-second refresh loop.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from app.agent.jobs.models import AgentJob
from app.agent.jobs.queue import claim_next_job
from app.agent.jobs.runner import run_job
from app.core.config import settings
from app.core.database import async_session_factory

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Module-level worker singleton — used by cancel_background_task tool
# to reach the running worker's _running_tasks dict.
# ------------------------------------------------------------------

_active_worker: AgentJobWorker | None = None


def get_active_worker() -> AgentJobWorker | None:
    """Return the currently running :class:`AgentJobWorker`, or ``None``."""
    return _active_worker


def set_active_worker(worker: AgentJobWorker | None) -> None:
    """Set (or clear) the module-level worker singleton.

    Called by :class:`BotGatewayManager` during start / stop.
    """
    global _active_worker
    _active_worker = worker


class AgentJobWorker:
    """Polls the ``agent_jobs`` table and executes pending work.

    On startup it runs a recovery pass that marks any jobs left in
    ``running`` or ``awaiting_approval`` as ``failed`` (the previous
    worker died before completing them).
    """

    def __init__(self) -> None:
        self._tasks: list[asyncio.Task[None]] = []
        self._running_tasks: dict[str, asyncio.Task[None]] = {}  # job_id -> Task
        self.running: bool = False

    # ------------------------------------------------------------------
    # Public lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the worker pool and run recovery."""
        self.running = True

        await self._recover()

        for i in range(settings.agent_worker_concurrency):
            task = asyncio.create_task(self._poll_loop(i), name=f"agent-worker-{i}")
            self._tasks.append(task)

        logger.info(
            "AgentJobWorker started — %d workers, poll interval %.1fs",
            settings.agent_worker_concurrency,
            settings.agent_job_poll_interval_seconds,
        )

    async def stop(self) -> None:
        """Cancel all worker loops and wait for running jobs to finish."""
        self.running = False

        # Cancel poll loops
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()

        # Wait for in-flight jobs (give them a grace period)
        if self._running_tasks:
            logger.info(
                "Waiting for %d in-flight job(s) to finish...",
                len(self._running_tasks),
            )
            done, pending = await asyncio.wait(
                list(self._running_tasks.values()), timeout=30.0,
            )
            for task in pending:
                job_id = next(
                    (k for k, v in self._running_tasks.items() if v is task), None,
                )
                logger.warning("Cancelling in-flight job %s during shutdown", job_id)
                task.cancel()
        self._running_tasks.clear()

        logger.info("AgentJobWorker stopped.")

    # ------------------------------------------------------------------
    # Recovery
    # ------------------------------------------------------------------

    async def _recover(self) -> None:
        """Mark any stranded in-flight jobs as failed."""
        async with async_session_factory() as db:
            from sqlalchemy import update

            stmt = (
                update(AgentJob)
                .where(AgentJob.status.in_(["running", "awaiting_approval"]))
                .values(
                    status="failed",
                    error="Worker restarted — job was stranded",
                    finished_at=datetime.now(UTC),
                )
            )
            result = await db.execute(stmt)
            await db.commit()
            count = result.rowcount
            if count:
                logger.warning("Recovery: marked %d stranded job(s) as failed", count)

    # ------------------------------------------------------------------
    # Poll loop
    # ------------------------------------------------------------------

    async def _poll_loop(self, worker_index: int) -> None:
        """Continuously poll for and execute pending jobs."""
        while self.running:
            try:
                async with async_session_factory() as db:
                    job = await claim_next_job(db)
                    if job is not None:
                        task = asyncio.create_task(
                            self._execute_job(job),
                            name=f"agent-job-{job.id}",
                        )
                        self._running_tasks[str(job.id)] = task
            except Exception:
                logger.exception("Error in worker poll loop %d", worker_index)

            await asyncio.sleep(settings.agent_job_poll_interval_seconds)

    async def _execute_job(self, job: AgentJob) -> None:
        """Run a single job in its own DB session and clean up tracking."""
        job_id_str = str(job.id)
        try:
            async with async_session_factory() as db:
                # Re-attach job to this session
                merged = await db.merge(job)
                # Refresh to get latest DB state — the job may have been
                # cancelled via the cancel_background_task tool between
                # claim and execution start.
                await db.refresh(merged)
                if merged.status == "cancelled":
                    logger.info("Job %s was cancelled before execution — skipping", job.id)
                    merged.finished_at = datetime.now(UTC)
                    await db.commit()
                    return
                await run_job(merged)
                # Persist final status
                if merged.status not in ("succeeded", "failed", "cancelled"):
                    merged.status = "succeeded"
                merged.finished_at = datetime.now(UTC)
                await db.commit()
                logger.info(
                    "Job %s finished with status=%s", job.id, merged.status,
                )
        except asyncio.CancelledError:
            async with async_session_factory() as db:
                merged = await db.merge(job)
                merged.status = "cancelled"
                merged.error = "Job was cancelled"
                merged.finished_at = datetime.now(UTC)
                await db.commit()
            logger.info("Job %s cancelled", job.id)
        except Exception:
            logger.exception("Job %s failed with unhandled exception", job.id)
            async with async_session_factory() as db:
                merged = await db.merge(job)
                merged.status = "failed"
                merged.error = "Unhandled exception during job execution"
                merged.finished_at = datetime.now(UTC)
                await db.commit()
        finally:
            self._running_tasks.pop(job_id_str, None)

    # ------------------------------------------------------------------
    # Cancellation (Phase 2 / Phase 3)
    # ------------------------------------------------------------------

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job's asyncio Task if it is still in-flight.

        Returns ``True`` if a running task was found and cancelled,
        ``False`` if the job was not currently executing.
        """
        task = self._running_tasks.get(job_id)
        if task is not None and not task.done():
            task.cancel()
            logger.info("Cancelled in-flight asyncio task for job %s", job_id)
            return True
        return False
