import os
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, Qt
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
    toolbar = window.findChild(QToolBar, "observerToolbar")
    assert connection_status is not None
    assert connection_status.text().endswith("Connected")
    assert window.menuBar().cornerWidget(Qt.Corner.TopRightCorner) is connection_status
    assert toolbar.findChild(QLabel, "connectionStatus") is None

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
