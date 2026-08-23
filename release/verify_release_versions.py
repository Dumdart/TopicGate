import json
import os
import tomllib
from pathlib import Path


def json_base_version(plugin) -> str:
    plugin_version = plugin["version"]
    return plugin_version.split("+", 1)[0]


def get_versions(expected: str | None = None) -> dict[str, str]:
    pyproject = tomllib.loads(
        Path("pyproject.toml").read_text(encoding="utf-8")
    )

    plugin = json.loads(
        Path("topicgate-plugin/plugin.json")
        .read_text(encoding="utf-8")
    )

    codex_plugin = json.loads(
        Path("topicgate-plugin/.codex-plugin/plugin.json")
        .read_text(encoding="utf-8")
    )

    claude_plugin = json.loads(
        Path("topicgate-plugin/.claude-plugin/plugin.json")
        .read_text(encoding="utf-8")
    )

    marketplace = json.loads(
        Path(".claude-plugin/marketplace.json")
        .read_text(encoding="utf-8")
    )

    marketplace_plugin = next(
        (
            candidate
            for candidate in marketplace["plugins"]
            if candidate["name"] == plugin["name"]
        ),
        None,
    )
    if marketplace_plugin is None:
        raise SystemExit(
            "Release version mismatch:\n"
            f"  Claude marketplace: missing plugin {plugin['name']}"
        )

    server = json.loads(
        Path("server.json")
        .read_text(encoding="utf-8")
    )

    package_version = pyproject["project"]["version"]

    plugin_base = json_base_version(plugin)
    codex_plugin_base = json_base_version(codex_plugin)
    claude_plugin_base = json_base_version(claude_plugin)
    marketplace_plugin_base = json_base_version(marketplace_plugin)
    serverbase = json_base_version(server)

    versions = {
        "Python package": package_version,
        "Plugin base version": plugin_base,
        "Codex plugin base version": codex_plugin_base,
        "Claude plugin base version": claude_plugin_base,
        "Claude marketplace base version": marketplace_plugin_base,
        "Server base version": serverbase,
    }

    if expected:
        versions["Git tag"] = expected

    return versions

def verify(versions: dict[str, str]) -> None:
    if len(set(versions.values())) != 1:
        raise SystemExit(
            "Release version mismatch:\n"
            + "\n".join(f"  {name}: {version}"
                        for name, version in versions.items())
        )
