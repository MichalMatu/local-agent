from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPO_ROOT / "scripts" / "chat_bridge_native_host.py"
HOST_NAME = "com.michalmatu.local_agent_bridge"


class ChatBridgeNativeHostInstallerTests(unittest.TestCase):
    def test_installer_registers_exact_extension_origin_under_home(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            environment = os.environ.copy()
            environment["HOME"] = str(home)
            extension_id = "a" * 32
            result = subprocess.run(
                [sys.executable, str(INSTALLER), "install", "--extension-id", extension_id],
                cwd=REPO_ROOT,
                env=environment,
                check=True,
                text=True,
                capture_output=True,
            )
            manifest_path = Path(result.stdout.strip())
            expected = (
                home
                / "Library"
                / "Application Support"
                / "Google"
                / "Chrome"
                / "NativeMessagingHosts"
                / f"{HOST_NAME}.json"
            )
            self.assertEqual(manifest_path, expected)
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["name"], HOST_NAME)
            self.assertEqual(payload["type"], "stdio")
            self.assertEqual(payload["allowed_origins"], [f"chrome-extension://{extension_id}/"])
            wrapper = Path(str(payload["path"]))
            self.assertTrue(wrapper.is_absolute())
            self.assertTrue(wrapper.is_file())
            wrapper_text = wrapper.read_text(encoding="utf-8")
            self.assertIn("local_agent.platform.chrome_native_host", wrapper_text)
            self.assertIn(str(REPO_ROOT), wrapper_text)
            self.assertNotIn("curl", wrapper_text)
            self.assertNotIn("bash -c", wrapper_text)

            status = subprocess.run(
                [
                    sys.executable,
                    str(INSTALLER),
                    "status",
                    "--extension-id",
                    extension_id,
                ],
                cwd=REPO_ROOT,
                env=environment,
                check=True,
                text=True,
                capture_output=True,
            )
            status_payload = json.loads(status.stdout)
            self.assertTrue(status_payload["healthy"])
            self.assertEqual(status_payload["problems"], [])
            self.assertTrue(status_payload["manifest_exists"])
            self.assertTrue(status_payload["wrapper_exists"])
            self.assertTrue(status_payload["wrapper_executable"])
            self.assertTrue(status_payload["wrapper_matches_expected"])
            self.assertEqual(status_payload["manifest_mode"], "0o600")
            self.assertEqual(status_payload["wrapper_mode"], "0o700")
            self.assertEqual(
                status_payload["allowed_origins"],
                [f"chrome-extension://{extension_id}/"],
            )
            self.assertEqual(status_payload["registered_extension_id"], extension_id)
            self.assertEqual(status_payload["expected_extension_id"], extension_id)

    def test_installer_rejects_non_chrome_extension_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            environment = os.environ.copy()
            environment["HOME"] = temp
            result = subprocess.run(
                [sys.executable, str(INSTALLER), "install", "--extension-id", "not-an-id"],
                cwd=REPO_ROOT,
                env=environment,
                check=False,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("extension id", result.stderr)

    def test_status_detects_wrong_extension_id_and_manifest_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            environment = os.environ.copy()
            environment["HOME"] = str(home)
            extension_id = "a" * 32
            subprocess.run(
                [sys.executable, str(INSTALLER), "install", "--extension-id", extension_id],
                cwd=REPO_ROOT,
                env=environment,
                check=True,
                text=True,
                capture_output=True,
            )

            wrong_id = "b" * 32
            wrong_origin = subprocess.run(
                [
                    sys.executable,
                    str(INSTALLER),
                    "status",
                    "--extension-id",
                    wrong_id,
                ],
                cwd=REPO_ROOT,
                env=environment,
                check=False,
                text=True,
                capture_output=True,
            )
            self.assertEqual(wrong_origin.returncode, 1)
            wrong_payload = json.loads(wrong_origin.stdout)
            self.assertFalse(wrong_payload["healthy"])
            self.assertIn("allowed_origin_mismatch", wrong_payload["problems"])

            manifest = (
                home
                / "Library"
                / "Application Support"
                / "Google"
                / "Chrome"
                / "NativeMessagingHosts"
                / f"{HOST_NAME}.json"
            )
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["path"] = "/tmp/not-the-local-agent-host"
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            os.chmod(manifest, 0o600)

            bad_path = subprocess.run(
                [
                    sys.executable,
                    str(INSTALLER),
                    "status",
                    "--extension-id",
                    extension_id,
                ],
                cwd=REPO_ROOT,
                env=environment,
                check=False,
                text=True,
                capture_output=True,
            )
            self.assertEqual(bad_path.returncode, 1)
            bad_payload = json.loads(bad_path.stdout)
            self.assertFalse(bad_payload["healthy"])
            self.assertIn("registered_path_mismatch", bad_payload["problems"])

    def test_status_detects_non_executable_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            environment = os.environ.copy()
            environment["HOME"] = str(home)
            extension_id = "a" * 32
            result = subprocess.run(
                [sys.executable, str(INSTALLER), "install", "--extension-id", extension_id],
                cwd=REPO_ROOT,
                env=environment,
                check=True,
                text=True,
                capture_output=True,
            )
            manifest = json.loads(Path(result.stdout.strip()).read_text(encoding="utf-8"))
            wrapper = Path(str(manifest["path"]))
            os.chmod(wrapper, 0o600)

            status = subprocess.run(
                [
                    sys.executable,
                    str(INSTALLER),
                    "status",
                    "--extension-id",
                    extension_id,
                ],
                cwd=REPO_ROOT,
                env=environment,
                check=False,
                text=True,
                capture_output=True,
            )
            self.assertEqual(status.returncode, 1)
            payload = json.loads(status.stdout)
            self.assertIn("wrapper_not_executable", payload["problems"])
            self.assertIn("wrapper_mode_unexpected", payload["problems"])

    def test_status_detects_wrapper_from_stale_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            environment = os.environ.copy()
            environment["HOME"] = str(home)
            extension_id = "a" * 32
            result = subprocess.run(
                [sys.executable, str(INSTALLER), "install", "--extension-id", extension_id],
                cwd=REPO_ROOT,
                env=environment,
                check=True,
                text=True,
                capture_output=True,
            )
            manifest = json.loads(Path(result.stdout.strip()).read_text(encoding="utf-8"))
            wrapper = Path(str(manifest["path"]))
            original = wrapper.read_text(encoding="utf-8")
            wrapper.write_text(original.replace(str(REPO_ROOT), "/tmp/old-local-agent-checkout"), encoding="utf-8")
            os.chmod(wrapper, 0o700)

            status = subprocess.run(
                [
                    sys.executable,
                    str(INSTALLER),
                    "status",
                    "--extension-id",
                    extension_id,
                ],
                cwd=REPO_ROOT,
                env=environment,
                check=False,
                text=True,
                capture_output=True,
            )
            self.assertEqual(status.returncode, 1)
            payload = json.loads(status.stdout)
            self.assertFalse(payload["wrapper_matches_expected"])
            self.assertIn("wrapper_content_mismatch", payload["problems"])


if __name__ == "__main__":
    unittest.main()
