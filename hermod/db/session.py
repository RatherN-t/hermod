from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from hermod.config import get_settings

engine = create_engine(get_settings().database_url, connect_args={"check_same_thread": False})


def init_db() -> None:
    from hermod.db import models  # noqa: F401  (register tables)

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


def new_session() -> Session:
    """For code outside request handlers (agent, scheduler). Looks up `engine` at call time
    so tests can swap it."""
    return Session(engine)
