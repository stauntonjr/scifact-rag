# SciFact RAG

A small, inspectable retrieval-augmented generation prototype over the public SciFact benchmark.
It uses PostgreSQL with pgvector for retrieval, `paraphrase-MiniLM-L6-v2` for 384-dimensional
embeddings, and `nvidia/Qwen3.6-35B-A3B-NVFP4` through an OpenAI-compatible endpoint hosted on one
DGX Spark.

Retrieval uses overlapping 126-token MiniLM windows with 32 tokens of overlap and aggregates the
best window score back to one document result. This preserves document IDs for citations while
allowing evidence beyond MiniLM's first 128 input tokens to affect ranking.

The product boundary is CLI-first. Domain and application contracts are Python dataclasses; one
visible composition root wires replaceable corpus, embedding, storage, and generation adapters.
HTTP, MCP, web UI, model tool-calling, and Pi effectiveness evaluation are intentionally inactive.

## Run with Docker Compose

The generator is external to this Compose project. It must be reachable from the host at
`http://127.0.0.1:8000/v1` or through `GENERATOR_BASE_URL`. The RAG project never stops, replaces,
or starts that GPU workload.

```bash
docker compose up -d postgres
docker compose build app
docker compose run --rm app download
docker compose run --rm app ingest
docker compose run --rm app search "What evidence links immune signaling to disease?"
docker compose run --rm app ask "What evidence links immune signaling to disease?"
docker compose run --rm app evaluate --cutoff 10
```

On this DGX, another SparkRun model may already occupy the endpoint and GPU memory. Stop or replace
that workload deliberately before starting the selected model; do not launch both blindly. The
verified TP1 command for SparkRun 0.2.40 is:

```bash
sparkrun run @eugr/qwen3.6-35b-a3b-nvfp4-no-mtp \
  --hosts 127.0.0.1 --tp 1 --port 8000 \
  --served-model-name nvidia/Qwen3.6-35B-A3B-NVFP4 \
  --max-model-len 32768 --no-follow
```

The corresponding MTP recipe currently emits malformed doubled braces around its speculative
decoding JSON. The no-MTP recipe serves the same checkpoint; speculative decoding is not required
by this application.

## Result contracts

- `search` emits ranked documents with `doc_id`, title, text, and cosine-derived score.
- `ask` accepts only citations matching retrieved document IDs. Missing or invalid citations are
  converted to `insufficient evidence` rather than returned as an ungrounded answer.
- `evaluate` reports mean nDCG, MAP, recall, precision, and reciprocal rank at the selected cutoff
  over the public BEIR SciFact qrels.

The current 300-query result at cutoff 10 is nDCG 0.601929, MAP 0.556945, recall 0.727944,
precision 0.081000, and MRR 0.568218. The original one-vector baseline was nDCG 0.526066 and recall
0.661722.

## Development checks

```bash
uv sync --locked
make smoke
docker compose up -d postgres
DATABASE_URL=postgresql+psycopg://scifact:scifact-local@127.0.0.1:5432/scifact \
  uv run pytest -m integration
```

## Data and model provenance

- SciFact claims/evidence annotations: CC BY 4.0.
- SciFact/S2ORC abstracts: ODC-By 1.0.
- MiniLM and the selected NVIDIA Qwen NVFP4 checkpoint: Apache-2.0.
- Application code is licensed under MIT. Dataset, model, and pgvector artifacts retain the
  separate licenses listed above.

See [the architecture ADR](docs/adr/0013-scifact-rag-composition-and-runtime.md) and
[the dependency and license review](docs/research/scifact-rag-existing-solutions.md).
