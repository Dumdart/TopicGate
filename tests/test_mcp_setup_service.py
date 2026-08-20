import json
from pathlib import Path

from topicgate.app.app_dependencies import AppDependencies


def test_desktop_mcp_setup_generates_resolved_modes_and_actionable_preflight(
    tmp_path: Path,
    credential_store,
) -> None:
    dependencies = AppDependencies(
        data_dir=tmp_path,
        credential_store=credential_store,
        control_owner="desktop",
    )
    setup = dependencies.mcp_setup

    try:
        read_only = json.loads(setup.configuration("read-only"))
        control = json.loads(setup.configuration("control"))
        read_server = read_only["mcpServers"]["topicgate"]
        control_server = control["mcpServers"]["topicgate"]

        assert Path(read_server["command"]).is_absolute()
        assert read_server["args"][-2:] == ["--mode", "read-only"]
        assert control_server["args"][-2:] == ["--mode", "control"]
        assert setup.information.data_path == tmp_path.resolve()
        assert setup.information.database_path == (tmp_path / "topicgate.db").resolve()

        checks = {check.name: check for check in setup.preflight()}
        assert checks["Database accessibility"].status == "pass"
        assert checks["Database migrations"].status == "pass"
        assert checks["Credential store"].status == "pass"
        assert checks["Broker profiles"].status == "pass"
        assert checks["Subscriptions"].status == "fail"
        assert "Add at least one subscription" in checks["Subscriptions"].detail
        assert checks["Snapshot service"].status == "pass"
        assert "Dashboard dependencies" in checks
    finally:
        dependencies.topic_messages.close()
        dependencies._db_context.dispose()
