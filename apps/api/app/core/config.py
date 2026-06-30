from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    environment: str = "development"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/openhuman"
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # Auth
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Encryption for bot tokens (AES-256-GCM, 32-byte key)
    encryption_key: str = ""

    # OpenRouter (for the agent team)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Cognee (for Phase 4 fork)
    cognee_data_dir: str = "./cognee_data"
    llm_provider: str = "openai"
    llm_endpoint: str = "https://openrouter.ai/api/v1"
    llm_api_key: str = ""
    llm_model: str = "openai/gpt-4o-mini"
    embedding_provider: str = "openai"
    embedding_endpoint: str = "https://openrouter.ai/api/v1"
    embedding_model: str = "openai/text-embedding-3-small"
    cognee_skip_connection_test: bool = True


settings = Settings()
