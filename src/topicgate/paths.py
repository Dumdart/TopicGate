import os
import sys
from pathlib import Path


DATABASE_FILENAME = "topicgate.db"


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


def prepare_database_path(target_directory: Path | None = None) -> Path:
    directory = target_directory or data_directory()
    directory.mkdir(parents=True, exist_ok=True)
    return directory / DATABASE_FILENAME


def sqlite_url(database_path: Path) -> str:
    return f"sqlite:///{database_path.resolve().as_posix()}"
