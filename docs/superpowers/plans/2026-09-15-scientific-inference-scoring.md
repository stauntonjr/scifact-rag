# Scientific Inference Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one resumable, provenance-bearing DeBERTa support/contradiction/neutral diagnostic over every document in the existing broad candidate pool without changing retrieval order or generation behavior.

**Architecture:** Reuse the selected six-generator candidate pool, stored 126-token raw DP chunks, and hosted ColBERT scorer. ColBERT orders each candidate's chunks; a deterministic assembler admits complete chunks under the exact 512-token DeBERTa pair budget and restores them to source order. A separate structured inference port calls a dedicated Transformers Compose service, while an append-and-fsync event journal preserves at-most-once attempts and derives all reports.

**Tech Stack:** Python 3.12, frozen dataclasses, Typer, httpx, Hugging Face Transformers, PyTorch/CUDA, PostgreSQL, ColBERT, Docker Compose, pytest

**Spec:** `docs/superpowers/specs/2026-09-15-scientific-inference-scoring-design.md`

## Global Constraints

- A bounded GitHub Issue for Phase 3 must exist and be linked before implementation begins.
- Use `cross-encoder/nli-deberta-v3-large` at revision `bab4bc7178836f731dcfd18c06ca9def0a137712`.
- Treat the model's published SNLI/MultiNLI provenance as a bounded source claim, not an independently audited guarantee.
- Use exactly the existing deterministic 160-claim `train-validation` partition for model-quality evaluation.
- Do not access the public test qrels, train or fine-tune a model, compare checkpoints, tune thresholds, calibrate scores, or sweep weights.
- Use `coref-nominal-dp-minilm` evidence chunks and an exact 512-token premise/hypothesis budget; never truncate a chunk or pair.
- Score every document in the broad candidate pool, not only the top ten.
- Keep inference results parallel to `CandidateScore`; do not add inference to scalar ranking or generation in this phase.
- Write and `fsync` an attempt-start event before the one allowed HTTP request. Never retry or resubmit an unmatched attempt under the same run ID.
- A new run ID is required after an interrupted, failed, or otherwise completed attempt.
- Regular CI must use fakes and must not download a model, require a GPU, or call PostgreSQL, ColBERT, or DeBERTa.
- The internal classifier service is not a public application HTTP API and does not activate `http-api-interface`.
- Capability disposition: `application-composition-root`, `cli-interface`, and `product-validation-challenges` are `use-active`; `semantic-evidence-ledger` and all other inactive capabilities are `not-applicable`.
- Solution assessment: adopt the pinned DeBERTa checkpoint; adapt the existing composition, DP, ColBERT, candidate-pool, and evaluation patterns; build only the structured inference boundary and diagnostic runner; defer fusion, graph, training, and additional models.
- The operator controls GPU service lifecycle and may free DGX memory; the application must not stop or reconfigure another model service.
- Keep the test surface focused on result-invalidating boundaries; do not construct a combinatorial suite.
- Push every implementation commit after its focused checks pass.

---

### Task 1: Establish the governed Phase 3 work item and decision record

**Files:**
- Create: `docs/adr/0030-scientific-inference-scoring.md`
- Modify: `harness/project.yaml`

**Interfaces:**
- Consumes: the owner-approved design spec and the repository's GitHub planning contract
- Produces: one bounded Phase 3 Issue URL and accepted ADR-0030 governing all later tasks

- [ ] **Step 1: Inspect planning state before any network write**

Run: `gh issue list --repo stauntonjr/scifact-rag --state all --limit 100`

Expected: no existing Issue already owns the complete Phase 3 scientific-inference slice. If one exists, reuse it and do not create a duplicate.

- [ ] **Step 2: Create and project-link the bounded Issue with explicit authorization**

Use the title `Phase 3: add scientific inference scoring` and this exact body:

```markdown
## Objective

Implement the owner-approved scientific-inference diagnostic in `docs/superpowers/specs/2026-09-15-scientific-inference-scoring-design.md`.

## Acceptance criteria

- The pinned DeBERTa checkpoint is served through a dedicated Transformers Compose service and passes fixed label, pair-order, revision, token-limit, and finite-logit qualification probes.
- Every document in the existing broad candidate pool receives a successful structured result or an explicit failure record.
- Evidence uses ColBERT-ordered `coref-nominal-dp-minilm` chunks admitted whole under the exact 512-token pair budget and restored to source order.
- Candidate identity exists before evidence assembly; bundle and attempt identity remain separately nullable.
- The journal fsyncs attempt start before one HTTP request and never resubmits unmatched starts in the same run.
- A fixed 160-claim validation report records three-way metrics, evidence coverage, latency, failures, the label-prior control, and unchanged ColBERT ranking metrics.
- No inference feature changes retrieval or generation, no public test data is accessed, and no model or fusion parameter is tuned.
- Regular CI remains model-, GPU-, database-, and service-free.

## Exclusions

Fusion, default promotion, graph scoring, scientific-domain training, calibration, additional NLI checkpoints, and public API/MCP/web work.
```

After creation, add the returned Issue URL to the configured GitHub Project with:

`python3 tools/github_planning.py add-item --url ISSUE_URL --yes`

Replace `ISSUE_URL` with the exact URL returned by GitHub. Re-read the Issue and Project membership before proceeding.

- [ ] **Step 3: Start the engineering-loop evidence boundary before repository edits**

Resolve the Issue number from the exact URL created or reused in Step 2, then run:

```bash
phase3_issue="$(gh issue view ISSUE_URL --json number --jq .number)"
python3 tools/loop.py start \
  --issue "$phase3_issue" \
  --objective "Add one fixed, provenance-bearing scientific inference diagnostic over every document in the existing broad candidate pool." \
  --criterion "AC1=Pinned DeBERTa service passes fixed label, pair-order, token-count, revision, limit, and finite-logit qualification probes." \
  --criterion "AC2=Every pooled candidate has a valid terminal result or explicit failure, and unmatched starts are never resubmitted in the same run." \
  --criterion "AC3=The 160-claim validation report is derived from canonical raw records and includes stance, evidence, ranking-control, coverage, latency, and failure evidence." \
  --criterion "AC4=Existing retrieval and generation defaults and outputs remain unchanged." \
  --criterion "AC5=Regular CI performs no database, ColBERT, DeBERTa, GPU, or network work." \
  --in-scope "Structured inference contracts, bounded evidence assembly, one-attempt client, dedicated Compose service, journal, evaluator, CLI, focused tests, qualification, and one fixed validation run." \
  --out-of-scope "Fusion, default promotion, graph scoring, model training, calibration, additional checkpoints, public test access, HTTP application API, MCP, and web UI." \
  --assurance-boundary "One DGX Spark; published model provenance; at-most-once client attempts; no exactly-once server guarantee; internal validation evidence only." \
  --budget-constraint "One pretrained 0.4B classifier, existing ColBERT service, one request per candidate, focused result-invalidating tests, and no parameter sweep." \
  --scope-revision-trigger "Model provenance conflict, tokenizer mismatch, unsupported checkpoint runtime, candidate-pool drift, need for another model, or any requested ranking/default change." \
  --write-path docs/adr/0030-scientific-inference-scoring.md \
  --write-path harness/project.yaml \
  --write-prefix src/scifact_rag \
  --write-prefix tests \
  --write-path Dockerfile.scientific-inference \
  --write-path compose.yaml \
  --write-path .env.example \
  --write-path docs/project/technical-reference.md \
  --write-path docs/project/handoff.md \
  --write-path docs/project/roadmap.md \
  --write-path docs/reports/scifact-retrieval-leaderboard.md \
  --write-path docs/reports/phase-3-scientific-inference-validation.md \
  --write-path README.md \
  --implementer codex/root
```

Replace `ISSUE_URL` with the exact URL from Step 2. Record the initial solution assessment as
`adapt`, research complete, citing the pinned DeBERTa model card, the rejected ModernBERT pinned
configuration, and the existing NVIDIA image digest. The rationale must name the three active
capabilities and state that all inactive capabilities are not applicable.

- [ ] **Step 4: Write ADR-0030 using the actual Issue URL**

Record:

- status `accepted` and the human owner as decider;
- the pinned DeBERTa model and published SNLI/MultiNLI provenance;
- rejection of the SciFact-exposed tasksource ModernBERT and inherited ModernCE checkpoints;
- the 512-token selective-bundle approach over 126-token DP chunks;
- the dedicated Transformers service using the existing digest-pinned NVIDIA image as a PyTorch/CUDA base;
- the diagnostic-only boundary, at-most-once journal, consequences, qualification evidence, and revisit triggers;
- the exact Issue URL from Step 2 as the governing Issue.

- [ ] **Step 5: Add the model and service license boundary**

Add this entry to `constraints.licenses` in `harness/project.yaml`:

```json
"DeBERTa v3 large NLI checkpoint: Apache-2.0; published training sources are SNLI and MultiNLI"
```

- [ ] **Step 6: Run the focused governance check**

Run: `python3 tools/harness_check.py`

Expected: PASS with ADR numbering, project contract, and planning topology valid.

- [ ] **Step 7: Commit and push**

```bash
git add docs/adr/0030-scientific-inference-scoring.md harness/project.yaml
git commit -m "docs: govern scientific inference scoring"
git push origin main
```

### Task 2: Add model-neutral inference and identity contracts

**Files:**
- Create: `src/scifact_rag/scientific_inference.py`
- Modify: `src/scifact_rag/ports.py`
- Create: `tests/test_scientific_inference.py`

**Interfaces:**
- Consumes: `EvidenceDocument`, `EvidenceChunk`, `SearchHit`, `StoredChunkSource`, and `Reranker`
- Produces: `ScientificInferenceLabel`, `InferenceLogits`, `InferenceRequest`, `InferenceResponse`, `candidate_identity()`, `bundle_identity()`, `request_identity()`, `PairTokenBudget`, and `ScientificInferenceClient`

- [ ] **Step 1: Write failing identity and logits tests**

```python
def test_candidate_identity_precedes_bundle_and_binds_document_content() -> None:
    document = EvidenceDocument("10", "Title", "Abstract")
    identity = candidate_identity("run-1", "7", "A claim", document)

    assert identity == candidate_identity("run-1", "7", "A claim", document)
    assert identity != candidate_identity(
        "run-1", "7", "A claim", EvidenceDocument("10", "Title", "Changed")
    )
    assert len(identity) == 64


def test_logits_are_labeled_finite_and_use_a_fixed_tie_rule() -> None:
    logits = InferenceLogits(entailment=1.0, contradiction=1.0, neutral=0.0)

    assert logits.predicted_label is ScientificInferenceLabel.ENTAILMENT
    assert logits.evidence_margin == pytest.approx(1.0 + math.log(2.0))
    assert logits.polarity_margin == 0.0

    with pytest.raises(ValueError, match="finite"):
        InferenceLogits(float("nan"), 0.0, 0.0)
```

- [ ] **Step 2: Run the focused tests and confirm the missing-contract failure**

Run: `uv run pytest tests/test_scientific_inference.py -q`

Expected: FAIL because `scifact_rag.scientific_inference` does not exist.

- [ ] **Step 3: Implement canonical labels, logits, requests, responses, and digests**

Use canonical JSON with `sort_keys=True` and `separators=(",", ":")`, SHA-256 over UTF-8 bytes, and this deterministic prediction order for equal maxima:

```python
class ScientificInferenceLabel(StrEnum):
    ENTAILMENT = "entailment"
    CONTRADICTION = "contradiction"
    NEUTRAL = "neutral"


@dataclass(frozen=True, slots=True)
class InferenceLogits:
    entailment: float
    contradiction: float
    neutral: float

    @property
    def predicted_label(self) -> ScientificInferenceLabel:
        ordered = (
            (ScientificInferenceLabel.ENTAILMENT, self.entailment),
            (ScientificInferenceLabel.CONTRADICTION, self.contradiction),
            (ScientificInferenceLabel.NEUTRAL, self.neutral),
        )
        return max(ordered, key=lambda item: item[1])[0]

    @property
    def evidence_margin(self) -> float:
        largest = max(self.entailment, self.contradiction)
        return largest + math.log(
            math.exp(self.entailment - largest) + math.exp(self.contradiction - largest)
        ) - self.neutral

    @property
    def polarity_margin(self) -> float:
        return self.entailment - self.contradiction
```

`InferenceRequest` contains `attempt_id`, `premise`, `hypothesis`, and `expected_pair_tokens`.
`InferenceResponse` contains `attempt_id`, `model_revision`, `pair_token_count`, and
`InferenceLogits`. Validate non-empty text, 64-character lowercase hexadecimal identifiers,
positive pair counts, and finite values in `__post_init__`. The client later requires the service's
observed pair count to equal the assembler's expected count.

`candidate_identity()` hashes `run_id`, `query_id`, `document_id`, `claim_sha256`, and a title/content digest. `bundle_identity()` hashes the canonical serialized bundle. `request_identity()` hashes `candidate_id`, `bundle_digest`, the canonical HTTP payload digest, and attempt ordinal `1`.

- [ ] **Step 4: Add the two narrow ports**

```python
class PairTokenBudget(Protocol):
    @property
    def maximum_pair_tokens(self) -> int: ...

    def pair_token_count(self, premise: str, hypothesis: str) -> int: ...


class ScientificInferenceClient(Protocol):
    def classify(self, request: InferenceRequest) -> InferenceResponse: ...
```

- [ ] **Step 5: Run focused tests**

Run: `uv run pytest tests/test_scientific_inference.py -q`

Expected: PASS.

- [ ] **Step 6: Commit and push**

```bash
git add src/scifact_rag/scientific_inference.py src/scifact_rag/ports.py tests/test_scientific_inference.py
git commit -m "feat: add scientific inference contracts"
git push origin main
```

### Task 3: Assemble complete DP evidence under the exact pair budget

**Files:**
- Modify: `src/scifact_rag/scientific_inference.py`
- Modify: `src/scifact_rag/adapters/tokenization.py`
- Modify: `tests/test_scientific_inference.py`
- Modify: `tests/test_strategies.py`

**Interfaces:**
- Consumes: `PairTokenBudget`, `StoredChunkSource`, `Reranker`, `COREF_NOMINAL_DP_MINILM`
- Produces: `HuggingFacePairTokenBudget`, `EvidenceBundle`, `EvidenceChunkSelection`, `EvidenceChunkRejection`, `EvidenceAssemblyError`, and `ScientificEvidenceAssembler.assemble(claim, document)`

- [ ] **Step 1: Write failing assembly tests**

Cover these exact behaviors in four tests:

```python
def test_assembler_admits_by_relevance_then_serializes_in_source_order() -> None:
    chunks = [chunk(0, "first"), chunk(1, "second"), chunk(2, "third")]
    assembler = ScientificEvidenceAssembler(
        FakeChunkStore(chunks),
        FakeReranker({"first": 0.1, "second": 0.9, "third": 0.8}),
        RejectTextPairBudget("first"),
    )

    bundle = assembler.assemble("claim", EvidenceDocument("10", "Title", "whole"))

    assert [item.ordinal for item in bundle.admitted] == [1, 2]
    assert bundle.premise.index("second") < bundle.premise.index("third")
    assert bundle.rejected == (EvidenceChunkRejection(0, "token_budget"),)


def test_assembler_continues_after_a_large_chunk_does_not_fit() -> None:
    chunks = [chunk(0, "small"), chunk(1, "oversized")]
    assembler = ScientificEvidenceAssembler(
        FakeChunkStore(chunks),
        FakeReranker({"small": 0.8, "oversized": 0.9}),
        RejectTextPairBudget("oversized"),
    )

    bundle = assembler.assemble("claim", EvidenceDocument("10", "Title", "whole"))

    assert [item.ordinal for item in bundle.admitted] == [0]
    assert bundle.rejected == (EvidenceChunkRejection(1, "token_budget"),)


def test_assembler_counts_title_claim_markers_separators_and_special_tokens() -> None:
    budget = RecordingPairBudget(pair_tokens=23)
    bundle = ScientificEvidenceAssembler(
        FakeChunkStore([chunk(0, "evidence")]),
        FakeReranker({"evidence": 1.0}),
        budget,
    ).assemble("raw claim", EvidenceDocument("10", "Document title", "whole"))

    assert budget.calls[-1] == (bundle.premise, "raw claim")
    assert bundle.premise == "[TITLE] Document title\n[EVIDENCE ordinal=0] evidence"
    assert bundle.pair_token_count == 23


@pytest.mark.parametrize(
    "chunks",
    (
        (),
        (EvidenceChunk("11", 0, "foreign", COREF_NOMINAL_DP_MINILM),),
        (chunk(0, "one"), chunk(0, "duplicate")),
        (EvidenceChunk("10", 0, "wrong", "token-window"),),
    ),
)
def test_assembler_rejects_invalid_store_results(chunks) -> None:
    with pytest.raises(EvidenceAssemblyError, match="stored evidence"):
        ScientificEvidenceAssembler(
            FakeChunkStore(chunks), FakeReranker({}), RecordingPairBudget(10)
        ).assemble("claim", EvidenceDocument("10", "Title", "whole"))
```

Define `chunk()` to return a non-embedded `EvidenceChunk` for document `10` and representation
`COREF_NOMINAL_DP_MINILM`. `FakeChunkStore` records requested document IDs and representations;
`FakeReranker` records title-free `SearchHit` inputs and returns the score mapped by chunk text;
`RecordingPairBudget` records each pair and returns its configured count;
`RejectTextPairBudget` returns 513 only when its configured text occurs in the premise and 100
otherwise. These helpers make each admission boundary deterministic without loading a tokenizer.

- [ ] **Step 2: Run the assembly tests and confirm they fail**

Run: `uv run pytest tests/test_scientific_inference.py -q`

Expected: FAIL because the assembler and pair budget do not exist.

- [ ] **Step 3: Add exact pair-token counting**

Implement `HuggingFacePairTokenBudget` beside `HuggingFaceTokenBudget`:

```python
class HuggingFacePairTokenBudget:
    def __init__(self, model_name: str, revision: str, *, maximum_pair_tokens: int = 512):
        from transformers import AutoTokenizer

        self._tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            revision=revision,
            use_fast=True,
        )
        self._maximum_pair_tokens = maximum_pair_tokens

    @property
    def maximum_pair_tokens(self) -> int:
        return self._maximum_pair_tokens

    def pair_token_count(self, premise: str, hypothesis: str) -> int:
        encoded = self._tokenizer(
            premise,
            hypothesis,
            add_special_tokens=True,
            truncation=False,
            verbose=False,
        )
        return len(encoded["input_ids"])
```

- [ ] **Step 4: Implement deterministic serialization and admission**

Use these exact markers:

```python
_TITLE_PREFIX = "[TITLE] "
_CHUNK_PREFIX = "[EVIDENCE ordinal={ordinal}] "
_GAP = "[OMITTED ordinals={start}-{end}]"
```

Load only `coref-nominal-dp-minilm`; validate document ID, representation, non-empty text, and unique ordinal. Score all chunks against the unmodified claim using title-free `SearchHit` values. Sort admission candidates by `(-score, ordinal)`. For each tentative addition, sort admitted chunks by ordinal, insert `_GAP` only between non-contiguous admitted ranges, serialize title once, and count the complete pair. Keep the chunk only if the pair is at most 512 tokens; otherwise retain a `token_budget` rejection and continue. Raise `EvidenceAssemblyError("no_evidence_fit", "no complete evidence chunk fits the pair token budget")` when no complete chunk fits.

- [ ] **Step 5: Run focused and affected chunking tests**

Run: `uv run pytest tests/test_scientific_inference.py tests/test_strategies.py tests/test_generation.py -q`

Expected: PASS, including unchanged DP construction and generation-context behavior.

- [ ] **Step 6: Commit and push**

```bash
git add src/scifact_rag/scientific_inference.py src/scifact_rag/adapters/tokenization.py tests/test_scientific_inference.py tests/test_strategies.py
git commit -m "feat: assemble bounded inference evidence"
git push origin main
```

### Task 4: Add the one-attempt HTTP client

**Files:**
- Create: `src/scifact_rag/adapters/scientific_inference.py`
- Create: `tests/test_scientific_inference_adapter.py`

**Interfaces:**
- Consumes: `InferenceRequest`, `InferenceResponse`, and the internal `/v1/classify` contract
- Produces: `TransformersScientificInferenceClient.classify(request)`

- [ ] **Step 1: Write failing client-contract tests**

```python
def test_client_sends_one_pair_and_preserves_labeled_logits(monkeypatch) -> None:
    calls = []

    def fake_post(url, *, json, timeout):
        calls.append((url, json, timeout))
        return FakeResponse(
            {
                "schema_version": "scientific-inference-response/v1",
                "attempt_id": "a" * 64,
                "model_revision": DEBERTA_REVISION,
                "pair_token_count": 17,
                "logits": {
                    "entailment": 2.0,
                    "contradiction": -1.0,
                    "neutral": 0.5,
                },
            }
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    response = TransformersScientificInferenceClient("http://nli:80", DEBERTA_REVISION).classify(
        InferenceRequest("a" * 64, "premise", "hypothesis", expected_pair_tokens=17)
    )

    assert len(calls) == 1
    assert response.logits.predicted_label is ScientificInferenceLabel.ENTAILMENT
```

Add parameterized failures for an echoed attempt mismatch, revision mismatch, missing/extra labels, non-finite logits, unknown schema, non-object payload, and HTTP error. Assert every case makes exactly one transport call.

- [ ] **Step 2: Run the client tests and confirm they fail**

Run: `uv run pytest tests/test_scientific_inference_adapter.py -q`

Expected: FAIL because the adapter does not exist.

- [ ] **Step 3: Implement the strict adapter**

POST exactly this payload once, with no retry transport:

```json
{
  "schema_version": "scientific-inference-request/v1",
  "attempt_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "premise": "[TITLE] Example\n[EVIDENCE ordinal=0] Example evidence.",
  "hypothesis": "Example claim.",
  "expected_pair_tokens": 17
}
```

Require the response keys and labels shown in Step 1, call `raise_for_status()`, reject non-finite
values, require the returned `pair_token_count` to equal `expected_pair_tokens`, and construct
`InferenceResponse`. Do not catch transport exceptions here; the evaluator owns failure recording.

- [ ] **Step 4: Run focused tests**

Run: `uv run pytest tests/test_scientific_inference_adapter.py -q`

Expected: PASS.

- [ ] **Step 5: Commit and push**

```bash
git add src/scifact_rag/adapters/scientific_inference.py tests/test_scientific_inference_adapter.py
git commit -m "feat: add scientific inference client"
git push origin main
```

### Task 5: Serve the pinned classifier through Docker Compose

**Files:**
- Create: `src/scifact_rag/scientific_inference_service.py`
- Create: `tests/test_scientific_inference_service.py`
- Create: `Dockerfile.scientific-inference`
- Modify: `compose.yaml`
- Modify: `.env.example`

**Interfaces:**
- Consumes: the request schema from Task 4 and the checkpoint's `id2label` configuration
- Produces: `GET /health` and `POST /v1/classify` on the opt-in `scientific-inference` Compose service

- [ ] **Step 1: Write failing pure service-contract tests**

Test the request/response function without importing or downloading Transformers:

```python
def test_classify_payload_preserves_pair_order_and_maps_checkpoint_labels() -> None:
    backend = RecordingBackend(
        id2label={0: "contradiction", 1: "entailment", 2: "neutral"},
        logits=(-2.0, 3.0, 0.5),
        pair_tokens=17,
    )

    response = classify_payload(
        {
            "schema_version": "scientific-inference-request/v1",
            "attempt_id": "a" * 64,
            "premise": "premise",
            "hypothesis": "hypothesis",
            "expected_pair_tokens": 17,
        },
        backend,
        maximum_pair_tokens=512,
    )

    assert backend.pairs == [("premise", "hypothesis")]
    assert response["logits"] == {
        "entailment": 3.0,
        "contradiction": -2.0,
        "neutral": 0.5,
    }
    assert response["pair_token_count"] == 17
```

Also reject an unexpected label map, more than 512 tokens, a computed pair count that differs from
`expected_pair_tokens`, invalid request shape, mismatched configured revision, and non-finite
backend output.

- [ ] **Step 2: Run the service tests and confirm they fail**

Run: `uv run pytest tests/test_scientific_inference_service.py -q`

Expected: FAIL because the service module does not exist.

- [ ] **Step 3: Implement the lazy Transformers backend and narrow HTTP server**

Use `AutoTokenizer.from_pretrained(DEBERTA_MODEL, revision=DEBERTA_REVISION, use_fast=True)` and `AutoModelForSequenceClassification.from_pretrained(DEBERTA_MODEL, revision=DEBERTA_REVISION)`. Validate the exact three-label map at startup. Tokenize as `tokenizer(premise, hypothesis, add_special_tokens=True, truncation=False, return_tensors="pt")`; require the computed pair count to equal the request's expected count, reject over-limit pairs, run `model.eval()` under `torch.inference_mode()` on CUDA, and return raw logits in checkpoint index order to the pure mapping function.

Use the standard-library `HTTPServer` so the application package gains no web-framework dependency. Return JSON with explicit status codes, cap request bodies at 1 MiB, expose health only after the backend loads, and log no premise, hypothesis, or raw request body.

- [ ] **Step 4: Build a dedicated image from the already pinned NVIDIA runtime**

`Dockerfile.scientific-inference` must begin with:

```dockerfile
FROM nvcr.io/nvidia/vllm:26.06-py3@sha256:bebcf9576b1720214319ee5c7ee4f7661954cbbf59ed3fcd188cd79a67f1967e
```

Copy `pyproject.toml`, `README.md`, and `src/`; install the project with `python3 -m pip install --no-deps .`; and set the entrypoint to `python3 -m scifact_rag.scientific_inference_service`. The digest pins the included PyTorch, Transformers, CUDA, and SentencePiece runtime; the live manifest records their observed versions.

- [ ] **Step 5: Add an opt-in Compose service**

Add `scientific-inference` with profile `scientific-inference`, GPU access, loopback port `8085:80`, the shared Hugging Face cache, and these environment defaults:

```yaml
SCIENTIFIC_INFERENCE_MODEL: cross-encoder/nli-deberta-v3-large
SCIENTIFIC_INFERENCE_REVISION: bab4bc7178836f731dcfd18c06ca9def0a137712
SCIENTIFIC_INFERENCE_MAX_TOKENS: "512"
HF_HOME: /data
```

Add `SCIENTIFIC_INFERENCE_BASE_URL=http://scientific-inference:80` to the app service. Do not add a Compose dependency that starts the model implicitly.

- [ ] **Step 6: Run focused tests and static Compose validation**

Run: `uv run pytest tests/test_scientific_inference_service.py -q`

Run: `docker compose config --quiet`

Expected: both PASS without starting or downloading the model.

- [ ] **Step 7: Commit and push**

```bash
git add src/scifact_rag/scientific_inference_service.py tests/test_scientific_inference_service.py Dockerfile.scientific-inference compose.yaml .env.example
git commit -m "feat: serve pinned DeBERTa classifier"
git push origin main
```

### Task 6: Add strict manifests and an append-and-fsync event journal

**Files:**
- Create: `src/scifact_rag/scientific_inference_evaluation.py`
- Create: `tests/test_scientific_inference_evaluation.py`

**Interfaces:**
- Consumes: `ComponentRevision`, `ScientificInferenceLabel`, identity helpers, and canonical evaluation cases
- Produces: `ScientificInferenceRunManifest`, `ScientificInferenceAttemptStarted`, `ScientificInferenceResult`, and `ScientificInferenceJournal.open(path, run_id)`

- [ ] **Step 1: Write failing manifest and event-state tests**

```python
def test_manifest_freezes_the_diagnostic_boundary() -> None:
    manifest = inference_manifest()

    assert manifest.source_split == "train-validation"
    assert manifest.candidate_pool_strategy == DEFAULT_RETRIEVAL_STRATEGY.value
    assert manifest.dp_representation == COREF_NOMINAL_DP_MINILM
    assert manifest.context_limit == 512
    assert manifest.request_attempt_policy == "at-most-once-per-run"
    assert ScientificInferenceRunManifest.from_json(manifest.to_json()) == manifest


def test_journal_accepts_started_then_terminal_but_rejects_impossible_transitions(tmp_path) -> None:
    path = tmp_path / "results.jsonl"
    started = inference_attempt_started_fixture()
    terminal = successful_inference_result_fixture()
    journal = ScientificInferenceJournal.open(path, run_id="run-1")
    journal.append(started)
    journal.append(terminal)

    state = ScientificInferenceJournal.open(path, run_id="run-1").state
    assert state.completed == {"c" * 64}
    assert not state.outcome_unknown

    with pytest.raises(ValueError, match="transition"):
        journal.append(started)
```

Define `inference_attempt_started_fixture()` and `successful_inference_result_fixture()` beside
the manifest fixture using the complete finalized dataclass fields from this task. Both use run
`run-1`, candidate ID `c` repeated 64 times, bundle ID `b` repeated 64 times, attempt ID `a`
repeated 64 times, and request digest `d` repeated 64 times, so their transition is explicit and
reusable across journal tests.

Add tests for a terminal pre-assembly failure with null bundle/attempt IDs, a post-assembly pre-request failure with only a bundle digest, an unmatched start classified as `outcome_unknown`, duplicate/foreign IDs, malformed JSON, unknown fields, and append durability by spying on `os.fsync`.

- [ ] **Step 2: Run the evaluation-contract tests and confirm they fail**

Run: `uv run pytest tests/test_scientific_inference_evaluation.py -q`

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement the frozen run manifest**

The manifest schema is `scientific-inference-run-manifest/v1` and contains:

```python
schema_version: str
run_id: str
repository_commit: str
evaluation_manifest_sha256: str
source_split: str
evidence_class: str
candidate_pool_strategy: str
candidate_limit_per_generator: int
ranking_cutoff: int
dp_representation: str
colbert_model: str
colbert_revision: str
model: str
model_revision: str
tokenizer: str
tokenizer_revision: str
transformers_version: str
container_image: str
endpoint: str
context_limit: int
request_attempt_policy: str
components: tuple[ComponentRevision, ...]
started_at: str
completed_at: str | None
host: str
results_path: str
test_qrels_inspected: bool
```

Reject any boundary other than `train-validation`, `internal-diagnostic`, the current selected retrieval strategy, candidate depth 50, cutoff 10, `coref-nominal-dp-minilm`, the pinned model/revisions, context 512, at-most-once, safe relative `.jsonl` results, and `test_qrels_inspected=True`.

- [ ] **Step 4: Implement strict journal event schemas and state validation**

Use `scientific-inference-attempt-started/v1` and `scientific-inference-result/v1`. A result stores all available identity, query/document content digests, baseline rank, ColBERT score, gold label, admitted/rejected chunk provenance, pair count, logits/margins/prediction, evidence-coverage partition, latency, attempt count, and nullable typed error fields.

Parse every line before returning state. Validate these transitions per candidate:

```text
no event -> terminal pre-request result
no event -> attempt started -> terminal success or request failure
attempt started with no terminal -> outcome_unknown
terminal result -> complete
```

Any other transition is invalid. `ScientificInferenceJournal.open()` reads and validates the
complete file once. Its writer retains the validated per-candidate state in memory, checks each
new transition in constant time, creates parent directories, appends one canonical line, flushes,
calls `os.fsync()`, and only then updates its in-memory state. It must not reparse the growing file
for every candidate.

- [ ] **Step 5: Run focused tests**

Run: `uv run pytest tests/test_scientific_inference_evaluation.py -q`

Expected: PASS.

- [ ] **Step 6: Commit and push**

```bash
git add src/scifact_rag/scientific_inference_evaluation.py tests/test_scientific_inference_evaluation.py
git commit -m "feat: journal scientific inference attempts"
git push origin main
```

### Task 7: Execute every pooled candidate without violating at-most-once semantics

**Files:**
- Modify: `src/scifact_rag/application.py`
- Modify: `src/scifact_rag/ports.py`
- Modify: `src/scifact_rag/scientific_inference.py`
- Modify: `src/scifact_rag/scientific_inference_evaluation.py`
- Modify: `tests/test_application.py`
- Modify: `tests/test_scientific_inference_evaluation.py`

**Interfaces:**
- Consumes: `CandidateDiagnosticRetriever.search_with_candidates()`, `ScientificEvidenceAssembler`, `ScientificInferenceClient`, and the event journal
- Produces: `CandidatePoolSource.retrieve_pool()`, `ScientificInferenceEvaluator.evaluate_candidate()`, and `ScientificInferenceEvaluationExecutor.run()`

- [ ] **Step 1: Write a failing candidate-pool application test**

```python
def test_application_exposes_complete_pooled_candidates_without_changing_search() -> None:
    ranked = [SearchHit("2", "Second", "body", 0.9)]
    candidates = [RetrievalCandidate(EvidenceDocument("1", "First", "body"), ())]
    retriever = RecordingCandidateRetriever(ranked, candidates)
    application = RagApplication(
        store=FakeStore(),
        embedder=None,
        generator=FakeGenerator(),
        strategy=FakeStrategy(),
        retriever=retriever,
    )

    actual_ranked, actual_candidates = application.retrieve_pool("claim", limit=10)

    assert actual_ranked == ranked
    assert actual_candidates == candidates
    assert application.search("claim", limit=10) == ranked
```

Define the four minimal fakes in `tests/test_application.py`; only `RecordingCandidateRetriever`
implements `search_with_candidates`, and its `search` method returns `ranked`. The other fakes use
the established no-I/O helper behavior in that file.

Reject non-pooled retrievers and invalid query/limit values. Add a `CandidatePoolSource` protocol so the evaluator does not depend on `RagApplication` internals.

- [ ] **Step 2: Write failing executor tests for identity and interruption**

```python
def test_executor_persists_start_before_one_request(tmp_path) -> None:
    events = []
    client = RecordingClient(events)
    executor = build_executor_fixture(client=client, event_observer=events.append)

    executor.run(
        run_id="run-1",
        evaluation_set=single_case_fixture(),
        output=tmp_path / "results.jsonl",
    )

    assert events == ["attempt-started", "http-request", "terminal-result"]
    assert client.calls == 1


def test_resume_does_not_resend_an_unmatched_start(tmp_path) -> None:
    output = tmp_path / "results.jsonl"
    ScientificInferenceJournal.open(output, run_id="run-1").append(
        inference_attempt_started_fixture()
    )
    client = RecordingClient([])

    summary = build_executor_fixture(client=client).run(
        run_id="run-1", evaluation_set=single_case_fixture(), output=output
    )

    assert client.calls == 0
    assert summary.outcome_unknown == 1
    assert summary.complete is False
```

Define `single_case_fixture()` with one `train-validation` claim and one gold SUPPORT rationale.
`build_executor_fixture()` supplies a two-document pool, deterministic bundle assembler, and the
same candidate and attempt identifiers used by `inference_attempt_started_fixture()`.
`RecordingClient.classify()` appends `http-request`, returns the pinned revision and fixed finite
logits, and increments `calls`. The journal appender invokes the injected observer after each
durable event so ordering is tested without mocking `fsync`.

Also test a missing chunk failure before an attempt ID exists, request failure after one attempt, successful logits and margins, terminal rows skipped on resume, deterministic candidate order, all pool candidates processed rather than top-ten only, and rejection of journal candidates outside the regenerated deterministic pool.

- [ ] **Step 3: Implement `RagApplication.retrieve_pool()` and its port**

Validate query and limit exactly as `search()` does, require `CandidateDiagnosticRetriever`, and return the retriever's ranked hits plus complete `RetrievalCandidate` sequence unchanged.

- [ ] **Step 4: Implement candidate evaluation**

For each query, retrieve the pool once. Derive a baseline rank map from the returned top-ten hits. Sort candidates by numeric document ID. Create `candidate_id` before loading chunks. Map public annotations to entailment/contradiction for annotated candidate documents and neutral for all other candidates. Retain the existing `colbert-content` signal as the comparison score.

On assembly success, derive the canonical request and `attempt_id`, persist and fsync start, call the client once, validate the echoed identifiers, and persist the terminal result. On assembly or scoring failure, write a terminal result with attempt count zero. On client failure, write a terminal result with attempt count one. Sanitize messages to exception type plus bounded single-line text; do not retain URLs, request bodies, or model inputs in error messages.

- [ ] **Step 5: Implement resume validation**

Read and validate the complete journal before any service call. Regenerate each deterministic query pool and reject an existing candidate for that query if its ID is absent from the regenerated pool. Skip terminal candidates. Surface unmatched starts as `outcome_unknown` and never call assembly or inference for them. A retry requires a manifest with a new run ID.

- [ ] **Step 6: Run focused and affected tests**

Run: `uv run pytest tests/test_application.py tests/test_scientific_inference.py tests/test_scientific_inference_evaluation.py -q`

Expected: PASS.

- [ ] **Step 7: Commit and push**

```bash
git add src/scifact_rag/application.py src/scifact_rag/ports.py src/scifact_rag/scientific_inference.py src/scifact_rag/scientific_inference_evaluation.py tests/test_application.py tests/test_scientific_inference_evaluation.py
git commit -m "feat: execute pooled scientific inference"
git push origin main
```

### Task 8: Derive diagnostic metrics and the retained failure corpus

**Files:**
- Modify: `src/scifact_rag/scientific_inference_evaluation.py`
- Modify: `tests/test_scientific_inference_evaluation.py`

**Interfaces:**
- Consumes: validated terminal journal records and the fixed evaluation set
- Produces: `ScientificInferenceEvaluationReport`, `build_scientific_inference_report()`, `write_scientific_inference_report()`, and `write_scientific_inference_failures()`

- [ ] **Step 1: Write failing report tests**

Construct a six-row fixture containing one correct entailment, one incorrect contradiction, two neutral results, one explicit failure, and one `outcome_unknown`. Assert:

```python
assert report.complete is False
assert report.scored_candidates == 4
assert report.failed_candidates == 1
assert report.outcome_unknown_candidates == 1
assert report.three_way.confusion["entailment"]["entailment"] == 1
assert report.label_prior.predicted_label == "neutral"
assert report.evidence_partitions.annotated_evidence_present == 1
assert report.ranking == evaluate_rankings(
    {"1": {"10": 1}},
    {"1": ["10"]},
    10,
)
```

Add exact tests for macro-F1 with a missing predicted class, deterministic tie ranks in Spearman correlation, median/min/max margin summaries, evidence-sentence matching after Unicode/whitespace normalization, structural citation-provenance validation, atomic report replacement, and failure JSONL rows with empty phenomenon tags.

- [ ] **Step 2: Run report tests and confirm they fail**

Run: `uv run pytest tests/test_scientific_inference_evaluation.py -q`

Expected: FAIL because report derivation is absent.

- [ ] **Step 3: Implement raw-record-only report derivation**

Calculate three-way accuracy; per-class precision, recall, F1, and support; macro-F1 over all three canonical classes; the validation label-prior control; scored, failed, outcome-unknown, skipped, and total counts; coverage; latency; min/median/max logits and margins; and deterministic Spearman rank correlation between ColBERT and both margins.

Reconstruct the unchanged top-ten ColBERT ranking from `baseline_rank` and use the existing `evaluate_rankings()` function. Partition annotated relations as gold document absent from the pool, gold document present but rationale text absent from admitted evidence, or rationale text present. Report evidence-sentence recall separately. Define citation correctness structurally: every admitted chunk's recorded document ID, representation, ordinal, text, and digest must match the validated stored evidence used to build the bundle.

- [ ] **Step 4: Emit a reviewable failure corpus without invented labels**

Write one canonical row for each request/assembly failure and stance misclassification. Include query/document IDs, gold and predicted labels, error stage/code, admitted source text and ordinals, and `phenomenon_tags: []`. Human review may later add only the predeclared synonymy, polarity, negation, qualifier, association/causation, species/evidence-boundary, or cross-sentence tags; the automatic run must not infer them.

- [ ] **Step 5: Run focused tests**

Run: `uv run pytest tests/test_scientific_inference_evaluation.py -q`

Expected: PASS.

- [ ] **Step 6: Commit and push**

```bash
git add src/scifact_rag/scientific_inference_evaluation.py tests/test_scientific_inference_evaluation.py
git commit -m "feat: report scientific inference diagnostics"
git push origin main
```

### Task 9: Wire the composition root and CLI without changing defaults

**Files:**
- Modify: `src/scifact_rag/composition.py`
- Modify: `src/scifact_rag/cli.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_scientific_inference_evaluation.py`
- Modify: `docs/project/technical-reference.md`

**Interfaces:**
- Consumes: all Tasks 2-8 interfaces and existing `GenerationEvaluationSet`
- Produces: `build_scientific_inference_executor()`, `scientific-inference-eval-dry-run`, and `run-scientific-inference-eval`

- [ ] **Step 1: Write failing dry-run and execution-boundary CLI tests**

```python
def test_scientific_inference_dry_run_never_constructs_services(tmp_path, monkeypatch) -> None:
    manifest = write_inference_manifest(tmp_path)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("dry-run must not construct a corpus, database, or model service")

    monkeypatch.setattr(cli_module, "build_scientific_inference_executor", fail_if_called)
    monkeypatch.setattr(cli_module.BeirSciFact, "ensure", fail_if_called)

    result = CliRunner().invoke(
        app, ["scientific-inference-eval-dry-run", "--manifest", str(manifest)]
    )

    assert result.exit_code == 0
```

Add one parameterized preflight test with mutations for evaluation digest, split, model,
tokenizer, candidate strategy, context limit, and each required component. Use the same
`fail_if_called` builder and assert every invocation exits with code 2 before composition.

Add a success test proving the command passes the exact run ID, fixed evaluation set, cutoff, and manifest results path to the executor and writes `.report.json` and `.failures.jsonl` beside the raw journal.

- [ ] **Step 2: Run CLI tests and confirm they fail**

Run: `uv run pytest tests/test_cli.py -q`

Expected: FAIL because the commands and builder do not exist.

- [ ] **Step 3: Extend settings and wire the evaluator explicitly**

Add settings for `SCIENTIFIC_INFERENCE_BASE_URL`, model, revision, and 512-token limit. `build_scientific_inference_executor()` constructs:

```text
selected pooled RagApplication -> CandidatePoolSource
PostgresEvidenceStore + VllmColbertReranker + HuggingFacePairTokenBudget
    -> ScientificEvidenceAssembler
TransformersScientificInferenceClient
    -> ScientificInferenceEvaluator -> ScientificInferenceEvaluationExecutor
```

Use constructor injection. Do not add a service locator, import-time model load, or fallback model.

- [ ] **Step 4: Implement strict CLI preflight and report derivation**

Both commands first parse the manifest. The run command then loads the existing canonical generation-evaluation JSONL, verifies its digest and `train-validation` split, verifies exactly 160 cases, and verifies required component records for application image, PostgreSQL image, ColBERT model/tokenizer, DeBERTa model/tokenizer, Transformers, and inference container. Only after every check passes may it build the executor or open the result journal.

- [ ] **Step 5: Document operator commands and artifact meanings**

Document:

```bash
docker compose --profile scientific-inference build scientific-inference app
docker compose --profile scientific-inference up -d scientific-inference
docker compose --profile scientific-inference run --rm app scientific-inference-eval-dry-run --manifest MANIFEST
docker compose --profile scientific-inference run --rm app run-scientific-inference-eval --manifest MANIFEST --evaluation-set artifacts/scifact-generation-validation.jsonl
```

State that the operator, not the application, controls service lifecycle; an incomplete journal is not a leaderboard result; and a new run ID is required after `outcome_unknown` or a terminal failure.

- [ ] **Step 6: Run focused and affected tests**

Run: `uv run pytest tests/test_cli.py tests/test_application.py tests/test_scientific_inference_evaluation.py -q`

Run: `uv run scifact-rag --help`

Expected: PASS; existing defaults remain `pooled-coref-interval-content-max-colbert` and `whole-document`.

- [ ] **Step 7: Commit and push**

```bash
git add src/scifact_rag/composition.py src/scifact_rag/cli.py tests/test_cli.py tests/test_scientific_inference_evaluation.py docs/project/technical-reference.md
git commit -m "feat: expose scientific inference evaluation"
git push origin main
```

### Task 10: Verify the software candidate and obtain independent review

**Files:**
- Modify after review only when a finding is accepted as an in-scope repair
- Modify: the active `.harness/runs/` record through `tools/loop.py`

**Interfaces:**
- Consumes: Tasks 1-9 candidate and the active engineering-loop run
- Produces: one passing current-attempt full gate, independent verdict, proportionality disposition, and release-impact recommendation

- [ ] **Step 1: Run cheap static checks and one affected suite**

Run: `uv run ruff format --check src tests`

Run: `uv run ruff check src tests`

Run: `uv run pyright`

Run: `uv run pytest tests/test_scientific_inference.py tests/test_scientific_inference_adapter.py tests/test_scientific_inference_service.py tests/test_scientific_inference_evaluation.py tests/test_cli.py -q`

Expected: all PASS.

- [ ] **Step 2: Record release impact before the final gate**

Record `patch`: the change adds opt-in CLI commands, schemas, and a Compose profile while leaving existing command behavior and defaults unchanged.

- [ ] **Step 3: Run exactly one final full gate for the current candidate**

Run: `make smoke`

Expected: PASS for harness, format, lint, types, unit, package smoke, and Compose configuration.

Then run:

```bash
python3 tools/product_version.py
git diff --check
git status --short
```

- [ ] **Step 4: Obtain independent adversarial review**

The reviewer must not be the implementer. Review criterion coverage, one-request ordering, resume transitions, strict schemas, token counting, no truncation, no model calls in CI, no retrieval/default mutation, and scope proportionality. Collect one deduplicated finding batch before repair.

- [ ] **Step 5: Disposition findings before mutation**

Record each finding as repair, simplification, narrowed claim, deferral, accepted risk, contract revision, or emergency stop. Any HTTP-protocol, dependency, write-scope, or second-failed-repair trigger requires an independent proportionality review and a current build/adopt/adapt/defer assessment. Repair only accepted in-scope findings in a new attempt, then repeat the affected checks and one new final full gate.

- [ ] **Step 6: Commit and push any accepted repair batch**

Stage only reviewed paths, commit once for the batch, and push. If review is clean, create no empty commit.

### Task 11: Qualify the DGX service, run the fixed diagnostic once, and record the result

**Files:**
- Create: `docs/reports/phase-3-scientific-inference-validation.md`
- Modify: `docs/reports/scifact-retrieval-leaderboard.md`
- Modify: `docs/project/handoff.md`
- Modify: `README.md`
- Modify: `docs/project/roadmap.md`
- Runtime-only ignored artifacts: `artifacts/scientific-inference-*/`

**Interfaces:**
- Consumes: independently approved software, pinned Compose service, fixed probes, and frozen 160-claim evaluation set
- Produces: live qualification evidence, canonical journal/report/failure artifacts, one explicitly non-fused internal leaderboard entry, and an owner-review gate

- [ ] **Step 1: Inspect the DGX before starting a workload**

Inspect current containers, GPU/unified-memory use, port 8085, and the Hugging Face cache. If sufficient memory is unavailable, stop and ask the operator which existing workload to stop. Do not stop anything implicitly.

- [ ] **Step 2: Build and start only the approved inference service**

Run:

```bash
docker compose --profile scientific-inference build scientific-inference app
docker compose --profile scientific-inference up -d scientific-inference
```

Record image digest, checkpoint snapshot commit, Transformers/PyTorch/CUDA versions, tokenizer maximum length, model `id2label`, host, and start time.

- [ ] **Step 3: Run fixed integration qualification probes**

Use one entailment pair, one contradiction pair, and one unrelated pair fixed before inspecting outputs. Verify service health, exact revision, premise/hypothesis order, 512-token rejection, complete label map, finite logits, and response structure. These prove integration only, not scientific quality.

- [ ] **Step 4: Run a small operational smoke with a distinct run ID**

Run a predeclared small set only to expose serving, serialization, and persistence failures. Do not use its logits to alter the model, evidence selector, thresholds, or validation manifest. Any smoke failure requires a new smoke run ID after repair.

- [ ] **Step 5: Open and complete the frozen validation run once**

After qualification passes, create the final manifest with exact component revisions and execute all 160 claims. Resume only missing candidates with no prior event. Never resubmit terminal or `outcome_unknown` candidates. If any candidate fails or is `outcome_unknown`, retain the run as incomplete and use a new run ID only after an owner-approved retry decision.

- [ ] **Step 6: Verify artifact consistency**

Re-read the full journal, regenerate the report and failure corpus, compare their digests and counts, and confirm the report is complete before describing model quality. Record total/scored/failed/outcome-unknown counts and elapsed time.

- [ ] **Step 7: Update the internal leaderboard and project status**

Add one diagnostic row containing stance accuracy, macro-F1, evidence coverage, latency, and correlation with ColBERT. Label it `non-fused` and `internal validation`; do not mix stance metrics into the retrieval nDCG ordering. Document failure categories only when supported by reviewed retained examples. Update the handoff, README status, roadmap outcome, and Issue report with verified facts and explicit limitations.

- [ ] **Step 8: Stop for owner review**

Do not implement inference fusion, change retrieval/generation defaults, access test qrels, start graph work, or select another model. Present the diagnostic and retained failures to the owner as the Phase 3 exit decision.

- [ ] **Step 9: Commit and push the evidence summary**

```bash
git add docs/reports docs/project/handoff.md docs/project/roadmap.md README.md
git commit -m "docs: record scientific inference diagnostic"
git push origin main
```
