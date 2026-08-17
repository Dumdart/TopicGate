import tomllib
from importlib.metadata import metadata, version
from pathlib import Path

FAST_MCP_APPS_VERSION = "3.4.7"
PREFAB_UI_VERSION = "0.20.2"
FAST_MCP_PREFAB_FLOOR = "0.18.0"


def test_dashboard_dependency_pair_matches_project_pins() -> None:
    project_path = Path(__file__).parents[1] / "pyproject.toml"
    project = tomllib.loads(project_path.read_text(encoding="utf-8"))

    assert f"fastmcp=={FAST_MCP_APPS_VERSION}" in project["project"][
        "dependencies"
    ]
    assert project["project"]["optional-dependencies"]["apps"] == [
        f"fastmcp[apps]=={FAST_MCP_APPS_VERSION}",
        f"prefab-ui=={PREFAB_UI_VERSION}",
    ]


def test_installed_dashboard_pair_is_supported_by_fastmcp_apps() -> None:
    assert version("fastmcp") == FAST_MCP_APPS_VERSION
    assert version("prefab-ui") == PREFAB_UI_VERSION

    fastmcp_requirements = metadata("fastmcp").get_all("Requires-Dist") or []
    apps_requirements = [
        item for item in fastmcp_requirements if "fastmcp-slim[apps]" in item
    ]
    assert len(apps_requirements) == 1
    assert f"=={FAST_MCP_APPS_VERSION}" in apps_requirements[0]

    slim_requirements = metadata("fastmcp-slim").get_all("Requires-Dist") or []
    prefab_requirements = [
        item for item in slim_requirements if "prefab-ui" in item
    ]
    assert len(prefab_requirements) == 1
    assert f">={FAST_MCP_PREFAB_FLOOR}" in prefab_requirements[0]
