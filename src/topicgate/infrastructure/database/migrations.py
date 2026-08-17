from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import Connection, Engine


BASELINE_REVISION = "93fa5748f4b5"
BASELINE_TABLES = {
    "app_config",
    "broker_profile",
    "mqtt_config",
    "observer_workspace",
    "subscription",
    "workspace_subscription",
}


def upgrade_database(engine: Engine) -> None:
    """Upgrade a new or existing TopicGate database to the latest schema."""
    with engine.begin() as connection:
        config = _alembic_config(connection)
        tables = set(inspect(connection).get_table_names())

        # Check databases created before Alembic was introduced. Their existing
        # tables represent the baseline revision and must not be recreated.
        if "alembic_version" not in tables and tables:
            missing_tables = BASELINE_TABLES - tables
            if missing_tables:
                missing = ", ".join(sorted(missing_tables))
                raise RuntimeError(
                    "Cannot migrate unversioned TopicGate database; "
                    f"baseline tables are missing: {missing}"
                )
            command.stamp(config, BASELINE_REVISION)

        command.upgrade(config, "head")


def _alembic_config(connection: Connection) -> Config:
    repository_root = Path(__file__).resolve().parents[4]
    config = Config(repository_root / "alembic.ini")
    config.set_main_option("script_location", str(repository_root / "alembic"))
    config.attributes["connection"] = connection
    return config
