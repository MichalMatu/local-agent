from __future__ import annotations

import local_agent.foundation.storage as storage
import local_agent.daemon.service as agentd
from local_agent.repository.context import RepositoryContext


def sync_control_quietly() -> None:
    "Run bounded routine control-branch sync without low-level Git output."
    storage.sync_control(agentd.core)


def bind_supervisor_control(
    repository: RepositoryContext,
    *,
    daemon_version: str,
) -> None:
    "Bind one repository checkout as the global control source."
    agentd.core.CONTROL = repository.control
    agentd.core.CONTROL_BRANCH = repository.control_branch
    agentd.DAEMON_VERSION = daemon_version
