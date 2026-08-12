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


def test_app_remains_open_when_initial_mqtt_connection_fails() -> None:
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
        app._qt_application = MagicMock()
        app._qt_application.aboutToQuit.connect.side_effect = (
            lambda callback: callback()
        )

        result = await app.run()

        assert result == 0
        app._view_model.start.assert_awaited_once()
        app._window.show.assert_called_once_with()
        app._view_model.log_message.emit.assert_called_once()
        app._view_model.stop.assert_awaited_once()
        app._services.stop_services.assert_awaited_once()

    asyncio.run(scenario())
