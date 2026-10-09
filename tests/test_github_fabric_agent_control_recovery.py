"""Strict read-only agent-control task/result observation with an in-memory Git API."""

from __future__ import annotations

import base64
import hashlib
import json
import unittest

from local_agent.conversation import github_fabric_agent_control_recovery as reader

CONTROL_SHA = "a" * 40
SOURCE_SHA = "c" * 40
BINDING = "2180d453-1357-4fbc-be1a-e1e5b8fbb10a"
TASK_ID = "local-agent-m8-private-reader-tests"
BRANCH = "work/m8-source-reader"


def _task():
    return {
        "id": TASK_ID,
        "agent_binding": BINDING,
        "work_branch": BRANCH,
        "allow_write": False,
        "resources": [],
        "mode": "commands",
        "commands": [
            'set -euo pipefail\n'
            f'test "$(git rev-parse HEAD)" = "{SOURCE_SHA}" || exit 3\n'
            'test -z "$(git status --porcelain)" || exit 4\n'
            'python -m unittest -q tests.test_github_fabric_recovery'
        ],
    }


def _result(task):
    return {
        "id": TASK_ID,
        "work_branch": BRANCH,
        "allow_write": False,
        "mode": "commands",
        "status": "done",
        "task_digest": reader._task_digest(task),
        "edits": {},
        "verification": [],
        "git_status": {"exit_code": 0, "output": ""},
        "git_diff": {"exit_code": 0, "output": ""},
        "stages": [{"outcome": "passed", "stage_phase": "commands", "stage_index": 1, "stage_total": 1}],
        "commands": [{
            "command": task["commands"][0],
            "exit_code": 0,
            "timed_out": False,
            "idle_timed_out": False,
            "memory_limited": False,
            "background_process_leak": False,
            "output_truncated": False,
            "output": "PRIVATE TEST OUTPUT DO NOT DISCLOSE",
        }],
    }


class MemoryControlAPI:
    def __init__(self, task=None, result=None):
        self.task = task if task is not None else _task()
        self.result = result if result is not None else _result(self.task)
        self.operations = []
        self.bad_blob_path = None

    def request(self, method, path, body=None):
        self.operations.append((method, path, body))
        if method != "GET" or body is not None:
            raise AssertionError("GET-only reader violated")
        if path == f"/git/commits/{CONTROL_SHA}":
            return {"tree": {"sha": "b" * 40}}
        path_task = f"/contents/.agent/tasks/{TASK_ID}.json?ref={CONTROL_SHA}"
        path_result = f"/contents/.agent/results/{TASK_ID}.json?ref={CONTROL_SHA}"
        if path not in (path_task, path_result):
            raise AssertionError("Unexpected GitHub path " + path)
        value = self.task if path == path_task else self.result
        raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        sha = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
        return {
            "type": "file", "encoding": "base64", "size": len(raw),
            "content": base64.b64encode(raw).decode(),
            "sha": "d" * 40 if path == self.bad_blob_path else sha,
        }


class AgentControlRecoveryTests(unittest.TestCase):
    def inspect(self, api, **overrides):
        kwargs = {
            "independently_pinned_control_sha": CONTROL_SHA,
            "independently_pinned_source_sha": SOURCE_SHA,
            "expected_agent_binding": BINDING,
            "expected_work_branch": BRANCH,
            "enabled": True, "api": api,
        }
        kwargs.update(overrides)
        return reader.recover_agent_control_result(TASK_ID, **kwargs)

    def test_read_only_success_redacts_raw_command_output(self):
        api = MemoryControlAPI()
        found = self.inspect(api)
        self.assertEqual(found.reported_outcome, "reported_pass_for_review")
        self.assertEqual(found.control_commit_sha, CONTROL_SHA)
        self.assertEqual(found.source_commit_sha, SOURCE_SHA)
        self.assertEqual(found.command_count, 1)
        self.assertFalse(found.effect_authorized)
        self.assertFalse(found.automatic_retry_permitted)
        self.assertFalse(found.result_execution_attested)
        self.assertTrue(found.write_disabled_in_task_record)
        self.assertFalse(found.command_effects_independently_verified)
        self.assertFalse(hasattr(found, "read_only_task"))
        self.assertFalse(found.output_disclosed)
        self.assertNotIn("PRIVATE TEST OUTPUT", repr(found))
        self.assertEqual(len(api.operations), 3)
        self.assertTrue(all(op[0] == "GET" and op[2] is None for op in api.operations))

    def test_failed_or_uncertain_outcome_retains_review_without_retry(self):
        for mutation in (
            {"status": "failed"},
            {"commands": [{"exit_code": 1}]},
            {"commands": [{"timed_out": True}]},
            {"git_diff": {"exit_code": 1, "output": "changed"}},
            {"stages": [{"outcome": "failed"}]},
            {"stages": [{"outcome": "passed", "stage_phase": "commands", "stage_index": 2, "stage_total": 1}]},
            {"commands": [{"exit_code": False}]},
            {"git_status": {"exit_code": False, "output": ""}},
            {"verification": [{"exit_code": 1}]},
        ):
            with self.subTest(mutation=mutation):
                api = MemoryControlAPI()
                for key, value in mutation.items():
                    if key == "commands":
                        api.result[key][0].update(value[0])
                    else:
                        api.result[key] = value
                summary = self.inspect(api)
                self.assertEqual(summary.reported_outcome, "reported_nonpass_for_review")
                self.assertFalse(summary.automatic_retry_permitted)

    def test_truncated_success_is_incomplete_not_failure_or_retry_permission(self):
        api = MemoryControlAPI()
        api.result["commands"][0]["output_truncated"] = True
        summary = self.inspect(api)
        self.assertEqual(
            summary.reported_outcome, "reported_incomplete_evidence_for_review"
        )
        self.assertEqual(summary.reported_status, "done")
        self.assertFalse(summary.result_execution_attested)
        self.assertFalse(summary.automatic_retry_permitted)
        self.assertFalse(summary.effect_authorized)
        self.assertFalse(summary.output_disclosed)
        self.assertNotIn("PRIVATE TEST OUTPUT", repr(summary))
        api.result["commands"][0]["exit_code"] = 1
        failed = self.inspect(api)
        self.assertEqual(failed.reported_outcome, "reported_nonpass_for_review")

    def test_invalid_task_digest_and_rewritten_command_fail_closed(self):
        api = MemoryControlAPI()
        api.result["task_digest"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "association"):
            self.inspect(api)
        api = MemoryControlAPI()
        api.result["commands"][0]["command"] = "echo forged"
        with self.assertRaisesRegex(ValueError, "reported command"):
            self.inspect(api)

    def test_unapproved_task_write_privileges_or_missing_guard_rejected(self):
        for key, value in (
            ("allow_write", True),
            ("resources", ["machine"]),
            ("work_branch", "main"),
            ("commands", ["echo skip the exact HEAD guard"]),
            ("verify_commands", ["echo unreviewed"]),
            ("commands", [_task()["commands"][0], "echo bypass unguarded"]),
            ("patch", "private diff"),
        ):
            api = MemoryControlAPI()
            api.task[key] = value
            api.result["task_digest"] = reader._task_digest(api.task)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "outside read-only"):
                self.inspect(api)

    def test_duplicate_json_keys_and_nonfinite_values_fail_closed(self):
        api = MemoryControlAPI()
        duplicate = '{"id":"first","id":"second"}'
        raw = duplicate.encode()
        # Construct a forged but internally SHA-correct GitHub blob.
        original_request = api.request

        def forged(method, path, body=None):
            if path == f"/contents/.agent/results/{TASK_ID}.json?ref={CONTROL_SHA}":
                api.operations.append((method, path, body))
                return {
                    "type": "file", "encoding": "base64", "size": len(raw),
                    "content": base64.b64encode(raw).decode(),
                    "sha": hashlib.sha1(
                        f"blob {len(raw)}\0".encode() + raw
                    ).hexdigest(),
                }
            return original_request(method, path, body)

        api.request = forged
        with self.assertRaisesRegex(ValueError, "duplicate fields"):
            self.inspect(api)

        invalid = b'{"id":NaN}'
        def nonfinite(method, path, body=None):
            if path == f"/contents/.agent/results/{TASK_ID}.json?ref={CONTROL_SHA}":
                return {
                    "type": "file", "encoding": "base64", "size": len(invalid),
                    "content": base64.b64encode(invalid).decode(),
                    "sha": hashlib.sha1(
                        f"blob {len(invalid)}\0".encode() + invalid
                    ).hexdigest(),
                }
            return original_request(method, path, body)

        api.request = nonfinite
        with self.assertRaisesRegex(ValueError, "non-finite"):
            self.inspect(api)

    def test_invalid_git_blob_identity_fail_closed(self):
        api = MemoryControlAPI()
        api.bad_blob_path = f"/contents/.agent/results/{TASK_ID}.json?ref={CONTROL_SHA}"
        with self.assertRaisesRegex(ValueError, "Git blob identity"):
            self.inspect(api)
        api = MemoryControlAPI()
        api.bad_blob_path = f"/contents/.agent/tasks/{TASK_ID}.json?ref={CONTROL_SHA}"
        with self.assertRaisesRegex(ValueError, "Git blob identity"):
            self.inspect(api)

    def test_disabled_bad_pin_and_binding_refuse_any_git_io(self):
        for overrides, exception in (
            ({"enabled": False}, PermissionError),
            ({"independently_pinned_control_sha": "bad"}, ValueError),
            ({"independently_pinned_source_sha": "bad"}, ValueError),
            ({"expected_agent_binding": "bad"}, ValueError),
            ({"expected_work_branch": "main"}, ValueError),
            ({"expected_work_branch": "work/../main"}, ValueError),
            ({"token": "unexpected token"}, ValueError),
        ):
            api = MemoryControlAPI()
            with self.subTest(overrides=overrides), self.assertRaises(exception):
                self.inspect(api, **overrides)
            self.assertEqual(api.operations, [])

    def test_get_only_guard_denies_mutations_even_for_fake_api(self):
        api = MemoryControlAPI()
        guard = reader._GetOnly(api)
        for method, body in (("POST", {}), ("PATCH", {}), ("DELETE", None), ("GET", {})):
            with self.subTest(method=method), self.assertRaises(PermissionError):
                guard.request(method, "/git/commits/anything", body)
        self.assertEqual(api.operations, [])

    def test_reported_status_invalid_fails_closed(self):
        api = MemoryControlAPI()
        api.result["status"] = ["done"]
        with self.assertRaisesRegex(ValueError, "reported status"):
            self.inspect(api)
        api = MemoryControlAPI()
        api.result["status"] = "x" * 100
        with self.assertRaisesRegex(ValueError, "reported status"):
            self.inspect(api)
        api = MemoryControlAPI()
        api.result["status"] = "PRIVATE_SECRET"
        with self.assertRaisesRegex(ValueError, "reported status"):
            self.inspect(api)


if __name__ == "__main__":
    unittest.main()
