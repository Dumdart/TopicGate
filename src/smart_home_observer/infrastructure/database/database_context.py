
from contextlib import contextmanager

from collections.abc import Iterator
from smart_home_observer.infrastructure.database.base import Base
import smart_home_observer.infrastructure.database.models  # noqa: F401 
from sqlalchemy.engine.create import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session


class DatabaseContext:
    def __init__(self, url: str):
        self._engine = create_engine(url)

        Base.metadata.create_all(self._engine)

        self._sessions = sessionmaker(
            bind=self._engine,
            expire_on_commit=False
        )

    @contextmanager
    def session(self) -> Iterator[Session]:
        with self._sessions() as session:
            yield session

    def dispose(self) -> None:
        self._engine.dispose()
