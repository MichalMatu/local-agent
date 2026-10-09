"""Synthetic global parent fence writer: atomic CAS and fail-closed recovery."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import unittest

from local_agent.conversation import github_fabric_github as git
from local_agent.conversation import github_fabric_parent_fence_preview as preview
from local_agent.conversation import github_fabric_parent_fence_private_github as writer
from local_agent.conversation import github_fabric_private_github as private
from tests.test_github_fabric_dispatch import admitted_children, operator_request
from tests.test_github_fabric_private_github import PrivateGitDataAPI


def _blob_sha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


class ParentFenceAPI(PrivateGitDataAPI):
    def __init__(self) -> None:
        super().__init__()
        self.truncated = False
        self.bad_tree = False
        self.bad_tree_blob_sha = False
        self.alter_contents_bytes = False
        self.bad_contents_path = False
        self.root_mode = "040000"
        self.root_present = True
        self.root_duplicated = False
        self.root_sha = "f" * 40

    def request(self, method, path, body=None):
        if method == "GET" and path.startswith("/git/trees/"):
            self.operations.append((method, path, None))
            sha, _, option = path[len("/git/trees/"):].partition("?")
            if option != "recursive=1":
                raise AssertionError("expected commit-pinned recursive tree")
            return {
                "sha": ("0" * 40) if self.bad_tree else sha,
                "truncated": self.truncated,
                "tree": ([
                    {
                        "path": "parents", "mode": self.root_mode,
                        "type": "tree", "sha": self.root_sha,
                    }
                ] * (1 + int(self.root_duplicated)) if (
                    self.root_present and any(
                        name.startswith("parents/") for name in self.trees[sha]
                    )
                ) else []) + [
                    {
                        "path": name, "mode": "100644", "type": "blob",
                        "sha": ("0" * 40 if self.bad_tree_blob_sha and name == preview.INDEX_PATH
                                else _blob_sha(self.trees[sha][name].encode("utf-8"))),
                    }
                    for name in sorted(self.trees[sha])
                ],
            }
        if method == "GET" and path.startswith("/contents/parents/"):
            response = super().request(method, path, body)
            raw = base64.b64decode(response["content"], validate=True)
            response["sha"] = _blob_sha(raw)
            response["path"] = (
                "parents/other.json" if self.bad_contents_path else
                path[len("/contents/"):].partition("?ref=")[0]
            )
            if self.alter_contents_bytes:
                changed = raw + b" "
                response["content"] = base64.b64encode(changed).decode("ascii")
                response["size"] = len(changed)
            return response
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

    def test_racing_opposite_transport_acquisition_fails_closed(self):
        legacy = preview.build_preview(
            self.operator, self.children, transport_mode="legacy_dom"
        )
        parent_path = self.path

        class CompetingModeAPI(ParentFenceAPI):
            competing = True

            def request(self, method, path, body=None):
                if method == "PATCH" and self.competing:
                    self.competing = False
                    # Another writer wins the exact same parent with the
                    # opposite transport before this writer updates the ref.
                    tree_sha = self.new_sha()
                    tree = copy.deepcopy(self.trees[self.commit_trees[self.head]])
                    tree[parent_path] = json.dumps(legacy)
                    tree[preview.INDEX_PATH] = json.dumps({
                        "schema_version": 1, "parent_ids": [legacy["id"]],
                    })
                    self.trees[tree_sha] = tree
                    competing_head = self.new_sha()
                    self.commit_trees[competing_head] = tree_sha
                    self.snapshots[competing_head] = copy.deepcopy(tree)
                    self.head = competing_head
                return super().request(method, path, body)

        self.api = CompetingModeAPI()
        with self.assertRaisesRegex(ValueError, "already occupied"):
            self.publish()
        self.assertEqual(self.api.ref_successes, 0)
        self.assertEqual(
            json.loads(self.api.snapshots[self.api.head][self.path]), legacy
        )
        self.assertEqual(
            json.loads(self.api.snapshots[self.api.head][preview.INDEX_PATH])[
                "parent_ids"
            ], [legacy["id"]]
        )
        self.assertEqual(self.api.commits[next(iter(self.api.commits))]["parents"], [
            "a" * 40
        ])
        self.assertEqual(self.publish(mode="legacy_dom").status, "replay")

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

    def test_parent_directory_missing_duplicated_or_unsafe_refused(self):
        for field, mutation, expected in (
            ("root_present", False, "root missing"),
            ("root_duplicated", True, "root invalid or duplicated"),
            ("root_mode", "120000", "root invalid or duplicated"),
            ("root_sha", "not-a-sha", "root tree SHA is invalid"),
        ):
            with self.subTest(field=field):
                self.api = ParentFenceAPI()
                self.publish()
                before = len(self.api.commits)
                setattr(self.api, field, mutation)
                with self.assertRaisesRegex(ValueError, expected):
                    self.publish()
                self.assertEqual(len(self.api.commits), before)
                self.assertEqual(self.api.ref_successes, 1)

    def test_tree_and_contents_blob_metadata_mismatch_fails_closed(self):
        self.publish()
        before = len(self.api.commits)
        self.api.bad_tree_blob_sha = True
        with self.assertRaisesRegex(ValueError, "pinned blob metadata SHA mismatch"):
            self.publish()
        self.assertEqual(len(self.api.commits), before)
        self.assertEqual(self.api.ref_successes, 1)

    def test_contents_path_mismatch_fails_before_any_write(self):
        self.publish()
        before = len(self.api.commits)
        self.api.bad_contents_path = True
        with self.assertRaisesRegex(ValueError, "pinned Contents path mismatch"):
            self.publish()
        self.assertEqual(len(self.api.commits), before)
        self.assertEqual(self.api.ref_successes, 1)

    def test_tree_advertised_blob_missing_from_contents_fails_closed(self):
        self.publish()
        before = len(self.api.commits)
        # The pinned tree still advertises the record; Contents now responds 404.
        self.api.snapshots[self.api.head].pop(self.path)
        with self.assertRaisesRegex(ValueError, "pinned blob is missing"):
            self.publish()
        self.assertEqual(len(self.api.commits), before)
        self.assertEqual(self.api.ref_successes, 1)

    def test_forged_contents_bytes_with_matching_metadata_fail_closed(self):
        self.publish()
        before = len(self.api.commits)
        self.api.alter_contents_bytes = True
        with self.assertRaisesRegex(ValueError, "pinned blob content SHA mismatch"):
            self.publish()
        self.assertEqual(len(self.api.commits), before)
        self.assertEqual(self.api.ref_successes, 1)

    def test_stale_tree_vs_semantically_valid_contents_fails_closed(self):
        self.publish()
        before = len(self.api.commits)
        # JSON whitespace is valid but the stored tree blob must still match.
        self.api.snapshots[self.api.head][self.path] += " "
        with self.assertRaisesRegex(ValueError, "pinned blob metadata SHA mismatch"):
            self.publish()
        self.assertEqual(len(self.api.commits), before)
        self.assertEqual(self.api.ref_successes, 1)

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
            ("PATCH", "/git/commits/" + "a" * 40),
            ("POST", "/git/ref/heads/fabric-data"),
            ("PATCH", "/git/ref/heads/fabric-data"),
            ("POST", "/git/trees/" + "a" * 40 + "?recursive=1"),
            ("POST", "/contents/projects/local-agent/index.json?ref=" + "a" * 40),
            ("GET", "/git/refs/heads/fabric-data"),
            ("GET", "/git/commits/not-a-sha"),
            ("GET", "/git/commits/" + "a" * 40 + "?ref=main"),
            ("GET", "/contents/projects/secret.json?ref=" + "a" * 40),
            ("GET", "/contents/projects/index.json?ref=main"),
            ("GET", "/contents/projects/local-agent/workflows/workflow-001/"
                "dispatches/fabric-" + "a" * 32 + ".json?ref=main"),
        ):
            with self.subTest(path=path), self.assertRaises(ValueError):
                api.request(method, path)
        self.assertEqual(writer.MAX_ATTEMPTS, 6)


if __name__ == "__main__":
    unittest.main()
