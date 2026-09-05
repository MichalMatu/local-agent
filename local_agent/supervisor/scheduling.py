"""Pure scheduling policy helpers for the bounded-parallel supervisor."""

from __future__ import annotations

import os
from dataclasses import dataclass

from local_agent.supervisor import policy as supervisor_policy

MAX_WORKERS_ENV = "LOCAL_AGENT_MAX_PARALLEL_WORKERS"
DEFAULT_MAX_WORKERS = 1
MAX_MAX_WORKERS = 3
RESOURCE_RETRY_BACKOFF_SECONDS = (2.0, 5.0, 10.0, 30.0, 60.0)
WORKER_FAILURE_RETRY_BASE_SECONDS = 2.0
WORKER_FAILURE_RETRY_MAX_SECONDS = 300.0
CONTROL_DEFER_RETRY_BASE_SECONDS = 2.0
CONTROL_DEFER_RETRY_MAX_SECONDS = 15.0
CONTROL_LEASE_BUSY_DRAIN_ATTEMPTS = 6
REPEATED_FAILURE_LOG_SECONDS = 60.0
OPERATOR_IDLE_HEARTBEAT_SECONDS = 300.0
LOCAL_LOG_MAINTENANCE_SECONDS = 30.0


@dataclass
class RepositorySchedule:
    last_poll_at: float | None = None
    last_activity_at: float | None = None
    retry_not_before: float = 0.0
    consecutive_failures: int = 0
    last_failure_code: int | None = None
    last_failure_log_at: float | None = None
    resource_deferrals: int = 0


def format_operator_idle_summary(repository_count: int, max_workers: int) -> str:
    noun = "repository" if repository_count == 1 else "repositories"
    return f"IDLE no active task ({repository_count} {noun}); max_workers={max_workers}"


def operator_idle_log_due(last_idle_log_at: float | None, now: float) -> bool:
    return last_idle_log_at is None or now - last_idle_log_at >= OPERATOR_IDLE_HEARTBEAT_SECONDS


def local_log_maintenance_due(last_maintenance_at: float | None, now: float) -> bool:
    return (
        last_maintenance_at is None
        or now - last_maintenance_at >= LOCAL_LOG_MAINTENANCE_SECONDS
    )


def bounded_retry_seconds(attempt: int, *, base: float, maximum: float) -> float:
    if attempt <= 0:
        return 0.0
    return min(maximum, base * (2 ** min(attempt - 1, 16)))


def resource_retry_seconds(attempt: int) -> float:
    if attempt <= 0:
        return 0.0
    index = min(attempt - 1, len(RESOURCE_RETRY_BACKOFF_SECONDS) - 1)
    return RESOURCE_RETRY_BACKOFF_SECONDS[index]


def worker_failure_retry_seconds(attempt: int) -> float:
    return bounded_retry_seconds(
        attempt,
        base=WORKER_FAILURE_RETRY_BASE_SECONDS,
        maximum=WORKER_FAILURE_RETRY_MAX_SECONDS,
    )


def control_defer_retry_seconds(attempt: int) -> float:
    return bounded_retry_seconds(
        attempt,
        base=CONTROL_DEFER_RETRY_BASE_SECONDS,
        maximum=CONTROL_DEFER_RETRY_MAX_SECONDS,
    )


def control_lease_busy_should_force_drain(attempt: int) -> bool:
    return attempt >= CONTROL_LEASE_BUSY_DRAIN_ATTEMPTS


def repeated_failure_log_due(last_log_at: float | None, now: float) -> bool:
    return last_log_at is None or now - last_log_at >= REPEATED_FAILURE_LOG_SECONDS


def reset_worker_failure_state(schedule: RepositorySchedule) -> None:
    schedule.consecutive_failures = 0
    schedule.last_failure_code = None
    schedule.last_failure_log_at = None


def reset_resource_deferral_state(schedule: RepositorySchedule) -> None:
    schedule.resource_deferrals = 0


def resolve_max_workers(cli_value: int | None) -> int:
    raw: object = cli_value if cli_value is not None else os.environ.get(
        MAX_WORKERS_ENV,
        str(DEFAULT_MAX_WORKERS),
    )
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"invalid {MAX_WORKERS_ENV}: {raw!r}") from None
    if value < 1 or value > MAX_MAX_WORKERS:
        raise ValueError(f"{MAX_WORKERS_ENV} must be 1..{MAX_MAX_WORKERS}, got {value}")
    return value


def repository_due(schedule: RepositorySchedule, now: float) -> bool:
    if schedule.retry_not_before > 0.0:
        return now >= schedule.retry_not_before
    _, interval = supervisor_policy.adaptive_poll_tier(schedule.last_activity_at, now)
    return supervisor_policy.interval_due(schedule.last_poll_at, interval, now)


def next_repository_delay(
    schedules: dict[str, RepositorySchedule],
    repository_ids: list[str],
    now: float,
) -> float:
    """Return the next due delay without depending on repository object shape."""
    if not repository_ids:
        return supervisor_policy.POLL_SECONDS
    delays: list[float] = []
    for repository_id in repository_ids:
        schedule = schedules.setdefault(repository_id, RepositorySchedule())
        if schedule.retry_not_before > 0.0:
            delays.append(max(0.0, schedule.retry_not_before - now))
            continue
        _, interval = supervisor_policy.adaptive_poll_tier(schedule.last_activity_at, now)
        delays.append(supervisor_policy.interval_remaining(schedule.last_poll_at, interval, now))
    return min(delays)
