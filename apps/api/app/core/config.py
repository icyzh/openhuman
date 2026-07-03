from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to the project root (apps/api/) regardless of CWD
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        extra="ignore",
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

    # Agent job worker
    agent_worker_concurrency: int = 4
    agent_job_poll_interval_seconds: float = 1.0

    # Postgres checkpointer (Phase 4) — psycopg-style DSN; falls back to deriving
    # from database_url if empty.
    checkpoint_database_url: str = ""

    # Clerk authentication
    clerk_secret_key: str = ""
    clerk_jwt_key: str | None = None
    clerk_authorized_parties: str = "http://localhost:3000"

    @property
    def clerk_authorized_parties_list(self) -> list[str]:
        return [p.strip() for p in self.clerk_authorized_parties.split(",") if p.strip()]

    @model_validator(mode="after")
    def validate_db_urls(self) -> "Settings":
        if self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self

    # Encryption for bot tokens (AES-256-GCM, 32-byte key)
    encryption_key: str = ""

    # Cognee memory (embedded — SQLite + LanceDB + Kuzu)
    cognee_data_dir: str = "./cognee_data"
    cognee_llm_provider: str = "openai"
    cognee_llm_endpoint: str = ""
    cognee_llm_api_key: str = ""
    cognee_llm_model: str = "openai/gpt-4o-mini"
    cognee_embedding_provider: str = "openai"
    cognee_embedding_endpoint: str = ""
    cognee_embedding_api_key: str = ""
    cognee_embedding_model: str = "openai/text-embedding-3-small"
    cognee_skip_connection_test: bool = True

    # OpenAI (used by LangGraph agent)
    openai_api_key: str = ""
    openai_base_url: str = ""  # empty = use OpenAI default; set for compatible APIs
    openai_model: str = "gpt-4o-mini"

    # Document storage
    upload_dir: str = "./uploads"

    # Storage backend: "local" (default) or "s3"
    storage_backend: str = "local"
    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_region: str = "auto"
    s3_bucket_name: str = "openhuman-uploads"
    s3_presigned_url_expiry: int = 3600

    # Bot Gateway
    gateway_enabled: bool = False
    """Whether to start the Discord/Slack bot gateway at application startup.
    Should be ``True`` in production or when bot integrations are needed.
    Defaults to ``False`` for local development safety."""

    # Slack App Token (for socket mode) — used in shared mode only
    slack_app_token: str = ""

    # Slack OAuth (for "Connect Slack" onboarding flow) — used in shared mode only
    slack_client_id: str = ""
    slack_client_secret: str = ""
    slack_oauth_redirect_uri: str = ""

    # Slack per-employee identity (Pattern A)
    slack_identity_mode: str = "shared"
    """Feature flag: 'shared' = one global Slack app (legacy), 'per_employee' = one
    app slot per AI employee (Pattern A)."""

    slack_slot_pool_threshold: int = 5
    """Alert when available slot count drops below this threshold."""

    slack_config_token: str = ""
    """xoxe- config token for Slack manifest API (Phase 2 dynamic provisioning)."""

    slack_config_refresh_token: str = ""
    """Refresh token for rotating the config token (Phase 2)."""

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
            if not self.clerk_secret_key:
                raise ValueError(
                    "clerk_secret_key must be set in production"
                )
            if not self.encryption_key or len(self.encryption_key) != 64:
                raise ValueError(
                    "encryption_key must be set to a 32-byte (64 hex character) "
                    "string in production"
                )
        return self


settings = Settings()
