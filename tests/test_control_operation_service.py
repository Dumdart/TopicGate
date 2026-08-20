import time

import pytest

from topicgate.app.services.control_operation_service import (
    ControlOperationConflict,
    ControlOperationService,
)
from topicgate.infrastructure.database.database_context import DatabaseContext


def test_control_lease_reports_live_conflicts_and_external_changes(tmp_path) -> None:
    url = f"sqlite:///{(tmp_path / 'lease.db').as_posix()}"
    desktop_database = DatabaseContext(url)
    mcp_database = DatabaseContext(url)
    desktop = ControlOperationService(desktop_database, "desktop")
    mcp = ControlOperationService(mcp_database, "mcp")

    with desktop.operation("delete stored observations"):
        with pytest.raises(ControlOperationConflict, match="desktop.*delete"):
            with mcp.operation("activate broker"):
                pass

    with pytest.raises(ControlOperationConflict, match="changed in another"):
        with mcp.operation("activate broker"):
            pass

    restarted_mcp = ControlOperationService(mcp_database, "mcp")
    with restarted_mcp.operation("activate broker"):
        pass
    desktop_database.dispose()
    mcp_database.dispose()


def test_control_lease_renews_during_long_operations(tmp_path) -> None:
    url = f"sqlite:///{(tmp_path / 'renew.db').as_posix()}"
    desktop_database = DatabaseContext(url)
    mcp_database = DatabaseContext(url)
    desktop = ControlOperationService(
        desktop_database,
        "desktop",
        lease_seconds=0.15,
    )
    mcp = ControlOperationService(mcp_database, "mcp", lease_seconds=0.15)

    with desktop.operation("reconnect and observe"):
        time.sleep(0.25)
        with pytest.raises(ControlOperationConflict, match="reconnect and observe"):
            with mcp.operation("publish MQTT message"):
                pass
    desktop_database.dispose()
    mcp_database.dispose()
