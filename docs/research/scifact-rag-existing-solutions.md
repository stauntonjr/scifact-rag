# SciFact RAG existing-solution review

- Date inspected: 2026-08-25
- Decision: choose maintained corpus, retrieval, embedding, persistence, CLI, and generation
  components for one DGX Spark prototype.
- Stop condition: primary sources establish fitness, license, and the first integration boundary;
  no general RAG-framework survey is needed.

## Constraints and comparison dimensions

The project requires a small public corpus with published retrieval evidence, PostgreSQL/pgvector,
the standard MiniLM paraphrase checkpoint, an NVFP4 generator on one DGX Spark, a Typer CLI, Python
dataclasses, and a visible composition root. Fitness, license, ARM64/DGX operability, replacement
cost, and integration size matter more than feature breadth.

| Component | Primary evidence | License/provenance | Disposition |
|---|---|---|---|
| BEIR SciFact | [BEIR repository](https://github.com/beir-cellar/beir), [dataset registry](https://github.com/beir-cellar/beir/wiki/Datasets-available) | Public BEIR qrels and standard IR metrics | Adopt |
| Original SciFact data | [AllenAI repository](https://github.com/allenai/scifact), [license](https://github.com/allenai/scifact/blob/master/LICENSE.md) | Claims/evidence CC BY 4.0; S2ORC abstracts ODC-By 1.0; code Apache-2.0 | Adopt data contract, not its legacy model stack |
| MiniLM embeddings | [model card](https://huggingface.co/sentence-transformers/paraphrase-MiniLM-L6-v2) | Apache-2.0; 384 dimensions; maximum sequence length 128 | Adopt with `vector(384)`; accept initial truncation limitation |
| PostgreSQL/pgvector | [canonical repository](https://github.com/pgvector/pgvector) | PostgreSQL license; official `0.8.6-pg17-bookworm` Docker tag | Adopt |
| NVIDIA Qwen NVFP4 | [NVIDIA model card](https://huggingface.co/nvidia/Qwen3.6-35B-A3B-NVFP4) | Apache-2.0; vLLM; single-DGX-Spark command; about 3.06x reduced model memory | Adopt as external OpenAI-compatible generator |
| Typer | [official documentation](https://typer.tiangolo.com/) | Maintained CLI library | Adopt for the first interface |
| SQLAlchemy Core | [official Core documentation](https://docs.sqlalchemy.org/20/core/) | Maintained persistence toolkit | Adopt only inside the PostgreSQL adapter |

## Findings

- BEIR SciFact is small enough for one-machine iteration and has public document-level qrels. The
  original SciFact test labels for claim verification are hidden, so this prototype uses BEIR
  retrieval evaluation and does not claim reproduction of the original full-pipeline test score.
- SciFact's original license distinguishes claims/evidence annotations from S2ORC abstracts; those
  attributions must remain visible in data documentation.
- MiniLM produces 384-dimensional vectors and truncates at 128 tokens. The initial prototype embeds
  title plus abstract as one document. Sentence-aware chunking is a revisit condition if retrieval
  error analysis shows truncation is material.
- The NVIDIA checkpoint is suitable for RAG and supplies a one-Spark vLLM recipe. It remains an
  external service so this application does not duplicate GPU lifecycle management.
- SQLModel was not selected. Dataclasses keep domain and application contracts framework-neutral;
  SQLAlchemy Core is confined to the storage adapter.

## Build, adopt, adapt, defer

- Build: only the small domain-specific application services, result contracts, grounding guard,
  and BEIR-format adapter.
- Adopt: Typer, SQLAlchemy Core, psycopg, pgvector, sentence-transformers, PostgreSQL, and the
  OpenAI-compatible chat-completions boundary.
- Adapt: Procurement Intelligence Lab's explicit composition-root architecture and BEIR's data and
  metric conventions.
- Defer: LangChain/LlamaIndex, SQLModel, HTTP/MCP/web adapters, agent tool-calling, durable memory,
  and a bespoke agent-effectiveness evaluation framework.

## Verification and reopen conditions

Verify the package and CLI locally, PostgreSQL through Compose, 5,183-document ingestion, public
qrels metrics, and one live cited answer. Reopen the decision if MiniLM truncation dominates errors,
the NVFP4 endpoint cannot produce grounded cited text, the published pgvector image is unavailable
on ARM64, or another interface is backed by a concrete consumer.
