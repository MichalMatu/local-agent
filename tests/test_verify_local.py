"""Hermetic source and environment gate: no hosted Actions or task execution."""
from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from scripts import verify_local as gate

HEAD = "a" * 40


class VerifyLocalGateTests(unittest.TestCase):
    def test_exact_source_sha_and_clean_checkout_required(self) -> None:
        good = subprocess.CompletedProcess([], 0, HEAD + "\n", "")
        clean = subprocess.CompletedProcess([], 0, "", "")
        with mock.patch.object(gate.subprocess, "run", side_effect=[good, clean]) as run:
            self.assertEqual(gate.exact_head(HEAD, root=Path("/tmp/isolated-root")), HEAD)
            self.assertEqual(run.call_count, 2)
        with self.assertRaisesRegex(ValueError, "exact lowercase"):
            gate.exact_head("not-a-sha")
        bad = subprocess.CompletedProcess([], 0, "b" * 40 + "\n", "")
        with mock.patch.object(gate.subprocess, "run", return_value=bad):
            with self.assertRaisesRegex(ValueError, "HEAD mismatch"):
                gate.exact_head(HEAD)
        changed = subprocess.CompletedProcess([], 0, " M test.txt\n", "")
        with mock.patch.object(gate.subprocess, "run", side_effect=[good, changed]):
            with self.assertRaisesRegex(ValueError, "not clean"):
                gate.exact_head(HEAD)

    def test_plan_is_explicit_and_pins_interpreter(self) -> None:
        core = gate.planned_commands("core", python="/tmp/python")
        self.assertEqual(len(core), 4)
        self.assertTrue(all(stage[1][0] == "/tmp/python" for stage in core))
        full = gate.planned_commands("full", include_browser=True,
                                     include_python314=True, python="/tmp/python")
        self.assertEqual(len(full), 12)
        self.assertEqual(full[-2][1][0], "python3.14")
        self.assertEqual(full[-1][0], "isolated Chromium")
        self.assertIn("--cov-fail-under=85", full[7][1])

    def test_sanitization_is_explicit_and_does_not_mutate_daemon_environment(self) -> None:
        env = {"LOCAL_AGENT_LEASE_FDS": "3", "LOCAL_AGENT_LEASE_KEYS_DIGEST": "abc",
               "LOCAL_AGENT_RESOURCE_LEASE_FDS": "4", "UNRELATED": "safe"}
        with mock.patch.dict(os.environ, env, clear=True):
            normal = gate.subprocess_environment()
            self.assertEqual(normal["LOCAL_AGENT_LEASE_FDS"], "3")
            hermetic = gate.subprocess_environment(sanitize_test_lease_markers=True)
            self.assertEqual(hermetic["UNRELATED"], "safe")
            self.assertTrue(all(k not in hermetic for k in gate._LEASE_MARKERS))
            self.assertEqual(os.environ["LOCAL_AGENT_LEASE_FDS"], "3")

    def test_missing_dependencies_stops_before_running_any_test(self) -> None:
        with mock.patch.object(gate, "exact_head", return_value=HEAD), \
             mock.patch.object(gate, "missing_dependencies", return_value=["httpx2"]), \
             mock.patch.object(gate.subprocess, "run") as execute:
            self.assertEqual(gate.main(["--expected-sha", HEAD]), 2)
            execute.assert_not_called()

    def test_failed_stage_does_not_report_success(self) -> None:
        with mock.patch.object(gate, "exact_head", return_value=HEAD), \
             mock.patch.object(gate, "missing_dependencies", return_value=[]), \
             mock.patch.object(gate, "planned_commands", return_value=[("fail", ["false"])]), \
             mock.patch.object(gate.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 1)):
            self.assertEqual(gate.main(["--expected-sha", HEAD]), 1)


if __name__ == "__main__":
    unittest.main()
