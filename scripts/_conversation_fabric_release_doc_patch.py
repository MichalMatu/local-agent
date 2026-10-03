from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def update_golden_standard() -> None:
    path = ROOT / "docs" / "GOLDEN_STANDARD.md"
    text = path.read_text(encoding="utf-8")
    _, separator, tail = text.partition("\n\n## Release/runtime invariants")
    if not separator:
        raise RuntimeError("GOLDEN_STANDARD release/runtime heading not found")
    head = (
        "# Local Agent Golden Standard\n\n"
        "This file records the current release/runtime invariants for `MichalMatu/local-agent`. "
        "The source release is `v4.20.1`; current production release is `v4.20.0` / Chat Bridge `0.7.0`. "
        "The 4.20.1 candidate keeps Chat Bridge 0.7.0 and extends Conversation Fabric operator "
        "requests with a fail-closed canonical target-repository identity while retaining runtime "
        "schema 3, content protocol v13 and assistant guard v8. The deployed production release "
        "remains `v4.20.0` until the explicit release decision advances `main`; Candidate source "
        "must not be described as current production before the explicit release decision advances "
        "`main`. Conversation Fabric operator intake remains default-disabled until explicit runtime "
        "configuration, and child chats remain reasoning-only while `.agent/tasks` retains all "
        "machine execution authority. Read the installed `self_revision` from live daemon status; "
        "never infer the deployed revision from a source checkout alone."
    )
    path.write_text(head + separator + tail, encoding="utf-8")


def update_operations() -> None:
    path = ROOT / "docs" / "OPERATIONS.md"
    text = path.read_text(encoding="utf-8")
    needle = "\nSupervisor intake is default-disabled."
    if text.count(needle) != 1:
        raise RuntimeError("OPERATIONS supervisor-intake marker is not unique")
    addition = (
        "\nOperator request schema v1 remains accepted for the original Local Agent DEV identity. "
        "Schema v2 adds one required request-level `repository_id` so a Superchat can delegate "
        "reasoning to a registered project repository without granting the child machine authority. "
        "The target is accepted only when it resolves uniquely in the runtime repository registry, "
        "is execution-enabled in the canonical binding catalog, carries the same canonical "
        "`agent_binding`, has a matching GitHub origin, and its configured default branch resolves "
        "to one canonical remote commit SHA. That immutable repository/ref/SHA identity is passed "
        "into the existing child lifecycle. Executable edits, builds and tests remain separate "
        "`.agent/tasks` using the exact target repository binding.\n"
    )
    path.write_text(text.replace(needle, addition + needle, 1), encoding="utf-8")


if __name__ == "__main__":
    update_golden_standard()
    update_operations()
