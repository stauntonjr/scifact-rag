from __future__ import annotations

import os
from dataclasses import dataclass

from .adapters.minilm import MiniLmEmbedder
from .adapters.openai_compatible import OpenAiCompatibleGenerator
from .adapters.postgres import PostgresEvidenceStore
from .application import RagApplication


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    embedding_model: str
    generator_base_url: str
    generator_model: str
    generator_api_key: str | None

    @classmethod
    def from_environment(cls) -> Settings:
        return cls(
            database_url=os.getenv(
                "DATABASE_URL",
                "postgresql+psycopg://scifact:scifact@postgres:5432/scifact",
            ),
            embedding_model=os.getenv(
                "EMBEDDING_MODEL",
                "sentence-transformers/paraphrase-MiniLM-L6-v2",
            ),
            generator_base_url=os.getenv(
                "GENERATOR_BASE_URL", "http://host.docker.internal:8000/v1"
            ),
            generator_model=os.getenv("GENERATOR_MODEL", "nvidia/Qwen3.6-35B-A3B-NVFP4"),
            generator_api_key=os.getenv("GENERATOR_API_KEY"),
        )


def build_application(settings: Settings | None = None) -> RagApplication:
    resolved = settings or Settings.from_environment()
    return RagApplication(
        store=PostgresEvidenceStore(resolved.database_url),
        embedder=MiniLmEmbedder(resolved.embedding_model),
        generator=OpenAiCompatibleGenerator(
            base_url=resolved.generator_base_url,
            model=resolved.generator_model,
            api_key=resolved.generator_api_key,
        ),
    )
