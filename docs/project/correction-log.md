# Failure correction log

## EI-TOKEN-001: Structured tokenizer return counted as fields

- Date: 2026-09-18. Workflow: Issue #23, CPU-only reader preparation.
- Failed approach: count `len(apply_chat_template(...))` without fixing the return format.
  Transformers 5.15.1 returned a structured encoding; every input appeared to have two tokens.
- Mutation status: an ignored diagnostic preparation was written; no model request was sent.
- Correction: request `return_dict=False` explicitly and count token IDs. Preserve the failed
  probe separately and regenerate acceptance artifacts at a fresh path after repair.
- Verification: exact local tokenizer-version comparisons cover 202 full/oracle messages and
  409 unique selector inputs. Correct full-context counts range from 977 to 14,052 tokens.
- Durable prevention: a regression test exercises the structured default; actual-tokenizer
  preparation must precede inference. Fake tokenizers alone do not establish production counts.

This log retains sanitized, reusable corrections for agent or tooling mistakes that are likely to
recur. It is not a transcript, retry counter, incident archive, or substitute for a regression
test. Never record tokens, secrets, private prompts, hidden reasoning, or unnecessary user data.

## Recording contract

Record a correction when a failed approach is repeatable or when another agent could plausibly
choose it again. Include:

- a stable ID, date, affected workflow, and public or synthetic provenance;
- the attempted approach and a short sanitized error signature;
- whether any local or external mutation occurred and how that was verified;
- the corrected command or decision path, including authorization boundaries;
- the exact verification that proved the correction; and
- the durable prevention surface: skill instruction, test, challenge candidate, or tool guard.

Do not rewrite a failure as success. If the correction is not verified, label it proposed. If the
failure exposes an escaped defect with a deterministic oracle, create a candidate under
`harness/challenges/`; do not store a live network call as a replay fixture.

## GH-PLANNING-001: Classic Project shortcut used for a Projects v2 item

- Date: 2026-08-24.
- Workflow: create GitHub Issues and add them to the configured Project v2 roadmap.
- Provenance: Agentic Application Assessor greenfield publication, sanitized operator-visible CLI
  evidence.
- Failed approach: passed `--project` to `gh issue create`.
- Error signature: the CLI attempted the deprecated Projects (classic) lookup and returned a
  Projects-classic deprecation error.
- Mutation check: the command created no Issue; a subsequent complete Issue-list read returned an
  empty list.
- Classification: client-command routing error, not Project drift, authentication failure, or a
  GraphQL API limitation.
- Corrected path:
  1. Create the Issue without `--project` and retain its exact URL.
  2. Preview `python3 tools/github_planning.py add-item --url ISSUE_URL`.
  3. After authorization, run the same command with `--yes`.
  4. Re-read Project items and the Issue's `projectItems` membership.
- Verification: seven Issues were created, added to Projects v2 Project #16, and re-read with exact
  membership; the final live planning audit reported no managed drift.
- Prevention: the GitHub-planning skill forbids the classic shortcut; the idempotent `add-item`
  command pre-reads membership, rejects duplicates, uses `gh project item-add` only when absent,
  and verifies post-write membership; unit tests assert each boundary.

## GH-PLANNING-008: corrected source remained absent from the active plugin cache

- Date: 2026-08-25.
- Workflow: create an Assessor follow-up Issue after its Macro Technical Pulse dogfood loop.
- Provenance: sanitized installed-plugin, canonical-source, and generated-application comparison.
- Failed approach: reused `gh issue create --project` while an installed plugin cache still exposed
  version `0.1.0`, then relied on the corrected canonical template as if it controlled the session.
- Error signature: the CLI attempted deprecated Projects (classic); the active cached planning
  skill lacked both the explicit prohibition and the supported `add-item` sequence.
- Mutation check: GitHub rejected the command before creating an Issue; a complete Issue re-read
  found no partial or duplicate object. The Issue was then created once through the supported flow.
- Classification: combined execution and distribution failure. The agent skipped a required
  safety-reference read, and corrected source was not cache-busted or reinstalled.
- Corrected path:
  1. Bump the plugin patch version and add a unique local cache identity during installation.
  2. Regenerate provenance and validate the canonical package.
  3. Reinstall from the reviewed local marketplace and compare the installed planning skill and
     safety-reference bytes with the reviewed generated distribution.
  4. Start a new thread so Codex loads the new plugin version.
- Verification: Issue #55 gives the plugin a new cache identity, regenerates provenance, and makes
  the isolated lifecycle probe compare the two exact installed planning files with the reviewed
  distribution.
- Prevention: refresh and verify the installed distribution whenever corrected plugin guidance
  changes. Command interception and general shell policy are explicitly outside this correction.

## GH-PLANNING-006: successful Project item write was immediately invisible

- Date: 2026-08-24.
- Workflow: add pull request #43 to the configured Projects v2 roadmap during publication.
- Provenance: sanitized live GitHub CLI evidence from the agentic-project-template repository.
- Failed approach: treated the first complete item-list response after `gh project item-add` as
  immediately consistent.
- Error signature: `Project v2 membership verification found 0 items ... expected 1`.
- Mutation check: no retry of `item-add` occurred. Independent complete re-reads found exactly one
  matching Project item, `PVTI_lAHOAiy8Ic4BhKnPzg30Ghk`, and the pull request's `projectItems`
  field named the expected roadmap.
- Classification: post-mutation read visibility lag, not a failed write, duplicate membership,
  invalid authentication, or Projects-classic routing.
- Corrected path:
  1. Perform the complete pre-read and one authorized `item-add` exactly as before.
  2. If the first complete post-write read has no exact match, retry only the complete read with
     bounded delays.
  3. Stop immediately on one match; fail closed on duplicates, truncation, malformed data, or
     persistent absence.
  4. Never repeat the mutation automatically; re-read live state before any operator retry.
- Verification: unit regressions prove delayed visibility succeeds after one mutation and bounded
  reads, while exhausted visibility fails after one mutation; live state contains exactly one pull
  request #43 membership.
- Prevention: the `add-item` implementation now separates its single mutation from bounded
  post-write reads, and the GitHub-planning guide documents the eventual-consistency boundary.

## GH-PR-METADATA-007: `gh pr edit` queried deprecated Project cards

- Date: 2026-08-24.
- Workflow: update pull request #43's body after pushing verified correction evidence.
- Provenance: sanitized live GitHub CLI evidence from the agentic-project-template repository.
- Failed approach: ran `gh pr edit NUMBER --body-file FILE` with GitHub CLI 2.45.0.
- Error signature: `GraphQL: Projects (classic) is being deprecated ... (projectCards)`.
- Mutation check: an exact pull-request re-read showed that neither correction-loop evidence nor
  the current test count was present; the head commit and existing Project membership were
  unchanged.
- Classification: installed-client GraphQL query incompatibility, not an invalid body file,
  authentication failure, Projects v2 membership error, or pull-request write rejection.
- Corrected path:
  1. Stop after the first failed `gh pr edit`; do not retry the same client route.
  2. Send the reviewed body file to the exact REST pull-request endpoint with
     `gh api --method PATCH repos/OWNER/REPOSITORY/pulls/NUMBER -F body=@FILE`.
  3. Re-read that pull request and require both the expected head SHA and distinguishing body
     content before reporting success.
- Verification: the REST mutation returned pull request #43; a subsequent REST read returned head
  `7cdca280d2ecd5d937126ba155a70c74995827ee` and both the correction-evidence marker and current
  206-test marker.
- Prevention: the GitHub-planning safety reference preserves the REST/body-file fallback and
  mandatory re-read; a repository test requires that packaged guidance and this ledger entry
  remain present.

## GH-AUTH-002: Sandboxed network failure reported as an invalid token

- Date: 2026-08-24.
- Workflow: validate GitHub CLI authentication before a read-only planning audit.
- Provenance: sanitized local CLI evidence from the agentic-project-template workspace.
- Failed approach: treated `gh auth status` inside a network-restricted sandbox as proof that the
  stored credential was invalid.
- Error signature: `Failed to log in` and `token ... is invalid`, followed by `gh api user`
  reporting that it could not connect to `api.github.com`.
- Mutation check: no local credential, GitHub object, or repository state was changed.
- Classification: unavailable network validation misclassified as credential rejection.
- Corrected path:
  1. Check for environment-token overrides without printing values.
  2. Retry the read-only check through the approved network-permission path.
  3. Call `gh api user` and require an authenticated HTTP success before declaring the token valid.
  4. Treat an unreachable API as indeterminate; rotate or reauthenticate only after an actual
     authentication rejection.
- Verification: the network-enabled API returned HTTP 200 for `stauntonjr`; `gh auth status`
  confirmed the keyring credential and expected scopes; the live Projects v2 audit passed.
- Prevention: the GitHub-planning safety reference requires sandbox-blocked network operations to
  use the approved permission path instead of being reported as GitHub or credential limitations.

## LOCAL-RUNTIME-003: Sandboxed loopback failure reported as an offline model

- Date: 2026-08-24.
- Workflow: determine whether the local SparkRun Qwen endpoint was available before a model-diversity
  canary run.
- Provenance: sanitized host Docker, SparkRun, listener, and OpenAI-compatible API evidence from the
  DGX workspace.
- Failed approach: called `http://127.0.0.1:8000/v1/models` only from a restricted sandbox and
  treated its connection failure as proof that the model was offline.
- Error signature: a sandbox-local connection failure to port 8000 even though the host service was
  already running.
- Mutation check: the corrective commands were read-only; they did not start, stop, restart, or
  reconfigure a container, model, listener, or repository.
- Classification: restricted loopback visibility misclassified as a host-runtime outage.
- Corrected path:
  1. Treat a failed network or loopback probe from a restricted runtime as indeterminate.
  2. Use the approved host-permission path to inspect the workload supervisor, such as
     `sparkrun status`.
  3. Inspect the candidate container and its start/restart state with `docker inspect`.
  4. Confirm the host listener with `ss`, then call the expected health or discovery endpoint, such
     as `/v1/models`, from the host boundary.
  5. If host verification is unavailable, report availability as unverified rather than offline.
  6. Never start a replacement workload before checking for an existing instance, especially when
     it can reserve GPU memory or collide on a host port.
- Verification: SparkRun reported job `8337765ded59` running the official
  `qwen3-coder-next-int4-autoround-vllm` recipe; Docker reported its host-network container running
  since `2026-08-24T02:12:31Z` with no restart or OOM state; the host listened on port 8000; and
  `/v1/models` returned `Intel/Qwen3-Coder-Next-int4-AutoRound`. The container start preceded the
  sandbox-only probe.
- Prevention: the engineering-loop skill requires host supervisor/container/listener/API evidence
  before classifying a local service unavailable and forbids starting a duplicate workload first;
  repository tests preserve the correction and reject the superseded availability claim.

## LOCAL-RUNNER-004: Pi shebang lost its adjacent Node runtime

- Date: 2026-08-24.
- Workflow: begin the first bounded paired Qwen canary through the repository model-stress runner.
- Provenance: sanitized local runner preflight in the agentic-project-template workspace.
- Failed approach: invoked the explicitly supplied `bin/pi` with an allowlisted environment whose
  `PATH` contained only system directories. Pi uses `#!/usr/bin/env node`, while its matching Node
  binary is adjacent to Pi in the self-contained installation.
- Error signature: `could not determine Pi version`.
- Mutation check: the runner stopped in its version preflight with `model_invoked: false`; it did
  not call the model, change the existing SparkRun workload, write GitHub state, or retain a model
  transcript.
- Classification: runner executable-resolution defect, not a model, provider, container, or
  endpoint outage.
- Corrected path: run the supplied self-contained Pi installation inside a networkless Bubblewrap
  version preflight, mount the complete installation read-only, and select its adjacent Node through
  the sandbox `PATH`.
- Verification: a registration-free regression inspects the version command's networkless,
  read-only installation mount and recognizes the fixture's semantic version; the repaired live
  runner preflight reports Pi 0.84.1 before model execution.
- Prevention: `test_pi_version_uses_networkless_read_only_self_contained_installation` preserves
  the self-contained runtime contract, and the live command continues to require an explicit
  `--pi` path.

## LOCAL-RUNNER-005: first canary overstated prompt and oracle provenance

- Date: 2026-08-24.
- Workflow: independently verify the first paired Qwen canary and its durable smoke report.
- Provenance: exact local runner source and ignored result digest recorded in the Issue #21 report.
- Failed approach: hashed `task.prompt` into the result while sending a different hard-coded prompt;
  passed every hidden oracle case and expectation through `HARNESS_ORACLE`; buffered model output
  before checking its size; retained arbitrary tool names; and initialized some post-invocation
  error output as `model_invoked: false`.
- Error signature: recorded prompt digest did not identify the prompt Pi received, and generated
  code could read the hidden expected answers from its own environment.
- Mutation check: no additional model invocation, SparkRun/container mutation, GitHub write, or
  retained transcript occurred during correction. The original run remains only diagnostic history.
- Classification: runner provenance, isolation, resource-bound, sanitization, and reporting defect;
  not evidence of a Qwen, Pi, vLLM, Docker, or endpoint failure.
- Corrected path: pass the exact contract prompt; run each oracle case in a separate networkless
  child containing no expectation; bound stdout during execution and discard stderr; mount Pi
  configuration read-only; sanitize tool identities; validate cross-field relationships; freeze
  one resource bundle and seed repository for every lane/trial; and carry invocation state through
  every failure path. The historical report now labels the old `.git`-excluding scope observation
  and post-hoc event-length check precisely instead of treating either as a verified bound. Task
  and resource paths are opened component by component without following a symlinked root or nested
  ancestor, preventing a dirty checkout from redirecting model-visible input outside the root.
- Verification: focused regressions cover prompt equality, answer-free oracle environments,
  operative event-size limits, deep JSON, stable tool categories, strict result relationships,
  schema/custom length parity, frozen-seed identity after source mutation, root/ancestor symlink
  rejection, pre-invocation output validation, and truthful post-invocation failure output.
- Prevention: acceptance-candidate evidence must come from the repaired runner and independent
  review; the first smoke cannot be promoted or used as the accepted baseline.

## LOCAL-RUNNER-006: read-only Pi config triggered a credential-lock startup failure

- Date: 2026-08-24.
- Workflow: begin the three-task, three-trial paired Qwen acceptance-candidate run.
- Provenance: sanitized runner result, host vLLM access log, and disposable zero-tool Pi probes.
- Failed approach: relied only on the synthetic `apiKey` in generated `models.json` while mounting
  the generated Pi configuration read-only. Pi 0.84.1 still consulted its credential store and
  attempted to create `auth.json.lock`, then exited before contacting the provider.
- Error signature: all six initial diagnostic lanes returned exit 1 in under one second, produced
  no edits, usage, settled event, or stable tool error, and generated no request in the vLLM log.
- Mutation check: the invalidated runs changed no candidate file, container, model service, GitHub
  object, or external repository; their sanitized ignored result is diagnostic only.
- Classification: Pi startup/configuration incompatibility, not model quality or endpoint failure.
- Corrected path:
  1. Confirm the existing SparkRun job, container, listener, and `/v1/models` response from the host.
  2. Reproduce the failure in a disposable zero-tool Bubblewrap session using the same read-only
     generated configuration.
  3. Pass Pi the explicit synthetic `--api-key not-needed` argument so it need not consult a
     credential store; never substitute or expose a real credential.
  4. Require a zero-tool Bubblewrap probe to settle and reach the loopback provider before rerunning
     any scored task.
  5. Invalidate every trial produced by the failed startup path rather than counting it as model
     evidence or retrying it as though the model had answered.
- Verification: the direct provider probe and the matching read-only-config Bubblewrap probe both
  settled against `Intel/Qwen3-Coder-Next-int4-AutoRound`; the latter succeeded only after the
  explicit synthetic API-key argument was supplied.
- Prevention: the lane-command regression requires the synthetic argument while retaining the
  read-only config mount; future reports must distinguish a Pi process start from a provider-backed,
  settled model response.

## LOCAL-RUNNER-007: API-key control design conflicted with the authorized subscription boundary

- Date: 2026-08-24.
- Workflow: add a GPT-5.6 Sol control to the paired Pi model-stress runner.
- Provenance: human authorization and local design inspection in the agentic-project-template
  workspace.
- Failed approach: the first proposed control would have accepted an OpenAI API key through a
  credential-isolating proxy.
- Error signature: the human owner explicitly prohibited an OpenAI API key and required use of the
  existing ChatGPT Pro/Codex subscription.
- Mutation check: no OpenAI request or model invocation occurred; no API key was read, printed,
  passed to Pi, persisted, or added to retained evidence. Only uncommitted local runner design work
  existed when the approach was stopped.
- Classification: authorization and credential-boundary mismatch, not a provider outage,
  authentication rejection, model failure, or Pi catalog limitation.
- Corrected path:
  1. Use Pi's native `openai-codex` Responses provider and exact `gpt-5.6-sol` model.
  2. Validate the existing Codex ChatGPT login while rejecting any API-key auth field.
  3. Keep the short-lived OAuth token in a host relay and give Pi only a random per-run canary JWT.
  4. Resolve the exact Pi model in a credential-free, offline catalog preflight before a request.
  5. Run a bounded smoke before any repeated paired evaluation.
- Verification: focused tests prove API-key rejection, private bounded no-symlink auth loading,
  canary authentication, fixed upstream routing, credential substitution, request budgets,
  sanitized Pi catalog resolution, exact control provenance, and no inherited API-key environment.
- Prevention: ADR-0009 and the runner make the subscription target explicit and fail closed;
  control documentation states that Pi's `--api-key` flag carries only a non-secret canary value.

## LOCAL-RUNNER-008: Pi Codex credential synchronization required ephemeral state

- Date: 2026-08-24.
- Workflow: run the first bounded GPT-5.6 Sol subscription-control smoke through Pi 0.84.1.
- Provenance: sanitized paired result, loopback relay metrics, and a no-credential disposable Pi
  reproduction.
- Failed approach: mounted the complete generated Pi agent directory read-only, assuming the
  explicit non-secret canary argument would prevent all credential-store writes.
- Error signature: Pi attempted `setRuntimeApiKey` synchronization for `openai-codex` and exited on
  a read-only `models-store.json` before emitting JSON events or reaching the relay.
- Mutation check: both lanes exited in under one second, changed no disposable task file, reported
  no provider tokens, and the relay observed zero requests and zero bytes. No ChatGPT model request,
  API-key use, GitHub write, or host credential/configuration mutation occurred.
- Classification: Pi runtime-state mount incompatibility, not a ChatGPT authentication rejection,
  GPT-5.6 Sol result, relay transport failure, or subscription-usage event.
- Corrected path: keep generated `models.json` and `settings.json` individually read-only while
  giving Pi an empty, sandbox-local writable agent-state directory for lock and runtime-store
  files. Continue to mount no host auth store and pass only the random canary.
- Verification: a no-credential reproduction must progress beyond credential synchronization to
  the deliberately closed loopback endpoint; the corrected host safety tests and bounded live
  smoke must then pass their respective startup and relay boundaries.
- Prevention: lane-command regressions require both configuration files to remain read-only,
  forbid an auth-file mount, and preserve the ephemeral-state layout.

## LOCAL-RUNNER-009: subscription auth parsing accepted ambiguous or malformed structures

- Date: 2026-08-24.
- Workflow: independently verify the GPT-5.6 Sol subscription-control candidate before publication.
- Provenance: synthetic private auth files and JWTs containing no real credential or account data.
- Failed approach: parsed the bounded Codex auth file with ordinary JSON semantics and accessed the
  nested JWT auth claim before confirming it was an object.
- Error signature: duplicate top-level JSON keys were accepted by last-value-wins parsing, while a
  string or list at the auth-claim path raised an uncaught `AttributeError` in the CLI check path.
- Mutation check: the verifier used only disposable local files; no model, provider, credential,
  candidate, GitHub object, or external repository was invoked or mutated.
- Classification: fail-closed input-validation defect, not a ChatGPT authentication rejection or
  subscription outage.
- Corrected path: reject duplicate keys in both the auth document and decoded JWT claims, validate
  the nested claim as an object before reading its account ID, and translate malformed input into
  the runner's structured non-invocation result.
- Verification: loader regressions cover duplicate auth keys and string/list claim shapes; the CLI
  regression requires exit 2, empty stderr, no traceback, `ok: false`, and `model_invoked: false`.
- Prevention: all host credential metadata remains bounded, private, no-symlink, strictly parsed,
  shape-checked, and outside the Pi/model sandbox before any provider preflight or request.

## LOCAL-RUNNER-010: unsafe credential header values could reach exception text

- Date: 2026-08-24.
- Workflow: independently verify the GPT-5.6 Sol subscription-control credential boundary.
- Provenance: synthetic private auth files and a fake upstream connection; no real credential or
  provider request.
- Failed approach: validated JWT structure and account consistency without first restricting the
  token and account ID to bounded header-safe character sets; upstream header construction errors
  also did not catch `ValueError`.
- Error signature: a synthetic access token with a trailing line feed reached `http.client`, whose
  rejected-header exception could include the supplied bearer value; control characters in a
  synthetic account ID had the same disclosure class.
- Mutation check: the verifier and regression use only disposable synthetic values and a mocked
  connection; no model, provider, credential, candidate, GitHub object, or external repository is
  invoked or mutated.
- Classification: credential-metadata validation and exception-sanitization defect, not a ChatGPT
  authentication rejection or subscription outage.
- Corrected path: accept only bounded JWT-token characters and bounded account-ID characters before
  decoding or constructing a credential; apply the same check in the relay constructor; catch an
  upstream header `ValueError` and return only the fixed sanitized relay error.
- Verification: loader regressions reject newline/carriage-return cases without echo, and a host
  relay regression forces an exception containing the synthetic bearer while requiring HTTP 502,
  empty stderr, no traceback, and no token or account value in the response.
- Prevention: no credential-derived string reaches an HTTP header until strict syntax, size,
  identity, expiry, private-file, duplicate-key, and nested-claim checks all pass.

## LOCAL-RUNNER-011: Pi Codex ignored the configured output-token option

- Date: 2026-08-24.
- Workflow: independently compare the GPT-5.6 Sol control contract with installed Pi 0.84.1.
- Provenance: read-only inspection of Pi's installed OpenAI-compatible and Codex Responses provider
  implementations plus the retained sanitized results.
- Failed approach: treated the generated `maxTokens: 4096` model override as an enforced provider
  request limit for both local Qwen and Codex subscription targets.
- Error signature: Pi's OpenAI-compatible completions implementation transmits its max-token field,
  but the Codex Responses implementation does not read the option or send `max_output_tokens`.
- Mutation check: the finding used static local inspection only; no model, provider, credential,
  GitHub object, candidate repository, or external repository was invoked or mutated.
- Classification: evidence-provenance and comparison-contract defect, not a GPT-5.6 Sol failure,
  timeout, or subscription rejection.
- Corrected path: schema 1.3 records `output_token_limit_enforcement` in the provider boundary;
  local Qwen requires `provider-request`, while Codex Sol requires `runner-config-only`. The Sol
  report excludes output-token enforcement from the equal-limit claim and discloses the asymmetry.
- Verification: custom and Draft 2020-12 validators reject target/enforcement mismatches; retained
  Sol artifacts are transparently annotated without changing any trial, usage, scope, request,
  timing, tool-error, or oracle value, and both original and corrected hashes are reported.
- Prevention: future cross-provider comparisons must distinguish configuration intent from an
  observed or source-verified provider request boundary.

## SCIFACT-RAG-001: Compose run did not accept an ad hoc GPU flag

- Date: 2026-08-26.
- Workflow: run the first MS MARCO cross-encoder retrieval evaluation on the DGX Spark GPU.
- Failed approach: documented and invoked `docker compose run --rm --gpus all app ...`, assuming
  the standalone Docker GPU flag was available on this host's Compose `run` command.
- Error signature: `unknown flag: --gpus` before any application or model process started.
- Mutation check: the failed command created no container, changed no database row or repository
  file, and invoked no model. A later CPU evaluation was deliberately interrupted after 417.39
  seconds when the owner required a hosted GPU model; it produced no metrics and is diagnostic only.
- Corrected path: define a separate digest-pinned Hugging Face TEI service with `gpus: all` in
  `compose.yaml`, verify its health and `/rerank` API, and have the application call it over the
  Compose network.
- Verification: the disposable and durable TEI services loaded the exact model revision as
  `FlashBert` on CUDA, enforced 512 tokens, and scored a relevant control above an irrelevant
  control. The completed 300-query Compose run returned all metrics in 87.91 seconds.
- Prevention: GPU device requests belong in this project's Compose service definition; documented
  application commands no longer depend on an unsupported `docker compose run --gpus` option.

## HARNESS-012: evidence-ordering repairs exhausted the engineering retry ceiling

- Date: 2026-08-26.
- Workflow: complete the independently reviewed MS MARCO reranker engineering loop.
- Failed approach: recorded attempt-scoped release-impact evidence after the full gate, then did not
  refresh it before a later attempt, consuming the three permitted repairs on harness evidence
  freshness rather than product defects.
- Error signature: completion validation reported stale release-impact evidence and, after repair,
  multiple current-attempt full gates.
- Mutation check: the exhausted repairs did not alter the reviewed reranker candidate; the human
  resume rebuilt only its evidence chain.
- Corrected path: record current-attempt release impact before the single final full gate, then bind
  independent review and verdict to that exact candidate and evidence identity.
- Verification: the resumed reranker run reported cleanly, and recovery fixture R005 now proves the
  owner-authorized five-failure ceiling blocks at attempt five without creating attempt six.
- Prevention: the engineering-loop ceiling is five for new runs, the second-failed-repair
  proportionality review remains mandatory, and retry exhaustion still requires human-reviewed
  structured recovery. Pi's separate unavailable-tool ceiling remains three.

## SCIFACT-RAG-002: representation ingestion invalidated the BM25 index

- Date: 2026-08-26.
- Workflow: evaluate fixed BM25 fusion and incremental candidate pools for semantic packing
  representations after ingesting a new full-corpus vector representation.
- Failed approach: every representation batch unconditionally updated existing document tuples and
  recomputed identical BM25 vectors, even though the corpus text had not changed. The first attempt
  also launched three BM25 evaluations concurrently against the resulting index.
- Error signature: VectorChord-BM25 raised `could not read blocks 1920..1920 ... read only 0 of
  8192 bytes`, followed by `ResourceOwnerForget called for relcache reference after release
  started`; a serialized retry reproduced the same stale tuple reference.
- Mutation check: the failed evaluations were read-only and returned no accepted metrics. All 5,183
  document rows remained readable. The local `documents_bm25_idx` was rebuilt once from the intact
  heap, shrinking from 370,130,944 to 155,115,520 bytes; no table, volume, or corpus row was deleted.
- Corrected path: the document upsert now executes its conflict update only for changed title/text
  or a previously missing retained embedding. BM25 vectors update only when retokenization is
  distinct from the stored vector. Representation rows remain independently replaceable.
- Verification: the isolated PostgreSQL test preserves document `ctid` and `xmin` across an
  additional representation upsert and then retrieves through BM25. A full 5,183-document no-op
  ingestion preserved the exact tuple-identity digest and BM25 index size, followed by a successful
  live BM25 search without reindexing.
- Prevention: unchanged representation ingestion must be tuple-idempotent at the document layer;
  the focused integration test is the durable guard. Full BM25 evaluations against this local
  extension are serialized rather than launched concurrently.

## SCIFACT-RAG-003: CI package smoke used an unsupported Python interpreter

- Date: 2026-09-15.
- Workflow: run the authoritative `make smoke` gate in GitHub Actions after applying the selected
  retrieval default and documentation cleanup.
- Failed approach: retained the template's Python 3.11 workflow pin after SciFact RAG adopted
  Python 3.12 as its minimum supported runtime. `uv run` selected Python 3.12 for project commands,
  masking the mismatch until the standalone package-smoke script created a clean environment from
  the workflow interpreter.
- Error signature: wheel installation rejected Python 3.11.16 because the package requires
  `>=3.12,<3.14`; harness validation, Ruff, Pyright, and 217 unit tests had already passed.
- Mutation check: the failed GitHub run installed only ephemeral runner dependencies and did not
  invoke PostgreSQL, a model service, the DGX, or an application evaluation.
- Corrected path: configure Python 3.12 in every existing GitHub workflow that invokes
  `make smoke`: harness verification, harness release, and harness upgrade.
- Verification: a repository-wide workflow audit confirms all three `make smoke` workflows use
  Python 3.12, matching `pyproject.toml`, `uv.lock`, the Docker image, and the documented project
  runtime. The complete local and remote gates are retained in the Issue #7 engineering evidence.
- Prevention: workflow interpreter pins must remain within the application's declared
  `requires-python` range whenever the workflow executes application package smoke.

## SCIFACT-RAG-004: proposition preflight misclassified cited NEI candidates

- Date: 2026-09-15.
- Workflow: authenticate the fixed Phase 3 candidate boundary before proposition extraction.
- Failed approach: the new external gold-label join mapped every cited case that was not SUPPORT to
  contradiction, overlooking cited `NOT_ENOUGH_INFO` cases that Phase 3 correctly labels neutral.
- Error signature: the authenticated dry-run stopped with `Phase 3 candidate identity or gold label
  is not reproducible`; no Qwen or MiniLM call had started.
- Mutation check: only ignored source/audit manifests existed, and neither proposition extraction
  nor scoring output had been created.
- Corrected path: map a candidate to neutral when its document is uncited or its case stance is
  `NOT_ENOUGH_INFO`, then map the remaining cited cases to entailment or contradiction.
- Verification: all 21,711 retained rows rejoined the exact 160 cases and corpus successfully; the
  dry-run reproduced 160 claims, 4,867 documents, and the same 100-row audit.
- Prevention: the authenticated no-model preflight remains mandatory before qualification or
  full-pool extraction.

## SCIFACT-RAG-005: deterministic review IDs exposed blinded policy assignments

- Date: 2026-09-16.
- Workflow: prepare the frozen generation-groundedness worksheet for human review.
- Failed approach: derive each displayed response ID from a published SHA-256 construction over
  the public query ID and one of three known context strategies, assuming truncating the digest
  made the identity opaque.
- Error signature: enumerating the 24 published query IDs and three strategy names reconstructed
  42 of 42 worksheet response IDs and their policy assignments.
- Mutation check: the defect was found before a reviewer identity, completion timestamp, or any of
  the 378 rubric fields had been written. No model request or result selection was repeated.
- Corrected path: assign unique random 128-bit response IDs once, retain them only through the
  separate map, re-freeze the blank worksheet/map digests, and hard-bind the local reviewer to the
  new 42-row worksheet.
- Verification: exact content projections prove every claim, evidence passage, answer,
  query/policy association, and raw-result identity is unchanged; only response IDs and row order
  differ. Independent review must confirm that public inputs no longer reconstruct the new IDs.
- Prevention: reviewer-visible opaque identifiers must not be derived from published low-entropy
  inputs; frozen mappings remain separate and are not supplied during scoring.

## GH-ACCESS-003: Dependency-review prerequisite and Projects OAuth scope

- Date: 2026-09-17 (America/New_York).
- Workflow: finish SciFact PR #14 and place template Issue #59 in Project #13.
- Evidence: SciFact run `35302453139` reports unsupported dependency review with a request to
  ensure Dependency graph is enabled. A subsequent dependency-diff read returns HTTP 403.
  Network-enabled `gh auth status` identifies the Mac keyring login with `repo`, `read:org`, and
  `gist`; `gh project view 13 --owner stauntonjr --format json` reports missing `read:project`.
  No environment-token override was present. The browser settings page was signed out.
- Failed approach: reported the graph as disabled without inspecting its live setting, and stopped
  at the read-scope error without documenting the write scope required for membership.
- Mutation status: Issue #59 exists; these diagnostics changed no credential, setting, or membership.
- Correction: follow [GitHub access recovery](github-access-recovery.md). An administrator checks
  the graph setting/eligibility; the account owner grants `project` for authorized membership work
  on the execution host. Then rerun the failed check and resume the existing item URL through
  `github_planning.py add-item`; verify both results.
- Verification boundary: error classification and official recovery commands were checked; live
  setting repair, OAuth refresh, and Project placement have not been completed by this entry.
- Durable prevention: the planning entry point links the prerequisite and recovery runbook.

## EI-PLANNING-001: Desired label absent from live repository

- Date: 2026-09-17.
- Failed approach: issue creation requested the configured `type:chore` label without confirming
  the live label list; GitHub returned `could not add label`.
- Mutation check: the open-issue list remained empty; no issue was created.
- Correction: read live labels/milestones, then create Issue #15 with existing `enhancement` and
  add the exact URL to Project #17. No duplicate issue or unrelated label reconciliation.
- Prevention: inspect live label identities before issue creation; desired configuration is not
  evidence that labels already exist.

## EI-TEST-001: Runtime tool imports are not static import paths

- Date: 2026-09-18. Evidence: PR #20, failed CI run `35341696584` at commit `4172131`.
- Failed approach: mutate `sys.path` and directly import a standalone `tools/` audit from its
  test. All 39 focused tests passed, but Pyright reported `reportMissingImports` at line 12.
- Mutation status: only test loading was affected; the audit and retained result were unchanged.
- Correction: use the explicit `importlib.util.spec_from_file_location` pattern already used by
  adjacent audit tests, asserting the module specification and loader before execution.
- Verification: focused tests and the full CI type-check boundary must both pass on the repaired
  commit; runtime success alone is not evidence of static import resolution.
- Durable prevention: reuse the adjacent explicit loader for standalone audit tests, and retain
  the required CI type check rather than suppressing unresolved imports globally.

## SCIFACT-RAG-006: Project field update used the item ID as a field ID

- Date: 2026-09-18.
- Workflow: mark UI showcase Issue #25 active and populate its GitHub Project #17 fields.
- Failed approach: passed the Issue's Project item node ID to the final `--field-id` argument while
  setting `Evidence Required`, after the preceding field updates had succeeded.
- Error signature: `Could not resolve to a node with the global id` for the item ID in
  `updateProjectV2ItemFieldValue`.
- Mutation check: Status, Area, Agentability, Risk, Work Type, and Priority were already updated;
  the failed final call did not change `Evidence Required` or create another item.
- Corrected path: resolve the live field list, use the `Evidence Required` field ID with its `Yes`
  option ID, and re-read the exact Project item after the write.
- Verification: the re-read item reports In Progress, UX, Ready, Low, Feature, P2, and Evidence
  Required Yes with one exact Issue #25 item.
- Prevention: never reuse an item node ID as a field ID; copy each field and option ID from the
  immediately preceding live `gh project field-list` response and verify the complete item once.
