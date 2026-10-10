"""Explicit token-backed, pinned, GET-only Mac evidence reader.

Authenticated status reads share the same synchronized 52-request,
8 MiB and 120-second session acceptance budgets as anonymous public reads.
This module cannot issue a write, follow redirects or select another host.
"""

from __future__ import annotations

from local_agent.conversation.github_fabric_agent_control_public_rest import (
    PublicAgentControlReadOnlyREST,
)


class AuthenticatedAgentControlReadOnlyREST(PublicAgentControlReadOnlyREST):
    """Fixed public-repository evidence GET with an explicitly supplied token."""

    def __init__(self, token: str) -> None:
        if (
            type(token) is not str
            or not 1 <= len(token) <= 4096
            or token != token.strip()
            or any(ord(char) < 33 or ord(char) > 126 for char in token)
        ):
            raise PermissionError("Agent-control authenticated read needs a valid explicit token")
        self._token = token
        super().__init__()

    def _request_headers(self) -> dict[str, str]:
        return {
            **super()._request_headers(),
            "Authorization": f"Bearer {self._token}",
        }
