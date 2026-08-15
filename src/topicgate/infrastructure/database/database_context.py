
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.engine.create import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session

from topicgate.infrastructure.database.migrations import upgrade_database


class DatabaseContext:
    def __init__(self, url: str):
        self._engine = create_engine(url)
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
