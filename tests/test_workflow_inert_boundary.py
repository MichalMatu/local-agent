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
    "from local_agent.development",
    "import local_agent.development",
)
UNWIRED_WORKFLOW_SIDE_EFFECT_MODULES = (
    "local_agent/workflow/git_control_plane.py",
    "local_agent/workflow/git_cancellation.py",
    "local_agent/workflow/lineage_coordinator.py",
    "local_agent/workflow/lineage_cancellation.py",
    "local_agent/workflow/lineage_cycle.py",
)


class WorkflowInertBoundaryTests(unittest.TestCase):
    def test_development_orchestration_is_not_imported_by_production_runtime_entrypoints(self) -> None:
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
            "Workflow/DEV infrastructure must remain inert until an explicit integration phase: "
            + ", ".join(violations),
        )

    def test_unwired_workflow_side_effect_modules_have_no_runtime_owner_import(self) -> None:
        forbidden = (
            "local_agent.daemon",
            "local_agent.supervisor",
            "local_agent.repository.worker",
        )
        violations: list[str] = []
        for relative in UNWIRED_WORKFLOW_SIDE_EFFECT_MODULES:
            path = ROOT / relative
            self.assertTrue(path.is_file(), f"missing workflow boundary file: {relative}")
            text = path.read_text(encoding="utf-8")
            if any(marker in text for marker in forbidden):
                violations.append(relative)
        self.assertEqual(
            violations,
            [],
            "Unwired workflow side-effect modules must not import runtime owners: "
            + ", ".join(violations),
        )


if __name__ == "__main__":
    unittest.main()
