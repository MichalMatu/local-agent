from __future__ import annotations

import unittest

from agent_config import load_timeout_config


class TimeoutConfigTests(unittest.TestCase):
    def test_defaults_and_overrides(self) -> None:
        defaults = load_timeout_config({})
        self.assertEqual(
            (
                defaults.command_default,
                defaults.command_max,
                defaults.idle_default,
                defaults.idle_max,
                defaults.task_default,
                defaults.task_max,
            ),
            (900, 7200, 300, 3600, 1800, 21600),
        )
        configured = load_timeout_config(
            {
                "LOCAL_AGENT_COMMAND_TIMEOUT_DEFAULT": "3600",
                "LOCAL_AGENT_COMMAND_TIMEOUT_MAX": "7200",
                "LOCAL_AGENT_IDLE_TIMEOUT_DEFAULT": "1200",
                "LOCAL_AGENT_IDLE_TIMEOUT_MAX": "3600",
                "LOCAL_AGENT_TASK_TIMEOUT_DEFAULT": "7200",
                "LOCAL_AGENT_TASK_TIMEOUT_MAX": "21600",
            }
        )
        self.assertEqual(configured.command_default, 3600)
        self.assertEqual(configured.task_default, 7200)

    def test_rejects_malformed_non_positive_and_out_of_range_values(self) -> None:
        for value in ("nope", "0", "-1", "86401"):
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "LOCAL_AGENT"
            ):
                load_timeout_config({"LOCAL_AGENT_TASK_TIMEOUT_MAX": value})

    def test_rejects_default_above_its_maximum(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            load_timeout_config(
                {
                    "LOCAL_AGENT_COMMAND_TIMEOUT_DEFAULT": "7201",
                    "LOCAL_AGENT_COMMAND_TIMEOUT_MAX": "7200",
                }
            )


if __name__ == "__main__":
    unittest.main()
