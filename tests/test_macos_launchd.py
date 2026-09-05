from __future__ import annotations

import plistlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from local_agent.platform.macos_launchd import (
    LABEL,
    build_launch_agent,
    build_program_arguments,
    default_launch_agent_path,
    render_launch_agent,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


class MacOSLaunchdTests(unittest.TestCase):
    def setUp(self) -> None:
        self.home = Path("/Users/tester")
        self.repo = self.home / "src" / "local-agent"

    def test_parallel_definition_uses_resolved_paths(self) -> None:
        payload = build_launch_agent(
            "parallel",
            repo_root=self.repo,
            home=self.home,
            max_workers=2,
        )
        self.assertEqual(payload["Label"], LABEL)
        self.assertEqual(payload["WorkingDirectory"], str(self.repo))
        self.assertEqual(
            payload["ProgramArguments"],
            [
                str(self.repo / ".venv" / "bin" / "python"),
                str(self.repo / "agent_entrypoint.py"),
                "--registry",
                str(
                    self.home
                    / "Library"
                    / "Application Support"
                    / "local-agent"
                    / "repositories.json"
                ),
                "--max-workers",
                "2",
            ],
        )
        environment = payload["EnvironmentVariables"]
        self.assertEqual(environment["HOME"], str(self.home))
        self.assertEqual(environment["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertNotIn("/Users/michal", repr(payload))

    def test_all_modes_select_expected_entrypoint(self) -> None:
        expected = {
            "parallel": "agent_entrypoint.py",
            "multirepo": "agent_multirepo.py",
            "single": "agentd.py",
        }
        for mode, entrypoint in expected.items():
            with self.subTest(mode=mode):
                arguments = build_program_arguments(
                    mode,
                    repo_root=self.repo,
                    home=self.home,
                )
                self.assertTrue(arguments[1].endswith(entrypoint))

    def test_parallel_worker_bound_matches_scheduler_contract(self) -> None:
        for value in (0, 4):
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_program_arguments(
                    "parallel",
                    repo_root=self.repo,
                    home=self.home,
                    max_workers=value,
                )

    def test_rendered_plist_round_trips(self) -> None:
        rendered = render_launch_agent(
            "parallel",
            repo_root=self.repo,
            home=self.home,
        )
        payload = plistlib.loads(rendered)
        self.assertEqual(payload["Label"], LABEL)
        self.assertEqual(payload["WorkingDirectory"], str(self.repo))

    def test_render_cli_runs_from_outside_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "macos_launchd.py"),
                    "render",
                    "--home",
                    str(self.home),
                    "--repo-root",
                    str(self.repo),
                ],
                cwd=tmp,
                text=False,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        payload = plistlib.loads(result.stdout)
        self.assertEqual(payload["Label"], LABEL)
        self.assertEqual(payload["WorkingDirectory"], str(self.repo))

    def test_default_install_location_is_user_launch_agents(self) -> None:
        self.assertEqual(
            default_launch_agent_path(self.home),
            self.home / "Library" / "LaunchAgents" / f"{LABEL}.plist",
        )


if __name__ == "__main__":
    unittest.main()
