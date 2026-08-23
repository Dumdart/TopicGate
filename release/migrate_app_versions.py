import argparse
import json
import re
import tomllib
from pathlib import Path


plugin_paths = [
    "topicgate-plugin/plugin.json",
    "topicgate-plugin/.codex-plugin/plugin.json",
    "topicgate-plugin/.claude-plugin/plugin.json",
]
marketplace_path = ".claude-plugin/marketplace.json"
server_path = "server.json"
toml_path = "pyproject.toml"

_JSON_VERSION = re.compile(r'("version"\s*:\s*")[^"]*(")')
_TOML_PROJECT_VERSION = re.compile(
    r'(?m)^(version\s*=\s*")[^"]*(")'
)


def _read_text(path: Path) -> str:
    # Check line endings are preserved so a release migration does not reformat files.
    with path.open(encoding="utf-8", newline="") as file:
        return file.read()


def _write_text(path: Path, content: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        file.write(content)


def get_json(path: str) -> dict:
    return json.loads(_read_text(Path(path)))


def _replace_json_versions(path: str, version: str, expected_count: int) -> None:
    file_path = Path(path)
    get_json(path)
    content = _read_text(file_path)
    content, replacements = _JSON_VERSION.subn(
        lambda match: f'{match.group(1)}{version}{match.group(2)}',
        content,
    )
    if replacements != expected_count:
        raise ValueError(
            f"Expected {expected_count} version field(s) in {path}, "
            f"found {replacements}"
        )
    _write_text(file_path, content)


def replace_plugin_version(version: str) -> None:
    for path in plugin_paths:
        _replace_json_versions(path, version, expected_count=1)


def replace_marketplace_plugin_version(version: str) -> None:
    marketplace = get_json(marketplace_path)
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list):
        raise ValueError(f"Expected a plugins list in {marketplace_path}")

    version_count = sum(
        isinstance(plugin, dict) and "version" in plugin
        for plugin in plugins
    )
    if not version_count:
        raise ValueError(f"No plugin version fields found in {marketplace_path}")
    _replace_json_versions(marketplace_path, version, expected_count=version_count)


def replace_server_version(version: str) -> None:
    server = get_json(server_path)
    packages = server.get("packages")
    if not isinstance(packages, list):
        raise ValueError(f"Expected a packages list in {server_path}")

    version_count = 1 + sum(
        isinstance(package, dict) and "version" in package
        for package in packages
    )
    _replace_json_versions(server_path, version, expected_count=version_count)


def replace_toml_version(version: str) -> None:
    file_path = Path(toml_path)
    content = _read_text(file_path)
    document = tomllib.loads(content)
    if "project" not in document or "version" not in document["project"]:
        raise ValueError(f"Expected project.version in {toml_path}")

    updated, replacements = _TOML_PROJECT_VERSION.subn(
        lambda match: f"{match.group(1)}{version}{match.group(2)}",
        content,
        count=1,
    )
    if replacements != 1:
        raise ValueError(f"Expected project.version in {toml_path}")
    _write_text(file_path, updated)


def replace_versions(version: str) -> None:
    replace_plugin_version(version)
    replace_marketplace_plugin_version(version)
    replace_server_version(version)
    replace_toml_version(version)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Update TopicGate's package, plugin, marketplace, and server versions."
    )
    parser.add_argument("version", help="The release version to apply")
    args = parser.parse_args()
    if not args.version:
        parser.error("version must not be empty")

    replace_versions(args.version)
    print(f"Migrated application versions to {args.version}")


if __name__ == "__main__":
    main()
