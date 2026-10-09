"""Synthetic global parent fence writer: atomic CAS and fail-closed recovery."""

from __future__ import annotations

import copy
import json
import unittest

from local_agent.conversation import github_fabric_github as git
from local_agent.conversation import github_fabric_parent_fence_preview as preview
from local_agent.conversation import github_fabric_parent_fence_private_github as writer
from local_agent.conversation import github_fabric_private_github as private
from tests.test_github_fabric_dispatch import admitted_children, operator_request
from tests.test_github_fabric_private_github import PrivateGitDataAPI


class ParentFenceAPI(PrivateGitDataAPI):
    def __init__(self) -> None:
        super().__init__()
        self.truncated = False
        self.bad_tree = False

    def request(self, method, path, body=None):
        if method == "GET" and path.startswith("/git/trees/"):
            self.operations.append((method, path, None))
            sha, _, option = path[len("/git/trees/"):].partition("?")
            if option != "recursive=1":
                raise AssertionError("expected commit-pinned recursive tree")
            return {
                "sha": ("0" * 40) if self.bad_tree else sha,
                "truncated": self.truncated,
                "tree": [
                    {"path": name, "mode": "100644", "type": "blob"}
                    for name in sorted(self.trees[sha])
                ],
            }
        if method == "POST" and path == "/git/trees" and len(body["tree"]) == 2:
            self.operations.append((method, path, copy.deepcopy(body)))
            sha = self.new_sha()
            data = copy.deepcopy(self.trees[body["base_tree"]])
            for entry in body["tree"]:
                if entry["type"] != "blob" or entry["mode"] != "100644":
                    raise AssertionError("unsafe tree write")
                data[entry["path"]] = self.blobs[entry["sha"]]
            self.trees[sha] = data
            return {"sha": sha}
        return super().request(method, path, body)


class PrivateParentFenceWriterTests(unittest.TestCase):
    def setUp(self):
        self.api = ParentFenceAPI()
        self.operator = operator_request()
        self.children = admitted_children()
        self.record = preview.build_preview(
            self.operator, self.children, transport_mode="github_first"
        )
        self.path = preview.parent_path(self.record["id"])

    def publish(self, *, mode="github_first", **kw):
        arguments = {"api": self.api, "enabled": True}
        arguments.update(kw)
        return writer.publish_private_parent_fence_synthetic(
            self.operator, self.children, transport_mode=mode, **arguments
        )

    def test_disabled_or_private_fixture_never_touches_remote(self):
        with self.assertRaises(PermissionError):
            self.publish(enabled=False)
        self.children[0]["scope"]["summary"] = "CONFIDENTIAL CUSTOMER REQUEST"
        with self.assertRaises(PermissionError):
            self.publish()
        self.assertEqual(self.api.operations, [])
        self.assertEqual(self.api.commits, {})

    def test_single_atomic_commit_and_restart_replay_zero_writes(self):
        first = self.publish()
        self.assertEqual(first.status, "converged")
        self.assertEqual(first.parent_id, self.record["id"])
        self.assertEqual(first.head_sha, self.api.head)
        self.assertEqual(len(self.api.commits), 1)
        commit = next(iter(self.api.commits.values()))
        self.assertEqual(commit["parents"], ["a" * 40])
        self.assertEqual(
            [x[0] for x in self.api.operations if x[0] == "PATCH"], ["PATCH"]
        )
        remote = self.api.snapshots[self.api.head]
        self.assertEqual(json.loads(remote[self.path]), self.record)
        self.assertEqual(
            json.loads(remote[preview.INDEX_PATH]),
            {"schema_version": 1, "parent_ids": [self.record["id"]]},
        )
        tree_posts = [
            body for method, path, body in self.api.operations
            if method == "POST" and path == "/git/trees"
        ]
        self.assertEqual(len(tree_posts), 1)
        self.assertEqual(
            {x["path"] for x in tree_posts[0]["tree"]},
            {self.path, preview.INDEX_PATH},
        )
        before = len([event for event in self.api.operations if event[0] == "POST"])
        second = self.publish()
        self.assertEqual(second.status, "replay")
        self.assertEqual(len(self.api.commits), 1)
        self.assertEqual(
            len([event for event in self.api.operations if event[0] == "POST"]), before
        )

    def test_lost_ack_reconciles_one_commit_without_duplicate(self):
        self.api.fail_after_ref_number = 1
        result = self.publish()
        self.assertEqual(result.status, "converged")
        self.assertEqual(len(self.api.commits), 1)
        self.assertEqual(self.publish().status, "replay")

    def test_raced_ref_is_replanned_from_new_head(self):
        self.api.reject_next_ref = True
        result = self.publish()
        self.assertEqual(result.status, "converged")
        self.assertGreaterEqual(len(self.api.commits), 2)
        self.assertEqual(
            json.loads(self.api.snapshots[self.api.head][self.path]), self.record
        )
        self.assertTrue(all(
            body["force"] is False
            for method, _path, body in self.api.operations if method == "PATCH"
        ))

    def test_global_parent_mode_conflict_requires_explicit_retirement(self):
        self.publish()
        before = len(self.api.commits)
        with self.assertRaisesRegex(ValueError, "already occupied"):
            self.publish(mode="legacy_dom")
        self.assertEqual(len(self.api.commits), before)

    def test_orphan_and_unapproved_extra_path_fail_before_blob_write(self):
        self.api.trees["b" * 40]["parents/parent-" + "f" * 32 + ".json"] = "{}"
        self.api.snapshots[self.api.head] = copy.deepcopy(self.api.trees["b" * 40])
        with self.assertRaisesRegex(ValueError, "orphan or dangling"):
            self.publish()
        self.assertEqual(self.api.commits, {})
        self.api = ParentFenceAPI()
        self.api.trees["b" * 40]["parents/foreign.json"] = "{}"
        with self.assertRaisesRegex(ValueError, "unexpected path"):
            self.publish()
        self.assertEqual(self.api.commits, {})

    def test_dangling_corruption_and_forged_ack_denied(self):
        self.publish()
        before = len(self.api.commits)
        self.api.trees[self.api.commit_trees[self.api.head]].pop(self.path)
        self.api.snapshots[self.api.head].pop(self.path)
        with self.assertRaisesRegex(ValueError, "orphan or dangling"):
            self.publish()
        self.assertEqual(len(self.api.commits), before)

        self.api = ParentFenceAPI()
        self.publish()
        parent = json.loads(self.api.snapshots[self.api.head][self.path])
        parent["browser_send_authorized"] = True
        parent["ack_state"] = "browser_received"
        bad = json.dumps(parent)
        self.api.snapshots[self.api.head][self.path] = bad
        self.api.trees[self.api.commit_trees[self.api.head]][self.path] = bad
        with self.assertRaisesRegex(ValueError, "record invalid"):
            self.publish()
        self.assertEqual(len(self.api.commits), 1)

    def test_truncated_or_invalid_tree_and_403_abort(self):
        self.api.truncated = True
        with self.assertRaisesRegex(ValueError, "origin tree incomplete"):
            self.publish()
        self.api.truncated = False
        self.api.bad_tree = True
        with self.assertRaisesRegex(ValueError, "origin tree incomplete"):
            self.publish()
        self.api.bad_tree = False
        self.api.deny_next_request = True
        with self.assertRaises(git.GithubFabricHTTPError):
            self.publish()
        self.assertEqual(self.api.commits, {})

    def test_scoped_private_rest_never_allows_parent_write_or_arbitrary_tree_get(self):
        api = private.PrivateFabricREST("synthetic-test-token")
        for method, path in (
            ("POST", f"/contents/parents/{self.record['id']}.json?ref=" + "a" * 40),
            ("PATCH", "/contents/parents/index.json?ref=" + "a" * 40),
            ("GET", "/contents/parents/private.txt?ref=" + "a" * 40),
            ("GET", "/git/trees/" + "a" * 40 + "?recursive=0"),
        ):
            with self.subTest(path=path), self.assertRaises(ValueError):
                api.request(method, path)
        self.assertEqual(writer.MAX_ATTEMPTS, 6)


if __name__ == "__main__":
    unittest.main()
