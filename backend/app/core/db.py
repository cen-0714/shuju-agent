from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings


def create_sync_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args, future=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


settings = Settings()
engine = create_sync_engine(settings.DATABASE_URL)
SessionLocal = create_session_factory(engine)


def get_db_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
