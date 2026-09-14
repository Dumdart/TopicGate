from pathlib import Path


WORKFLOWS = Path(".github/workflows")


def test_workflows_only_use_repository_owned_actions() -> None:
    external_actions: list[str] = []

    for workflow in WORKFLOWS.glob("*.y*ml"):
        for line_number, line in enumerate(workflow.read_text().splitlines(), start=1):
            value = line.strip().removeprefix("- ").strip()
            if value.startswith("uses:"):
                action = value.removeprefix("uses:").strip()
                if not action.startswith(("./", "Dumdart/")):
                    external_actions.append(f"{workflow}:{line_number}: {action}")

    assert external_actions == []


def test_wheel_verification_workflows_install_linux_gui_dependencies() -> None:
    smoketests = (WORKFLOWS / "smoketests.yml").read_text(encoding="utf-8")
    release = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")

    assert "if: runner.os == 'Linux'" in smoketests
    assert "sudo apt-get install --yes libegl1" in smoketests
    assert "sudo apt-get install --yes libegl1" in release
    assert release.index("install --yes libegl1") < release.index(
        "Verify clean wheel installation"
    )


def test_release_publish_steps_support_transient_failure_recovery() -> None:
    release = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")

    assert "--check-url https://pypi.org/simple" in release
    assert "python -m release.publish_mcp_registry server.json" in release


def test_recovery_workflow_uses_published_artifacts() -> None:
    recovery = (WORKFLOWS / "recover-release.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in recovery
    assert "python -m release.run_cd" in recovery
    assert "https://pypi.org/pypi/topicgate/{version}/json" in recovery
    assert "hashlib.sha256(content).hexdigest()" in recovery
    assert "python -m release.publish_mcp_registry server.json" in recovery
    assert 'gh release create "${RELEASE_TAG}" dist/*' in recovery
