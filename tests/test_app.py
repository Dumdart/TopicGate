import asyncio
from unittest.mock import AsyncMock, MagicMock

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QGuiApplication

from topicgate.gui.app import App, configure_application_identity


def test_application_uses_topicgate_identity() -> None:
    configure_application_identity()

    assert QCoreApplication.organizationName() == "Dumdart"
    assert QCoreApplication.applicationName() == "TopicGate"
    assert QGuiApplication.applicationDisplayName() == "TopicGate Desktop"


async def test_app_remains_open_when_initial_mqtt_connection_fails() -> None:
    async def scenario() -> None:
        app = object.__new__(App)
        app._services = MagicMock()
        app._services.start_services = AsyncMock(
            side_effect=ConnectionError("broker unavailable")
        )
        app._services.stop_services = AsyncMock()
        app._view_model = MagicMock()
        app._view_model.start = AsyncMock()
        app._view_model.stop = AsyncMock()
        app._window = MagicMock()
        app._window.cancel_pending_operations = AsyncMock()
        app._qt_application = MagicMock()
        app._qt_application.lastWindowClosed.connect.side_effect = (
            lambda callback: callback()
        )

        result = await app.run()

        assert result == 0
        app._view_model.start.assert_awaited_once()
        app._window.show.assert_called_once_with()
        app._view_model.log_message.emit.assert_called_once()
        app._view_model.stop.assert_awaited_once()
        app._services.stop_services.assert_awaited_once()

    await scenario()


async def test_app_cleans_window_and_view_model_before_services() -> None:
    events: list[str] = []
    app = object.__new__(App)
    app._services = MagicMock()
    app._services.start_services = AsyncMock()
    app._services.stop_services = AsyncMock(
        side_effect=lambda: events.append("services")
    )
    app._view_model = MagicMock()
    app._view_model.start = AsyncMock()
    app._view_model.stop = AsyncMock(
        side_effect=lambda: events.append("view-model")
    )
    app._window = MagicMock()
    app._window.cancel_pending_operations = AsyncMock(
        side_effect=lambda: events.append("window")
    )
    app._qt_application = MagicMock()
    app._qt_application.lastWindowClosed.connect.side_effect = (
        lambda callback: callback()
    )

    assert await app.run() == 0
    assert events == ["window", "view-model", "services"]


async def test_app_keeps_qt_event_loop_running_during_shutdown() -> None:
    app = object.__new__(App)
    app._services = MagicMock()
    app._services.start_services = AsyncMock()
    app._services.stop_services = AsyncMock()
    app._view_model = MagicMock()
    app._view_model.start = AsyncMock()
    app._view_model.stop = AsyncMock()
    app._window = MagicMock()
    app._window.cancel_pending_operations = AsyncMock()
    app._qt_application = MagicMock()
    app._qt_application.lastWindowClosed.connect.side_effect = (
        lambda callback: callback()
    )

    assert await app.run() == 0

    app._qt_application.setQuitOnLastWindowClosed.assert_called_once_with(False)


async def test_repeated_shutdown_signal_only_cleans_up_once() -> None:
    app = object.__new__(App)
    app._services = MagicMock()
    app._services.start_services = AsyncMock()
    app._services.stop_services = AsyncMock()
    app._view_model = MagicMock()
    app._view_model.start = AsyncMock()
    app._view_model.stop = AsyncMock()
    app._window = MagicMock()
    app._window.cancel_pending_operations = AsyncMock()
    app._qt_application = MagicMock()
    app._qt_application.lastWindowClosed.connect.side_effect = (
        lambda callback: (callback(), callback())
    )

    assert await app.run() == 0
    app._view_model.stop.assert_awaited_once()
    app._services.stop_services.assert_awaited_once()


async def test_partial_view_model_startup_is_cleaned_up() -> None:
    app = object.__new__(App)
    app._services = MagicMock()
    app._services.start_services = AsyncMock()
    app._services.stop_services = AsyncMock()
    app._view_model = MagicMock()
    app._view_model.start = AsyncMock(side_effect=RuntimeError("start failed"))
    app._view_model.stop = AsyncMock()
    app._window = MagicMock()
    app._window.cancel_pending_operations = AsyncMock()
    app._qt_application = MagicMock()

    try:
        await app.run()
    except RuntimeError as error:
        assert str(error) == "start failed"
    else:
        raise AssertionError("Expected startup failure")
    app._view_model.stop.assert_awaited_once()
    app._services.stop_services.assert_awaited_once()
    app._window.show.assert_not_called()
