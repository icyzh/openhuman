"""Cognee bootstrap — must be imported before any module that imports cognee."""

import os


def apply_cognee_config() -> None:
    """Set Cognee env vars from settings BEFORE cognee SDK is imported.

    Cognee reads os.environ at import time. If this isn't called first,
    Cognee initializes with empty/wrong config and won't work.
    """
    from app.core.config import settings

    os.environ.setdefault("LLM_PROVIDER", settings.cognee_llm_provider)
    if settings.cognee_llm_endpoint:
        os.environ["LLM_ENDPOINT"] = settings.cognee_llm_endpoint
    if settings.cognee_llm_api_key:
        os.environ["LLM_API_KEY"] = settings.cognee_llm_api_key
    os.environ.setdefault("LLM_MODEL", settings.cognee_llm_model)
    os.environ.setdefault("EMBEDDING_PROVIDER", settings.cognee_embedding_provider)
    if settings.cognee_embedding_endpoint:
        os.environ["EMBEDDING_ENDPOINT"] = settings.cognee_embedding_endpoint
    os.environ.setdefault("EMBEDDING_MODEL", settings.cognee_embedding_model)
    os.environ.setdefault(
        "COGNEE_SKIP_CONNECTION_TEST",
        str(settings.cognee_skip_connection_test).lower(),
    )
    if os.environ.get("VERCEL") == "1":
        os.environ["SYSTEM_ROOT_DIRECTORY"] = "/tmp/cognee_system"
        os.environ["COGNEE_DATA_DIR"] = "/tmp/cognee_data"
    else:
        os.environ.setdefault("COGNEE_DATA_DIR", settings.cognee_data_dir)

