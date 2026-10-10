"""Anonymous, strictly scoped GET-only GitHub reader for public agent-control evidence.

This reader can access only public GitHub API resources under the hard-coded
repository and an exact commit/tree/task/result identity. It has no token,
write capability, redirects, browser or local task execution authority.
"""

from __future__ import annotations

import json
import re
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from local_agent.conversation import github_fabric_github as git

_API_ROOT = "https://api.github.com/repos/MichalMatu/local-agent"
_MAX_RESPONSE_BYTES = 512 * 1024
_REQUEST_TIMEOUT_SECONDS = 15
_MAX_SESSION_SECONDS = 120.0
_MAX_SESSION_REQUESTS = 52  # 2 tree/commit + up to 16 times 3 recovery GETs
_MAX_SESSION_BYTES = 8 * 1024 * 1024
_SHA = r"[0-9a-f]{40}"
_TASK_ID = r"[A-Za-z0-9._-]{1,200}"
_SCOPED_GET = (
    re.compile(rf"/git/commits/{_SHA}\Z"),
    re.compile(rf"/git/trees/{_SHA}\?recursive=1\Z"),
    re.compile(rf"/contents/\.agent/(?:tasks|results)/{_TASK_ID}\.json\?ref={_SHA}\Z"),
)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> None:
        return None


class PublicAgentControlReadOnlyREST:
    """Read **public** pinned GitHub evidence without implicit credentials.

    All requests from one instance share a time, count and byte budget.
    Neither HTTP failure nor partial data consumption resets that budget.
    """

    def __init__(self) -> None:
        self._budget_lock = threading.Lock()
        self._started_at: float | None = None
        self._requests = 0
        self._received_bytes = 0

    def request(
        self, method: str, path: str, body: Any = None,
    ) -> dict[str, Any]:
        if (
            method != "GET" or body is not None or type(path) is not str
            or not any(pattern.fullmatch(path) for pattern in _SCOPED_GET)
        ):
            raise PermissionError("Public agent-control reader only allows pinned GET paths")
        # Serialize callers so requests cannot race to evade aggregate budgets.
        with self._budget_lock:
            return self._bounded_get(path)

    def _bounded_get(self, path: str) -> dict[str, Any]:
        now = time.monotonic()
        if self._started_at is None:
            self._started_at = now
        deadline = self._started_at + _MAX_SESSION_SECONDS
        remaining = deadline - now
        byte_allowance = min(
            _MAX_RESPONSE_BYTES, _MAX_SESSION_BYTES - self._received_bytes
        )
        if (
            self._requests >= _MAX_SESSION_REQUESTS
            or remaining <= 0
            or byte_allowance <= 0
        ):
            raise ValueError("Public GitHub evidence session budget exhausted")
        # Count attempts, including HTTP 4xx/5xx and transport failures.
        self._requests += 1
        # GitHub's public Contents API can expose output from old tasks. Do not
        # expose raw responses to a caller-facing CLI; reconcile and redact.
        request = Request(
            _API_ROOT + path,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "local-agent-no-bridge-readonly",
            },
            method="GET",
        )
        opener = build_opener(_NoRedirect())
        try:
            with opener.open(
                request, timeout=min(_REQUEST_TIMEOUT_SECONDS, remaining)
            ) as response:
                if response.status != 200:
                    raise git.GithubFabricHTTPError(response.status)
                declared = response.headers.get("Content-Length")
                if declared is not None:
                    if (
                        not declared.isascii() or not declared.isdecimal()
                        or int(declared) > _MAX_RESPONSE_BYTES
                    ):
                        raise ValueError("Public GitHub evidence response is oversized")
                    if int(declared) > byte_allowance:
                        raise ValueError("Public GitHub evidence response exceeds budget")
                raw = response.read(byte_allowance + 1)
        except HTTPError as exc:
            raise git.GithubFabricHTTPError(exc.code) from None
        except (URLError, TimeoutError, OSError):
            raise git.GithubFabricTransportError(
                "Public GitHub evidence read failed"
            ) from None
        if len(raw) > byte_allowance:
            if byte_allowance == _MAX_RESPONSE_BYTES:
                raise ValueError("Public GitHub evidence response is oversized")
            raise ValueError("Public GitHub evidence response exceeds budget")
        self._received_bytes += len(raw)
        if time.monotonic() >= deadline:
            raise ValueError("Public GitHub evidence session budget exhausted")

        def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            value: dict[str, Any] = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("Public GitHub evidence contains duplicate JSON keys")
                value[key] = item
            return value

        def _reject_constant(_constant: str) -> Any:
            raise ValueError("Public GitHub evidence contains non-finite JSON")

        try:
            decoded = json.loads(
                raw.decode("utf-8"),
                object_pairs_hook=_unique_keys,
                parse_constant=_reject_constant,
            )
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("Public GitHub evidence JSON malformed") from None
        if type(decoded) is not dict:
            raise ValueError("Public GitHub evidence must be an object")
        return decoded
