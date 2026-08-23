"""
app/config.py — Application configuration via pydantic-settings.

All settings are read from environment variables (or a .env file via
python-dotenv).  See .env.example for the full list of supported variables
with descriptions.

No AWS-specific configuration is present here.  AWS services are documented
ONLY as future production deployment options in docs/future_aws_deployment.md.
"""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """
    Central configuration for the VITian Chatbot Local POC.

    All fields are read from environment variables.  The field names below
    correspond 1-to-1 with the variable names documented in .env.example.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",          # silently ignore unknown env vars
    )

    # ------------------------------------------------------------------
    # LLM provider
    # ------------------------------------------------------------------

    llm_provider: str = Field(
        default="openai",
        description=(
            "Name of the LLM provider to use.  Supported values in later phases: "
            "'openai', 'anthropic', 'google', 'ollama'.  The provider abstraction "
            "lives in app/llm/provider.py."
        ),
    )

    llm_api_key_env: str = Field(
        default="OPENAI_API_KEY",
        description=(
            "Name of the environment variable that holds the provider's API key.  "
            "The application reads os.environ[llm_api_key_env] at runtime; the key "
            "itself is never stored in this Settings object."
        ),
    )

    llm_model_name: str = Field(
        default="gpt-4o-2024-05-13",
        description=(
            "Fully-qualified model name / version string (e.g. 'gpt-4o-2024-05-13').  "
            "Recorded verbatim in every results CSV row and LLM-call log entry to "
            "ensure reproducibility."
        ),
    )

    llm_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description=(
            "Sampling temperature for evaluation runs.  Keep at 0.0 (or as close to "
            "deterministic as the provider allows) for all experiment runs.  Only "
            "raise for demos or exploratory use."
        ),
    )

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------

    embedding_model_name: str = Field(
        default="all-MiniLM-L6-v2",
        description=(
            "Name of the sentence-transformers model used for local embeddings.  "
            "Downloaded from HuggingFace on first run and cached locally.  "
            "Provider-abstracted in app/llm/embeddings.py so a hosted embedding API "
            "can be swapped in without touching callers."
        ),
    )

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------

    database_url: str = Field(
        default="postgresql://vitian:vitian_pw@localhost:5432/vitian_chatbot",
        description=(
            "SQLAlchemy-compatible PostgreSQL connection URL.  The Docker Compose "
            "default matches the credentials in docker-compose.yml."
        ),
    )

    # ------------------------------------------------------------------
    # ChromaDB (local persistent directory — no separate Chroma server)
    # ------------------------------------------------------------------

    chroma_persist_dir: str = Field(
        default="./chroma_data",
        description=(
            "Path to the local directory where ChromaDB persists its vector store.  "
            "Must be writable by the app process.  No separate Chroma server is "
            "used in this POC."
        ),
    )

    # ------------------------------------------------------------------
    # RAG / chunking
    # ------------------------------------------------------------------

    chunking_strategy: str = Field(
        default="fixed_size",
        description=(
            "Chunking strategy used by the ingestion pipeline.  "
            "Supported values: 'fixed_size', 'semantic'.  "
            "Both strategies are implemented in app/rag/chunking.py and compared "
            "in Experiment 4."
        ),
    )

    chunk_size: int = Field(
        default=512,
        gt=0,
        description="Token/character size for fixed-size chunking.",
    )

    chunk_overlap: int = Field(
        default=64,
        ge=0,
        description="Overlap in tokens/characters between consecutive fixed-size chunks.",
    )

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    log_dir: str = Field(
        default="./logs",
        description=(
            "Directory where rotating log files are written.  Created automatically "
            "on startup if it does not exist."
        ),
    )

    log_level: str = Field(
        default="INFO",
        description="Log level: DEBUG | INFO | WARNING | ERROR.",
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def llm_api_key(self) -> str | None:
        """
        Return the actual API key by reading the env var named in llm_api_key_env.

        Returns None if the variable is not set (useful for testing without a key).
        """
        return os.environ.get(self.llm_api_key_env)


# Module-level singleton — import this instead of instantiating Settings directly.
settings = Settings()
