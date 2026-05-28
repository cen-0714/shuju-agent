from collections.abc import Generator

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.db import get_db_session


def get_session() -> Generator[Session, None, None]:
    yield from get_db_session()


def get_settings() -> Settings:
    return Settings()
