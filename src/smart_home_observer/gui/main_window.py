import asyncio
from collections.abc import Coroutine
from typing import Any
from uuid import UUID

from PySide6.QtCore import QByteArray, QSettings, Qt
from PySide6.QtGui import QAction, QCloseEvent, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSplitter,
)

from smart_home_observer.core.config.mqtt_config import MqttConfig
from smart_home_observer.core.models.subscription import Subscription
from smart_home_observer.gui.components.add_subscription_dialog import AddSubscriptionDialog
from smart_home_observer.gui.components.broker_settings_dialog import (
    BrokerSettingsDialog,
)
from smart_home_observer.gui.components.connection_controls import ConnectionControls
from smart_home_observer.gui.components.log_console import LogConsoleDock
from smart_home_observer.gui.components.observer_tree import ObserverTreePane
from smart_home_observer.gui.components.subscription_settings import (
    SubscriptionSettingsPane,
)
from smart_home_observer.gui.components.topic_details import TopicDetailsPane
from smart_home_observer.gui.main_view_model import MainViewModel


class MainWindow(QMainWindow):
    """Compose and coordinate the observer's three-pane workspace."""

    def __init__(
        self,
        view_model: MainViewModel,
        settings: QSettings | None = None,
    ) -> None:
        super().__init__()
        self._view_model = view_model
        self._settings = settings or QSettings()
        self.setWindowTitle(view_model.title)
        self.setObjectName("mainWindow")

        self._create_workspace()
        self._create_actions()
        self._create_menu_bar()
        self._create_log_dock()
        self._connect_view_model()
        self._restore_state()
        self._render_all()

    def _create_workspace(self) -> None:
        self._observer_tree = ObserverTreePane()
        self._topic_details = TopicDetailsPane()
        self._subscription_settings = SubscriptionSettingsPane()
        self._observer_tree.topic_selected.connect(self._view_model.select_topic)
        self._observer_tree.add_filter_requested.connect(
            self._show_add_filter_dialog
        )
        self._observer_tree.remove_filter_requested.connect(
            self._remove_subscription
        )
        self._observer_tree.broker_profile_selected.connect(
            self._confirm_broker_profile_switch
        )
        self._observer_tree.add_broker_profile_requested.connect(
            self._show_create_broker_profile_dialog
        )
        self._observer_tree.edit_broker_profile_requested.connect(
            self._show_broker_settings_dialog
        )
        self._observer_tree.delete_broker_profile_requested.connect(
            self._confirm_delete_broker_profile
        )
        self._subscription_settings.apply_requested.connect(
            self._apply_subscription
        )

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setObjectName("workspaceSplitter")
        self._splitter.setChildrenCollapsible(False)
        self._splitter.addWidget(self._observer_tree)
        self._splitter.addWidget(self._topic_details)
        self._splitter.addWidget(self._subscription_settings)
        self._splitter.setStretchFactor(0, 4)
        self._splitter.setStretchFactor(1, 4)
        self._splitter.setStretchFactor(2, 2)
        self.setCentralWidget(self._splitter)
        self.resize(1220, 760)
        self._splitter.setSizes([420, 430, 270])

    def _create_actions(self) -> None:
        self._connection_controls = ConnectionControls(self)
        self._connection_controls.connect_requested.connect(
            lambda: self._run_async(self._view_model.connect_to_broker())
        )
        self._connection_controls.reconnect_requested.connect(
            lambda: self._run_async(self._view_model.reconnect_to_broker())
        )
        self._connection_controls.disconnect_requested.connect(
            lambda: self._run_async(self._view_model.disconnect_from_broker())
        )
        self._broker_settings_action = QAction("Edit broker profile...", self)
        self._broker_settings_action.setObjectName("brokerSettingsAction")
        self._broker_settings_action.setToolTip("Edit the active broker profile")
        self._broker_settings_action.triggered.connect(
            self._show_broker_settings_dialog
        )
        self._add_broker_profile_action = QAction("Add broker profile...", self)
        self._add_broker_profile_action.setObjectName("addBrokerProfileAction")
        self._add_broker_profile_action.triggered.connect(
            self._show_create_broker_profile_dialog
        )
        self._delete_broker_profile_action = QAction(
            "Delete broker profile...",
            self,
        )
        self._delete_broker_profile_action.setObjectName(
            "deleteBrokerProfileAction"
        )
        self._delete_broker_profile_action.triggered.connect(
            self._confirm_delete_broker_profile
        )

        self._add_filter_action = QAction("Add filter", self)
        self._add_filter_action.setToolTip("Add an MQTT subscription filter")
        self._add_filter_action.triggered.connect(self._show_add_filter_dialog)

        self._expand_action = QAction("Expand all", self)
        self._expand_action.triggered.connect(self._observer_tree.expand_all)
        self._collapse_action = QAction("Collapse all", self)
        self._collapse_action.triggered.connect(self._observer_tree.collapse_all)

        self._console_action = QAction("Log console", self)
        self._console_action.setCheckable(True)

        self._quit_action = QAction("Quit", self)
        self._quit_action.setShortcut("Ctrl+Q")
        self._quit_action.triggered.connect(
            lambda: QApplication.instance() and QApplication.instance().quit()
        )

        self._about_action = QAction("About Smart Home Observer", self)
        self._about_action.triggered.connect(
            lambda: QMessageBox.about(
                self,
                "About Smart Home Observer",
                "Smart Home Observer\n\n"
                "Browse live MQTT topics and manage subscriptions.",
            )
        )

    def _create_menu_bar(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self._add_filter_action)
        file_menu.addSeparator()
        file_menu.addAction(self._quit_action)

        connection_menu = self.menuBar().addMenu("&Connection")
        connection_menu.addActions(self._connection_controls.actions)
        connection_menu.addSeparator()
        connection_menu.addAction(self._add_broker_profile_action)
        connection_menu.addAction(self._broker_settings_action)
        connection_menu.addAction(self._delete_broker_profile_action)

        self._view_menu: QMenu = self.menuBar().addMenu("&View")
        self._view_menu.addAction(self._expand_action)
        self._view_menu.addAction(self._collapse_action)

        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(self._about_action)

        self.menuBar().setCornerWidget(
            self._connection_controls.status_label,
            Qt.Corner.TopRightCorner,
        )

    def _create_log_dock(self) -> None:
        self._log_dock = LogConsoleDock(self)
        self.addDockWidget(
            Qt.DockWidgetArea.BottomDockWidgetArea,
            self._log_dock,
        )
        self._console_action.setChecked(self._log_dock.isVisible())
        self._console_action.toggled.connect(self._log_dock.setVisible)
        self._log_dock.visibilityChanged.connect(self._console_action.setChecked)
        self._view_menu.addSeparator()
        self._view_menu.addAction(self._console_action)

    def _connect_view_model(self) -> None:
        self._view_model.state_changed.connect(self._render_details)
        self._view_model.topics_changed.connect(self._render_tree)
        self._view_model.subscriptions_changed.connect(self._render_settings)
        self._view_model.connection_changed.connect(self._render_connection)
        self._view_model.configuration_changed.connect(self._render_broker_profiles)
        self._view_model.log_message.connect(self._log_dock.append_message)

    def _render_all(self) -> None:
        self._render_tree()
        self._render_details()
        self._render_settings()
        self._render_connection()
        self._render_broker_profiles()

    def _render_tree(self) -> None:
        self._observer_tree.render(
            self._view_model.topic_paths,
            self._view_model.topic,
            self._view_model.subscriptions,
        )

    def _render_details(self) -> None:
        self._topic_details.render(self._view_model)

    def _render_settings(self) -> None:
        self._subscription_settings.render(
            self._view_model.topic,
            self._view_model.selected_subscription,
        )

    def _render_connection(self) -> None:
        self._connection_controls.render(self._view_model.connection_status)

    def _render_broker_profiles(self) -> None:
        self._observer_tree.render_broker_profiles(
            self._view_model.broker_profiles,
            self._view_model.active_broker_profile.id,
        )
        self._delete_broker_profile_action.setEnabled(
            len(self._view_model.broker_profiles) > 1
        )

    def _apply_subscription(
        self,
        original_filter: str,
        subscription: Subscription,
    ) -> None:
        self._run_async(
            self._view_model.update_subscription(
                original_filter,
                subscription,
            )
        )

    def _show_add_filter_dialog(self) -> None:
        subscription = AddSubscriptionDialog(self).subscription()
        if subscription is not None:
            self._run_async(self._view_model.add_subscription(subscription))

    def _show_broker_settings_dialog(self, profile_id: object = None) -> None:
        selected_profile_id = profile_id if isinstance(profile_id, UUID) else None
        dialog = BrokerSettingsDialog(
            self._view_model,
            self,
            profile_id=selected_profile_id,
        )
        dialog.save_requested.connect(
            lambda: self._save_broker_settings(dialog)
        )
        dialog.apply_requested.connect(
            lambda: self._apply_broker_settings(dialog)
        )
        dialog.open()

    def _show_create_broker_profile_dialog(self) -> None:
        dialog = BrokerSettingsDialog(self._view_model, self, creating=True)
        dialog.apply_requested.connect(
            lambda: self._apply_create_broker_profile(dialog)
        )
        dialog.open()

    def _apply_create_broker_profile(
        self,
        dialog: BrokerSettingsDialog,
    ) -> None:
        try:
            self._view_model.create_broker_profile(
                dialog.profile_name,
                dialog.mqtt_config,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Profile creation failed", str(error))
            return
        dialog.accept()

    def _confirm_broker_profile_switch(self, profile_id: UUID) -> None:
        current_profile = self._view_model.active_broker_profile
        if profile_id == current_profile.id:
            return
        next_profile = next(
            profile
            for profile in self._view_model.broker_profiles
            if profile.id == profile_id
        )
        result = QMessageBox.question(
            self,
            "Switch broker profile?",
            f"Do you want to switch from '{current_profile.name}' to "
            f"'{next_profile.name}'?\n\n"
            "This requires shutting down the current MQTT connection before "
            "connecting to the selected broker profile.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result == QMessageBox.StandardButton.Yes:
            self._observer_tree.set_profile_switching(True)
            self._run_async(
                self._switch_broker_profile(profile_id, next_profile.config)
            )

    async def _switch_broker_profile(
        self,
        profile_id: UUID,
        mqtt_config: MqttConfig,
    ) -> None:
        try:
            await self._view_model.activate_broker_profile(profile_id, mqtt_config)
        finally:
            self._observer_tree.set_profile_switching(False)

    def _confirm_delete_broker_profile(self) -> None:
        profile = self._view_model.active_broker_profile
        if len(self._view_model.broker_profiles) == 1:
            return
        result = QMessageBox.question(
            self,
            "Delete broker profile?",
            f"Delete '{profile.name}' and its observer workspace?\n\n"
            "The application will connect to another broker profile first.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result == QMessageBox.StandardButton.Yes:
            self._observer_tree.set_profile_switching(True)
            self._run_async(self._delete_broker_profile(profile.id))

    async def _delete_broker_profile(self, profile_id: UUID) -> None:
        try:
            await self._view_model.delete_broker_profile(profile_id)
        finally:
            self._observer_tree.set_profile_switching(False)

    def _apply_broker_settings(self, dialog: BrokerSettingsDialog) -> None:
        try:
            profile_name = dialog.profile_name
            mqtt_config = dialog.mqtt_config
        except ValueError:
            return
        profile_id = dialog.profile_id
        if profile_id is None:
            return
        dialog.set_applying(True)
        self._run_async(
            self._apply_broker_settings_async(
                dialog,
                profile_id,
                profile_name,
                mqtt_config,
            )
        )

    def _save_broker_settings(self, dialog: BrokerSettingsDialog) -> None:
        try:
            profile_name = dialog.profile_name
            mqtt_config = dialog.mqtt_config
            profile_id = dialog.profile_id
            if profile_id is None:
                return
            self._view_model.save_broker_profile(
                profile_id,
                mqtt_config,
                profile_name,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Broker update failed", str(error))
            return
        dialog.accept()

    async def _apply_broker_settings_async(
        self,
        dialog: BrokerSettingsDialog,
        profile_id: UUID,
        profile_name: str,
        mqtt_config: MqttConfig,
    ) -> None:
        try:
            await self._view_model.activate_broker_profile(
                profile_id,
                mqtt_config,
                profile_name,
            )
        except Exception as error:
            dialog.set_applying(False)
            QMessageBox.warning(self, "Broker update failed", str(error))
            return
        dialog.accept()

    def _remove_subscription(self, subscription: Subscription) -> None:
        self._run_async(self._view_model.remove_subscription(subscription))

    def _run_async(self, operation: Coroutine[Any, Any, None]) -> None:
        task = asyncio.create_task(operation)

        def report_error(completed: asyncio.Task[None]) -> None:
            if completed.cancelled():
                return
            error = completed.exception()
            if error is not None:
                self._log_dock.append_message(f"Error: {error}")
                QMessageBox.warning(self, "Operation failed", str(error))

        task.add_done_callback(report_error)

    def _restore_state(self) -> None:
        splitter_state = self._settings.value("workspace/splitter")
        if isinstance(splitter_state, QByteArray):
            self._splitter.restoreState(splitter_state)
        selected_topic = str(
            self._settings.value(
                "workspace/selectedTopic",
                self._view_model.topic,
            )
            or ""
        )
        if selected_topic:
            self._view_model.select_topic(selected_topic)
        log_visible = self._settings.value(
            "workspace/logVisible",
            False,
            type=bool,
        )
        self._log_dock.setVisible(log_visible)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._settings.setValue(
            "workspace/splitter",
            self._splitter.saveState(),
        )
        self._settings.setValue(
            "workspace/selectedTopic",
            self._view_model.topic,
        )
        self._settings.setValue(
            "workspace/logVisible",
            self._log_dock.isVisible(),
        )
        self._settings.sync()
        super().closeEvent(event)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._topic_details.focus_payload()
