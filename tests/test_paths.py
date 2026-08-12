import sqlite3
from pathlib import Path

import pytest

from topicgate.core.config.app_config import AppConfig
from topicgate.core.config.mqtt_config import MqttConfig
from topicgate.core.models.subscription import Subscription
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.app.broker_profile_service import BrokerProfileService
from topicgate.paths import (
    DatabaseMigrationError,
    prepare_database_path,
    sqlite_url,
)


def test_fresh_installation_uses_new_database_path(tmp_path: Path) -> None:
    target = prepare_database_path(tmp_path / "data", tmp_path / "missing.db")

    assert target == tmp_path / "data" / "topicgate.db"
    assert not target.exists()


def test_legacy_database_migration_preserves_profiles_and_subscriptions(
    tmp_path: Path,
    credential_store,
) -> None:
    legacy = tmp_path / "smart_observer.db"
    legacy_context = DatabaseContext(sqlite_url(legacy))
    repository = BrokerProfileService(
        legacy_context,
        AppConfig(MqttConfig("default", 1883, "user", "secret")),
        credential_store=credential_store,
    )
    profile = repository.create_profile(
        "Remote",
        MqttConfig("remote", 8883, "observer", "secret", use_tls=True),
    )
    profile.workspace.subscriptions = (Subscription("home/#", qos=2),)
    repository.update_profile(profile)
    repository.activate_profile(profile.id)
    legacy_context.dispose()

    target = prepare_database_path(tmp_path / "data", legacy)
    migrated_context = DatabaseContext(sqlite_url(target))
    migrated = BrokerProfileService(
        migrated_context,
        credential_store=credential_store,
    )

    assert legacy.exists()
    assert migrated.get_profile().id == profile.id
    assert migrated.get_profile().name == "Remote"
    assert migrated.get_profile().workspace.subscriptions == (
        Subscription("home/#", qos=2),
    )
    migrated_context.dispose()


def test_repeated_startup_keeps_migrated_database(tmp_path: Path) -> None:
    legacy = tmp_path / "smart_observer.db"
    legacy.write_bytes(b"legacy replacement must not be attempted")
    target_directory = tmp_path / "data"
    target_directory.mkdir()
    target = target_directory / "topicgate.db"
    with sqlite3.connect(target) as database:
        database.execute("CREATE TABLE marker (value TEXT)")
        database.execute("INSERT INTO marker VALUES ('new')")

    assert prepare_database_path(target_directory, legacy) == target
    assert prepare_database_path(target_directory, legacy) == target
    with sqlite3.connect(target) as database:
        assert database.execute("SELECT value FROM marker").fetchone() == ("new",)


def test_both_database_files_prefer_topicgate_database(tmp_path: Path) -> None:
    legacy = tmp_path / "smart_observer.db"
    legacy.write_bytes(b"not a database")
    target_directory = tmp_path / "data"
    target_directory.mkdir()
    target = target_directory / "topicgate.db"
    with sqlite3.connect(target) as database:
        database.execute("CREATE TABLE marker (value TEXT)")

    assert prepare_database_path(target_directory, legacy) == target


def test_failed_migration_does_not_damage_legacy_database(tmp_path: Path) -> None:
    legacy = tmp_path / "smart_observer.db"
    original = b"not a sqlite database"
    legacy.write_bytes(original)
    target_directory = tmp_path / "data"

    with pytest.raises(DatabaseMigrationError):
        prepare_database_path(target_directory, legacy)

    assert legacy.read_bytes() == original
    assert not (target_directory / "topicgate.db").exists()
    assert not list(target_directory.glob("*.migrating"))
