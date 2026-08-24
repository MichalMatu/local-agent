from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import agent_repo_admin as admin
from agent_repository import RepositoryContext


def repository(root: Path) -> RepositoryContext:
    return RepositoryContext(
        repository_id="project-a",
        repository="owner/project-a",
        control=root / "control",
        work=root / "work",
        checkpoints=root / "checkpoints",
    )


class RepositoryAdminTests(unittest.TestCase):
    def test_normalize_remote_url_accepts_common_github_forms(self) -> None:
        expected = "owner/project-a"
        self.assertEqual(admin.normalize_remote_url("https://github.com/owner/project-a.git"), expected)
        self.assertEqual(admin.normalize_remote_url("git@github.com:owner/project-a.git"), expected)
        self.assertEqual(admin.normalize_remote_url("ssh://git@github.com/owner/project-a.git"), expected)

    def test_validate_checkout_rejects_wrong_origin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = repository(Path(tmp))
            (repo.control / ".git").mkdir(parents=True)
            result = subprocess.CompletedProcess(
                args=["git"],
                returncode=0,
                stdout="https://github.com/owner/other.git\n",
            )
            with mock.patch.object(admin, "run_git", return_value=result):
                with self.assertRaisesRegex(RuntimeError, "origin mismatch"):
                    admin.validate_checkout(repo.control, repo, "control")

    def test_provision_uses_existing_remote_control_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = repository(Path(tmp))
            with mock.patch.object(
                admin, "remote_branch_exists", return_value=True
            ), mock.patch.object(
                admin,
                "_clone_if_missing",
                side_effect=[True, True],
            ) as clone, mock.patch.object(admin, "validate_repository"):
                result = admin.provision_repository(repo)

            self.assertEqual(
                result,
                {
                    "control_created": True,
                    "control_branch_created": False,
                    "work_created": True,
                },
            )
            self.assertTrue(repo.checkpoints.is_dir())
            self.assertEqual(clone.call_count, 2)
            self.assertTrue(clone.call_args_list[0].kwargs["single_branch"])
            self.assertFalse(clone.call_args_list[1].kwargs["single_branch"])

    def test_provision_initializes_missing_remote_control_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = repository(Path(tmp))
            with mock.patch.object(
                admin, "remote_branch_exists", return_value=False
            ), mock.patch.object(
                admin,
                "_clone_if_missing",
                side_effect=[True, True],
            ) as clone, mock.patch.object(
                admin, "initialize_control_branch"
            ) as initialize, mock.patch.object(admin, "validate_repository"):
                result = admin.provision_repository(repo)

            self.assertEqual(
                result,
                {
                    "control_created": True,
                    "control_branch_created": True,
                    "work_created": True,
                },
            )
            initialize.assert_called_once_with(repo)
            self.assertFalse(clone.call_args_list[0].kwargs["single_branch"])
            self.assertEqual(clone.call_args_list[0].kwargs["branch"], "main")

    def test_existing_non_git_destination_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = repository(Path(tmp))
            repo.control.mkdir(parents=True)
            (repo.control / "keep.txt").write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "checkout missing"):
                admin._clone_if_missing(
                    repo,
                    path=repo.control,
                    branch=repo.control_branch,
                    single_branch=True,
                    label="control",
                )
            self.assertEqual((repo.control / "keep.txt").read_text(encoding="utf-8"), "keep")

    def test_select_repository_rejects_unknown_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = repository(Path(tmp))
            with self.assertRaisesRegex(ValueError, "not enabled"):
                admin.select_repositories([repo], "missing")


if __name__ == "__main__":
    unittest.main()
