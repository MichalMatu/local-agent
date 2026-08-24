from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import agent_core as core


class WorkspaceCheckpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.repo = root / "repo"
        self.checkpoints = root / "checkpoints"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "Checkpoint Test"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "checkpoint@example.invalid"], cwd=self.repo, check=True)
        (self.repo / "tracked.txt").write_text("original\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=self.repo, check=True)
        self.original_work = core.WORK
        self.original_checkpoints = core.CHECKPOINTS
        core.WORK = self.repo
        core.CHECKPOINTS = self.checkpoints

    def tearDown(self) -> None:
        core.WORK = self.original_work
        core.CHECKPOINTS = self.original_checkpoints
        self.tmp.cleanup()

    def test_clean_worktree_does_not_create_checkpoint(self) -> None:
        self.assertIsNone(core.checkpoint_worktree("task-clean", reason="unit"))
        self.assertFalse(self.checkpoints.exists())

    def test_checkpoint_preserves_tracked_and_untracked_content(self) -> None:
        (self.repo / "tracked.txt").write_text("changed\n", encoding="utf-8")
        nested = self.repo / "new" / "blob.bin"
        nested.parent.mkdir()
        nested.write_bytes(b"\x00\x01checkpoint\xff")

        metadata = core.checkpoint_worktree("task-dirty", reason="unit")
        self.assertIsNotNone(metadata)
        assert metadata is not None
        checkpoint = Path(metadata["path"])
        self.assertTrue(checkpoint.is_dir())
        self.assertIn("tracked.txt", (checkpoint / "tracked.patch").read_text(encoding="utf-8"))
        self.assertEqual((checkpoint / "untracked" / "new" / "blob.bin").read_bytes(), nested.read_bytes())
        saved = json.loads((checkpoint / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["base_head"], metadata["base_head"])
        self.assertEqual(saved["untracked_files"], ["new/blob.bin"])

        subprocess.run(["git", "reset", "--hard", "-q", "HEAD"], cwd=self.repo, check=True)
        subprocess.run(["git", "clean", "-fdq"], cwd=self.repo, check=True)
        subprocess.run(["git", "apply", "--binary", str(checkpoint / "tracked.patch")], cwd=self.repo, check=True)
        restored = self.repo / "new" / "blob.bin"
        restored.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(checkpoint / "untracked" / "new" / "blob.bin", restored)
        self.assertEqual((self.repo / "tracked.txt").read_text(encoding="utf-8"), "changed\n")
        self.assertEqual(restored.read_bytes(), b"\x00\x01checkpoint\xff")


if __name__ == "__main__":
    unittest.main()
