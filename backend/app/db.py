"""SQLAlchemy engine and session. Supabase Postgres via DATABASE_URL, otherwise local SQLite."""
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import DATABASE_URL, IS_SQLITE

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    hide_parameters=True,  # database errors are shown to users and logged, and parameters hold bank accounts
    # Detection runs in a background thread, so SQLite must accept cross-thread connections.
    # On Postgres, batching stops a run paying one network round trip per event.
    **({"connect_args": {"check_same_thread": False, "timeout": 30}} if IS_SQLITE else {"executemany_mode": "values_plus_batch"}),
)

if IS_SQLITE:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(conn, _record) -> None:
        # WAL lets the API keep reading while a run writes; foreign_keys is off by default in SQLite.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db


def init_db() -> None:
    from . import models  # noqa: F401  (registers tables on Base.metadata)
    Base.metadata.create_all(engine)
