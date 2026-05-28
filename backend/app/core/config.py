from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "local"
    DATABASE_URL: str = "postgresql+psycopg://copilot:copilot@localhost:5432/copilot"
    TEST_DATABASE_URL: str = "sqlite+pysqlite:///:memory:"
    STORAGE_ROOT: str = "backend/storage"
    LLM_PROVIDER: str = "mock"
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_API_KEY: str | None = None
    LLM_MODEL: str = "gpt-4.1-mini"
    LLM_TIMEOUT_SECONDS: int = 30
    PUBLIC_BASE_URL: str | None = None
    AMAZON_LWA_CLIENT_ID: str | None = None
    AMAZON_LWA_CLIENT_SECRET: str | None = None
    AMAZON_LWA_TOKEN_URL: str = "https://api.amazon.com/auth/o2/token"
    AMAZON_OAUTH_LOGIN_PATH: str = "/api/auth/amazon/login"
    AMAZON_OAUTH_REDIRECT_PATH: str = "/api/auth/amazon/callback"
    AMAZON_OAUTH_STATE_TTL_MINUTES: int = 10
    AMAZON_LWA_TIMEOUT_SECONDS: int = 15
    TOKEN_ENCRYPTION_KEY: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
