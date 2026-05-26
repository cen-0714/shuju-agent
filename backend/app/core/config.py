from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "local"
    DATABASE_URL: str = "postgresql+psycopg://copilot:copilot@localhost:5432/copilot"
    TEST_DATABASE_URL: str = "sqlite+pysqlite:///:memory:"
    STORAGE_ROOT: str = "backend/storage"
    LLM_PROVIDER: str = "mock"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
