"""Anonymous, strictly scoped GET-only GitHub reader for public agent-control evidence.

This reader can access only public GitHub API resources under the hard-coded
repository and an exact commit/tree/task/result identity. It has no token,
write capability, redirects, browser or local task execution authority.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from local_agent.conversation import github_fabric_github as git

_API_ROOT = "https://api.github.com/repos/MichalMatu/local-agent"
_MAX_RESPONSE_BYTES = 512 * 1024
_REQUEST_TIMEOUT_SECONDS = 15
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
    """Read **public** pinned GitHub evidence without implicit credentials."""

    def request(
        self, method: str, path: str, body: Any = None,
    ) -> dict[str, Any]:
        if (
            method != "GET" or body is not None or type(path) is not str
            or not any(pattern.fullmatch(path) for pattern in _SCOPED_GET)
        ):
            raise PermissionError("Public agent-control reader only allows pinned GET paths")
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
            with opener.open(request, timeout=_REQUEST_TIMEOUT_SECONDS) as response:
                if response.status != 200:
                    raise git.GithubFabricHTTPError(response.status)
                declared = response.headers.get("Content-Length")
                if declared is not None and (
                    not declared.isascii() or not declared.isdecimal()
                    or int(declared) > _MAX_RESPONSE_BYTES
                ):
                    raise ValueError("Public GitHub evidence response is oversized")
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            raise git.GithubFabricHTTPError(exc.code) from None
        except (URLError, TimeoutError, OSError):
            raise git.GithubFabricTransportError(
                "Public GitHub evidence read failed"
            ) from None
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise ValueError("Public GitHub evidence response is oversized")
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("Public GitHub evidence JSON malformed") from None
        if type(decoded) is not dict:
            raise ValueError("Public GitHub evidence must be an object")
        return decoded
