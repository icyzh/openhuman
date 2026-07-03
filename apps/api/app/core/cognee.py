"""Cognee bootstrap — must be imported before any module that imports cognee."""

import os


def apply_cognee_config() -> None:
    """Set Cognee env vars from settings BEFORE cognee SDK is imported.

    Cognee reads os.environ at import time. If this isn't called first,
    Cognee initializes with empty/wrong config and won't work.
    """
    from app.core.config import settings

    llm_api_key = settings.cognee_llm_api_key or settings.openai_api_key
    llm_endpoint = settings.cognee_llm_endpoint or settings.openai_base_url
    
    llm_model = settings.cognee_llm_model
    if not settings.cognee_llm_api_key and settings.openai_model:
        # Cognee expects provider prefix in model name: "openai/model_name"
        llm_model = f"openai/{settings.openai_model}"

    embedding_api_key = getattr(settings, "cognee_embedding_api_key", None) or settings.cognee_llm_api_key or settings.openai_api_key
    embedding_endpoint = settings.cognee_embedding_endpoint or settings.openai_base_url
    
    embedding_model = settings.cognee_embedding_model
    if not settings.cognee_embedding_endpoint and settings.openai_model:
        # Use same model for embeddings if compatible, or keep default
        pass

    os.environ.setdefault("LLM_PROVIDER", settings.cognee_llm_provider)
    if llm_endpoint:
        os.environ["LLM_ENDPOINT"] = llm_endpoint
    if llm_api_key:
        os.environ["LLM_API_KEY"] = llm_api_key
    os.environ["LLM_MODEL"] = llm_model

    os.environ.setdefault("EMBEDDING_PROVIDER", settings.cognee_embedding_provider)
    if embedding_endpoint:
        os.environ["EMBEDDING_ENDPOINT"] = embedding_endpoint
    if embedding_api_key:
        os.environ["EMBEDDING_API_KEY"] = embedding_api_key
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

