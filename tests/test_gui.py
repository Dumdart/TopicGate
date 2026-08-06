import asyncio
import os
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QSettings, Qt
from PySide6.QtGui import QAction
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDockWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QToolBar,
    QToolButton,
    QTreeView,
)

from smart_home_observer.core.config.mqtt_config import MqttConfig
from smart_home_observer.core.models.mqtt_message import MqttMessage
from smart_home_observer.core.models.observer_model import ObserverModel, TopicState
from smart_home_observer.core.models.subscription import Subscription
from smart_home_observer.gui.components.connection_controls import ConnectionControls
from smart_home_observer.gui.components.broker_settings_dialog import (
    BrokerSettingsDialog,
)
from smart_home_observer.gui.components.observer_tree import ObserverTreePane
from smart_home_observer.gui.gui import MainWindow
from smart_home_observer.gui.main_view_model import MainViewModel


class FakeGuiRepository:
    connection_status = "connected"
    subscriptions = (Subscription("home/+/temperature"),)

    def __init__(self) -> None:
        self.subscriptions = type(self).subscriptions
        self.removed_subscriptions: list[Subscription] = []
        self.broker_configurations: list[MqttConfig] = []
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

    async def remove_subscription(self, subscription: Subscription) -> None:
        self.removed_subscriptions.append(subscription)
        self.subscriptions = tuple(
            item for item in self.subscriptions if item != subscription
        )

    async def update_broker(self, mqtt_config: MqttConfig) -> None:
        self.broker_configurations.append(mqtt_config)


class FakeBrokerRepository:
    def __init__(self, mqtt_config: MqttConfig) -> None:
        self._mqtt_config = mqtt_config
        self.updated_mqtt: list[MqttConfig] = []

    def get_mqtt(self) -> MqttConfig:
        return self._mqtt_config

    def update_mqtt(self, mqtt_config: MqttConfig) -> None:
        self._mqtt_config = mqtt_config
        self.updated_mqtt.append(mqtt_config)


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


def test_observer_tree_adds_trash_buttons_only_to_subscription_filters() -> None:
    application = QApplication.instance() or QApplication([])
    pane = ObserverTreePane()
    subscription = Subscription("home/+/temperature")
    requested: list[Subscription] = []
    pane.remove_filter_requested.connect(requested.append)

    pane.render(
        [subscription.topic_filter, "home/kitchen/temperature"],
        "",
        (subscription,),
    )

    buttons = pane.findChildren(QToolButton, "removeSubscriptionButton")
    tree = pane.findChild(QTreeView, "observerTree")
    assert len(buttons) == 1
    assert tree is not None
    assert tree.header().sectionSize(1) == 34
    assert buttons[0].size().width() == 24
    assert buttons[0].size().height() == 18
    assert "background-color: #7f1d1d" in buttons[0].styleSheet()
    assert "QToolButton:hover" in buttons[0].styleSheet()
    assert buttons[0].toolTip() == (
        "Remove subscription home/+/temperature"
    )

    buttons[0].click()

    assert requested == [subscription]
    pane.deleteLater()
    application.processEvents()


def test_subscription_trash_button_runs_the_removal_workflow() -> None:
    async def scenario() -> None:
        application = QApplication.instance() or QApplication([])
        repository = FakeGuiRepository()
        view_model = MainViewModel(repository, repository.state.topic)
        settings = QSettings(
            str(Path(".pytest_cache/gui-remove.ini").resolve()),
            QSettings.Format.IniFormat,
        )
        settings.clear()
        window = MainWindow(view_model, settings)
        button = window.findChild(QToolButton, "removeSubscriptionButton")

        assert button is not None
        button.click()
        await asyncio.sleep(0)

        assert repository.removed_subscriptions == [
            Subscription("home/+/temperature")
        ]
        assert repository.subscriptions == ()
        application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        application.processEvents()
        assert window.findChild(
            QToolButton, "removeSubscriptionButton"
        ) is None
        tree = window.findChild(QTreeView, "observerTree")
        assert tree is not None
        assert tree.model().rowCount() == 0
        window.close()
        application.processEvents()

    asyncio.run(scenario())


def test_broker_settings_dialog_loads_current_configuration_and_validates_input() -> None:
    application = QApplication.instance() or QApplication([])
    repository = FakeGuiRepository()
    mqtt_config = MqttConfig("broker.local", 1883, "", "", False)
    view_model = MainViewModel(
        repository,
        broker_repository=FakeBrokerRepository(mqtt_config),
    )
    dialog = BrokerSettingsDialog(view_model)

    host_edit = dialog.findChild(QLineEdit, "brokerHostEdit")
    port_edit = dialog.findChild(QLineEdit, "brokerPortEdit")
    password_edit = dialog.findChild(QLineEdit, "brokerPasswordEdit")
    tls_checkbox = dialog.findChild(QCheckBox, "brokerUseTlsCheckbox")
    apply_button = dialog.findChild(QPushButton, "applyBrokerSettingsButton")
    assert host_edit is not None
    assert port_edit is not None
    assert password_edit is not None
    assert tls_checkbox is not None
    assert apply_button is not None
    assert host_edit.text() == "broker.local"
    assert port_edit.text() == "1883"
    assert password_edit.echoMode() == QLineEdit.EchoMode.Password
    assert not tls_checkbox.isChecked()
    assert apply_button.isEnabled()

    host_edit.setText(" ")
    assert not apply_button.isEnabled()
    host_edit.setText("broker.local")
    port_edit.setText("not-a-port")
    assert not apply_button.isEnabled()
    port_edit.setText("65536")
    assert not apply_button.isEnabled()
    port_edit.setText("1883")
    assert apply_button.isEnabled()

    dialog.close()
    application.processEvents()


def test_tls_defaults_port_only_until_the_user_changes_it() -> None:
    application = QApplication.instance() or QApplication([])
    repository = FakeGuiRepository()
    view_model = MainViewModel(
        repository,
        broker_repository=FakeBrokerRepository(MqttConfig("broker", 1883, "", "")),
    )
    dialog = BrokerSettingsDialog(view_model)
    port_edit = dialog.findChild(QLineEdit, "brokerPortEdit")
    tls_checkbox = dialog.findChild(QCheckBox, "brokerUseTlsCheckbox")
    assert port_edit is not None
    assert tls_checkbox is not None

    tls_checkbox.setChecked(True)
    assert port_edit.text() == "8883"
    port_edit.setFocus()
    port_edit.selectAll()
    QTest.keyClicks(port_edit, "1884")
    tls_checkbox.setChecked(False)
    tls_checkbox.setChecked(True)
    assert port_edit.text() == "1884"

    dialog.close()
    application.processEvents()


def test_applying_broker_settings_updates_the_view_model_and_closes_dialog() -> None:
    async def scenario() -> None:
        application = QApplication.instance() or QApplication([])
        repository = FakeGuiRepository()
        broker_repository = FakeBrokerRepository(MqttConfig("old", 1883, "", ""))
        view_model = MainViewModel(repository, broker_repository=broker_repository)
        window = MainWindow(view_model)
        window.findChild(QAction, "brokerSettingsAction").trigger()
        dialog = window.findChild(BrokerSettingsDialog, "brokerSettingsDialog")
        assert dialog is not None
        dialog.findChild(QLineEdit, "brokerHostEdit").setText("new-broker")
        dialog.findChild(QLineEdit, "brokerPortEdit").setText("8883")
        dialog.findChild(QCheckBox, "brokerUseTlsCheckbox").setChecked(True)

        dialog.findChild(QPushButton, "applyBrokerSettingsButton").click()
        await asyncio.sleep(0)

        expected = MqttConfig("new-broker", 8883, "", "", True)
        assert repository.broker_configurations == [expected]
        assert broker_repository.updated_mqtt == [expected]
        assert dialog.result() == QDialog.DialogCode.Accepted
        assert not dialog.isVisible()
        window.close()
        application.processEvents()

    asyncio.run(scenario())


def test_failed_broker_update_keeps_dialog_open_and_shows_error() -> None:
    class FailingGuiRepository(FakeGuiRepository):
        async def update_broker(self, mqtt_config: MqttConfig) -> None:
            raise ConnectionError("broker unavailable")

    async def scenario() -> None:
        application = QApplication.instance() or QApplication([])
        broker_repository = FakeBrokerRepository(MqttConfig("old", 1883, "", ""))
        view_model = MainViewModel(
            FailingGuiRepository(),
            broker_repository=broker_repository,
        )
        window = MainWindow(view_model)
        window.findChild(QAction, "brokerSettingsAction").trigger()
        dialog = window.findChild(BrokerSettingsDialog, "brokerSettingsDialog")
        assert dialog is not None

        with patch(
            "smart_home_observer.gui.main_window.QMessageBox.warning"
        ) as warning:
            dialog.findChild(QPushButton, "applyBrokerSettingsButton").click()
            await asyncio.sleep(0)

        assert dialog.isVisible()
        assert dialog.result() == QDialog.DialogCode.Rejected
        assert broker_repository.updated_mqtt == []
        warning.assert_called_once_with(
            window,
            "Broker update failed",
            "broker unavailable",
        )
        window.close()
        application.processEvents()

    asyncio.run(scenario())
