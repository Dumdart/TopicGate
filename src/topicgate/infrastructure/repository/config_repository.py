from sqlalchemy import select
from sqlalchemy.orm import joinedload

from topicgate.core.config.app_config import AppConfig
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.database.mappers.config_mapper import (
    ConfigMapper,
)
from topicgate.infrastructure.database.models.app_config_row import (
    AppConfigRow,
)


class ConfigRepository:
    """Persists application configurations without retaining an in-memory cache."""

    def __init__(
        self,
        db: DatabaseContext,
        app_config: AppConfig | None = None,
    ) -> None:
        self._db = db
        self.is_password_set = False
        self.is_updated = False

        if app_config:
            self.create_app_config(app_config)

    def get_app_config(self, config_id: int) -> AppConfig | None:
        with self._db.session() as session:
            row = session.scalar(
                select(AppConfigRow)
                .options(joinedload(AppConfigRow.mqtt_config_row))
                .where(AppConfigRow.id == config_id)
            )
            self.is_updated = True
            return ConfigMapper.to_app_config(row) if row else None

    def get_all_app_configs(self) -> list[AppConfig]:
        with self._db.session() as session:
            rows = session.scalars(
                select(AppConfigRow)
                .options(joinedload(AppConfigRow.mqtt_config_row))
                .order_by(AppConfigRow.id)
            ).all()
            return [ConfigMapper.to_app_config(row) for row in rows]

    def create_app_config(self, app_config: AppConfig) -> AppConfig:
        with self._db.session() as session:
            row = ConfigMapper.to_app_config_row(app_config)
            session.add(row)
            session.flush()
            created_config = ConfigMapper.to_app_config(row)
            session.commit()
            self.is_updated = True
            return created_config

    def update_app_config(self, app_config: AppConfig) -> None:
        with self._db.session() as session:
            try:
                row = session.scalar(
                    select(AppConfigRow)
                    .options(joinedload(AppConfigRow.mqtt_config_row))
                    .where(AppConfigRow.id == app_config.id)
                )

                if row is None:
                    raise ValueError(f"App config {app_config.id} does not exist.")

                row.mqtt_config_row.host = app_config.mqtt.host
                row.mqtt_config_row.port = app_config.mqtt.port
                row.mqtt_config_row.username = app_config.mqtt.username
                row.mqtt_config_row.use_tls = app_config.mqtt.use_tls
                session.commit()
                self.is_updated = True
            except Exception as e:
                session.rollback()
                self.is_updated = False
                raise Exception(f"Failed to update app config. Conducted Rollback! {e}")

    def seed_app_config(self, app_config: AppConfig) -> AppConfigRow:
        """Create a configuration row for callers that still use the seed API."""
        with self._db.session() as session:
            row = ConfigMapper.to_app_config_row(app_config)
            session.add(row)
            session.flush()
            session.commit()
            return row
