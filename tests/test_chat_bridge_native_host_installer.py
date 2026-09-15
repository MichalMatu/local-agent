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
                [sys.executable, str(INSTALLER), "status"],
                cwd=REPO_ROOT,
                env=environment,
                check=True,
                text=True,
                capture_output=True,
            )
            status_payload = json.loads(status.stdout)
            self.assertTrue(status_payload["manifest_exists"])
            self.assertTrue(status_payload["wrapper_exists"])
            self.assertEqual(
                status_payload["allowed_origins"],
                [f"chrome-extension://{extension_id}/"],
            )

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


if __name__ == "__main__":
    unittest.main()
