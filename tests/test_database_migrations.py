from sqlalchemy import create_engine, inspect

from topicgate.infrastructure.database.base import Base
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.database.migrations import BASELINE_REVISION
import topicgate.infrastructure.database.models  # noqa: F401


def test_new_database_is_migrated_to_head(tmp_path) -> None:
    database_path = tmp_path / "new.db"

    database = DatabaseContext(f"sqlite:///{database_path.as_posix()}")

    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    assert "mqtt_message" in inspect(engine).get_table_names()
    with engine.connect() as connection:
        revision = connection.exec_driver_sql(
            "SELECT version_num FROM alembic_version"
        ).scalar_one()
    assert revision != BASELINE_REVISION
    database.dispose()
    engine.dispose()


def test_existing_unversioned_database_is_stamped_then_upgraded(tmp_path) -> None:
    database_path = tmp_path / "legacy.db"
    url = f"sqlite:///{database_path.as_posix()}"
    engine = create_engine(url)
    mqtt_message = Base.metadata.tables["mqtt_message"]
    Base.metadata.create_all(
        engine,
        tables=[table for table in Base.metadata.sorted_tables if table is not mqtt_message],
    )
    engine.dispose()

    database = DatabaseContext(url)

    engine = create_engine(url)
    assert "mqtt_message" in inspect(engine).get_table_names()
    with engine.connect() as connection:
        revision = connection.exec_driver_sql(
            "SELECT version_num FROM alembic_version"
        ).scalar_one()
    assert revision != BASELINE_REVISION
    database.dispose()
    engine.dispose()
