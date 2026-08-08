import logging
import os
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path


LOGGER = logging.getLogger(__name__)
DATABASE_FILENAME = "topicgate.db"
LEGACY_DATABASE_FILENAME = "smart_observer.db"


class DatabaseMigrationError(RuntimeError):
    """Report a failed legacy database migration without altering its source."""


def data_directory() -> Path:
    configured = os.environ.get("TOPICGATE_DATA_DIR")
    if configured:
        return Path(configured).expanduser()

    home = Path.home()
    if sys.platform == "win32":
        local_app_data = Path(
            os.environ.get("LOCALAPPDATA", home / "AppData" / "Local")
        )
        return local_app_data / "Dumdart" / "TopicGate"
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "TopicGate"
    return home / ".local" / "share" / "TopicGate"


def prepare_database_path(
    target_directory: Path | None = None,
    legacy_database: Path | None = None,
) -> Path:
    directory = target_directory or data_directory()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / DATABASE_FILENAME
    if target.exists():
        return target

    legacy = legacy_database or Path.cwd() / LEGACY_DATABASE_FILENAME
    if not legacy.is_file():
        return target

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=directory,
            prefix="topicgate-",
            suffix=".db.migrating",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)

        source_uri = f"file:{legacy.resolve().as_posix()}?mode=ro"
        with (
            closing(sqlite3.connect(source_uri, uri=True)) as source,
            closing(sqlite3.connect(temporary_path)) as destination,
        ):
            with destination:
                source.backup(destination)
                validation = destination.execute("PRAGMA quick_check").fetchone()
                if validation != ("ok",):
                    raise sqlite3.DatabaseError(
                        f"SQLite validation returned {validation!r}"
                    )

        temporary_path.replace(target)
    except Exception as error:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise DatabaseMigrationError(
            f"Could not migrate the legacy database from {legacy}"
        ) from error

    LOGGER.info("Migrated the legacy TopicGate database to %s", target)
    return target


def sqlite_url(database_path: Path) -> str:
    return f"sqlite:///{database_path.resolve().as_posix()}"
