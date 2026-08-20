import json
from pathlib import Path
import shutil
import subprocess
import sys

from fastmcp import Client


REPOSITORY_ROOT = Path(__file__).parents[1]
PLUGIN_ROOT = REPOSITORY_ROOT / "topicgate-plugin"


def test_plugin_bundle_matches_codex_ingestion_contract() -> None:
    manifest = json.loads(
        (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    interface = manifest["interface"]
    marketplace = json.loads(
        (REPOSITORY_ROOT / ".agents" / "plugins" / "marketplace.json").read_text(
            encoding="utf-8"
        )
    )
    marketplace_plugin = next(
        plugin for plugin in marketplace["plugins"] if plugin["name"] == manifest["name"]
    )

    assert marketplace_plugin["source"]["path"] == "./topicgate-plugin"
    assert manifest["author"]["name"]
    assert manifest["mcpServers"] == "./.mcp.json"
    assert interface["longDescription"]
    assert interface["developerName"]
    assert interface["category"]
    assert interface["capabilities"]
    assert 1 <= len(interface["defaultPrompt"]) <= 3

    for asset_field in ("composerIcon", "logo"):
        asset = PLUGIN_ROOT / interface[asset_field].removeprefix("./")
        assert asset.is_file()


def test_plugin_skills_have_valid_frontmatter() -> None:
    skill_files = sorted((PLUGIN_ROOT / "skills").glob("*/SKILL.md"))

    assert skill_files
    for skill_file in skill_files:
        lines = skill_file.read_text(encoding="utf-8").splitlines()
        assert lines[0] == "---"
        closing_delimiter = lines.index("---", 1)
        frontmatter = lines[1:closing_delimiter]
        assert f"name: {skill_file.parent.name}" in frontmatter
        assert any(line.startswith("description: ") for line in frontmatter)


async def test_cached_plugin_bundle_exposes_read_only_tools(
    tmp_path: Path,
) -> None:
    cached_plugin = tmp_path / "topicgate"
    shutil.copytree(PLUGIN_ROOT, cached_plugin)
    config = json.loads((cached_plugin / ".mcp.json").read_text(encoding="utf-8"))
    server_config = config["mcpServers"]["topicgate"]
    server_config["env"]["TOPICGATE_DATA_DIR"] = str(tmp_path / "data")

    assert "$schema" not in config
    assert server_config["command"] == "python"
    assert server_config["args"][:2] == ["-m", "topicgate"]
    assert "PYTHONPATH" not in server_config["env"]

    async with Client(config) as client:
        tools = await client.list_tools()

    assert {tool.name for tool in tools} == {
        "get_broker_snapshot",
        "get_connection_status",
        "get_topic_state",
        "list_brokers",
        "list_subscriptions",
        "list_topics",
    }


def test_topicgate_package_supports_python_module_execution() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "topicgate", "--help"],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0
    assert "Run the TopicGate MCP server." in result.stdout
