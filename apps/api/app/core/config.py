from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "change-me-in-production"

# Resolve .env relative to the project root (apps/api/) regardless of CWD
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
    )

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
    jwt_secret_key: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Encryption for bot tokens (AES-256-GCM, 32-byte key)
    encryption_key: str = ""

    # Cognee (deferred — Phase 5 real implementation)
    cognee_data_dir: str = "./cognee_data"

    # OpenAI (used by LangGraph agent)
    openai_api_key: str = ""
    openai_base_url: str = ""  # empty = use OpenAI default; set for compatible APIs
    openai_model: str = "gpt-4o-mini"

    # Document storage
    upload_dir: str = "./uploads"

    # Bot Gateway
    gateway_enabled: bool = False
    """Whether to start the Discord/Slack bot gateway at application startup.
    Should be ``True`` in production or when bot integrations are needed.
    Defaults to ``False`` for local development safety."""

    # Slack App Token (for socket mode)
    slack_app_token: str = ""

    # Slack OAuth (for "Connect Slack" onboarding flow)
    slack_client_id: str = ""
    slack_client_secret: str = ""
    slack_oauth_redirect_uri: str = ""

    # Frontend URL (used for OAuth redirects back to the dashboard)
    frontend_url: str = "http://localhost:3000"

    # MCP OAuth — per-connector client credentials for the generic MCP OAuth flow.
    # Only connectors that require a registered OAuth app need these (Notion, Vercel,
    # GitHub OAuth mode).  Leave empty for connectors that use PAT / API-key /
    # no-auth modes.
    notion_client_id: str = ""
    notion_client_secret: str = ""
    vercel_client_id: str = ""
    vercel_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""

    # The full redirect URI that OAuth providers send the user back to after consent.
    # Must be registered with each provider's OAuth app config.
    # Example: "https://api.example.com/api/mcp/oauth/callback"
    mcp_oauth_redirect_uri: str = ""

    @property
    def mcp_oauth_credentials(self) -> dict[str, dict[str, str]]:
        """Return ``{slug: {client_id, client_secret}}`` for every OAuth connector
        whose credentials are configured in the environment."""
        creds: dict[str, dict[str, str]] = {}
        if self.notion_client_id:
            creds["notion"] = {
                "client_id": self.notion_client_id,
                "client_secret": self.notion_client_secret,
            }
        if self.vercel_client_id:
            creds["vercel"] = {
                "client_id": self.vercel_client_id,
                "client_secret": self.vercel_client_secret,
            }
        if self.github_client_id:
            creds["github"] = {
                "client_id": self.github_client_id,
                "client_secret": self.github_client_secret,
            }
        return creds

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """Fail fast if production is configured with development-only secrets."""
        if self.environment.lower() in {"production", "prod"}:
            if self.jwt_secret_key == DEFAULT_JWT_SECRET or len(self.jwt_secret_key) < 32:
                raise ValueError(
                    "jwt_secret_key must be set to a non-default value of at least "
                    "32 characters in production"
                )
            if not self.encryption_key or len(self.encryption_key) != 64:
                raise ValueError(
                    "encryption_key must be set to a 32-byte (64 hex character) "
                    "string in production"
                )
        return self


settings = Settings()
