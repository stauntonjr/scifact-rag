# Cross-encoder reranking solution assessment

- Search date: 2026-08-26
- Decision: adopt a pinned MS MARCO MiniLM checkpoint and adapt it behind the existing retriever port
- Disposition: adapt
- Trigger: the frozen BM25/vector unions improve recall but sometimes displace BM25 successes
- Stop condition: one 300-query SciFact run with one model and no parameter sweep

## Need and constraints

The experiment needs a standard second-stage ranker, not a corpus-wide retrieval replacement. It
must run on one DGX Spark, rank raw SciFact title-plus-abstract documents from the existing
retrieval channels, and add no database schema or Python package dependency. After an in-process
CPU run remained incomplete at 417.39 seconds, the owner required the model to be hosted on the GPU
like the other inference workloads. The public SciFact qrels have already been inspected
repeatedly, so the result is exploratory and cannot support tuning or default promotion.

Primary-source searches covered maintained SentenceTransformers cross-encoder guidance, official
model cards, immutable model revisions, model licenses, checkpoint size, maximum sequence length,
and domain/training provenance. The comparison dimensions were fit to the bounded reranking task,
DGX feasibility, provenance, license, integration size, and risk of adding unrelated capability.

| Candidate | Primary evidence | License and size | Disposition |
|---|---|---|---|
| `cross-encoder/ms-marco-MiniLM-L6-v2` | SentenceTransformers model card; trained for MS MARCO passage ranking; standard query/passage `CrossEncoder.predict` use | Apache-2.0; 90.9 MB safetensors checkpoint | Adopt and adapt |
| `ncbi/MedCPT-Cross-Encoder` | Biomedical PubMed search-log training and 512-token inputs | Public domain; about 438 MB weights | Defer; attractive domain comparator, but not needed for the first standard baseline |
| `BAAI/bge-reranker-v2-m3` | Multilingual reranking model | Apache-2.0; about 2.27 GB | Defer; substantially larger than the selected baseline |
| `Qwen/Qwen3-Reranker-0.6B` | Instruction-aware reranking with long context | Apache-2.0; 0.6B parameters | Defer; adds prompt and instruction choices that widen the experiment |
| Project-trained or graph-aware ranker | No existing project training/evaluation boundary | New training and graph surfaces | Defer explicitly |

Serving options were then compared separately. Hugging Face Text Embeddings Inference (TEI) has a
native `/rerank` endpoint, publishes an ARM64 CUDA image for DGX Spark compute capability 12.1, and
uses token-aware dynamic batching. A disposable live probe proved that the selected BERT
sequence-classification model loads as `FlashBert` on CUDA and serves its fixed 512-token boundary.
A bespoke FastAPI/SentenceTransformers server was rejected because TEI already owns this standard
serving capability. vLLM was rejected because this is a sequence-classification cross-encoder, not
a generative model.

## Adaptation boundary

Compose pins the DGX Spark TEI image to digest
`sha256:c42fb67547f6100002a0ea60e33d2ebbbcddce669314d4459f326f402bc2e84c` and pins
`cross-encoder/ms-marco-MiniLM-L6-v2` to immutable Hugging Face revision
`233902d25c440f23af6f7d6e94d2946bac0bee0a`. Each query retrieves top 50 candidates independently
from BM25, token windows, strict coreference, and nominal coreference. Candidates are deduplicated
by `doc_id`, producing at most 200 raw documents. The application calls TEI with the unchanged
query and raw title plus newline plus abstract; TEI auto-truncates at the model's 512-token boundary
and alone defines the final order. Equal scores break by `doc_id`.

No fusion weights, score calibration, prompts, query rewriting, fine-tuning, candidate-depth sweep,
or model comparison are part of the run. Token windows remain the default. NER, triple extraction,
knowledge-graph construction, graph querying, and graph retrieval are separately deferred.

## Measured result

The durable TEI service was healthy and loaded `FlashBert` on CUDA. Across all 300 public BEIR
SciFact queries at cutoff 10, the one completed GPU run reported nDCG 0.686962, MAP 0.642502,
recall 0.806556, precision 0.090333, and MRR 0.658184 in 87.91 seconds end to end. It leads the
current leaderboard only in MRR. It ranks fourth by nDCG, lowers recall by 0.015333 versus
standalone BM25, and lowers recall by 0.029444 versus the nominal-RRF nDCG leader. This is a useful
standard baseline but not a promotion result.

TEI logs disclose that its Candle backend uses an efficient GeLU-tanh approximation for this
checkpoint rather than Transformers' exact GeLU. The approximation is part of the immutable
serving boundary and may produce subtle score or ordering differences. No alternate backend or
rerun was used.

## Recommendation and reopen triggers

Run the pinned baseline once and retain it as a selectable strategy regardless of outcome. Reopen
model selection only with a separately held-out evaluation boundary or a product requirement that
the standard baseline cannot meet. Reopen graph work only by an owner-approved capability decision
with explicit entity, relation, provenance, and graph-retrieval contracts.

## Primary sources

- SentenceTransformers cross-encoder reranking guidance:
  <https://www.sbert.net/examples/cross_encoder/applications/README.html>
- TEI reranker API, DGX Spark image, dynamic batching, and Apache-2.0 license:
  <https://github.com/huggingface/text-embeddings-inference>
- Immutable TEI container package:
  <https://github.com/huggingface/text-embeddings-inference/pkgs/container/text-embeddings-inference>
- Selected model card and license:
  <https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2>
- Immutable selected model tree:
  <https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2/tree/233902d25c440f23af6f7d6e94d2946bac0bee0a>
- MedCPT model card: <https://huggingface.co/ncbi/MedCPT-Cross-Encoder>
- BGE reranker model card: <https://huggingface.co/BAAI/bge-reranker-v2-m3>
- Qwen reranker model card: <https://huggingface.co/Qwen/Qwen3-Reranker-0.6B>
