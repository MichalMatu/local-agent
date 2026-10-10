from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

from local_agent.foundation import process as process_lifecycle
from local_agent.repository.worker import MULTIREPO_DAEMON_VERSION
from local_agent.repository.context import load_repository_registry, repository_config_digest


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


def write_test_catalog(root: Path, repository_id: str, repository: str, agent_binding: str) -> Path:
    catalog = root / "agent_bindings.json"
    payload = {"version": 1, "agents": []}
    if catalog.exists():
        payload = json.loads(catalog.read_text(encoding="utf-8"))
    payload["agents"] = [
        item for item in payload["agents"]
        if str(item.get("id", "")).casefold() != repository_id.casefold()
    ]
    payload["agents"].append(
        {
            "id": repository_id,
            "repository": repository,
            "agent_binding": agent_binding,
            "execution_enabled": True,
        }
    )
    catalog.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return catalog


def create_repository_fixture(root: Path, repository_id: str) -> dict[str, Path | str]:
    repository = f"test/{repository_id}"
    agent_binding = str(
        uuid.uuid5(uuid.NAMESPACE_URL, f"local-agent-integration:{repository}")
    )
    write_test_catalog(root, repository_id, repository, agent_binding)
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
    (seed / ".agent" / "binding.json").write_text(
        json.dumps(
            {
                "version": 1,
                "repository_id": repository_id,
                "repository": repository,
                "agent_binding": agent_binding,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    git(["add", ".agent"], cwd=seed)
    git(["commit", "-m", "Initialize bound agent control"], cwd=seed)
    git(["push", "-u", "origin", "agent-control"], cwd=seed)

    git(["clone", "--branch", "agent-control", str(remote), str(control)])
    git(["clone", "--branch", "main", str(remote), str(work)])
    configure_identity(control)
    configure_identity(work)

    task = {
        "id": "shared-task-id",
        "agent_binding": agent_binding,
        "mode": "commands",
        "work_branch": "main",
        "allow_write": False,
        "resources": [],
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
        "repository": repository,
        "agent_binding": agent_binding,
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
                        "agent_binding": item["agent_binding"],
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
    hook = root / "sitecustomize.py"
    hook.write_text(
        "import os\n"
        "from pathlib import Path\n"
        "import local_agent.repository.binding as binding\n"
        "catalog = os.environ.get('LOCAL_AGENT_TEST_CATALOG')\n"
        "if catalog:\n"
        "    binding.DEFAULT_CATALOG_PATH = Path(catalog)\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    # These subprocess fixtures form independent fake repositories. Python's
    # normal subprocess.Popen closes outer task lease descriptors, so copying
    # their environment markers would advertise FDs the child does not own.
    # Drop them from the *fixture copy* only; never alter real task leases.
    for key in (
        process_lifecycle.LEASE_FDS_ENV,
        process_lifecycle.LEASE_KEYS_DIGEST_ENV,
        process_lifecycle.RESOURCE_LEASE_FDS_ENV,
    ):
        env.pop(key, None)
    env["HOME"] = str(home)
    env["LOCAL_AGENT_TEST_CATALOG"] = str(root / "agent_bindings.json")
    env["PYTHONPATH"] = os.pathsep.join((str(root), str(REPO_ROOT)))
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


def queue_equivalent_duplicate(
    root: Path,
    item: dict[str, Path | str],
) -> Path:
    control = Path(item["control"])
    original_path = control / ".agent" / "tasks" / "shared-task-id.json"
    original = json.loads(original_path.read_text(encoding="utf-8"))
    counter = root / "serial-dedupe-counter.txt"
    command = (
        f"printf 'run\\n' >> {str(counter)!r}; "
        f"printf '{item['id']}-ok\\n'"
    )
    original["steps"][0]["command"] = command
    original_path.write_text(json.dumps(original, indent=2) + "\n", encoding="utf-8")

    duplicate = json.loads(json.dumps(original))
    duplicate["id"] = "zz-duplicate-task-id"
    duplicate_path = control / ".agent" / "tasks" / "zz-duplicate-task-id.json"
    duplicate_path.write_text(json.dumps(duplicate, indent=2) + "\n", encoding="utf-8")

    git(
        [
            "add",
            ".agent/tasks/shared-task-id.json",
            ".agent/tasks/zz-duplicate-task-id.json",
        ],
        cwd=control,
    )
    git(["commit", "-m", "Queue equivalent duplicate tasks"], cwd=control)
    git(["push", "origin", "agent-control"], cwd=control)
    return counter


class MultiRepositoryIntegrationTests(unittest.TestCase):
    def test_isolated_fixture_env_does_not_advertise_outer_lease_fds(self) -> None:
        inherited = {
            process_lifecycle.LEASE_FDS_ENV: "4",
            process_lifecycle.LEASE_KEYS_DIGEST_ENV: "a" * 64,
            process_lifecycle.RESOURCE_LEASE_FDS_ENV: "5",
            "LOCAL_AGENT_FIXTURE_SENTINEL": "safe-value",
        }
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, inherited):
                _home, child_env = test_environment(Path(tmp))
                for name in (
                    process_lifecycle.LEASE_FDS_ENV,
                    process_lifecycle.LEASE_KEYS_DIGEST_ENV,
                    process_lifecycle.RESOURCE_LEASE_FDS_ENV,
                ):
                    self.assertNotIn(name, child_env)
                    self.assertEqual(os.environ[name], inherited[name])
                self.assertEqual(
                    child_env["LOCAL_AGENT_FIXTURE_SENTINEL"], "safe-value"
                )

    def test_two_repository_workers_with_same_task_id_are_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = create_repository_fixture(root, "project-a")
            second = create_repository_fixture(root, "project-b")
            registry = write_registry(root, (first, second))
            home, env = test_environment(root)
            repositories = {
                repository.repository_id: repository
                for repository in load_repository_registry(home=home, path=registry)
            }

            for item in (first, second):
                repository_id = str(item["id"])
                result = subprocess.run(
                    [
                        sys.executable,
                        "-m", "local_agent.repository.worker",
                        "--repository-id",
                        repository_id,
                        "--expected-config-digest",
                        repository_config_digest(repositories[repository_id]),
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

    def test_serial_supervisor_uses_parallel_dedupe_admission_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            item = create_repository_fixture(root, "project-a")
            counter = queue_equivalent_duplicate(root, item)
            registry = write_registry(root, (item,))
            _home, env = test_environment(root)

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
            self.assertEqual(counter.read_text(encoding="utf-8").splitlines(), ["run"])

            control = Path(item["control"])
            executed = json.loads(
                (control / ".agent" / "results" / "shared-task-id.json").read_text(
                    encoding="utf-8"
                )
            )
            suppressed = json.loads(
                (control / ".agent" / "results" / "zz-duplicate-task-id.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(executed["status"], "done")
            self.assertEqual(suppressed["status"], "done")
            self.assertEqual(suppressed["outcome"], "duplicate_task_suppressed")
            self.assertEqual(suppressed["duplicate_of"], "shared-task-id")
            self.assertEqual(suppressed["duplicate_reason"], "queued_duplicate")


if __name__ == "__main__":
    unittest.main()
