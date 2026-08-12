import asyncio
import os
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QSettings, Qt
from PySide6.QtGui import QAction
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDockWidget,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QToolBar,
    QToolButton,
    QTreeView,
)

from topicgate.core.config.mqtt_config import MqttConfig
from topicgate.app.topicgate_runtime import TopicGateRuntime
from topicgate.core.models.mqtt_message import MqttMessage
from topicgate.core.models.broker_profile import BrokerProfile
from topicgate.core.models.observer_model import ObserverModel, TopicState
from topicgate.core.models.observer_workspace import ObserverWorkspace
from topicgate.core.models.subscription import Subscription
from topicgate.gui.components.about_dialog import AboutDialog
from topicgate.gui.components.connection_controls import ConnectionControls
from topicgate.gui.components.broker_settings_dialog import (
    BrokerSettingsDialog,
)
from topicgate.gui.components.observer_tree import ObserverTreePane
from topicgate.gui.components.topic_details import TopicDetailsPane
from topicgate.gui.gui import MainWindow
from topicgate.gui.main_view_model import MainViewModel


def test_redesigned_window_exposes_header_and_publish_workspace() -> None:
    application = QApplication.instance() or QApplication([])
    repository = FakeGuiRepository()
    view_model = MainViewModel(runtime_for(repository), repository.state.topic)
    window = MainWindow(view_model)

    assert window.minimumWidth() == 1024
    assert window.minimumHeight() == 640
    assert window.findChild(QComboBox, "brokerSelector") is not None
    assert window.findChild(QLabel, "brokerEndpoint").text() == "mqtt://broker:1883"
    assert window.findChild(QLineEdit, "publishTopic").text() == repository.state.topic
    assert window.findChild(QPlainTextEdit, "publishPayload") is not None
    publish_payload = window.findChild(QPlainTextEdit, "publishPayload")
    assert not window.findChild(QPushButton, "publishButton").isEnabled()
    publish_payload.setPlainText("open")
    assert window.findChild(QPushButton, "publishButton").isEnabled()
    assert "#f3f4f6" in window.styleSheet()

    window.close()
    application.processEvents()


class FakeGuiRepository:
    connection_status = "connected"
    topic_update_interval = 0.0
    dropped_message_count = 0
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

    async def connection_statuses(self) -> AsyncIterator[object]:
        if False:
            yield "connected"

    def drain_pending_messages(self) -> tuple[MqttMessage, ...]:
        return ()

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def connect(self) -> None:
        pass

    async def reconnect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def remove_subscription(self, subscription: Subscription) -> None:
        self.removed_subscriptions.append(subscription)
        self.subscriptions = tuple(
            item for item in self.subscriptions if item != subscription
        )

    async def add_subscription(self, subscription: Subscription) -> None:
        self.subscriptions += (subscription,)

    async def update_subscription(
        self, original_filter: str, subscription: Subscription
    ) -> None:
        self.subscriptions = tuple(
            subscription if item.topic_filter == original_filter else item
            for item in self.subscriptions
        )

    async def update_broker(
        self,
        mqtt_config: MqttConfig,
        model: ObserverModel | None = None,
        subscriptions: tuple[Subscription, ...] | None = None,
    ) -> None:
        self.broker_configurations.append(mqtt_config)


class FakeBrokerRepository:
    def __init__(self, mqtt_config: MqttConfig) -> None:
        default_profile = self._profile("Default", mqtt_config)
        local_profile = self._profile("Local MQTT", MqttConfig("localhost", 1883, "", ""))
        self._profiles = {
            default_profile.id: default_profile,
            local_profile.id: local_profile,
        }
        self._active_profile_id = default_profile.id
        self.updated_mqtt: list[MqttConfig] = []

    def get_mqtt(self) -> MqttConfig:
        return self.get_profile().config

    def update_mqtt(self, mqtt_config: MqttConfig) -> None:
        self.activate_profile(self._active_profile_id, mqtt_config)

    def get_profile(self, profile_id: UUID | None = None) -> BrokerProfile:
        return self._profiles[profile_id or self._active_profile_id]

    def get_all_profiles(self) -> tuple[BrokerProfile, ...]:
        return tuple(self._profiles.values())

    def create_profile(
        self,
        name: str,
        mqtt_config: MqttConfig,
    ) -> BrokerProfile:
        profile = self._profile(name.strip(), mqtt_config)
        self._profiles[profile.id] = profile
        return profile

    def update_profile(self, profile: BrokerProfile) -> None:
        self._profiles[profile.id] = profile

    def delete_profile(self, profile_id: UUID) -> BrokerProfile:
        return self._profiles.pop(profile_id)

    def activate_profile(
        self,
        profile_id: UUID,
        mqtt_config: MqttConfig | None = None,
    ) -> None:
        profile = self.get_profile(profile_id)
        if mqtt_config is not None:
            profile.config = mqtt_config
            self.updated_mqtt.append(mqtt_config)
        self._active_profile_id = profile_id

    def select_active_profile(self, profile_id: UUID) -> None:
        self.activate_profile(profile_id)
        self.updated_mqtt.append(self.get_profile(profile_id).config)

    def replace_subscriptions(
        self, workspace_id: UUID, subscriptions: tuple[Subscription, ...]
    ) -> None:
        profile = next(
            item for item in self._profiles.values() if item.workspace_id == workspace_id
        )
        profile.workspace.subscriptions = subscriptions

    def update_observer_workspace(self, workspace: ObserverWorkspace) -> None:
        self._profiles[workspace.profile_id].workspace = workspace

    def update_observer_model(self, model: ObserverModel) -> None:
        self.get_profile().workspace.model = model

    @staticmethod
    def _profile(name: str, mqtt_config: MqttConfig) -> BrokerProfile:
        profile_id = uuid4()
        workspace = ObserverWorkspace(
            id=uuid4(),
            profile_id=profile_id,
            model=ObserverModel(root_stats=[]),
        )
        return BrokerProfile(profile_id, name, mqtt_config, workspace.id, workspace)


class FakeTopicGateRuntime(TopicGateRuntime):
    """Runtime test double backed by in-memory repositories."""


def runtime_for(
    repository: FakeGuiRepository,
    broker_repository: FakeBrokerRepository | None = None,
) -> FakeTopicGateRuntime:
    brokers = broker_repository or FakeBrokerRepository(
        MqttConfig("broker", 1883, "", "")
    )
    profiles = brokers.get_all_profiles()
    repositories = {profile.id: repository for profile in profiles}
    return FakeTopicGateRuntime(
        brokers,
        repositories,
        brokers.get_profile().id,
        lambda _profile: repository,
    )


def test_main_window_builds_three_pane_workspace_and_collapsible_log() -> None:
    application = QApplication.instance() or QApplication([])
    repository = FakeGuiRepository()
    view_model = MainViewModel(
        runtime_for(
            repository,
            FakeBrokerRepository(MqttConfig("broker", 1883, "", "")),
        ),
        repository.state.topic,
    )
    settings = QSettings(
        str(Path(".pytest_cache/gui-layout.ini").resolve()),
        QSettings.Format.IniFormat,
    )
    settings.clear()

    window = MainWindow(view_model, settings)

    splitter = window.findChild(QSplitter, "workspaceSplitter")
    log_dock = window.findChild(QDockWidget, "logConsoleDock")
    assert window.windowTitle() == "TopicGate Desktop"
    assert window.findChild(QAction, "aboutAction").text() == "About TopicGate"
    assert splitter is not None
    assert splitter.count() == 3
    assert log_dock is not None
    assert window.findChild(QLabel, "settingsHint").text() == (
        "Matched by subscription: home/+/temperature"
    )
    assert (
        window.findChild(QLabel, "settingsHint").textFormat()
        == Qt.TextFormat.PlainText
    )
    connection_status = window.findChild(QLabel, "connectionStatus")
    connection_controls = window.findChild(ConnectionControls)
    assert connection_controls is not None
    assert connection_status is not None
    assert connection_status.text() == "MQTT Connected"
    assert connection_status.status == "connected"
    assert connection_status.minimumWidth() >= 188
    assert connection_status.minimumHeight() >= 34
    assert connection_status.accessibleDescription() == (
        "MQTT connection is connected."
    )
    assert connection_status.toolTip() == "MQTT broker is connected"
    assert window.findChild(QToolButton, "brokerSettingsButton") is None
    assert (
        window.menuBar().cornerWidget(Qt.Corner.TopRightCorner)
        is connection_status
    )
    assert window.findChild(QToolBar, "observerToolbar") is None
    assert not window.findChild(QAction, "connectAction").isEnabled()
    assert window.findChild(QAction, "reconnectAction").isEnabled()
    assert window.findChild(QAction, "disconnectAction").isEnabled()

    window.close()
    application.processEvents()


def test_topic_details_renders_broker_topics_as_literal_plain_text() -> None:
    application = QApplication.instance() or QApplication([])
    repository = FakeGuiRepository()
    pane = TopicDetailsPane()
    topic_label = pane.findChild(QLabel, "topicPathLabel")
    assert topic_label is not None
    assert topic_label.textFormat() == Qt.TextFormat.PlainText

    topics = (
        "home/kitchen/temperature",
        '<b>spoofed</b><img src="file:///C:/secret">',
        '\\\\attacker\\share\\<img src="//attacker/share/pixel.png">',
    )
    for topic in topics:
        pane.render(MainViewModel(runtime_for(repository), topic))
        assert topic_label.text() == topic
        assert topic_label.textFormat() == Qt.TextFormat.PlainText

    pane.deleteLater()
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
    view_model = MainViewModel(
        runtime_for(
            repository,
            FakeBrokerRepository(MqttConfig("broker", 1883, "", "")),
        ),
    )
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
    view_model = MainViewModel(
        runtime_for(
            repository,
            FakeBrokerRepository(MqttConfig("broker", 1883, "", "")),
        ),
        "unmatched/topic",
    )
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


async def test_subscription_trash_button_runs_the_removal_workflow() -> None:
    async def scenario() -> None:
        application = QApplication.instance() or QApplication([])
        repository = FakeGuiRepository()
        view_model = MainViewModel(
            runtime_for(
                repository,
                FakeBrokerRepository(MqttConfig("broker", 1883, "", "")),
            ),
            repository.state.topic,
        )
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

    await scenario()


def test_broker_settings_dialog_loads_current_configuration_and_validates_input() -> None:
    application = QApplication.instance() or QApplication([])
    repository = FakeGuiRepository()
    mqtt_config = MqttConfig("broker.local", 1883, "", "", False)
    view_model = MainViewModel(
        runtime_for(repository, FakeBrokerRepository(mqtt_config)),
    )
    dialog = BrokerSettingsDialog(view_model)

    host_edit = dialog.findChild(QLineEdit, "brokerHostEdit")
    port_edit = dialog.findChild(QLineEdit, "brokerPortEdit")
    password_edit = dialog.findChild(QLineEdit, "brokerPasswordEdit")
    username_edit = dialog.findChild(QLineEdit, "brokerUsernameEdit")
    tls_checkbox = dialog.findChild(QCheckBox, "brokerUseTlsCheckbox")
    security_error = dialog.findChild(QLabel, "brokerTransportSecurityError")
    apply_button = dialog.findChild(QPushButton, "applyBrokerSettingsButton")
    assert host_edit is not None
    assert port_edit is not None
    assert password_edit is not None
    assert username_edit is not None
    assert tls_checkbox is not None
    assert security_error is not None
    assert apply_button is not None
    assert host_edit.text() == "broker.local"
    assert port_edit.text() == "1883"
    assert password_edit.echoMode() == QLineEdit.EchoMode.Password
    assert not tls_checkbox.isChecked()
    assert security_error.isHidden()
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
    username_edit.setText("observer")
    assert apply_button.isEnabled()
    assert not security_error.isHidden()
    assert dialog.mqtt_config == MqttConfig(
        "broker.local", 1883, "observer", "", False
    )
    tls_checkbox.setChecked(True)
    assert security_error.isHidden()

    dialog.close()
    application.processEvents()


def test_broker_settings_dialog_masks_a_configured_password() -> None:
    application = QApplication.instance() or QApplication([])
    mqtt_config = MqttConfig(
        "broker.local",
        8883,
        "observer",
        "os-loaded-secret",
        True,
    )
    view_model = MainViewModel(
        runtime_for(FakeGuiRepository(), FakeBrokerRepository(mqtt_config)),
    )
    dialog = BrokerSettingsDialog(view_model)

    password_edit = dialog.findChild(QLineEdit, "brokerPasswordEdit")

    assert password_edit is not None
    assert password_edit.text() == ""
    assert password_edit.placeholderText() == "********"
    assert "os-loaded-secret" not in password_edit.text()

    dialog.close()
    application.processEvents()


def test_observer_tree_renders_a_broker_profile_dropdown() -> None:
    application = QApplication.instance() or QApplication([])
    broker_repository = FakeBrokerRepository(MqttConfig("broker", 1883, "", ""))
    pane = ObserverTreePane()
    selected: list[UUID] = []
    edited: list[UUID] = []
    pane.broker_profile_selected.connect(selected.append)
    pane.edit_broker_profile_requested.connect(edited.append)

    pane.render_broker_profiles(
        broker_repository.get_all_profiles(),
        broker_repository.get_profile().id,
    )

    button = pane.findChild(QToolButton, "brokerProfileButton")
    assert button is not None
    assert button.text() == "Default"
    actions = button.menu().actions()
    assert [action.text() for action in actions] == [
        "Default",
        "Local MQTT",
        "",
        "Add profile...",
        "Edit profile...",
        "Delete current profile...",
    ]
    edit_actions = actions[4].menu().actions()
    assert [action.text() for action in edit_actions] == ["Default", "Local MQTT"]
    edit_actions[1].trigger()
    assert edited == [broker_repository.get_all_profiles()[1].id]
    assert actions[0].isChecked()
    assert not actions[0].isEnabled()

    actions[1].trigger()

    assert selected == [broker_repository.get_all_profiles()[1].id]
    pane.deleteLater()
    application.processEvents()


def test_profile_menu_creates_a_new_broker_profile() -> None:
    application = QApplication.instance() or QApplication([])
    broker_repository = FakeBrokerRepository(MqttConfig("broker", 1883, "", ""))
    view_model = MainViewModel(
        runtime_for(FakeGuiRepository(), broker_repository),
    )
    window = MainWindow(view_model)
    button = window.findChild(QToolButton, "brokerProfileButton")
    assert button is not None
    add_action = next(
        action
        for action in button.menu().actions()
        if action.objectName() == "addBrokerProfileAction"
    )

    add_action.trigger()
    dialog = window.findChild(BrokerSettingsDialog, "createBrokerProfileDialog")
    assert dialog is not None
    name_edit = dialog.findChild(QLineEdit, "brokerProfileNameEdit")
    host_edit = dialog.findChild(QLineEdit, "brokerHostEdit")
    apply_button = dialog.findChild(QPushButton, "applyBrokerSettingsButton")
    assert name_edit is not None
    assert host_edit is not None
    assert apply_button is not None
    assert not apply_button.isEnabled()

    name_edit.setText("Remote")
    host_edit.setText("remote.local")
    apply_button.click()

    assert [profile.name for profile in view_model.broker_profiles] == [
        "Default",
        "Local MQTT",
        "Remote",
    ]
    assert dialog.result() == QDialog.DialogCode.Accepted
    window.close()
    application.processEvents()


def test_about_action_opens_the_project_about_view() -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow(
        MainViewModel(
            runtime_for(
                FakeGuiRepository(),
                FakeBrokerRepository(MqttConfig("broker", 1883, "", "")),
            ),
        )
    )

    window.findChild(QAction, "aboutAction").trigger()

    dialog = window.findChild(AboutDialog, "aboutDialog")
    assert dialog is not None
    assert dialog.findChild(QLabel, "aboutTitle").text() == "TopicGate"
    assert dialog.findChild(QLabel, "aboutVersion").text().startswith("Version ")
    assert "SQLite" in dialog.findChild(QLabel, "aboutStorageText").text()
    assert "github.com/Dumdart/TopicGate" in dialog.findChild(
        QLabel,
        "aboutProjectLink",
    ).text()
    dialog.reject()
    window.close()
    application.processEvents()


def test_profile_menu_edits_an_inactive_profile_without_connecting() -> None:
    application = QApplication.instance() or QApplication([])
    repository = FakeGuiRepository()
    broker_repository = FakeBrokerRepository(MqttConfig("broker", 1883, "", ""))
    active_profile = broker_repository.get_profile()
    inactive_profile = broker_repository.get_all_profiles()[1]
    view_model = MainViewModel(runtime_for(repository, broker_repository))
    window = MainWindow(view_model)
    profile_button = window.findChild(QToolButton, "brokerProfileButton")
    edit_menu = profile_button.menu().actions()[4].menu()

    edit_menu.actions()[1].trigger()
    dialog = window.findChild(BrokerSettingsDialog, "brokerSettingsDialog")
    assert dialog is not None
    assert dialog.profile_id == inactive_profile.id
    dialog.findChild(QLineEdit, "brokerHostEdit").setText("fixed.local")
    dialog.findChild(QPushButton, "saveBrokerSettingsButton").click()

    assert repository.broker_configurations == []
    assert broker_repository.get_profile().id == active_profile.id
    assert broker_repository.get_profile(inactive_profile.id).config.host == "fixed.local"
    assert dialog.result() == QDialog.DialogCode.Accepted
    window.close()
    application.processEvents()


async def test_profile_menu_deletes_the_active_profile_after_switching() -> None:
    async def scenario() -> None:
        application = QApplication.instance() or QApplication([])
        repository = FakeGuiRepository()
        broker_repository = FakeBrokerRepository(MqttConfig("broker", 1883, "", ""))
        view_model = MainViewModel(runtime_for(repository, broker_repository))
        window = MainWindow(view_model)
        button = window.findChild(QToolButton, "brokerProfileButton")
        assert button is not None
        delete_action = next(
            action
            for action in button.menu().actions()
            if action.objectName() == "deleteBrokerProfileAction"
        )

        with patch(
            "topicgate.gui.main_window.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            delete_action.trigger()
            await asyncio.sleep(0)

        assert [profile.name for profile in view_model.broker_profiles] == [
            "Local MQTT"
        ]
        assert view_model.active_broker_profile.name == "Local MQTT"
        assert not window.findChild(
            QAction,
            "deleteBrokerProfileAction",
        ).isEnabled()
        window.close()
        application.processEvents()

    await scenario()


async def test_profile_dropdown_confirms_before_shutting_down_and_switching() -> None:
    async def scenario() -> None:
        application = QApplication.instance() or QApplication([])
        repository = FakeGuiRepository()
        broker_repository = FakeBrokerRepository(MqttConfig("broker", 1883, "", ""))
        view_model = MainViewModel(runtime_for(repository, broker_repository))
        window = MainWindow(view_model)
        button = window.findChild(QToolButton, "brokerProfileButton")
        assert button is not None
        local_profile = broker_repository.get_all_profiles()[1]

        with patch(
            "topicgate.gui.main_window.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ) as question:
            button.menu().actions()[1].trigger()
            await asyncio.sleep(0)

        assert repository.broker_configurations == [local_profile.config]
        assert broker_repository.get_profile().id == local_profile.id
        assert "Do you want to switch" in question.call_args.args[2]
        assert "shutting down the current MQTT connection" in question.call_args.args[2]
        window.close()
        application.processEvents()

    await scenario()


def test_tls_defaults_port_only_until_the_user_changes_it() -> None:
    application = QApplication.instance() or QApplication([])
    repository = FakeGuiRepository()
    view_model = MainViewModel(
        runtime_for(
            repository,
            FakeBrokerRepository(MqttConfig("broker", 1883, "", "")),
        ),
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


async def test_applying_broker_settings_updates_the_view_model_and_closes_dialog() -> None:
    async def scenario() -> None:
        application = QApplication.instance() or QApplication([])
        repository = FakeGuiRepository()
        broker_repository = FakeBrokerRepository(MqttConfig("old", 1883, "", ""))
        view_model = MainViewModel(runtime_for(repository, broker_repository))
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

    await scenario()


async def test_failed_broker_update_keeps_dialog_open_and_shows_error() -> None:
    class FailingGuiRepository(FakeGuiRepository):
        async def update_broker(
            self,
            mqtt_config: MqttConfig,
            model: ObserverModel | None = None,
            subscriptions: tuple[Subscription, ...] | None = None,
        ) -> None:
            raise ConnectionError("broker unavailable")

    async def scenario() -> None:
        application = QApplication.instance() or QApplication([])
        broker_repository = FakeBrokerRepository(MqttConfig("old", 1883, "", ""))
        view_model = MainViewModel(
            runtime_for(FailingGuiRepository(), broker_repository),
        )
        window = MainWindow(view_model)
        window.findChild(QAction, "brokerSettingsAction").trigger()
        dialog = window.findChild(BrokerSettingsDialog, "brokerSettingsDialog")
        assert dialog is not None

        with patch(
            "topicgate.gui.main_window.QMessageBox.warning"
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

    await scenario()
