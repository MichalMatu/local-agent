"""Authenticated Mac evidence GET stays scoped, bounded and deny-only."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest import mock
from urllib.error import HTTPError
import io

from local_agent.conversation import github_fabric_agent_control_authenticated_rest as auth_rest
from local_agent.conversation import github_fabric_agent_control_public_rest as public_rest
from local_agent.conversation import github_fabric_agent_control_recovery as recovery
from local_agent.conversation import github_fabric_agent_control_index as history
from local_agent.conversation import github_fabric_github as git
from tests.test_github_fabric_agent_control_public_rest import (
    FakeOpener, FakeResponse, GOOD_PATHS,
)
from tests.test_github_fabric_agent_control_recovery import (
    BINDING, BRANCH, CONTROL_SHA, SOURCE_SHA, TASK_ID, MemoryControlAPI,
)
from tests.test_github_fabric_agent_control_index import HistoryAPI, PREFIX

TOKEN = "FIXTURE_EXPLICIT_READ_TOKEN"


class AuthenticatedAgentControlRESTTests(unittest.TestCase):
    def setUp(self):
        self.api = auth_rest.AuthenticatedAgentControlReadOnlyREST(TOKEN)
        self.opener = FakeOpener()

    def request(self, path=GOOD_PATHS[0], method="GET", body=None):
        with mock.patch.object(public_rest, "build_opener", return_value=self.opener):
            return self.api.request(method, path, body)

    def test_explicit_token_and_only_exact_pinned_https_get(self):
        for path in GOOD_PATHS:
            with self.subTest(path=path):
                self.assertEqual(self.request(path), {"sha": "test"})
                request, timeout = self.opener.calls[-1]
                self.assertEqual(request.get_method(), "GET")
                self.assertEqual(timeout, public_rest._REQUEST_TIMEOUT_SECONDS)
                self.assertEqual(request.get_header("Authorization"), "Bearer " + TOKEN)
                self.assertEqual(request.full_url,
                    "https://api.github.com/repos/MichalMatu/local-agent" + path)
                self.assertNotIn(TOKEN, request.full_url)
        count = len(self.opener.calls)
        for method, path, body in (
            ("POST", GOOD_PATHS[0], {}),
            ("PATCH", GOOD_PATHS[0], {"force": False}),
            ("GET", GOOD_PATHS[0], {}),
            ("GET", "/git/commits/main", None),
            ("GET", "https://attacker.example/other", None),
            ("GET", "/contents/.agent/status/daemon.json?ref=" + "a" * 40, None),
        ):
            with self.subTest(method=method, path=path):
                with self.assertRaises(PermissionError):
                    self.request(path, method, body)
        self.assertEqual(len(self.opener.calls), count)

    def test_bad_token_refused_before_request(self):
        for bad in (None, "", " ", "test token", "token\\nnewline", "x" * 4097, 123):
            with self.subTest(bad=type(bad).__name__):
                with self.assertRaises(PermissionError):
                    auth_rest.AuthenticatedAgentControlReadOnlyREST(bad)

    def test_failures_never_echo_bearer_or_http_response(self):
        self.opener.error = HTTPError(
            "https://api.github.com/private", 403, "SECRET_ERROR",
            {}, io.BytesIO(b"SECRET_BODY"),
        )
        with self.assertRaises(git.GithubFabricHTTPError) as exc:
            self.request()
        self.assertEqual(exc.exception.status, 403)
        self.assertNotIn(TOKEN, str(exc.exception))
        self.assertNotIn("SECRET", str(exc.exception))

    def test_session_attempts_are_thread_safe_and_exhaustive(self):
        with mock.patch.object(public_rest, "build_opener", return_value=self.opener):
            with ThreadPoolExecutor(max_workers=8) as pool:
                outcomes = list(pool.map(
                    lambda _: self._concurrent_attempt(), range(64)
                ))
        self.assertEqual(outcomes.count("accepted"), public_rest._MAX_SESSION_REQUESTS)
        self.assertEqual(outcomes.count("refused"), 64 - public_rest._MAX_SESSION_REQUESTS)
        self.assertEqual(len(self.opener.calls), public_rest._MAX_SESSION_REQUESTS)

    def _concurrent_attempt(self):
        try:
            self.api.request("GET", GOOD_PATHS[0])
            return "accepted"
        except ValueError as exc:
            self.assertIn("session budget", str(exc))
            return "refused"

    def test_shared_byte_and_deadline_budget(self):
        self.api._received_bytes = public_rest._MAX_SESSION_BYTES - 8
        self.opener.response = FakeResponse(declared="99")
        with self.assertRaisesRegex(ValueError, "exceeds budget"):
            self.request()
        self.opener.response = FakeResponse()
        with mock.patch.object(public_rest.time, "monotonic", return_value=100.0):
            with self.assertRaisesRegex(ValueError, "exceeds budget"):
                self.request()
        self.assertEqual(self.api._requests, 2)
        # Use an independent session to prove the deadline even with credentials.
        api = auth_rest.AuthenticatedAgentControlReadOnlyREST(TOKEN)
        with mock.patch.object(public_rest, "build_opener", return_value=FakeOpener()):
            with mock.patch.object(public_rest.time, "monotonic", return_value=100.0):
                self.assertEqual(api.request("GET", GOOD_PATHS[0]), {"sha": "test"})
            with mock.patch.object(public_rest.time, "monotonic", return_value=221.0):
                with self.assertRaisesRegex(ValueError, "session budget"):
                    api.request("GET", GOOD_PATHS[0])

    def test_direct_recovery_uses_bounded_adapter_with_explicit_token(self):
        fixture = MemoryControlAPI()
        with mock.patch.object(
            recovery.auth_rest, "AuthenticatedAgentControlReadOnlyREST",
            return_value=fixture,
        ) as factory:
            observed = recovery.recover_agent_control_result(
                TASK_ID,
                independently_pinned_control_sha=CONTROL_SHA,
                independently_pinned_source_sha=SOURCE_SHA,
                expected_agent_binding=BINDING,
                expected_work_branch=BRANCH,
                enabled=True, token=TOKEN,
            )
        factory.assert_called_once_with(TOKEN)
        self.assertEqual(observed.reported_outcome, "reported_pass_for_review")
        self.assertFalse(observed.effect_authorized)

    def test_history_reuses_one_authenticated_session_for_all_gets(self):
        fixture = HistoryAPI()
        with mock.patch.object(
            history.auth_rest, "AuthenticatedAgentControlReadOnlyREST",
            return_value=fixture,
        ) as factory:
            observed = history.discover_agent_control_results(
                task_id_prefix=PREFIX,
                independently_pinned_control_sha=CONTROL_SHA,
                independently_pinned_source_sha=SOURCE_SHA,
                expected_agent_binding=BINDING,
                expected_work_branch=BRANCH,
                enabled=True, token=TOKEN,
            )
        factory.assert_called_once_with(TOKEN)
        self.assertEqual(len(fixture.operations), 5)
        self.assertEqual(len(observed.result_observations), 1)
        self.assertFalse(observed.can_authorize_browser_effect)


if __name__ == "__main__":
    unittest.main()
