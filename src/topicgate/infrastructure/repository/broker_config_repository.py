from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from topicgate.core.config.mqtt_config import MqttConfig
from topicgate.infrastructure.database.database_context import DatabaseContext
from topicgate.infrastructure.database.mappers.config_mapper import ConfigMapper
from topicgate.infrastructure.database.models.broker_profile_row import BrokerProfileRow
from topicgate.infrastructure.database.models.mqtt_config_row import MqttConfigRow


class BrokerConfigRepository:
    """Persist MQTT connection settings without accessing credentials."""

    def __init__(self, db: DatabaseContext) -> None:
        self._db = db

    def get(self, broker_id: UUID) -> MqttConfig:
        with self._db.session() as session:
            row = session.scalar(
                select(BrokerProfileRow)
                .options(joinedload(BrokerProfileRow.config))
                .where(BrokerProfileRow.id == broker_id)
            )
            if row is None:
                raise KeyError(f"Unknown broker profile: {broker_id}")
            return ConfigMapper.to_mqtt_config(row.config)

    def get_configuration(self, broker_id: UUID) -> MqttConfig:
        return self.get(broker_id)

    def update(self, broker_id: UUID, config: MqttConfig) -> None:
        with self._db.session() as session:
            row = session.scalar(
                select(BrokerProfileRow)
                .options(joinedload(BrokerProfileRow.config))
                .where(BrokerProfileRow.id == broker_id)
            )
            if row is None:
                raise KeyError(f"Unknown broker profile: {broker_id}")
            row.config.host = config.host
            row.config.port = config.port
            row.config.username = config.username
            row.config.use_tls = config.use_tls
            session.commit()

    def update_configuration(self, broker_id: UUID, config: MqttConfig) -> None:
        self.update(broker_id, config)

    def create(self, config: MqttConfig, *, session=None) -> int:
        """Create config data for linking in the profile creation transaction."""
        if session is not None:
            return self._create(config, session)
        with self._db.transaction() as owned_session:
            return self._create(config, owned_session)

    @staticmethod
    def _create(config: MqttConfig, session) -> int:
        row = MqttConfigRow(
            host=config.host,
            port=config.port,
            username=config.username,
            use_tls=config.use_tls,
        )
        session.add(row)
        session.flush()
        return row.id
