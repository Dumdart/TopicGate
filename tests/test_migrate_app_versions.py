import json
from pathlib import Path
import shutil
import subprocess
import sys


REPOSITORY_ROOT = Path(__file__).parents[1]
SCRIPT = REPOSITORY_ROOT / "release" / "migrate_app_versions.py"


def test_migrate_app_versions_updates_release_version_sources(tmp_path: Path) -> None:
    for relative_path in (
        "pyproject.toml",
        "server.json",
        ".claude-plugin/marketplace.json",
        "topicgate-plugin/plugin.json",
        "topicgate-plugin/.codex-plugin/plugin.json",
        "topicgate-plugin/.claude-plugin/plugin.json",
    ):
        source = REPOSITORY_ROOT / relative_path
        destination = tmp_path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "2.1.4"],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Migrated application versions to 2.1.4" in result.stdout

    for relative_path in (
        "topicgate-plugin/plugin.json",
        "topicgate-plugin/.codex-plugin/plugin.json",
        "topicgate-plugin/.claude-plugin/plugin.json",
    ):
        manifest = json.loads((tmp_path / relative_path).read_text(encoding="utf-8"))
        assert manifest["version"] == "2.1.4"

    marketplace = json.loads(
        (tmp_path / ".claude-plugin/marketplace.json").read_text(encoding="utf-8")
    )
    assert marketplace["plugins"][0]["version"] == "2.1.4"

    server = json.loads((tmp_path / "server.json").read_text(encoding="utf-8"))
    assert server["version"] == "2.1.4"
    assert server["packages"][0]["version"] == "2.1.4"

    pyproject = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "2.1.4"' in pyproject
