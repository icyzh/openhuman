"""Async job queue for background agent tool execution.

The job queue decouples heavy tool execution (PDF analysis, knowledge-base
search, etc.) from the agent graph so that Slack Socket Mode event handlers
never block for minutes.
"""

from app.agent.jobs.models import AgentJob
from app.agent.jobs.queue import (
    cancel_active_jobs_for_thread,
    claim_next_job,
    enqueue_job,
    get_active_jobs_for_thread,
    get_job,
    is_cancel_intent,
)
from app.agent.jobs.runner import run_job
from app.agent.jobs.worker import AgentJobWorker

__all__ = [
    "AgentJob",
    "AgentJobWorker",
    "cancel_active_jobs_for_thread",
    "claim_next_job",
    "enqueue_job",
    "get_active_jobs_for_thread",
    "get_job",
    "is_cancel_intent",
    "run_job",
]
