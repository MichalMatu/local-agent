from __future__ import annotations

import copy
import unittest

from local_agent.workflow import activation


VALID = {
    "schema_version": 1,
    "workflow_id": "workflow-a",
    "revision": 1,
    "revision_digest": "sha256:" + "a" * 64,
    "parent_tip_digest": "sha256:" + "b" * 64,
    "checkpoint_node_id": "review-audit",
    "checkpoint_resolution_digest": "sha256:" + "c" * 64,
    "prior_state_digest": "sha256:" + "d" * 64,
    "new_node_states": {"implement": "ready"},
    "activated_at": "2026-09-19T14:30:00Z",
}


class WorkflowActivationValidationTests(unittest.TestCase):
    def test_valid_activation_shape_is_accepted(self) -> None:
        activation.validate_activation_shape(copy.deepcopy(VALID))

    def test_non_hex_digest_is_rejected(self) -> None:
        payload = copy.deepcopy(VALID)
        payload["revision_digest"] = "sha256:" + "g" * 64
        with self.assertRaisesRegex(ValueError, "sha256 digest"):
            activation.validate_activation_shape(payload)

    def test_uppercase_digest_is_rejected(self) -> None:
        payload = copy.deepcopy(VALID)
        payload["prior_state_digest"] = "sha256:" + "A" * 64
        with self.assertRaisesRegex(ValueError, "sha256 digest"):
            activation.validate_activation_shape(payload)

    def test_noncanonical_checkpoint_identifier_is_rejected(self) -> None:
        payload = copy.deepcopy(VALID)
        payload["checkpoint_node_id"] = "../review"
        with self.assertRaisesRegex(ValueError, "canonical identifier"):
            activation.validate_activation_shape(payload)

    def test_invalid_activation_timestamp_is_rejected(self) -> None:
        payload = copy.deepcopy(VALID)
        payload["activated_at"] = "tomorrow"
        with self.assertRaisesRegex(ValueError, "RFC3339 UTC"):
            activation.validate_activation_shape(payload)

    def test_checkpoint_resolution_requires_rfc3339_utc_timestamp(self) -> None:
        with self.assertRaisesRegex(ValueError, "checkpoint resolution timestamp"):
            activation._validate_checkpoint_resolution(
                {
                    "workflow_id": "workflow-a",
                    "node_id": "review-audit",
                    "resolver": "planner",
                    "resolved_at": "not-a-time",
                },
                workflow_id="workflow-a",
                checkpoint_node_id="review-audit",
            )

    def test_checkpoint_resolution_resolver_is_bounded(self) -> None:
        with self.assertRaisesRegex(ValueError, "resolver is invalid"):
            activation._validate_checkpoint_resolution(
                {
                    "workflow_id": "workflow-a",
                    "node_id": "review-audit",
                    "resolver": "x" * 201,
                    "resolved_at": "2026-09-19T14:31:00Z",
                },
                workflow_id="workflow-a",
                checkpoint_node_id="review-audit",
            )


if __name__ == "__main__":
    unittest.main()
