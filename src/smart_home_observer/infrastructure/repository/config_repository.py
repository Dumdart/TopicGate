from sqlalchemy import select
from sqlalchemy.orm import joinedload

from smart_home_observer.core.config.config_loader import AppConfig
from smart_home_observer.infrastructure.database.database_context import DatabaseContext
from smart_home_observer.infrastructure.database.mappers.config_mapper import (
    ConfigMapper,
)
from smart_home_observer.infrastructure.database.models.app_config_row import (
    AppConfigRow,
)


class ConfigRepository:
    def __init__(self, db: DatabaseContext, app_config: AppConfig | None):
        self._db = db

        self.is_password_set = False
        self.is_updated = False
        self.app_config = self._load_or_seed(app_config)

    def _load_or_seed(self, defaults: AppConfig | None) -> AppConfig | None:
        with self._db.session() as session:
            if not defaults:
                return None

            row = session.scalar(
                select(AppConfigRow)
                .options(joinedload(AppConfigRow.mqtt_config_row))
                .where(AppConfigRow.id == defaults.id)
            )

            if row is None:
                row = self.seed_app_config(defaults)

            return ConfigMapper.to_app_config(row)

    def get_app_config(self, config_id: int) -> AppConfig | None:
        if self.app_config:
            return self.app_config

        with self._db.session() as session:
            row = session.scalar(
                select(AppConfigRow)
                .options(joinedload(AppConfigRow.mqtt_config_row))
                .where(AppConfigRow.id == config_id)
            )
            self.is_updated = True
            return ConfigMapper.to_app_config(row) if row else None

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
                self.app_config = app_config
                self.is_updated = True
            except Exception as e:
                session.rollback()
                self.is_updated = False
                raise Exception(f"Failed to update app config. Conducted Rollback! {e}")

    def seed_app_config(self, app_config: AppConfig) -> AppConfigRow:
        """Seeds the app config into the database and returns the config id."""
        with self._db.session() as session:
            row = ConfigMapper.to_app_config_row(app_config)
            session.add(row)
            session.flush()
            session.commit()
            return row
