from pathlib import Path

import pytest

from release.verify_distribution import (
    _environment_python,
    _environment_script,
    verify_distribution,
)


def test_environment_paths_match_platform_layout(tmp_path: Path) -> None:
    python_path = _environment_python(tmp_path)
    topicgate_path = _environment_script(tmp_path, "topicgate")

    assert python_path.parent == topicgate_path.parent
    assert python_path.name.startswith("python")
    assert topicgate_path.name.startswith("topicgate")


def test_verify_distribution_rejects_missing_wheel(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Expected a built wheel"):
        verify_distribution(tmp_path / "topicgate.whl")


def test_verify_distribution_rejects_non_wheel(tmp_path: Path) -> None:
    archive = tmp_path / "topicgate.tar.gz"
    archive.touch()

    with pytest.raises(ValueError, match="Expected a built wheel"):
        verify_distribution(archive)
