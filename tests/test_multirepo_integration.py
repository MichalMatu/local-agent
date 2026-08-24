from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agent_repo_worker import MULTIREPO_DAEMON_VERSION


REPO_ROOT = Path(__file__).resolve().parents[1]


def git(args: list[str], *, cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed:\n{result.stdout}")
    return result.stdout


def configure_identity(path: Path) -> None:
    git(["config", "user.name", "local-agent-tests"], cwd=path)
    git(["config", "user.email", "local-agent-tests@example.invalid"], cwd=path)


def create_repository_fixture(root: Path, repository_id: str) -> dict[str, Path | str]:
    remote = root / f"{repository_id}.git"
    seed = root / f"{repository_id}-seed"
    control = root / f"{repository_id}-control"
    work = root / f"{repository_id}-work"
    checkpoints = root / f"{repository_id}-checkpoints"

    git(["init", "--bare", str(remote)])
    git(["init", str(seed)])
    configure_identity(seed)
    (seed / "README.md").write_text(f"# {repository_id}\n", encoding="utf-8")
    git(["add", "README.md"], cwd=seed)
    git(["commit", "-m", "Initial main"], cwd=seed)
    git(["branch", "-M", "main"], cwd=seed)
    git(["remote", "add", "origin", str(remote)], cwd=seed)
    git(["push", "-u", "origin", "main"], cwd=seed)

    git(["checkout", "--orphan", "agent-control"], cwd=seed)
    git(["rm", "-rf", "."], cwd=seed)
    for directory in (
        ".agent/tasks",
        ".agent/results",
        ".agent/runs",
        ".agent/status",
        ".agent/daemon/acks",
    ):
        target = seed / directory
        target.mkdir(parents=True, exist_ok=True)
        (target / ".gitkeep").write_text("", encoding="utf-8")
    git(["add", ".agent"], cwd=seed)
    git(["commit", "-m", "Initialize agent control"], cwd=seed)
    git(["push", "-u", "origin", "agent-control"], cwd=seed)

    git(["clone", "--branch", "agent-control", str(remote), str(control)])
    git(["clone", "--branch", "main", str(remote), str(work)])
    configure_identity(control)
    configure_identity(work)

    task = {
        "id": "shared-task-id",
        "mode": "commands",
        "work_branch": "main",
        "allow_write": False,
        "command_timeout": 30,
        "idle_timeout": 10,
        "task_timeout": 120,
        "memory_limit_mb": 256,
        "steps": [
            {
                "name": "identity",
                "command": f"printf '{repository_id}-ok\\n'",
                "timeout": 30,
            }
        ],
    }
    task_path = control / ".agent" / "tasks" / "shared-task-id.json"
    task_path.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
    git(["add", ".agent/tasks/shared-task-id.json"], cwd=control)
    git(["commit", "-m", f"Queue {repository_id} smoke task"], cwd=control)
    git(["push", "origin", "agent-control"], cwd=control)

    return {
        "id": repository_id,
        "repository": f"test/{repository_id}",
        "control": control,
        "work": work,
        "checkpoints": checkpoints,
    }


def write_registry(root: Path, repositories: tuple[dict[str, Path | str], ...]) -> Path:
    registry = root / "repositories.json"
    registry.write_text(
        json.dumps(
            {
                "version": 1,
                "repositories": [
                    {
                        "id": item["id"],
                        "repository": item["repository"],
                        "control_dir": str(item["control"]),
                        "work_dir": str(item["work"]),
                        "checkpoints_dir": str(item["checkpoints"]),
                    }
                    for item in repositories
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry


def test_environment(root: Path) -> tuple[Path, dict[str, str]]:
    home = root / "home"
    home.mkdir()
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PYTHONPATH"] = str(REPO_ROOT)
    return home, env


def assert_repository_result(
    case: unittest.TestCase,
    item: dict[str, Path | str],
    home: Path,
) -> dict:
    result_path = Path(item["control"]) / ".agent" / "results" / "shared-task-id.json"
    case.assertTrue(result_path.exists())
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    case.assertEqual(payload["status"], "done")
    case.assertEqual(payload["daemon_version"], MULTIREPO_DAEMON_VERSION)
    case.assertIn(f"{item['id']}-ok", payload["commands"][0]["output"])

    claim_root = (
        home
        / "Library"
        / "Application Support"
        / "local-agent"
        / "repositories"
        / str(item["id"])
        / "claims"
    )
    case.assertEqual(list(claim_root.glob("*.json")), [])
    case.assertEqual(git(["status", "--porcelain"], cwd=Path(item["work"])), "")
    return payload


class MultiRepositoryIntegrationTests(unittest.TestCase):
    def test_two_repository_workers_with_same_task_id_are_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = create_repository_fixture(root, "project-a")
            second = create_repository_fixture(root, "project-b")
            registry = write_registry(root, (first, second))
            home, env = test_environment(root)

            for item in (first, second):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(REPO_ROOT / "agent_repo_worker.py"),
                        "--repository-id",
                        str(item["id"]),
                        "--registry",
                        str(registry),
                    ],
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=60,
                    check=False,
                )
                self.assertEqual(result.returncode, 10, result.stdout)

            first_result = assert_repository_result(self, first, home)
            second_result = assert_repository_result(self, second, home)
            self.assertNotEqual(
                first_result["commands"][0]["output"],
                second_result["commands"][0]["output"],
            )

    def test_supervisor_processes_two_repositories_across_serial_cycles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = create_repository_fixture(root, "project-a")
            second = create_repository_fixture(root, "project-b")
            registry = write_registry(root, (first, second))
            home, env = test_environment(root)

            for _ in range(2):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(REPO_ROOT / "agent_multirepo.py"),
                        "--registry",
                        str(registry),
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

            first_result = assert_repository_result(self, first, home)
            second_result = assert_repository_result(self, second, home)
            self.assertNotEqual(
                first_result["commands"][0]["output"],
                second_result["commands"][0]["output"],
            )


if __name__ == "__main__":
    unittest.main()
