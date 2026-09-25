import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "local-agent"
MARKETPLACE = ROOT / ".agents" / "plugins" / "marketplace.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_plugin_manifest_is_portable_and_uses_registered_apps_file() -> None:
    manifest = _load_json(PLUGIN_ROOT / "plugin.json")

    assert manifest["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    assert manifest["name"] == "local-agent"
    assert manifest["extensions"]["com.openai"]["apps"] == "./.app.json"
    assert "sandbox" in manifest["keywords"]


def test_private_plugin_requires_github_connector() -> None:
    app_manifest = _load_json(PLUGIN_ROOT / ".app.json")
    github = app_manifest["apps"]["github"]

    assert github["id"].startswith("connector_")
    assert github["required"] is True


def test_repo_marketplace_points_at_local_agent_plugin() -> None:
    marketplace = _load_json(MARKETPLACE)
    entry = marketplace["plugins"][0]

    assert marketplace["name"] == "local-agent-dev"
    assert entry["name"] == "local-agent"
    assert entry["source"] == {
        "source": "local",
        "path": "./plugins/local-agent",
    }
    assert entry["policy"]["installation"] == "AVAILABLE"
    assert entry["policy"]["authentication"] == "ON_INSTALL"


def test_control_skill_keeps_core_executor_safety_invariants() -> None:
    skill = (PLUGIN_ROOT / "skills" / "local-agent-control" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    required_fragments = (
        ".agent/binding.json",
        "agent-control",
        "Task files are immutable",
        "resources: []",
        "terminal result",
        "cancel_task",
        "Do not guess",
        "ChatGPT sandbox",
        "user's own connected GitHub account",
    )

    for fragment in required_fragments:
        assert fragment in skill


def test_sandbox_skill_preserves_exact_source_and_offline_cache_contract() -> None:
    skill = (PLUGIN_ROOT / "skills" / "sandbox-execution" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    required_fragments = (
        "GitHub remains the source of truth",
        "exact target Git SHA",
        "verify the snapshot checksum",
        "verify the embedded source SHA",
        "ChatGPT Library",
        "dependency key",
        "/mnt/data",
        "Local Agent",
        "Do not store secrets",
        "MichalMatu/photomap",
        "MichalMatu/tracker",
    )

    for fragment in required_fragments:
        assert fragment in skill
