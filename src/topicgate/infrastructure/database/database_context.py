
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import event
from sqlalchemy.engine.create import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session

from topicgate.infrastructure.database.migrations import upgrade_database


class DatabaseContext:
    def __init__(self, url: str):
        self.url = url
        self._engine = create_engine(
            url,
            connect_args={"timeout": 5.0} if url.startswith("sqlite") else {},
        )
        if self._engine.dialect.name == "sqlite":
            event.listen(self._engine, "connect", self._configure_sqlite_connection)
        upgrade_database(self._engine)

        self._sessions = sessionmaker(
            bind=self._engine,
            expire_on_commit=False
        )

    @contextmanager
    def session(self) -> Iterator[Session]:
        with self._sessions() as session:
            yield session

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        """Share one commit or rollback across cooperating repositories."""
        with self._sessions() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    def dispose(self) -> None:
        self._engine.dispose()

    @staticmethod
    def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA journal_mode=WAL")
        finally:
            cursor.close()
