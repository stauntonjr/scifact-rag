# Changelog

All notable changes to the harness are recorded here. The harness version and a derived project's product version are independent release streams.

## [0.5.0] - Unreleased

### Changed

- Added a fixed, resumable three-strategy retrieval-default comparison over the already-inspected
  validation split. The CLI validates exact dataset digests and checks the required
  operator-attested runtime-component inventory before composition, durably retains every
  per-query ranking or failure, and derives metrics plus
  BM25-to-ColBERT query transitions only from raw rows. This is internal comparative evidence; the
  product retrieval default has not changed.
- Simplified generation-context evaluation to the two distinct policies supported by the corrected
  validation: `whole-document` and `adaptive`. The legacy `top-dp-chunks` CLI value remains a
  compatibility alias for adaptive assembly, while new paired runs no longer spend a duplicate
  row or model call on it. Aggregate reporting still recognizes retained three-policy artifacts.
- Completed the corrected automatic 160-claim generation-context comparison with 480/480 retained
  rows, zero execution failures, 480 parseable verdicts, and exact response reuse for 249 duplicate
  prompts. Whole-document scores 0.8125 stance accuracy versus 0.8250 for the identical DP/adaptive
  policy, but they tie on long cases, DP does not lower median input, and it loses some gold
  evidence. Whole-document remains default; the frozen 42-response human worksheet is pending.
- Froze a 24-claim, length- and stance-stratified human groundedness review before the repaired
  validation outputs are generated. The blinded rubric separates grounding, material
  overstatement, and six scientific-context omission types from automatic stance and citation
  scores; it cannot retroactively supply the missing non-inferiority margin or authorize promotion.
- Made SciFact generation evaluation reproducible and directly scoreable without changing the
  interactive RAG prompt. Evaluation requests now use a manifest-verified prompt profile, fixed
  seed 1729, and a strict leading SUPPORT/CONTRADICT/NOT_ENOUGH_INFO verdict; raw text remains
  retained while aggregate reports count only parseable stance predictions. The paired evaluator
  also reuses a successful response for byte-identical claim/context prompts and records its source
  policy, avoiding backend nondeterminism and duplicate GPU work without suppressing failed retries.
- Retained the first fixed 160-claim, 480-row generation-context execution as diagnostic evidence.
  All rows completed, but `top-dp-chunks` and `adaptive` supplied identical context and unseeded
  temperature-0.1 sampling produced different answers. DP did not reduce median input tokens and
  lost some gold evidence, so `whole-document` remains the default; no quality promotion is claimed
  until deterministic stance output and fixed human review exist.
- Added selectable generation-context assembly after retrieval. `whole-document` remains the
  compatibility default; `top-dp-chunks` ColBERT-scores the stored raw 510-token DP views and sends
  at most two per retrieved parent; `adaptive` preserves a whole abstract only when it is one exact
  DP view and otherwise uses the same chunk policy. Parent document citations remain authoritative,
  malformed or missing views fail explicitly, and no live generation-effectiveness claim or
  default promotion is made.
- Added two opt-in component ablations on the unchanged six-generator development pool. Raw
  content-max-only ColBERT reaches nDCG 0.755459 and recall 0.870853, versus 0.759619 and 0.869055
  for the whole-title-plus-abstract control. Taking the equal mean of raw title and content lowers
  nDCG by -0.038623 to 0.716835; separately robust-normalizing those channels before the same equal
  mean lowers it by a further -0.061568 to 0.655268. The fixed comparisons identify both raw 50/50
  title fusion and especially separate robust normalization as measured losses on development,
  without a weight sweep, validation/test run, or default promotion.
- Added an opt-in fixed-pool ColBERT ablation that applies the existing robust-normalized
  title/max-content scorer to the unchanged six-generator interval pool. On the fixed 649-query
  development split, candidate recall and oracle nDCG are identical to the whole-document control,
  but nDCG changes from 0.759619 to 0.655268 (-0.104351) and recall from 0.869055 to 0.795095.
  Applying the same scorer to the prior four-generator pool changes nDCG by only +0.002063,
  locating the measured regression in the complete multiview scoring bundle rather than pool
  composition. The later component ablations above separate content-only, raw equal-mean, and
  robust-normalized equal-mean scoring. No component sweep or default promotion followed.
- Added an opt-in dual-profile nominal-coreference DP strategy that derives raw-source 112/126
  MiniLM candidate chunks and raw-source 510-token ColBERT scorer chunks from one analysis. The
  primary pool is limited to BM25, title, rewritten nominal sentences, and raw MiniLM-DP vectors;
  ColBERT separately scores title and every large content view, takes the per-document content max,
  robust-normalizes both channels per query, and ranks their equal mean. Full ingestion stores
  17,807 embedded MiniLM-DP rows and 5,573 non-embedded ColBERT-DP rows with zero tokenizer-limit or
  raw-source violations. One fixed 649-query development run reaches candidate recall 0.955059 and
  oracle nDCG 0.955886 but final nDCG 0.657331 and recall 0.795095, so the strategy remains opt-in
  without a weight sweep or default promotion.
- Separated title embeddings from every abstract-derived MiniLM representation and made fixed
  equal RRF between the dedicated title and abstract-token channels the pre-1.0 default. Expanded
  the global-interval pool to six generators and added one opt-in RankZephyr listwise scorer through
  a pinned, memory-bounded vLLM service and pinned RankLLM HTTP coordinator. MS MARCO, ColBERT, and
  RankZephyr remain independent scorers over the identical pool; no scorer fusion or parameter
  sweep is introduced. A live RankZephyr throughput probe projected roughly 3.4 hours for 160
  queries, so the owner deferred it from practical use and rejected its distilled-frontier-model
  approach; its services are stopped while the opt-in integration remains.
- Recorded one fixed exploratory comparison on all 300 already-inspected SciFact test queries. The
  six-generator pool reaches candidate recall 0.950333 and oracle nDCG 0.951169. ColBERT reaches
  nDCG 0.744417 and recall 0.852667, 0.003283 below AnswerAI's non-equivalent published full-corpus
  nDCG 0.7477; MS MARCO reaches nDCG 0.688308 and recall 0.812222. The current dedicated-title plus
  abstract-token equal-RRF default reaches only nDCG 0.548652 and recall 0.705167, making the
  default policy a revisit item without automatically changing it from reused test evidence.
- Added independent MS MARCO and ColBERT scoring over the five-generator coreference-interval
  candidate pool. The expanded pool raises candidate recall to 0.925000; MS MARCO reaches
  validation nDCG 0.701572 with recall 0.790625, while ColBERT retains nDCG 0.734958 and recall
  0.800000. Neither changed the then-current default or added a fusion.
- Added opt-in global equal-cost coreference-interval packing, three fixed BM25 packing fusions,
  and three one-at-a-time additions to the existing candidate pool. The interval pack leads the
  packers at validation nDCG 0.630108 and recall 0.762500; either coreference pack raises pooled
  candidate recall to 0.925000 and oracle nDCG to 0.926414, but equal five-channel RRF regresses.
  Representation ingestion is now document/BM25 tuple-idempotent, preventing unchanged vector
  ingestion from invalidating the VectorChord-BM25 index.
- Added opt-in MiniLM `sentence-pack` and `coref-aware-pack` representations with deterministic
  sentence boundaries, original-offset coreference cohesion, bounded 126-token fallback, and one
  frozen validation result per strategy; neither changes the default.
- Added one opt-in hosted ColBERT late-interaction scorer over the unchanged four-generator pool.
  The digest-pinned NVIDIA vLLM service loads an immutable Apache-2.0 AnswerAI checkpoint and
  explicitly right-truncates at 512 tokens. Frozen validation nDCG improves to 0.734958, but recall
  falls to 0.800000 below the guardrail, so no test run or default promotion occurred. The measured
  MiniLM/abstract length mismatch and semantic chunking follow-on are documented separately.
- Added a generic immutable candidate feature matrix, score-normalizer port, and setwise ranking
  policy boundary. One opt-in four-channel robust normalized mean uses fixed median/MAD logistic
  normalization with deterministic zero-MAD and constant-channel fallbacks. It improves pooled
  validation nDCG from 0.683622 to 0.688954 at unchanged recall 0.806250, but remains below the
  BM25/token-window leader, so no test confirmation or default promotion occurred.
- Added feature-preserving candidate generation, complete corpus-global BM25/vector rescoring,
  fixed four- and five-channel pooled RRF strategies, exact matching-passage provenance, and a
  deterministic 649/160 train development/validation partition. The shared pool reaches validation
  recall 0.906250 and oracle nDCG 0.907664, but neither fixed pooled ranker beats the validation
  BM25/token-window leader, so no test confirmation or default promotion occurred. ADR-0020 aligns
  future graph-projection ownership with Procurement Intelligence Lab without adding a dependency,
  schema, service, graph implementation, or template runtime capability.
- Added one pinned `ms-marco-MiniLM-L6-v2` cross-encoder experiment over the deduplicated top-50
  candidate union from BM25, token windows, strict coreference, and nominal coreference. A
  digest-pinned Hugging Face TEI service hosts the model on the DGX Spark GPU; the model revision,
  512-token input boundary, candidate depth, and batching ceiling are fixed, while graph work and
  default promotion remain deferred. The one 300-query run leads MRR at 0.658184 but ranks fourth
  by nDCG at 0.686962 and lowers recall versus BM25, so it remains experimental.
- Added four fixed BM25-plus-vector RRF strategies for token windows, strict coreference, nominal
  coreference, and coreference-max. All reuse symmetric top-50, `k=60` fusion with no sweep or
  weights. Nominal fusion leads nDCG@10 at 0.697360, token-window fusion leads recall@10 at
  0.842667; that exploratory public-qrels evidence did not authorize promotion at that stage.
- Migrated the PostgreSQL 17 Compose image to preserve pgvector 0.8.6 while adding
  pg_tokenizer 0.1.1 and VectorChord-BM25 0.3.0. The independent raw title-plus-abstract BM25
  strategy was the leaderboard leader at that intermediate stage with nDCG@10 0.681034 and
  recall@10 0.821889, but it did not replace the then-current default; later BM25 fusion uses one frozen
  protocol rather than tuning.
- Added independently selectable PostgreSQL keyword and strict-dense-plus-keyword RRF retrieval
  experiments without a new dependency or service. Keyword search rescues 13 strict-dense misses,
  but keyword-only and symmetric RRF underperform strict dense overall, so both remain
  experimental and did not replace the then-current default.
- Added independently selectable token-window, strict coreference-sentence, broader
  coreference-sentence, and max-fused retrieval strategies. Titles are a parallel representation,
  strategy rows coexist in PostgreSQL, and token windows remained the default pending a separate
  promotion decision. At that intermediate stage the strict strategy led the internal SciFact
  leaderboard at nDCG@10 0.618163 and recall@10 0.779500.
- Improved SciFact retrieval from nDCG@10 0.526066 and recall@10 0.661722 to 0.601929 and
  0.727944 by ranking documents over bounded overlapping MiniLM token windows. Document-level
  search results and citation IDs remain unchanged.
- Activated the product-validation challenge capability with 12 real baseline misses rescued by
  the accepted retrieval strategy; the full 300-query BEIR evaluation remains authoritative.
- Stopped new-project intake from copying the template-maintenance root `tests/` suite into derived
  applications. The raw template unittest stage now runs only in template mode; generated
  repositories retain the portable executable harness checks and run application tests through
  their selected quality profile.
- Feature-froze the harness around its implemented original core and made one time-boxed ordinary
  greenfield application the sole active proof target. Later security, provider, orchestration,
  analytics, and semantic-merge work is explicitly deferred rather than implied by the MVP.

### Added

- A dependency-free inactive-capability catalog derived from S3NTINEL, Kortex, Procurement
  Intelligence Lab, and Macro Technical Pulse. Agents must check its IDs, aliases, and claimed
  responsibilities before planning; initial activation requires human approval, and inactive
  skeletons add no implementation, runtime dependency, or CI check.
- Required, separate Issue-form fields for included scope, exclusions, assurance boundary,
  complexity and budget constraints, and scope-revision triggers.
- Loop schema 1.4 with revision-bound build/adopt/adapt/defer solution assessments, per-finding
  repair dispositions, and a candidate-bound proportionality gate before repair. Parser, sandbox,
  protocol, cryptography, concurrency, filesystem-security, dependency, write-scope, threat-model,
  budget, and repeated-repair triggers require a reviewer independent of both implementer and
  technical verifier.
- Superseding resolution for blocked or candidate-stale solution research and an explicit no-code
  finding-batch resolution for deferral, human-accepted risk, and emergency stop. Mixed emergency
  batches retain every disposition and bind exactly one deterministic next attempt or contract
  revision.
- A primary-source build-versus-adopt research note and ADR-0012, which adapt native GitHub Issue
  forms and existing loop primitives without adding an orchestration dependency.
- Batched stable-candidate independent review cycles with deduplicated findings, explicit critical
  emergency stops, tiered verification timing, immutable expensive-evidence reuse provenance, and
  exactly one executed final full gate per completed attempt.
- An explicit schema-1.2 or schema-1.3 to schema-1.4 in-flight loop migration that preserves the
  original dirty baseline instead of recreating evidence after implementation.

- Accepted shared-program versus dedicated-application GitHub Project topology, with
  Project #13 as the canonical field/view copy source.
- Live, non-destructive Project title, saved-view, and repository-link drift auditing.
- Idempotent creation of missing basic saved views through GitHub's typed API.
- Fail-closed validation for every supported write-bearing planning value and explicit
  drift for ambiguous duplicate live identities.
- A reproducible live-model Pi tool-call probe covering strict questionnaire sampling, valid reads,
  unavailable-tool ceilings, zero-tool sessions, and least-authority continuations.
- A credential-isolated ChatGPT Pro/Codex subscription control for GPT-5.6 Sol, with strict
  duplicate-key, JWT-claim, and credential-header validation; fixed loopback routing; sanitized
  upstream errors; non-secret canary substitution; and bounded request evidence without OpenAI
  API-key use.
- A layered domain-routing forward scenario and pinned S3NTINEL evaluation that keep repository
  Spark rules local while exercising reusable loop, verifier, release-steward, and Project
  ownership boundaries.
- Six sanitized disposable recovery fixtures covering dirty worktrees, partial loops, stale
  branches, agent crashes, retry exhaustion, and reviewed resumable handoffs.
- Candidate-versus-approved challenge provenance with explicit human-review promotion and two
  minimized dogfood-derived executable candidates.
- A read-only Kortex provenance and governed-learning evaluation that separates evidence tiers,
  keeps learned policy changes proposed pending human review, uses sanitized durable handoffs, and
  replays interrupted-session recovery without application or memory-store mutation.
- Opt-in, content-free per-loop outcome telemetry with explicit measurement provenance, strict
  local schemas, stdout-only defaults, retrospective observation timestamps, and a de-identified
  aggregation boundary that preserves unavailable values and unlike units.
- A SemVer-versioned `agentic-engineering-harness` Codex plugin containing the seven reusable
  workflow skills, generated from repository-local canonical sources with per-file provenance,
  collision-safe namespacing, and a repository marketplace entry.
- A sanitized failure-correction log and dry-run-first Projects v2 work-item membership command
  that verifies exact post-write membership with bounded read-only retries for visibility lag.
- An accepted local Qwen model-diversity canary policy, machine-readable cadence and evidence
  contract, and dependency-free due-status command that never invokes a model by default.
- A fail-closed held-out task contract and paired Qwen runner that freezes one resource bundle and
  clones one byte-verified seed Git repository for every lane and trial, with explicit bare versus
  harness resource loading, `read`/`edit`-only Pi authority,
  sanitized evidence, and a separate networkless resource-bounded executable oracle.
- A schema-1.1 three-class held-out corpus covering bounded implementation, defect repair, and
  cross-file integration, with task-class provenance in every sanitized runner result and
  multi-entrypoint oracle coverage that directly tests both modules in the cross-file task.
- The first one-trial paired Qwen smoke as explicitly negative evidence: neither lane passed the
  oracle; bare timed out in an unavailable-tool loop while the harness lane settled without that
  loop. No accepted baseline or general harness-lift claim is recorded.
- Independent review downgraded that first smoke to diagnostic history because its recorded prompt
  digest described an unsent field and its oracle exposed hidden answers. The runner now sends the
  exact contract prompt, evaluates one answer-free oracle case per process, bounds output while it
  is produced, closes result relationships, sanitizes tool identities, records the frozen resource
  digest, rejects symlinked task/resource roots and ancestors, and reports invocation truthfully;
  the model was not rerun as part of the repair.
- A provider-backed three-class acceptance candidate with three trials per lane and task: bare
  passed 0/9 and harness-enabled passed 1/9, an observed +1 confined to implementation. The result
  stays supplemental, unaccepted, and explicitly makes no general harness-lift claim. A Pi 0.84.1
  read-only-config credential-lock startup failure is preserved as invalidated diagnostic evidence;
  the runner now supplies an explicit non-secret synthetic API-key override.
- An optional exact `openai-codex/gpt-5.6-sol` frontier control using the existing Codex ChatGPT
  Pro subscription without an OpenAI API key. A loopback-only canary-authenticated relay keeps OAuth
  out of Pi's sandbox, fixes the upstream host and path, bounds requests and request bytes, and
  retains only sanitized provider and relay metrics. Result schema 1.3 distinguishes a token cap
  sent in the provider request from Pi Codex's runner-configuration-only value.

### Changed

- Derived intake now clears the template's live Project identity and prepares a dedicated
  one-time copy bootstrap; adopters may explicitly select a shared Project instead.
- The planning contract now requires `topology` and `canonical_source`. Existing derived
  repositories must review and add these keys before upgrading.
- Existing-repository adoption now copies only upstream-owned harness internals and records
  merge-required, workflow, test, license, changelog, and dependency-lock paths
  for explicit reconciliation instead of silently overwriting application policy.
- Engineering-loop retries now persist the fifth consecutive failure as `blocked` without creating
  attempt six. A retry-exhausted resume preserves partial work and starts a new evidence revision
  only from a structured `human:IDENTITY` handoff.
- Plugin packaging now deterministically qualifies cross-skill references while retaining
  progressively disclosed `SKILL.md` and reference files. Repository policy and application state
  remain outside the user-installed bundle.
- GitHub planning instructions now reject the deprecated classic-Projects shortcut and document
  the supported `gh project` versus typed Projects v2 GraphQL boundary.
- Release readiness now treats due Qwen canary evidence as supplemental and conditional for
  minor/major harness releases without weakening deterministic checks or human authority.
- Model-stress evidence now labels one paired trial as smoke, rejects ambiguous two-trial runs,
  treats three or more trials only as acceptance candidates, and cannot self-approve a baseline.
- Pi model-stress configuration is mounted as individually read-only files over an ephemeral
  writable agent-state directory, allowing Pi 0.84.1 to synchronize only its non-secret runtime
  canary without exposing a host credential store.

### Fixed

- The installable plugin now uses a new patch/cache identity, and its isolated lifecycle probe
  byte-verifies the installed GitHub planning skill and safety reference against the reviewed
  generated distribution.

- Adopted harness validation now imports the Actions supply-chain implementation from the
  harness-owned `harness.runtime` namespace. An incompatible application-owned
  `tools/check_actions_supply_chain.py` remains byte-for-byte intact, is reported as a
  reconciliation collision, and no longer causes the copied validator to crash during import.
- Adopt-mode dry runs and applies now record an `adopt` lifecycle, exact reconciliation disposition
  counts, `context_readiness`, and separate reconciliation and overall activation states. Project
  activation remains `provisional` until both adoption gaps and essential intake context are
  resolved; harness validation and reported loop completion fail closed until then.
- Harness validation can use a trusted application-owned GitHub planning loader when the
  application intentionally retains its own planning implementation.
- Adoption preflights every target path, rejects symlink traversal and non-directory ancestors
  before copying, preserves existing generated artifacts under non-overwriting proposal names,
  and refuses a second proposal collision.
- Greenfield template copies apply the same lexical target-root preflight before creating any
  project files.
- The Pi adapter requests strict JSON-schema tool sampling when supported and aborts after three
  consecutive unavailable-tool calls before a fourth sibling can be preflighted, while active calls
  reset the counter.
- Existing-repository adoption can explicitly run an application's authoritative quality command
  before and after copying harness files. It records the command, exit codes, compatibility, and
  implicated copied paths; missing, indeterminate, or incompatible evidence keeps activation
  provisional.
- Universal copied Python harness sources now satisfy Procurement Intelligence Lab's locked Ruff
  0.16.3 format and lint discovery without changing its configuration, lock, or ignore rules.

## [0.4.1] - 2026-08-22

### Fixed

- Live GitHub planning audit now works with supported GitHub CLI versions that do not
  provide `gh api --slurp`, while retaining zero-, single-, and multi-page JSON parsing.

## [0.4.0] - 2026-08-22

### Added

- Provider-neutral roles, skills, engineering loop, evidence reports, intake, GitHub planning, and project profiles.
- Codex and experimental Pi adapters.
- Integrity-checked write scopes, independent verifier verdicts, and provenance-locked harness upgrades.
- Configurable product-version, engineering-quality, and GitHub security contracts.
- Dependabot, dependency review, CodeQL, and immutable GitHub Actions validation.

### Security

- Completion fingerprints worktree, index, hidden index flags, submodules, and embedded repositories.
- Third-party GitHub Actions are pinned to reviewed full commit SHAs.
