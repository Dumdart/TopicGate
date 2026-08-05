import os
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QLabel,
    QPushButton,
    QSplitter,
    QToolBar,
)

from smart_home_observer.core.models.mqtt_message import MqttMessage
from smart_home_observer.core.models.observer_model import ObserverModel, TopicState
from smart_home_observer.core.models.subscription import Subscription
from smart_home_observer.gui.components.connection_controls import ConnectionControls
from smart_home_observer.gui.gui import MainWindow
from smart_home_observer.gui.main_view_model import MainViewModel


class FakeGuiRepository:
    connection_status = "connected"
    subscriptions = (Subscription("home/+/temperature"),)

    def __init__(self) -> None:
        self.state = TopicState(
            name="temperature",
            topic="home/kitchen/temperature",
            payload=b"21.5",
            qos=1,
            retain=False,
            recieved_at=datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc),
        )

    def get(self) -> ObserverModel:
        return ObserverModel(root_stats=[], topic_states={self.state.topic: self.state})

    def get_state(self, topic: str) -> TopicState | None:
        return self.state if topic == self.state.topic else None

    async def messages(self) -> AsyncIterator[MqttMessage]:
        if False:
            yield MqttMessage("", b"", 0, False)


def test_main_window_builds_three_pane_workspace_and_collapsible_log() -> None:
    application = QApplication.instance() or QApplication([])
    repository = FakeGuiRepository()
    view_model = MainViewModel(repository, repository.state.topic)
    settings = QSettings(
        str(Path(".pytest_cache/gui-layout.ini").resolve()),
        QSettings.Format.IniFormat,
    )
    settings.clear()

    window = MainWindow(view_model, settings)

    splitter = window.findChild(QSplitter, "workspaceSplitter")
    log_dock = window.findChild(QDockWidget, "logConsoleDock")
    assert splitter is not None
    assert splitter.count() == 3
    assert log_dock is not None
    assert window.findChild(QLabel, "settingsHint").text() == (
        "Matched by subscription: home/+/temperature"
    )
    connection_status = window.findChild(QLabel, "connectionStatus")
    connection_controls = window.findChild(ConnectionControls)
    toolbar = window.findChild(QToolBar, "observerToolbar")
    assert connection_controls is not None
    assert connection_status is not None
    assert connection_status.text().endswith("Connected")
    assert window.menuBar().cornerWidget(Qt.Corner.TopRightCorner) is connection_status
    assert toolbar.findChild(QLabel, "connectionStatus") is None
    assert not window.findChild(QAction, "connectAction").isEnabled()
    assert window.findChild(QAction, "reconnectAction").isEnabled()
    assert window.findChild(QAction, "disconnectAction").isEnabled()

    window.close()
    application.processEvents()


def test_connection_controls_bundle_actions_and_request_signals() -> None:
    application = QApplication.instance() or QApplication([])
    controls = ConnectionControls()
    requests: list[str] = []
    controls.connect_requested.connect(lambda: requests.append("connect"))
    controls.reconnect_requested.connect(lambda: requests.append("reconnect"))
    controls.disconnect_requested.connect(lambda: requests.append("disconnect"))

    for action in controls.actions:
        action.setEnabled(True)
        action.trigger()

    assert requests == ["connect", "reconnect", "disconnect"]
    controls.status_label.deleteLater()
    controls.deleteLater()
    application.processEvents()


def test_connection_actions_follow_the_rendered_connection_status() -> None:
    application = QApplication.instance() or QApplication([])
    repository = FakeGuiRepository()
    view_model = MainViewModel(repository)
    window = MainWindow(view_model)

    connect_action = window.findChild(QAction, "connectAction")
    reconnect_action = window.findChild(QAction, "reconnectAction")
    disconnect_action = window.findChild(QAction, "disconnectAction")

    view_model._connection_status = "disconnected"
    view_model.connection_changed.emit()
    assert connect_action.isEnabled()
    assert not reconnect_action.isEnabled()
    assert not disconnect_action.isEnabled()

    view_model._connection_status = "reconnecting"
    view_model.connection_changed.emit()
    assert not connect_action.isEnabled()
    assert reconnect_action.isEnabled()
    assert disconnect_action.isEnabled()

    window.close()
    application.processEvents()


def test_unmatched_dynamic_topic_leaves_settings_disabled() -> None:
    application = QApplication.instance() or QApplication([])
    repository = FakeGuiRepository()
    view_model = MainViewModel(repository, "unmatched/topic")
    settings = QSettings(
        str(Path(".pytest_cache/gui-unmatched.ini").resolve()),
        QSettings.Format.IniFormat,
    )
    settings.clear()

    window = MainWindow(view_model, settings)

    settings_hint = window.findChild(QLabel, "settingsHint")
    apply_button = window.findChild(QPushButton, "applySubscriptionButton")
    assert settings_hint.text() == "No editable subscription filter selected."
    assert not apply_button.isEnabled()
    window.close()
    application.processEvents()
