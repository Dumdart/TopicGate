from PySide6.QtCore import QSettings


MIGRATION_MARKER = "migration/legacySettingsComplete"
MIGRATED_KEYS = (
    "workspace/splitter",
    "workspace/selectedTopic",
    "workspace/logVisible",
)


def migrate_legacy_settings(
    settings: QSettings,
    legacy_settings: QSettings | None = None,
) -> None:
    if settings.value(MIGRATION_MARKER, False, type=bool):
        return

    if settings.allKeys():
        settings.setValue(MIGRATION_MARKER, True)
        settings.sync()
        return

    legacy = legacy_settings or QSettings(
        "SmartHomeObserver",
        "Smart Home Observer",
    )
    for key in MIGRATED_KEYS:
        if legacy.contains(key):
            settings.setValue(key, legacy.value(key))
    settings.setValue(MIGRATION_MARKER, True)
    settings.sync()
