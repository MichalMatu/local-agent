from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from local_agent.conversation import contract
from local_agent.development.lab import build_dev_lab_layout, initialize_dev_lab
from local_agent.development.live_slice import (
    MAX_ACTIVE_CHILDREN,
    MAX_BROWSER_SPAWNS,
    arm_live_slice,
    build_live_slice_plan,
    consume_live_slice_arm,
    live_slice_paths,
    live_slice_plan_digest,
    live_slice_status,
    load_prepared_live_slice,
    prepare_live_slice,
)


BINDING = "12345678-1234-4abc-8def-1234567890ab"
PARENT_URL = "https://chatgpt.com/c/11111111-1111-4111-8111-111111111111"


def child_request() -> dict:
    return {
        "schema_version": contract.CHILD_REQUEST_SCHEMA_VERSION,
        "id": "live-child-001",
        "workflow_id": "live-workflow",
        "workflow_node_id": "reasoning-node",
        "workflow_node_revision": 0,
        "workflow_node_introduction_digest": "sha256:" + "1" * 64,
        "parent_conversation_url": PARENT_URL,
        "created_at": "2026-09-24T18:00:00Z",
        "role": "verification",
        "repository_id": "local-agent",
        "agent_binding": BINDING,
        "repository_ref": "develop/conversation-fabric",
        "repository_commit_sha": "a" * 40,
        "scope": {
            "summary": "Run one bounded real-ChatGPT child proof in the DEV lab.",
            "paths": ["local_agent/conversation"],
        },
        "context_refs": [],
        "bootstrap_contract_version": contract.BOOTSTRAP_CONTRACT_VERSION,
    }


class DevelopmentLiveSliceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.layout = build_dev_lab_layout(home=self.home)
        extension = self.layout.checkout / "chat_bridge"
        extension.mkdir(parents=True)
        (extension / "manifest.json").write_text("{}\n", encoding="utf-8")
        initialize_dev_lab(self.layout)
        self.request = child_request()

    def test_plan_is_one_child_and_keeps_dangerous_capabilities_disabled(self) -> None:
        plan = build_live_slice_plan(self.layout, self.request)

        self.assertEqual(plan["mode"], "real-chatgpt-bounded")
        self.assertEqual(plan["limits"]["max_active_children"], MAX_ACTIVE_CHILDREN)
        self.assertEqual(plan["limits"]["max_browser_spawns"], MAX_BROWSER_SPAWNS)
        self.assertEqual(MAX_ACTIVE_CHILDREN, 1)
        self.assertEqual(MAX_BROWSER_SPAWNS, 1)
        self.assertTrue(plan["capabilities"]["real_chatgpt_enabled"])
        self.assertTrue(plan["capabilities"]["browser_spawn_enabled"])
        for capability in (
            "executor_enabled",
            "remote_control_enabled",
            "native_host_registration_enabled",
            "production_chrome_profile_enabled",
        ):
            self.assertFalse(plan["capabilities"][capability])
        self.assertEqual(
            plan["request"]["child_request_digest"],
            contract.child_request_digest(self.request),
        )
        self.assertEqual(plan["request"]["parent_conversation_url"], PARENT_URL)
        self.assertIn("LOCAL AGENT CHILD BOOTSTRAP", plan["request"]["bootstrap_text"])
        self.assertEqual(
            plan["protected_operational_branches"],
            ["chat-bridge-state", "operator-control"],
        )

        browser_profile = Path(plan["paths"]["browser_profile"])
        self.assertIn(self.layout.root.resolve(), browser_profile.resolve().parents)
        self.assertNotEqual(browser_profile, self.home / "Library/Application Support/Google/Chrome")

    def test_live_plan_requires_initialized_healthy_lab(self) -> None:
        other = build_dev_lab_layout(
            home=self.home,
            root=self.home / "other-lab",
            checkout=self.home / "other-checkout",
        )
        extension = other.checkout / "chat_bridge"
        extension.mkdir(parents=True)
        (extension / "manifest.json").write_text("{}\n", encoding="utf-8")

        with self.assertRaisesRegex(RuntimeError, "initialized and healthy"):
            build_live_slice_plan(other, self.request)

    def test_prepare_is_idempotent_but_refuses_different_request(self) -> None:
        first = prepare_live_slice(self.layout, self.request)
        second = prepare_live_slice(self.layout, self.request)
        self.assertEqual(first, second)
        self.assertEqual(first["plan_digest"], live_slice_plan_digest(first["plan"]))
        self.assertEqual(load_prepared_live_slice(self.layout), first)

        changed = copy.deepcopy(self.request)
        changed["id"] = "live-child-002"
        with self.assertRaisesRegex(RuntimeError, "differs"):
            prepare_live_slice(self.layout, changed)

    def test_arm_requires_exact_digest_and_is_consumed_before_external_effect(self) -> None:
        prepared = prepare_live_slice(self.layout, self.request)
        now = datetime(2026, 9, 24, 18, 30, tzinfo=timezone.utc)

        with self.assertRaisesRegex(ValueError, "digest does not match"):
            arm_live_slice(
                self.layout,
                expected_plan_digest="sha256:" + "f" * 64,
                now=now,
            )

        arm = arm_live_slice(
            self.layout,
            expected_plan_digest=prepared["plan_digest"],
            ttl_seconds=300,
            now=now,
        )
        self.assertEqual(len(arm["launch_nonce"]), 32)
        self.assertTrue(live_slice_status(self.layout, now=now)["armed"])

        with self.assertRaisesRegex(RuntimeError, "active one-shot arm"):
            arm_live_slice(
                self.layout,
                expected_plan_digest=prepared["plan_digest"],
                now=now + timedelta(seconds=1),
            )
        with self.assertRaisesRegex(ValueError, "nonce"):
            consume_live_slice_arm(
                self.layout,
                launch_nonce="0" * 32,
                now=now + timedelta(seconds=1),
            )

        consumed = consume_live_slice_arm(
            self.layout,
            launch_nonce=arm["launch_nonce"],
            now=now + timedelta(seconds=1),
        )
        self.assertEqual(consumed, prepared)
        self.assertFalse(live_slice_paths(self.layout).arm.exists())
        self.assertFalse(live_slice_status(self.layout, now=now)["armed"])
        with self.assertRaisesRegex(RuntimeError, "not armed"):
            consume_live_slice_arm(
                self.layout,
                launch_nonce=arm["launch_nonce"],
                now=now + timedelta(seconds=2),
            )

    def test_expired_arm_never_authorizes_launch_and_can_be_rearmed(self) -> None:
        prepared = prepare_live_slice(self.layout, self.request)
        now = datetime(2026, 9, 24, 18, 30, tzinfo=timezone.utc)
        arm = arm_live_slice(
            self.layout,
            expected_plan_digest=prepared["plan_digest"],
            ttl_seconds=1,
            now=now,
        )
        later = now + timedelta(seconds=2)
        status = live_slice_status(self.layout, now=later)
        self.assertFalse(status["armed"])
        self.assertTrue(status["expired"])

        with self.assertRaisesRegex(RuntimeError, "expired"):
            consume_live_slice_arm(
                self.layout,
                launch_nonce=arm["launch_nonce"],
                now=later,
            )
        replacement = arm_live_slice(
            self.layout,
            expected_plan_digest=prepared["plan_digest"],
            ttl_seconds=60,
            now=later,
        )
        self.assertNotEqual(replacement["launch_nonce"], arm["launch_nonce"])

    def test_symlinked_live_browser_profile_is_rejected(self) -> None:
        paths = live_slice_paths(self.layout)
        external = self.home / "external-profile"
        external.mkdir()
        paths.browser_profile.symlink_to(external, target_is_directory=True)

        with self.assertRaisesRegex(ValueError, "browser profile must stay below DEV lab root"):
            build_live_slice_plan(self.layout, self.request)

    def test_tampered_prepared_plan_fails_closed(self) -> None:
        prepared = prepare_live_slice(self.layout, self.request)
        paths = live_slice_paths(self.layout)
        tampered = copy.deepcopy(prepared)
        tampered["plan"]["limits"]["max_active_children"] = 2
        paths.plan.write_text(json.dumps(tampered), encoding="utf-8")

        with self.assertRaisesRegex(RuntimeError, "plan digest mismatch"):
            load_prepared_live_slice(self.layout)

    def test_prepare_refuses_existing_arm_record(self) -> None:
        prepared = prepare_live_slice(self.layout, self.request)
        now = datetime(2026, 9, 24, 18, 30, tzinfo=timezone.utc)
        arm_live_slice(
            self.layout,
            expected_plan_digest=prepared["plan_digest"],
            now=now,
        )

        with self.assertRaisesRegex(RuntimeError, "while an arm record exists"):
            prepare_live_slice(self.layout, self.request)


if __name__ == "__main__":
    unittest.main()
