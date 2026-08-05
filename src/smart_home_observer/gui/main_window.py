import asyncio
from collections.abc import Coroutine
from typing import Any

from PySide6.QtCore import QByteArray, QSettings, Qt
from PySide6.QtGui import QAction, QCloseEvent, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSplitter,
    QToolBar,
)

from smart_home_observer.core.models.subscription import Subscription
from smart_home_observer.gui.components.add_subscription_dialog import AddSubscriptionDialog
from smart_home_observer.gui.components.connection_status import ConnectionStatusLabel
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
        self._create_toolbar()
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
        self._reconnect_action = QAction("Reconnect", self)
        self._reconnect_action.setToolTip("Reconnect to the MQTT broker")
        self._reconnect_action.triggered.connect(
            lambda: self._run_async(self._view_model.reconnect())
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
        connection_menu.addAction(self._reconnect_action)

        self._view_menu: QMenu = self.menuBar().addMenu("&View")
        self._view_menu.addAction(self._expand_action)
        self._view_menu.addAction(self._collapse_action)

        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(self._about_action)

        self._connection_status = ConnectionStatusLabel()
        self.menuBar().setCornerWidget(
            self._connection_status,
            Qt.Corner.TopRightCorner,
        )

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Observer tools", self)
        toolbar.setObjectName("observerToolbar")
        toolbar.setMovable(False)
        toolbar.addAction(self._reconnect_action)
        toolbar.addAction(self._add_filter_action)
        toolbar.addSeparator()
        toolbar.addAction(self._console_action)
        self.addToolBar(toolbar)

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
        self._view_model.log_message.connect(self._log_dock.append_message)

    def _render_all(self) -> None:
        self._render_tree()
        self._render_details()
        self._render_settings()
        self._render_connection()

    def _render_tree(self) -> None:
        self._observer_tree.render(
            self._view_model.topic_paths,
            self._view_model.topic,
        )

    def _render_details(self) -> None:
        self._topic_details.render(self._view_model)

    def _render_settings(self) -> None:
        self._subscription_settings.render(
            self._view_model.topic,
            self._view_model.selected_subscription,
        )

    def _render_connection(self) -> None:
        self._connection_status.render(self._view_model.connection_status)

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
