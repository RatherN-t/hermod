from collections.abc import Iterator

from sqlalchemy import inspect, literal, text
from sqlmodel import Session, SQLModel, create_engine

from hermod.config import get_settings


def _make_engine(url: str):
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    # Postgres (Supabase). pre_ping drops connections the pooler has closed.
    if url.startswith(("postgres://", "postgresql://")):
        url = "postgresql+psycopg://" + url.split("://", 1)[1]
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)


engine = _make_engine(get_settings().database_url)


def init_db() -> None:
    from hermod.db import models  # noqa: F401  (register tables)

    SQLModel.metadata.create_all(engine)
    add_missing_columns(engine)
    if engine.dialect.name == "postgresql":
        lock_down_supabase_tables(engine)


def add_missing_columns(eng) -> list[str]:
    """`create_all` never alters existing tables, so new model fields would break old
    databases. Add any missing column, backfilling NOT NULL ones from the field default.
    Returns what was added. (Additive only: renames and drops still need a hand migration.)"""
    insp = inspect(eng)
    added = []
    with eng.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name in have:
                    continue
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" ' + \
                    col.type.compile(dialect=eng.dialect)
                default = col.default.arg if col.default is not None and \
                    col.default.is_scalar else None
                if default is not None:
                    lit = literal(default, type_=col.type).compile(
                        dialect=eng.dialect, compile_kwargs={"literal_binds": True})
                    ddl += f" NOT NULL DEFAULT {lit}"
                conn.execute(text(ddl))
                added.append(f"{table.name}.{col.name}")
    return added


def lock_down_supabase_tables(eng) -> None:
    """Supabase serves every table in `public` through its Data API. Enabling RLS with no
    policies blocks that path entirely; Hermod connects as the table owner, which bypasses
    RLS, so the app is unaffected."""
    tables = inspect(eng).get_table_names(schema="public")
    with eng.begin() as conn:
        for t in SQLModel.metadata.tables:
            if t in tables:
                conn.execute(text(f'ALTER TABLE public."{t}" ENABLE ROW LEVEL SECURITY'))


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    with Session(engine) as session:
        yield session


def new_session() -> Session:
    """For code outside request handlers (agent, scheduler)."""
    return Session(engine)
