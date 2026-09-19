from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from local_agent.repository.context import RepositoryContext
from local_agent.runtime.task_contract import task_digest
from local_agent.workflow import contract, evidence, lineage_coordinator, publishing, revisions
from local_agent.workflow.activation import WorkflowRevisionActivationStore
from local_agent.workflow.effective_state import WorkflowEffectiveStateStore
from local_agent.workflow.revision_store import WorkflowRevisionStore
from local_agent.workflow.store import WorkflowStore


BINDINGS = {
    "repo-a": "00000000-0000-4000-8000-000000000141",
    "repo-b": "00000000-0000-4000-8000-000000000142",
}
WORKFLOW_ID = "temporary-git-lineage"


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


def task_node(
    node_id: str,
    repository_id: str,
    depends_on: list[str],
) -> dict:
    return {
        "id": node_id,
        "kind": "task",
        "repository_id": repository_id,
        "agent_binding": BINDINGS[repository_id],
        "depends_on": depends_on,
        "task": {
            "work_branch": "main",
            "allow_write": False,
            "resources": [],
            "commands": ["true"],
        },
    }


def base_manifest() -> dict:
    return {
        "schema_version": 1,
        "id": WORKFLOW_ID,
        "created_at": "2026-09-19T15:40:00Z",
        "nodes": [
            task_node("audit", "repo-a", []),
            {
                "id": "review-audit",
                "kind": "planner_checkpoint",
                "depends_on": ["audit"],
            },
        ],
    }


def revision_one(base: dict) -> dict:
    return {
        "schema_version": 1,
        "workflow_id": WORKFLOW_ID,
        "revision": 1,
        "created_at": "2026-09-19T15:41:00Z",
        "parent_digest": contract.manifest_digest(base),
        "checkpoint_node_id": "review-audit",
        "nodes": [
            task_node("implement", "repo-a", ["review-audit"]),
            {
                "id": "review-implementation",
                "kind": "planner_checkpoint",
                "depends_on": ["implement"],
            },
        ],
    }


def revision_two(base: dict, first: dict) -> dict:
    return {
        "schema_version": 1,
        "workflow_id": WORKFLOW_ID,
        "revision": 2,
        "created_at": "2026-09-19T15:42:00Z",
        "parent_digest": revisions.revision_digest(first),
        "checkpoint_node_id": "review-implementation",
        "nodes": [task_node("verify", "repo-b", ["review-implementation"])],
    }


def read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError(f"expected object JSON: {path}")
    return payload


class DisposableGitLineageControlPlane:
    """Test-only local Git adapter; it never pushes a remote."""

    def inspect_child(
        self,
        repository: RepositoryContext,
        task_id: str,
        expected_digest: str,
    ):
        control = repository.control
        return evidence.classify_child_evidence(
            task_payload=read_json(control / ".agent" / "tasks" / f"{task_id}.json"),
            status_payload=read_json(control / ".agent" / "status" / "daemon.json"),
            result_payload=read_json(control / ".agent" / "results" / f"{task_id}.json"),
            expected_task_id=task_id,
            expected_digest=expected_digest,
        )

    def publish_child(self, repository: RepositoryContext, task: dict) -> None:
        control = repository.control.resolve()
        target = (control / ".agent" / "tasks" / f"{task['id']}.json").resolve()
        if control not in target.parents:
            raise AssertionError("test task path escaped disposable checkout")
        if target.exists():
            raise AssertionError("duplicate lineage child publication")
        target.write_text(
            json.dumps(task, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        relative = target.relative_to(control).as_posix()
        run_git(control, "add", "--", relative)
        run_git(control, "commit", "-m", f"Publish lineage child {task['id']}", "--", relative)

    def has_unrelated_work(
        self,
        repository: RepositoryContext,
        child_task_id: str,
    ) -> bool:
        control = repository.control
        tasks: list[dict] = []
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

    @staticmethod
    def publish_success(repository: RepositoryContext, task: dict) -> None:
        result = {
            "id": task["id"],
            "status": "done",
            "task_digest": task_digest(task),
        }
        path = repository.control / ".agent" / "results" / f"{task['id']}.json"
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class WorkflowTemporaryGitLineageTests(unittest.TestCase):
    def test_revision_one_to_two_uses_real_disposable_git_without_republishing_old_child(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo_a = repository(root, "repo-a")
            repo_b = repository(root, "repo-b")
            repositories = [repo_a, repo_b]
            control = DisposableGitLineageControlPlane()

            workflow_store = WorkflowStore(root / "workflow-state")
            base = base_manifest()
            workflow_store.submit(base)
            for target in ("dispatched", "running", "succeeded"):
                workflow_store.set_node_state(WORKFLOW_ID, "audit", target)
            audit_resolution = workflow_store.resolve_planner_checkpoint(
                WORKFLOW_ID,
                "review-audit",
                resolver="chatgpt-planner",
            )

            revision_store = WorkflowRevisionStore(workflow_store)
            activation_store = WorkflowRevisionActivationStore(
                workflow_store,
                revision_store,
            )
            first = revision_one(base)
            revision_store.append(WORKFLOW_ID, first)
            base_states = dict(workflow_store.load_state(WORKFLOW_ID)["node_states"])
            activation_store.append(
                WORKFLOW_ID,
                1,
                base_states,
                audit_resolution,
                activated_at="2026-09-19T15:43:00Z",
            )
            effective = WorkflowEffectiveStateStore(
                workflow_store,
                revision_store,
                activation_store,
            )
            effective.initialize(WORKFLOW_ID)

            implement_rev1 = publishing.materialize_lineage_child_task(
                base,
                [first],
                "implement",
            )
            first_tick = lineage_coordinator.tick_lineage_workflow(
                effective,
                WORKFLOW_ID,
                repositories,
                control,
            )
            self.assertEqual(first_tick.published, ("implement",))
            self.assertTrue(
                (repo_a.control / ".agent" / "tasks" / f"{implement_rev1['id']}.json").is_file()
            )
            self.assertEqual(int(run_git(repo_a.control, "rev-list", "--count", "HEAD")), 2)

            control.publish_success(repo_a, implement_rev1)
            lineage_coordinator.tick_lineage_workflow(
                effective,
                WORKFLOW_ID,
                repositories,
                control,
            )
            self.assertEqual(
                effective.load(WORKFLOW_ID)["node_states"]["review-implementation"],
                "waiting_planner",
            )
            implementation_resolution = effective.resolve_planner_checkpoint(
                WORKFLOW_ID,
                "review-implementation",
                resolver="chatgpt-planner",
                resolved_at="2026-09-19T15:44:00Z",
            )

            second = revision_two(base, first)
            revision_store.append(WORKFLOW_ID, second)
            before_rev2 = effective.load(WORKFLOW_ID)
            activation_store.append(
                WORKFLOW_ID,
                2,
                dict(before_rev2["node_states"]),
                implementation_resolution,
                activated_at="2026-09-19T15:44:01Z",
            )
            effective.activate_next_revision(WORKFLOW_ID)

            implement_rev2_view = publishing.materialize_lineage_child_task(
                base,
                [first, second],
                "implement",
            )
            self.assertEqual(implement_rev2_view, implement_rev1)

            restarted = WorkflowEffectiveStateStore(WorkflowStore(root / "workflow-state"))
            second_tick = lineage_coordinator.tick_lineage_workflow(
                restarted,
                WORKFLOW_ID,
                repositories,
                control,
            )
            self.assertEqual(second_tick.published, ("verify",))
            self.assertEqual(int(run_git(repo_a.control, "rev-list", "--count", "HEAD")), 2)
            self.assertEqual(
                len(list((repo_a.control / ".agent" / "tasks").glob("*.json"))),
                1,
            )

            verify = publishing.materialize_lineage_child_task(
                base,
                [first, second],
                "verify",
            )
            self.assertTrue(
                (repo_b.control / ".agent" / "tasks" / f"{verify['id']}.json").is_file()
            )
            self.assertEqual(int(run_git(repo_b.control, "rev-list", "--count", "HEAD")), 2)

            control.publish_success(repo_b, verify)
            lineage_coordinator.tick_lineage_workflow(
                restarted,
                WORKFLOW_ID,
                repositories,
                control,
            )
            final = restarted.load(WORKFLOW_ID)
            self.assertEqual(final["workflow_state"], "completed")
            self.assertEqual(final["node_states"]["implement"], "succeeded")
            self.assertEqual(final["node_states"]["verify"], "succeeded")


if __name__ == "__main__":
    unittest.main()
