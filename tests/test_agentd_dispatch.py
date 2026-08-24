from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import agentd


class AgentEntrypointDispatchTests(unittest.TestCase):
    def test_no_registry_keeps_single_repository_daemon(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            agentd, "STATE_DIR", Path(tmp)
        ), mock.patch.object(agentd.os, "execv") as execv:
            self.assertFalse(agentd.dispatch_multirepo_if_configured())
            execv.assert_not_called()

    def test_registry_execs_multi_repository_supervisor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state"
            state.mkdir()
            (state / "repositories.json").write_text("{}", encoding="utf-8")
            (root / "agent_multirepo.py").write_text("# supervisor\n", encoding="utf-8")
            with mock.patch.object(agentd, "STATE_DIR", state), mock.patch.object(
                agentd, "SELF_REPO", root
            ), mock.patch.object(agentd.os, "execv") as execv:
                self.assertTrue(agentd.dispatch_multirepo_if_configured())
            execv.assert_called_once()
            argv = execv.call_args.args[1]
            self.assertEqual(
                argv[-2:], ["--registry", str(state / "repositories.json")]
            )


if __name__ == "__main__":
    unittest.main()
