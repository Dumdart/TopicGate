from pathlib import Path

from PySide6.QtCore import QSettings

from topicgate.gui.settings_migration import (
    MIGRATION_MARKER,
    migrate_legacy_settings,
)


def ini_settings(path: Path) -> QSettings:
    return QSettings(str(path), QSettings.Format.IniFormat)


def test_legacy_qt_preferences_are_copied_once(tmp_path: Path) -> None:
    legacy = ini_settings(tmp_path / "legacy.ini")
    legacy.setValue("workspace/splitter", b"splitter-state")
    legacy.setValue("workspace/selectedTopic", "home/status")
    legacy.setValue("workspace/logVisible", True)
    legacy.sync()
    settings = ini_settings(tmp_path / "topicgate.ini")

    migrate_legacy_settings(settings, legacy)

    assert settings.value("workspace/splitter") == b"splitter-state"
    assert settings.value("workspace/selectedTopic") == "home/status"
    assert settings.value("workspace/logVisible", type=bool)
    assert settings.value(MIGRATION_MARKER, type=bool)

    legacy.setValue("workspace/selectedTopic", "changed/topic")
    migrate_legacy_settings(settings, legacy)
    assert settings.value("workspace/selectedTopic") == "home/status"


def test_existing_topicgate_preferences_are_not_overwritten(tmp_path: Path) -> None:
    legacy = ini_settings(tmp_path / "legacy.ini")
    legacy.setValue("workspace/selectedTopic", "legacy/topic")
    settings = ini_settings(tmp_path / "topicgate.ini")
    settings.setValue("workspace/selectedTopic", "new/topic")

    migrate_legacy_settings(settings, legacy)

    assert settings.value("workspace/selectedTopic") == "new/topic"
    assert settings.value(MIGRATION_MARKER, type=bool)
