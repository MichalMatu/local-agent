from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_ENTRYPOINTS = (
    "local_agent/entrypoint.py",
    "local_agent/daemon/service.py",
    "local_agent/supervisor/orchestrator.py",
    "local_agent/supervisor/serial.py",
    "local_agent/supervisor/worker.py",
    "local_agent/repository/worker.py",
    "local_agent/platform/macos_launchd.py",
)
FORBIDDEN_IMPORT_MARKERS = (
    "from local_agent.workflow",
    "import local_agent.workflow",
)


class WorkflowInertBoundaryTests(unittest.TestCase):
    def test_execution_fabric_is_not_imported_by_production_runtime_entrypoints(self) -> None:
        violations: list[str] = []
        for relative in PRODUCTION_ENTRYPOINTS:
            path = ROOT / relative
            self.assertTrue(path.is_file(), f"missing production boundary file: {relative}")
            text = path.read_text(encoding="utf-8")
            if any(marker in text for marker in FORBIDDEN_IMPORT_MARKERS):
                violations.append(relative)
        self.assertEqual(
            violations,
            [],
            "Execution Fabric must remain inert until an explicit integration phase: "
            + ", ".join(violations),
        )

    def test_lineage_coordinator_has_no_service_or_supervisor_import(self) -> None:
        text = (ROOT / "local_agent/workflow/lineage_coordinator.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("local_agent.daemon", text)
        self.assertNotIn("local_agent.supervisor", text)
        self.assertNotIn("local_agent.repository.worker", text)


if __name__ == "__main__":
    unittest.main()
