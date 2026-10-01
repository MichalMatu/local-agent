from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from local_agent.conversation import contract
from local_agent.conversation.spawn_store import WorkflowConversationSpawnStore
from local_agent.conversation.store import WorkflowConversationStore
from local_agent.development.lab import build_dev_lab_layout, initialize_dev_lab
from local_agent.development.live_runner import (
    _write_journal,
    load_runner_journal,
    run_live_slice,
    runner_paths,
)
from local_agent.development.live_slice import (
    arm_live_slice,
    live_slice_paths,
    prepare_live_slice,
)
from local_agent.workflow import contract as workflow_contract
from local_agent.workflow.store import WorkflowStore


BINDING = "12345678-1234-4abc-8def-1234567890ab"
PARENT_URL = "https://chatgpt.com/c/11111111-1111-4111-8111-111111111111"
CHILD_URL = "https://chatgpt.com/c/22222222-2222-4222-8222-222222222222"
WORKFLOW_ID = "live-runner-workflow"
NODE_ID = "reasoning-node"
REQUEST_ID = "live-runner-child"


def workflow_manifest() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "id": WORKFLOW_ID,
        "created_at": "2026-09-24T18:00:00Z",
        "nodes": [
            {
                "id": NODE_ID,
                "kind": "reasoning",
                "repository_id": "local-agent",
                "agent_binding": BINDING,
                "depends_on": [],
            }
        ],
    }


def child_request(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": contract.CHILD_REQUEST_SCHEMA_VERSION,
        "id": REQUEST_ID,
        "workflow_id": WORKFLOW_ID,
        "workflow_node_id": NODE_ID,
        "workflow_node_revision": 0,
        "workflow_node_introduction_digest": workflow_contract.manifest_digest(manifest),
        "parent_conversation_url": PARENT_URL,
        "created_at": "2026-09-24T18:01:00Z",
        "role": "verification",
        "repository_id": "local-agent",
        "agent_binding": BINDING,
        "repository_ref": "develop/conversation-fabric",
        "repository_commit_sha": "a" * 40,
        "scope": {
            "summary": "Run one bounded live runner proof.",
            "paths": ["local_agent/conversation"],
        },
        "context_refs": [],
        "bootstrap_contract_version": contract.BOOTSTRAP_CONTRACT_VERSION,
    }


class FakeBrowserSession:
    def __init__(
        self,
        *,
        ready: dict[str, Any] | None = None,
        create: dict[str, Any] | None = None,
        recover_create: dict[str, Any] | None = None,
        probe: dict[str, Any] | None = None,
        submit: dict[str, Any] | None = None,
        reconcile: dict[str, Any] | None = None,
    ) -> None:
        self.responses = {
            "wait_ready": ready or {"ok": True, "reason": "chatgpt_ready"},
            "create": create or {"ok": True, "reason": "tab_created", "tabId": 41},
            "recover_create": recover_create
            or {"ok": True, "reason": "tab_recovered", "tabId": 41},
            "probe": probe or {"ok": True, "reason": "spawn_ready"},
            "submit": submit
            or {
                "ok": True,
                "reason": "identity_discovered",
                "childConversationUrl": CHILD_URL,
            },
            "reconcile": reconcile
            or {
                "ok": True,
                "reason": "identity_discovered",
                "childConversationUrl": CHILD_URL,
            },
        }
        self.calls: list[str] = []

    def wait_ready(self, *, timeout_seconds: int) -> dict[str, Any]:
        self.assert_timeout(timeout_seconds)
        self.calls.append("wait_ready")
        return dict(self.responses["wait_ready"])

    @staticmethod
    def assert_timeout(timeout_seconds: int) -> None:
        if timeout_seconds < 1:
            raise AssertionError("timeout must be positive")

    def create(self, intent: dict[str, Any]) -> dict[str, Any]:
        self.calls.append("create")
        self._assert_intent(intent)
        return dict(self.responses["create"])

    def recover_create(self, intent: dict[str, Any]) -> dict[str, Any]:
        self.calls.append("recover_create")
        self._assert_intent(intent)
        return dict(self.responses["recover_create"])

    def probe(self, intent: dict[str, Any]) -> dict[str, Any]:
        self.calls.append("probe")
        self._assert_intent(intent, require_tab=True)
        return dict(self.responses["probe"])

    def submit(self, intent: dict[str, Any]) -> dict[str, Any]:
        self.calls.append("submit")
        self._assert_intent(intent, require_tab=True)
        return dict(self.responses["submit"])

    def reconcile(self, intent: dict[str, Any]) -> dict[str, Any]:
        self.calls.append("reconcile")
        self._assert_intent(intent, require_tab=True)
        return dict(self.responses["reconcile"])

    def close(self) -> None:
        self.calls.append("close")

    @staticmethod
    def _assert_intent(intent: dict[str, Any], *, require_tab: bool = False) -> None:
        if not str(intent.get("transaction_id", "")).startswith("spawn-"):
            raise AssertionError("missing spawn transaction identity")
        if require_tab and not isinstance(intent.get("tab_id"), int):
            raise AssertionError("browser action requires durable tab id")


class DevelopmentLiveRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.layout = build_dev_lab_layout(home=self.home)
        extension = self.layout.checkout / "chat_bridge"
        extension.mkdir(parents=True)
        (extension / "manifest.json").write_text("{}\n", encoding="utf-8")
        initialize_dev_lab(self.layout)

        self.workflow_store = WorkflowStore(self.layout.state_dir)
        self.manifest = workflow_manifest()
        self.workflow_store.submit(self.manifest)
        self.conversations = WorkflowConversationStore(self.workflow_store, WORKFLOW_ID)
        self.request = child_request(self.manifest)
        self.conversations.admit_request(self.request)
        self.spawns = WorkflowConversationSpawnStore(self.conversations)
        self.base_time = datetime(2026, 9, 24, 18, 30, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.base_time

    def prepare_and_arm(self, *, now: datetime | None = None) -> dict[str, Any]:
        prepared = prepare_live_slice(
            self.layout,
            WORKFLOW_ID,
            REQUEST_ID,
            created_at="2026-09-24T18:10:00Z",
        )
        arm = arm_live_slice(
            self.layout,
            expected_plan_digest=prepared["plan_digest"],
            ttl_seconds=300,
            now=now or self.base_time,
        )
        return {"prepared": prepared, "arm": arm}

    def run_with(self, session: FakeBrowserSession, nonce: str) -> dict[str, Any]:
        return run_live_slice(
            self.layout,
            launch_nonce=nonce,
            session_factory=lambda _layout: session,
            now=self.now,
        )

    def test_success_persists_registration_before_done_and_writes_evidence(self) -> None:
        armed = self.prepare_and_arm()
        session = FakeBrowserSession()

        result = self.run_with(session, armed["arm"]["launch_nonce"])

        self.assertEqual(result["status"], "completed")
        self.assertFalse(result["recovered"])
        self.assertEqual(result["child_conversation_url"], CHILD_URL)
        self.assertEqual(self.spawns.load_attempt(REQUEST_ID, 1)["state"], "done")
        self.assertEqual(
            self.conversations.load_registration(REQUEST_ID)["child_conversation_url"],
            CHILD_URL,
        )
        self.assertEqual(self.conversations.load_state(REQUEST_ID)["state"], "active")
        self.assertEqual(
            session.calls,
            ["wait_ready", "create", "probe", "submit", "close"],
        )
        self.assertFalse(live_slice_paths(self.layout).plan.exists())
        self.assertFalse(live_slice_paths(self.layout).arm.exists())
        self.assertFalse(runner_paths(self.layout).journal.exists())
        self.assertTrue(runner_paths(self.layout).evidence.is_file())

    def test_login_pause_consumes_arm_but_keeps_pending_attempt_rearmable(self) -> None:
        armed = self.prepare_and_arm()
        first = FakeBrowserSession(
            ready={"ok": False, "reason": "chatgpt_login_timeout"}
        )
        result = self.run_with(first, armed["arm"]["launch_nonce"])
        self.assertEqual(result["status"], "paused")
        self.assertEqual(self.spawns.load_attempt(REQUEST_ID, 1)["state"], "pending")
        self.assertEqual(load_runner_journal(self.layout)["phase"], "waiting_login")

        rearm = arm_live_slice(
            self.layout,
            expected_plan_digest=armed["prepared"]["plan_digest"],
            ttl_seconds=300,
            now=self.base_time + timedelta(seconds=1),
        )
        second = FakeBrowserSession()
        result = self.run_with(second, rearm["launch_nonce"])
        self.assertEqual(result["status"], "completed")
        self.assertIn("create", second.calls)
        self.assertNotIn("recover_create", second.calls)

    def test_uncertain_create_is_recovery_only_on_next_arm(self) -> None:
        armed = self.prepare_and_arm()
        first = FakeBrowserSession(
            create={"ok": False, "reason": "synthetic_create_uncertain"}
        )
        result = self.run_with(first, armed["arm"]["launch_nonce"])
        self.assertEqual(result["status"], "create_uncertain")
        self.assertEqual(self.spawns.load_attempt(REQUEST_ID, 1)["state"], "pending")
        self.assertEqual(load_runner_journal(self.layout)["phase"], "create_started")

        rearm = arm_live_slice(
            self.layout,
            expected_plan_digest=armed["prepared"]["plan_digest"],
            ttl_seconds=300,
            now=self.base_time + timedelta(seconds=1),
        )
        second = FakeBrowserSession(
            recover_create={"ok": True, "reason": "tab_recovered", "tabId": 77}
        )
        result = self.run_with(second, rearm["launch_nonce"])
        self.assertEqual(result["status"], "completed")
        self.assertIn("recover_create", second.calls)
        self.assertNotIn("create", second.calls)

    def test_missing_marker_after_uncertain_create_never_creates_replacement(self) -> None:
        armed = self.prepare_and_arm()
        first = FakeBrowserSession(
            create={"ok": False, "reason": "synthetic_create_uncertain"}
        )
        self.run_with(first, armed["arm"]["launch_nonce"])
        rearm = arm_live_slice(
            self.layout,
            expected_plan_digest=armed["prepared"]["plan_digest"],
            ttl_seconds=300,
            now=self.base_time + timedelta(seconds=1),
        )
        second = FakeBrowserSession(
            recover_create={"ok": False, "reason": "spawn_create_recovery_missing"}
        )

        result = self.run_with(second, rearm["launch_nonce"])

        self.assertEqual(result["status"], "manual_attach_required")
        self.assertEqual(self.spawns.load_attempt(REQUEST_ID, 1)["state"], "pending")
        self.assertEqual(second.calls.count("recover_create"), 1)
        self.assertNotIn("create", second.calls)

    def test_pre_submit_pause_resumes_same_tab_without_new_create(self) -> None:
        armed = self.prepare_and_arm()
        first = FakeBrowserSession(
            probe={"ok": False, "reason": "spawn_send_button_not_ready"}
        )
        result = self.run_with(first, armed["arm"]["launch_nonce"])
        self.assertEqual(result["status"], "paused")
        self.assertEqual(self.spawns.load_attempt(REQUEST_ID, 1)["state"], "bootstrap_ready")

        rearm = arm_live_slice(
            self.layout,
            expected_plan_digest=armed["prepared"]["plan_digest"],
            ttl_seconds=300,
            now=self.base_time + timedelta(seconds=1),
        )
        second = FakeBrowserSession()
        result = self.run_with(second, rearm["launch_nonce"])
        self.assertEqual(result["status"], "completed")
        self.assertNotIn("create", second.calls)
        self.assertIn("probe", second.calls)
        self.assertIn("submit", second.calls)

    def test_failed_submit_becomes_ambiguous_and_never_auto_retries(self) -> None:
        armed = self.prepare_and_arm()
        session = FakeBrowserSession(
            submit={"ok": False, "reason": "spawn_submission_ambiguous"}
        )

        result = self.run_with(session, armed["arm"]["launch_nonce"])

        self.assertEqual(result["status"], "manual_attach_required")
        transaction = self.spawns.load_attempt(REQUEST_ID, 1)
        self.assertEqual(transaction["state"], "ambiguous")
        self.assertFalse(result["needs_rearm"])
        with self.assertRaisesRegex(RuntimeError, "terminal or ambiguous"):
            arm_live_slice(
                self.layout,
                expected_plan_digest=armed["prepared"]["plan_digest"],
                now=self.base_time + timedelta(seconds=1),
            )

    def test_bootstrap_submitting_restart_reconciles_without_second_submit(self) -> None:
        armed = self.prepare_and_arm()
        transaction = self.spawns.begin_browser_attempt(
            REQUEST_ID,
            1,
            tab_id=91,
            updated_at="2026-09-24T18:20:00Z",
        )
        self.assertEqual(transaction["state"], "tab_created")
        self.spawns.advance(
            REQUEST_ID,
            1,
            target="bootstrap_ready",
            updated_at="2026-09-24T18:21:00Z",
        )
        self.spawns.advance(
            REQUEST_ID,
            1,
            target="bootstrap_submitting",
            updated_at="2026-09-24T18:22:00Z",
        )
        session = FakeBrowserSession()

        result = self.run_with(session, armed["arm"]["launch_nonce"])

        self.assertEqual(result["status"], "completed")
        self.assertIn("reconcile", session.calls)
        self.assertNotIn("submit", session.calls)
        self.assertNotIn("create", session.calls)

    def test_registration_written_before_crash_is_completed_without_new_arm(self) -> None:
        armed = self.prepare_and_arm()
        self.spawns.begin_browser_attempt(
            REQUEST_ID,
            1,
            tab_id=101,
            updated_at="2026-09-24T18:20:00Z",
        )
        self.spawns.advance(
            REQUEST_ID,
            1,
            target="bootstrap_ready",
            updated_at="2026-09-24T18:21:00Z",
        )
        self.spawns.advance(
            REQUEST_ID,
            1,
            target="bootstrap_submitting",
            updated_at="2026-09-24T18:22:00Z",
        )
        self.spawns.advance(
            REQUEST_ID,
            1,
            target="identity_discovered",
            child_conversation_url=CHILD_URL,
            updated_at="2026-09-24T18:23:00Z",
        )
        self.spawns.advance(
            REQUEST_ID,
            1,
            target="registration_submitting",
            updated_at="2026-09-24T18:24:00Z",
        )
        _write_journal(
            self.layout,
            document=armed["prepared"],
            phase="registration_started",
            now=self.base_time,
        )
        self.conversations.register_child(
            {
                "schema_version": contract.CHILD_REGISTRATION_SCHEMA_VERSION,
                "child_request_id": REQUEST_ID,
                "child_request_digest": contract.child_request_digest(self.request),
                "parent_conversation_url": PARENT_URL,
                "child_conversation_url": CHILD_URL,
                "registered_at": "2026-09-24T18:25:00Z",
            }
        )
        live_slice_paths(self.layout).arm.unlink()

        result = run_live_slice(
            self.layout,
            launch_nonce="already-consumed",
            session_factory=lambda _layout: self.fail("browser must not start"),
            now=self.now,
        )

        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["recovered"])
        self.assertEqual(self.spawns.load_attempt(REQUEST_ID, 1)["state"], "done")
        self.assertTrue(runner_paths(self.layout).evidence.is_file())


if __name__ == "__main__":
    unittest.main()
