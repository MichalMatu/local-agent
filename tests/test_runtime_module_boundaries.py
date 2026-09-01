from __future__ import annotations

import unittest
from unittest import mock

import agent_runtime
from local_agent.runtime import output, telemetry


class RuntimeModuleBoundaryTests(unittest.TestCase):
    def test_output_symbols_remain_compatibly_reexported(self) -> None:
        self.assertIs(agent_runtime.LiveCommandOutput, output.LiveCommandOutput)
        self.assertIs(agent_runtime.emit_summary_failure_tail, output.emit_summary_failure_tail)
        self.assertEqual(agent_runtime.LIVE_DIFF_MAX_LINES, output.LIVE_DIFF_MAX_LINES)
        self.assertEqual(agent_runtime.LIVE_DIFF_MAX_CHARS, output.LIVE_DIFF_MAX_CHARS)

    def test_telemetry_parsers_remain_compatibly_reexported(self) -> None:
        self.assertIs(agent_runtime.parse_mac_vm_stat, telemetry.parse_mac_vm_stat)
        self.assertIs(agent_runtime.parse_process_group_ps, telemetry.parse_process_group_ps)

    def test_rss_compatibility_adapter_retains_runtime_patch_seam(self) -> None:
        ps_output = "1 77 1.0 1024\n2 77 2.0 3072\n"
        with mock.patch.object(agent_runtime, "_safe_command", return_value=ps_output):
            self.assertEqual(agent_runtime.sample_process_group_rss_mb(77), 4.0)

    def test_extracted_telemetry_module_works_independently(self) -> None:
        parsed = telemetry.parse_process_group_ps(
            "1 7 2.0 1024\n2 7 3.0 2048\n", 7
        )
        self.assertEqual(parsed["command_cpu_percent"], 5.0)
        self.assertEqual(parsed["command_children"], 1)
        output.LiveCommandOutput().finish()


if __name__ == "__main__":
    unittest.main()
