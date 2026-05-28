from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings


def create_sync_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine_kwargs = {}
    if database_url in {"sqlite:///:memory:", "sqlite+pysqlite:///:memory:"}:
        engine_kwargs["poolclass"] = StaticPool
    return create_engine(database_url, connect_args=connect_args, future=True, **engine_kwargs)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


settings = Settings()
engine = create_sync_engine(settings.DATABASE_URL)
SessionLocal = create_session_factory(engine)


def get_db_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
