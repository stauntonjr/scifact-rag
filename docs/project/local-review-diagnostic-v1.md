# Local scientific-review diagnostic v1

This is the executable preparation protocol for the 24-case local-model diagnostic. It tests whether an individual local reviewer can recognize explicitly defined scientific meaning changes and preserve adequate answers. It does not rerun the historical assessment, measure corpus prevalence, qualify a judge, change a generator, or authorize promotion.

The runner creates a deterministic 24-case synthetic fixture with eight paired contrasts and eight boundary cases. Expected decisions are coordinator-only. They are never included in the model request; the request contains only the complete rubric, claim, answer, supplied passages and the strict schema.

Prepare a fresh fixture, then capture read-only endpoint state:

```bash
uv run python tools/local_review_diagnostic.py prepare \
  --fixture artifacts/local-review-diagnostic-v1-ready-r2/fixture.json

uv run python tools/local_review_diagnostic.py preflight \
  --endpoint http://127.0.0.1:8000 \
  --endpoint http://127.0.0.1:8082 \
  --output artifacts/local-review-diagnostic-v1-ready-r2/preflight.json
```

The second command uses only `/v1/models`. It does not invoke inference and requires at least one admitted endpoint. Capture the full service inventory, process identities, memory observation and quiet-window check in the adjacent operator note before execution. Existing services must remain loaded, healthy and unchanged throughout. If Qwen3.8 cannot coexist in its own trial container while retaining the memory reserve, its arm is not admitted; no existing model may be unloaded, restarted or reconfigured to make room.

Execution requires a separately admitted local endpoint, an immutable Qwen checkpoint/tokenizer/runtime identity record, the frozen fixture and the full rubric. It is deliberately opt-in:

```bash
uv run python tools/local_review_diagnostic.py execute \
  --fixture artifacts/local-review-diagnostic-v1-ready-r2/fixture.json \
  --preflight artifacts/local-review-diagnostic-v1-ready-r2/preflight.json \
  --rubric docs/project/generation-review-rubric-v3-draft.md \
  --endpoint http://127.0.0.1:18080 \
  --model Qwen/Qwen3.8-27B-FP8 \
  --output artifacts/local-review-diagnostic-v1-ready-r2/qwen38-run \
  --execute
```

At most one request is in flight. A request exception, including any transport exception before a response is recorded, is recorded as unknown and stops that arm, because it may have reached the server. Source-validation failure and a known non-200 response are separately retained as attributable failures. If the endpoint reports a model identifier other than the admitted identifier, that attributable failure ends the arm immediately. The runner never normalizes quotations after a response. A new output root is required, so existing results cannot be overwritten or silently resumed.

The trial report separates source-valid usable output from semantic agreement with the independently reviewed synthetic reference. Any miss of a definite qualifier, population, or causal contrast—or false positive on its faithful counterpart—limits the model to source-reviewed assistance for that capability. No numerical result establishes autonomous scientific qualification.
