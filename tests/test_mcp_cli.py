from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class MCPCLITests(unittest.TestCase):
    def test_servers_command_uses_explicit_machine_registry_and_emits_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registry = Path(tmp) / "servers.json"
            registry.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "servers": [
                            {
                                "id": "cli-test",
                                "transport": "streamable_http",
                                "endpoint": "http://127.0.0.1:8765/mcp",
                                "enabled": True,
                                "tools": [],
                                "allowed_artifact_mime_types": [],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "local_agent.mcp.cli",
                    "--registry",
                    str(registry),
                    "servers",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["registry"], str(registry))
        self.assertEqual(payload["servers"][0]["id"], "cli-test")
        self.assertEqual(payload["servers"][0]["endpoint"], "http://127.0.0.1:8765/mcp")

    def test_help_is_packaged_and_executable(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "local_agent.mcp.cli", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Local Agent local MCP client", result.stdout)
        self.assertIn("servers", result.stdout)
        self.assertIn("tools", result.stdout)
        self.assertIn("call", result.stdout)


if __name__ == "__main__":
    unittest.main()
