from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from local_agent.repository.context import RepositoryContext
from local_agent.runtime.task_contract import task_digest
from local_agent.workflow import coordinator, evidence, publishing
from local_agent.workflow.store import WorkflowStore


BINDINGS = {
    "repo-a": "00000000-0000-4000-8000-0000000000d1",
    "repo-b": "00000000-0000-4000-8000-0000000000d2",
    "repo-c": "00000000-0000-4000-8000-0000000000d3",
}
WORKFLOW_ID = "temporary-git-three-repo"


def run_git(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=20,
    )
    if completed.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {completed.stdout}")
    return completed.stdout.strip()


def init_control_checkout(path: Path) -> None:
    path.mkdir(parents=True)
    run_git(path, "init")
    run_git(path, "config", "user.email", "workflow-test@example.invalid")
    run_git(path, "config", "user.name", "Workflow Test")
    run_git(path, "checkout", "-b", "agent-control")
    for relative in (".agent/tasks", ".agent/results", ".agent/status"):
        (path / relative).mkdir(parents=True)
    (path / ".agent" / ".keep").write_text("test-only\n", encoding="utf-8")
    run_git(path, "add", ".agent/.keep")
    run_git(path, "commit", "-m", "Initialize disposable control branch")


def repository(root: Path, repository_id: str) -> RepositoryContext:
    control = root / repository_id / "control"
    init_control_checkout(control)
    return RepositoryContext(
        repository_id=repository_id,
        repository=f"Owner/{repository_id}",
        control=control,
        work=root / repository_id / "work",
        checkpoints=root / repository_id / "checkpoints",
        control_branch="agent-control",
        agent_binding=BINDINGS[repository_id],
    )


def task_node(node_id: str, repository_id: str) -> dict:
    return {
        "id": node_id,
        "kind": "task",
        "repository_id": repository_id,
        "agent_binding": BINDINGS[repository_id],
        "depends_on": [],
        "task": {
            "work_branch": "main",
            "allow_write": False,
            "resources": [],
            "commands": ["true"],
        },
    }


def workflow_manifest() -> dict:
    return {
        "schema_version": 1,
        "id": WORKFLOW_ID,
        "created_at": "2026-09-19T14:00:00Z",
        "nodes": [
            task_node("backend", "repo-a"),
            task_node("android", "repo-b"),
            task_node("firmware", "repo-c"),
            {
                "id": "join",
                "kind": "barrier",
                "depends_on": ["backend", "android", "firmware"],
            },
        ],
    }


def read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError(f"expected object JSON: {path}")
    return payload


class DisposableGitControlPlane:
    """Test-only adapter. It never pushes and only writes supplied temp checkouts."""

    def inspect_child(
        self,
        repository: RepositoryContext,
        task_id: str,
        expected_digest: str,
    ) -> coordinator.ChildEvidence:
        control = repository.control
        return evidence.classify_child_evidence(
            task_payload=read_json(control / ".agent" / "tasks" / f"{task_id}.json"),
            status_payload=read_json(control / ".agent" / "status" / "daemon.json"),
            result_payload=read_json(control / ".agent" / "results" / f"{task_id}.json"),
            expected_task_id=task_id,
            expected_digest=expected_digest,
        )

    def publish_child(
        self,
        repository: RepositoryContext,
        task: dict,
    ) -> None:
        control = repository.control.resolve()
        target = (control / ".agent" / "tasks" / f"{task['id']}.json").resolve()
        if control not in target.parents:
            raise AssertionError("test task path escaped disposable control checkout")
        if target.exists():
            raise AssertionError("duplicate test child publication")
        target.write_text(
            json.dumps(task, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        relative = target.relative_to(control).as_posix()
        run_git(control, "add", "--", relative)
        run_git(control, "commit", "-m", f"Publish workflow child {task['id']}", "--", relative)

    def has_unrelated_work(
        self,
        repository: RepositoryContext,
        child_task_id: str,
    ) -> bool:
        control = repository.control
        tasks = []
        for path in sorted((control / ".agent" / "tasks").glob("*.json")):
            payload = read_json(path)
            if payload is not None:
                tasks.append(payload)
        results: dict[str, dict] = {}
        for path in sorted((control / ".agent" / "results").glob("*.json")):
            payload = read_json(path)
            if payload is not None and isinstance(payload.get("id"), str):
                results[str(payload["id"])] = payload
        return evidence.has_unrelated_work(
            child_task_id=child_task_id,
            status_payload=read_json(control / ".agent" / "status" / "daemon.json"),
            task_payloads=tasks,
            result_payloads=results,
        )

    def publish_success(
        self,
        repository: RepositoryContext,
        task: dict,
    ) -> None:
        result = {
            "id": task["id"],
            "status": "done",
            "task_digest": task_digest(task),
        }
        path = repository.control / ".agent" / "results" / f"{task['id']}.json"
        path.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


class WorkflowTemporaryGitIntegrationTests(unittest.TestCase):
    def test_three_repositories_publish_to_correct_disposable_control_branches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repositories = [
                repository(root, "repo-a"),
                repository(root, "repo-b"),
                repository(root, "repo-c"),
            ]
            by_id = {item.repository_id: item for item in repositories}
            manifest = workflow_manifest()
            store = WorkflowStore(root / "workflow-state")
            store.submit(manifest)
            control = DisposableGitControlPlane()

            tick = coordinator.tick_workflow(
                store,
                WORKFLOW_ID,
                repositories,
                control,
            )
            self.assertEqual(set(tick.published), {"backend", "android", "firmware"})

            for node_id, repository_id in (
                ("backend", "repo-a"),
                ("android", "repo-b"),
                ("firmware", "repo-c"),
            ):
                child = publishing.materialize_child_task(manifest, node_id)
                owner = by_id[repository_id]
                self.assertTrue(
                    (owner.control / ".agent" / "tasks" / f"{child['id']}.json").is_file()
                )
                for other_id, other in by_id.items():
                    if other_id == repository_id:
                        continue
                    self.assertFalse(
                        (other.control / ".agent" / "tasks" / f"{child['id']}.json").exists()
                    )
                self.assertEqual(
                    int(run_git(owner.control, "rev-list", "--count", "HEAD")),
                    2,
                )
                control.publish_success(owner, child)

            coordinator.tick_workflow(store, WORKFLOW_ID, repositories, control)
            final = store.load_state(WORKFLOW_ID)
            self.assertEqual(final["workflow_state"], "completed")
            self.assertEqual(final["node_states"]["join"], "succeeded")

    def test_unrelated_disposable_task_makes_only_that_repository_yield(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo_a = repository(root, "repo-a")
            repo_b = repository(root, "repo-b")
            manifest = {
                "schema_version": 1,
                "id": WORKFLOW_ID,
                "created_at": "2026-09-19T14:01:00Z",
                "nodes": [
                    task_node("backend", "repo-a"),
                    task_node("android", "repo-b"),
                ],
            }
            store = WorkflowStore(root / "workflow-state")
            store.submit(manifest)
            unrelated = {
                "id": "standalone-task",
                "agent_binding": BINDINGS["repo-a"],
                "resources": [],
                "commands": ["true"],
            }
            unrelated_path = repo_a.control / ".agent" / "tasks" / "standalone-task.json"
            unrelated_path.write_text(json.dumps(unrelated), encoding="utf-8")

            tick = coordinator.tick_workflow(
                store,
                WORKFLOW_ID,
                [repo_a, repo_b],
                DisposableGitControlPlane(),
            )
            self.assertEqual(tick.deferred_unrelated_work, ("backend",))
            self.assertEqual(tick.published, ("android",))
            backend = publishing.materialize_child_task(manifest, "backend")
            android = publishing.materialize_child_task(manifest, "android")
            self.assertFalse(
                (repo_a.control / ".agent" / "tasks" / f"{backend['id']}.json").exists()
            )
            self.assertTrue(
                (repo_b.control / ".agent" / "tasks" / f"{android['id']}.json").is_file()
            )


if __name__ == "__main__":
    unittest.main()
