from __future__ import annotations

import importlib
import unittest
from pathlib import Path


ALIASES = (
    ("agent_cleanup", "local_agent.repository.cleanup"),
    ("agent_core", "local_agent.foundation.core"),
    ("agent_parallel_worker", "local_agent.supervisor.worker"),
    ("agent_process", "local_agent.foundation.process"),
    ("agent_repo_admin", "local_agent.repository.admin"),
    ("agent_repo_worker", "local_agent.repository.worker"),
    ("agent_runtime", "local_agent.runtime.executor"),
    ("agent_storage", "local_agent.foundation.storage"),
    ("agentctl", "local_agent.cli.diagnostics"),
)


class PackageLayoutTests(unittest.TestCase):
    def test_root_compatibility_modules_alias_packaged_owners(self) -> None:
        for legacy_name, owner_name in ALIASES:
            with self.subTest(legacy_name=legacy_name, owner_name=owner_name):
                legacy = importlib.import_module(legacy_name)
                owner = importlib.import_module(owner_name)
                self.assertIs(legacy, owner)
                self.assertIn("/local_agent/", str(Path(owner.__file__).as_posix()))

    def test_root_compatibility_sources_remain_thin(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for legacy_name, _owner_name in ALIASES:
            with self.subTest(legacy_name=legacy_name):
                source = (root / f"{legacy_name}.py").read_text(encoding="utf-8")
                meaningful = [line for line in source.splitlines() if line.strip()]
                self.assertLessEqual(len(meaningful), 10)
                self.assertNotIn("\ndef ", source)
                self.assertNotIn("\nclass ", source)


if __name__ == "__main__":
    unittest.main()
