"""Anonymous public GitHub evidence adapter stays bounded and token-free."""

from __future__ import annotations

import io
import json
import unittest
from unittest import mock
from urllib.error import HTTPError, URLError

from local_agent.conversation import github_fabric_agent_control_public_rest as reader
from local_agent.conversation import github_fabric_github as git

SHA = "a" * 40
TASK = "local-agent-m8-pr253-full-local-20261009-v1"
GOOD_PATHS = (
    f"/git/commits/{SHA}",
    f"/git/trees/{SHA}?recursive=1",
    f"/contents/.agent/tasks/{TASK}.json?ref={SHA}",
    f"/contents/.agent/results/{TASK}.json?ref={SHA}",
)


class FakeResponse:
    def __init__(self, data=b'{"sha":"test"}', *, status=200, declared=None):
        self.raw = data
        self.status = status
        self.headers = {} if declared is None else {"Content-Length": declared}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size):
        if not isinstance(size, int):
            raise AssertionError("Unbounded read is forbidden")
        return self.raw[:size]


class FakeOpener:
    def __init__(self, response=None, error=None):
        self.response = response or FakeResponse()
        self.error = error
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        if self.error:
            raise self.error
        return self.response


class PublicAgentControlRESTTests(unittest.TestCase):
    def setUp(self):
        self.api = reader.PublicAgentControlReadOnlyREST()
        self.opener = FakeOpener()

    def invoke(self, method="GET", path=GOOD_PATHS[0], body=None):
        with mock.patch.object(reader, "build_opener", return_value=self.opener):
            return self.api.request(method, path, body)

    def test_all_supported_endpoints_are_exactly_pinned_anonymous_get(self):
        for path in GOOD_PATHS:
            with self.subTest(path=path):
                self.opener.calls.clear()
                self.assertEqual(self.invoke(path=path), {"sha": "test"})
                self.assertEqual(len(self.opener.calls), 1)
                request, timeout = self.opener.calls[0]
                self.assertEqual(request.get_method(), "GET")
                self.assertEqual(timeout, reader._REQUEST_TIMEOUT_SECONDS)
                self.assertTrue(request.full_url.startswith(
                    "https://api.github.com/repos/MichalMatu/local-agent/"
                ))
                self.assertTrue(request.full_url.endswith(path))
                self.assertNotIn("Authorization", request.headers)
                self.assertNotIn("Cookie", request.headers)
                self.assertNotIn("PRIVATE", repr(request.headers))

    def test_other_paths_methods_and_data_are_refused_without_network(self):
        bad = (
            ("POST", GOOD_PATHS[0], None),
            ("PATCH", GOOD_PATHS[0], {"sha": SHA}),
            ("DELETE", GOOD_PATHS[0], None),
            ("GET", GOOD_PATHS[0], {}),
            ("GET", "/git/commits/main", None),
            ("GET", f"/git/commits/{SHA}?extra=1", None),
            ("GET", f"/git/trees/{SHA}?recursive=0", None),
            ("GET", f"/git/trees/{SHA}", None),
            ("GET", f"/contents/.agent/status/daemon.json?ref={SHA}", None),
            ("GET", f"/contents/.agent/tasks/../results/{TASK}.json?ref={SHA}", None),
            ("GET", f"/contents/.agent/tasks/{TASK}.json?ref=main", None),
            ("GET", f"/contents/.agent/results/{TASK}.json?ref={SHA}&x=1", None),
            ("GET", f"/contents/.agent/results/{TASK}.json?ref={SHA}#fragment", None),
            ("GET", "https://attacker.test/anything", None),
            ("GET", None, None),
        )
        for method, path, body in bad:
            with self.subTest(method=method, path=path):
                with self.assertRaises(PermissionError):
                    self.invoke(method, path, body)
        self.assertEqual(self.opener.calls, [])

    def test_no_http_redirect_even_when_server_attempts_one(self):
        self.assertIsNone(reader._NoRedirect().redirect_request(
            None, None, 302, "Found", {"Location": "https://other.test"}, "https://other.test"
        ))

    def test_http_errors_do_not_contain_response_body_or_original_url(self):
        self.opener.error = HTTPError(
            "https://private.example/secret", 403, "TOP_SECRET_REMOTE",
            {}, io.BytesIO(b"PRIVATE_API_ERROR_TOKEN")
        )
        with self.assertRaises(git.GithubFabricHTTPError) as caught:
            self.invoke()
        self.assertEqual(caught.exception.status, 403)
        self.assertNotIn("TOP_SECRET", str(caught.exception))
        self.assertNotIn("PRIVATE_API_ERROR", str(caught.exception))

    def test_transport_errors_do_not_echo_credentials_or_urls(self):
        self.opener.error = URLError("PRIVATE_TOKEN from proxy")
        with self.assertRaises(git.GithubFabricTransportError) as caught:
            self.invoke()
        self.assertNotIn("PRIVATE_TOKEN", str(caught.exception))

    def test_session_request_count_refuses_before_another_network_get(self):
        for _ in range(reader._MAX_SESSION_REQUESTS):
            self.assertEqual(self.invoke(), {"sha": "test"})
        self.assertEqual(self.api._requests, reader._MAX_SESSION_REQUESTS)
        observed = len(self.opener.calls)
        with self.assertRaisesRegex(ValueError, "session budget"):
            self.invoke()
        self.assertEqual(len(self.opener.calls), observed)

    def test_elapsed_session_deadline_blocks_before_network_io(self):
        with mock.patch.object(reader.time, "monotonic", return_value=100.0):
            self.assertEqual(self.invoke(), {"sha": "test"})
        before = len(self.opener.calls)
        with mock.patch.object(reader.time, "monotonic", return_value=221.0):
            with self.assertRaisesRegex(ValueError, "session budget"):
                self.invoke()
        self.assertEqual(len(self.opener.calls), before)

    def test_each_get_timeout_is_bounded_by_remaining_session_time(self):
        with mock.patch.object(
            reader.time, "monotonic", side_effect=[100.0, 100.0, 215.0, 215.0],
        ):
            self.assertEqual(self.invoke(), {"sha": "test"})
            self.assertEqual(self.invoke(), {"sha": "test"})
        self.assertEqual(self.opener.calls[-1][1], 5.0)

    def test_download_finishing_after_deadline_cannot_return_success(self):
        with mock.patch.object(
            reader.time, "monotonic", side_effect=[100.0, 221.0],
        ):
            with self.assertRaisesRegex(ValueError, "session budget"):
                self.invoke()
        self.assertEqual(len(self.opener.calls), 1)

    def test_aggregate_byte_budget_rejects_before_parsing(self):
        self.api._received_bytes = reader._MAX_SESSION_BYTES - 8
        self.opener.response = FakeResponse(declared="13")
        with self.assertRaisesRegex(ValueError, "exceeds budget"):
            self.invoke()
        self.opener.response = FakeResponse()
        with self.assertRaisesRegex(ValueError, "exceeds budget"):
            self.invoke()
        self.assertEqual(self.api._received_bytes, reader._MAX_SESSION_BYTES - 8)

    def test_failed_get_attempt_consumes_request_budget_without_secret_echo(self):
        self.opener.error = URLError("PRIVATE_BEARER")
        with self.assertRaises(git.GithubFabricTransportError):
            self.invoke()
        self.assertEqual(self.api._requests, 1)
        self.assertEqual(self.api._received_bytes, 0)

    def test_refused_method_cannot_consume_any_session_budget(self):
        with self.assertRaises(PermissionError):
            self.invoke("PATCH", GOOD_PATHS[0], {})
        self.assertIsNone(self.api._started_at)
        self.assertEqual(self.api._requests, 0)
        self.assertEqual(len(self.opener.calls), 0)

    def test_payload_size_is_hard_capped_before_parsing(self):
        self.opener.response = FakeResponse(declared=str(reader._MAX_RESPONSE_BYTES + 1))
        with self.assertRaisesRegex(ValueError, "oversized"):
            self.invoke()
        self.opener.response = FakeResponse(b"x" * (reader._MAX_RESPONSE_BYTES + 2))
        with self.assertRaisesRegex(ValueError, "oversized"):
            self.invoke()
        self.opener.response = FakeResponse(declared="-1")
        with self.assertRaisesRegex(ValueError, "oversized"):
            self.invoke()

    def test_refuse_bad_json_and_scalar_response(self):
        for payload in (b"{", b"[]", b"null", b'"secret"', b"\xff"):
            with self.subTest(payload=payload):
                self.opener.response = FakeResponse(payload)
                with self.assertRaises(ValueError):
                    self.invoke()

    def test_duplicate_keys_and_nonfinite_constants_refuse_github_json(self):
        for payload, expected in (
            (b'{"sha":"trusted","sha":"different"}', "duplicate JSON keys"),
            (b'{"tree":{"sha":"one","sha":"two"}}', "duplicate JSON keys"),
            (b'{"sha":NaN}', "non-finite JSON"),
            (b'{"count":Infinity}', "non-finite JSON"),
        ):
            with self.subTest(payload=payload):
                self.opener.response = FakeResponse(payload)
                with self.assertRaisesRegex(ValueError, expected):
                    self.invoke()

    def test_non_200_status_is_refused(self):
        self.opener.response = FakeResponse(status=404)
        with self.assertRaises(git.GithubFabricHTTPError) as caught:
            self.invoke()
        self.assertEqual(caught.exception.status, 404)

    def test_json_response_was_never_injected_with_token(self):
        self.opener.response = FakeResponse(json.dumps({
            "sha": SHA, "tree": {"sha": "b" * 40}
        }).encode("utf-8"))
        self.assertEqual(self.invoke()["sha"], SHA)
        request = self.opener.calls[0][0]
        self.assertEqual(request.get_method(), "GET")
        self.assertNotIn("authorization", str(request.header_items()).lower())


    def test_overflowing_float_and_deep_json_fail_closed(self):
        # Python's default json.loads accepts 1e999 as infinity despite
        # rejecting the bare Infinity token via parse_constant.
        for payload, expected in (
            (b'{"count":1e999}', "non-finite JSON"),
            (b'{"nested":' + b'[' * 12000 + b'0' + b']' * 12000 + b'}', "JSON malformed"),
        ):
            with self.subTest(expected=expected):
                self.opener.response = FakeResponse(payload)
                with self.assertRaisesRegex(ValueError, expected):
                    self.invoke()


if __name__ == "__main__":
    unittest.main()
