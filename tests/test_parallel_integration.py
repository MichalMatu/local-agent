from __future__ import annotations

import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agent_version import RELEASE_VERSION
from tests.test_multirepo_integration import (
    REPO_ROOT,
    create_repository_fixture,
    git,
    test_environment,
    write_registry,
)


def configure_parallel_barrier_task(
    item: dict[str, Path | str],
    *,
    own_marker: Path,
    peer_marker: Path,
) -> None:
    control = Path(item["control"])
    task_path = control / ".agent" / "tasks" / "shared-task-id.json"
    task = json.loads(task_path.read_text(encoding="utf-8"))
    own = shlex.quote(str(own_marker))
    peer = shlex.quote(str(peer_marker))
    task["resources"] = []
    task["memory_limit_mb"] = 256
    task["steps"] = [
        {
            "name": "parallel-barrier",
            "command": (
                f"touch {own}; "
                'i=0; while [ "$i" -lt 120 ]; do '
                f"[ -f {peer} ] && exit 0; "
                'i=$((i+1)); sleep 0.05; done; exit 7'
            ),
            "timeout": 15,
        }
    ]
    task_path.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
    git(["add", ".agent/tasks/shared-task-id.json"], cwd=control)
    git(["commit", "-m", f"Configure parallel barrier {item['id']}"], cwd=control)
    git(["push", "origin", "agent-control"], cwd=control)


def result_for(item: dict[str, Path | str]) -> dict:
    path = Path(item["control"]) / ".agent" / "results" / "shared-task-id.json"
    return json.loads(path.read_text(encoding="utf-8"))


class ParallelIntegrationTests(unittest.TestCase):
    def test_two_parallel_safe_repositories_reach_shared_barrier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = create_repository_fixture(root, "parallel-a")
            second = create_repository_fixture(root, "parallel-b")
            marker_a = root / "parallel-a.started"
            marker_b = root / "parallel-b.started"
            configure_parallel_barrier_task(
                first,
                own_marker=marker_a,
                peer_marker=marker_b,
            )
            configure_parallel_barrier_task(
                second,
                own_marker=marker_b,
                peer_marker=marker_a,
            )
            registry = write_registry(root, (first, second))
            home, env = test_environment(root)

            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "agent_parallel.py"),
                    "--registry",
                    str(registry),
                    "--max-workers",
                    "2",
                    "--once",
                ],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=90,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue(marker_a.exists(), result.stdout)
            self.assertTrue(marker_b.exists(), result.stdout)

            for item in (first, second):
                payload = result_for(item)
                self.assertEqual(payload["status"], "done", result.stdout)
                self.assertEqual(payload["daemon_version"], RELEASE_VERSION)
                claim_root = (
                    home
                    / "Library"
                    / "Application Support"
                    / "local-agent"
                    / "repositories"
                    / str(item["id"])
                    / "claims"
                )
                self.assertEqual(list(claim_root.glob("*.json")), [])
                self.assertEqual(
                    git(["status", "--porcelain"], cwd=Path(item["work"])),
                    "",
                )


if __name__ == "__main__":
    unittest.main()
