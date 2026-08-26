# Project handoff

This is a concise orientation index for a fresh human or agent. It is not a transcript, decision log, or second roadmap.

## Read first

1. `AGENTS.md`.
2. `harness/project.yaml`.
3. The active GitHub Issue and Project item.
4. Linked files in `docs/adr/`.
5. The relevant repository-local skill.

## Current state

- Harness version: 0.5.0.
- Project status: template; project intake not yet accepted.
- Issue #51's ordinary greenfield proof is accepted after the bounded Issue #53 repair. Owner
  direction on 2026-08-25 sets the next sequence: add data-only inactive capability skeletons from
  S3NTINEL, Kortex, Procurement Intelligence Lab, and Macro Technical Pulse; build the separate
  `scifact-rag` greenfield application; then apply the refined template first to Procurement
  Intelligence Lab. Issues #5, #16, #19, #20, and #21 remain deferred. The live Issue #22 roadmap
  text has not yet been reconciled with this new sequence.
- The capability catalog at `harness/capabilities.json` owns optional responsibilities even while
  inactive. `AGENTS.md` requires a pre-plan catalog disposition, forbids parallel replacement, and
  reserves initial activation or supersession for explicit human approval. The catalog adds no
  capability implementation or dependency.
- Issue #53 is the sole bounded blocker found by that proof: new-project generation no longer copies
  the template-maintenance `tests/` suite into applications. Portable harness checks remain in the
  authoritative `make smoke` path; the raw template unittest stage runs only in template mode,
  while applications run their own tests through the selected quality profile.
- Latest implemented harness changes: Issue #14 enforces the three-failure stop, reviewed handoff
  resume, and a sanitized six-class recovery matrix. Issue #15 adds a read-only Kortex provenance
  and governed-learning evaluation. Issue #2 validates layered domain routing on S3NTINEL without
  mutating it; Issues #25-#27 keep adoption fail-closed, isolate copied runtime imports, and test
  application quality discovery. Issue #17 adds opt-in local outcome telemetry with explicit
  provenance, privacy and retention defaults, and a de-identified aggregation boundary.
- Issue #18 packages the seven reusable workflows as the installed SemVer-versioned
  `agentic-engineering-harness` Codex plugin while keeping repository-local skills canonical and
  project policy out of user configuration.
- Issue #55 gives that plugin a distinct patch/cache identity and extends the isolated lifecycle
  probe to byte-verify the installed GitHub planning skill and safety reference. The scope is
  distribution freshness; it deliberately does not add command interception or shell policy.
- Issue #46 adds ADR-0010 and loop schema 1.3: independent reviewers collect one deduplicated
  stable-candidate finding batch before repair, checks carry tier/duration/evidence-origin data,
  expensive retained evidence requires immutable provenance, and reported completion requires
  exactly one executed passing full gate for the final current attempt.
- Issue #49 integrated ADR-0012 and loop schema 1.4. It separates
  Issue scope from exclusions, binds assurance and budget boundaries, requires a current
  build/adopt/adapt/defer assessment before planning, and inserts finding disposition plus a
  proportionality decision before repair. Independent scope review is conditional on explicit
  complexity, scope, budget, dependency, threat-model, or repeated-repair triggers.
  Triggered reassessment must be current and completed; blocked or candidate-stale evidence can be
  superseded without deletion while same-candidate duplicates fail. Non-mutating dispositions have
  an explicit candidate-bound resolution, and mixed emergency batches preserve every disposition
  while binding exactly one next attempt or contract revision.
- Issue #21 now has an accepted local Qwen model-diversity policy, an exact machine-readable due
  contract, a dependency-free status command, and a bounded paired runner. Its versioned first
  task keeps the executable oracle outside the model-visible repository, gives identical
  disposable inputs to bare and harness-enabled Pi lanes, and retains only sanitized evidence.
  The first one-trial smoke produced no passing lane: bare timed out after 79 unavailable `run`
  calls and passed 6/7 cases; harness settled in 15.333 seconds with no unavailable-tool loop and
  passed 5/7. Review then found invalid prompt provenance and an exposed-oracle boundary in that
  first runner. The runner is repaired, but the old run remains diagnostic negative history—not an
  accepted, contract-valid baseline or harness-lift claim. A replacement three-class,
  three-trial-per-lane acceptance candidate is now complete: bare passed 0/9 and harness-enabled
  passed 1/9, with the only pass on the implementation task. The observed +1 is not a general
  harness-lift claim and remains unaccepted pending a separate human decision.
- ADR-0009 adds an explicitly selected `openai-codex/gpt-5.6-sol` frontier control through the
  existing Codex ChatGPT Pro subscription, without an OpenAI API key or a credential inside Pi's
  sandbox. It reuses the exact task bytes and paired protocol, but its evolved harness-resource
  bundle is not byte-identical to the earlier Qwen bundle; it never replaces or self-accepts the
  Qwen baseline. Exact execution results and limitations are maintained in
  `docs/reports/issue-21-gpt-5-6-sol-control.md`; this handoff intentionally does not duplicate
  volatile trial totals.
- Agentic Repo Auditor Issue #8 published the first packaged, read-only audit against pinned
  S3NTINEL commit `14ba0416` through Auditor PR #15. The exact installed CLI output is deterministic,
  the target fingerprint remained unchanged, and the report explicitly excludes application and
  runtime assessment.
- Agentic Repo Auditor Issue #13 is repaired through Auditor PR #16 at `b0fa931a`: instruction
  coverage now uses a documented token-bounded vocabulary and exact matched-term evidence while
  explicitly denying semantic-understanding claims.
- Agentic Repo Auditor Issue #12 merged through PR #17 at `a0dc7a9`: configuration schema 1.1 can
  declare a safe repository-relative JSON/YAML project contract or an explicit reasoned
  not-applicable disposition while retaining automatic harness compatibility.
- Agentic Repo Auditor Issue #14 merged through PR #18 at `09e02e9`: configuration schema 1.2 can
  declare an exact non-executed primary-check command and safe repository-relative provenance
  source, or an explicit reasoned disposition. It retains automatic harness detection and does not
  infer authority from prose or CI presence.
- Agentic Repo Auditor Issue #19 merged through PR #21 at `2365676`: the installed schema-1.2
  Auditor audited Procurement Intelligence Lab commit `0f9d1a45` with `make check` / `Makefile`
  provenance, produced byte-identical JSON and Markdown with 9 pass and 4 warn findings, and left
  the complete target snapshot unchanged. The report explicitly excludes application assessment.
- Auditor Issue #20 captures the run's one reproduced product defect: concrete confidentiality,
  authorization, token, and non-deletion guardrails are not recognized as the instruction safety
  signal without literal `safe` / `safely` / `safety` vocabulary.
- Active harness loop: Issue #21 has completed the held-out implementation, defect-repair, and
  cross-file-integration acceptance candidate. All 18 scored trials were provider-backed and in
  scope; one bare cross-file trial timed out. Independent post-run verification and a separate human
  accept/reject decision remain. Auditor Issue #20 and its application-report roadmap remain
  separate Agentic Repo Auditor work.
- Release state: not applicable.
- Publication target: public GitHub template `stauntonjr/agentic-project-template`.

## Implemented control plane

- Machine-readable project, role, loop, schema, profile, and planning contracts.
- Repository-local skills for intake, existing-solution research, execution, reporting, GitHub planning, ADRs, and release readiness.
- Codex role adapters with separated planner, explorer, implementer, verifier, and release-steward authority.
- Experimental Pi adapter with native skill discovery, workflow prompts, ignored session state, structured context questions, and explicit delegation/sandbox limitations.
- Dependency-free validators, intake rendering, loop evidence, reporting, and GitHub audit/dry-run tools.
- Criterion-linked completion gates with revision-bound verifier verdicts and content-aware baseline/write-scope enforcement.
- Batched review cycles, tiered verification timing, explicit contract-revision versus repair-attempt
  semantics, and provenance-bound reuse of expensive external evidence.
- Revision-bound scope contracts and existing-solution assessments, followed by candidate-bound
  finding disposition and proportionality review before any review-driven mutation.
- Provenance-locked, ownership-aware three-way upgrade plans with explicit apply resolutions, receipts, and rollback.
- Ten isolated forward-test scenarios covering routing, context gaps, evidence, safety behavior,
  layered domain rules, and governed learning.
- CI for the harness itself.
- Separate harness and product version contracts with current-revision release-impact reporting.
- Profile-driven quality capabilities, concrete Python defaults, repository hygiene files, and a shared local/CI command boundary.
- Dependabot, dependency review, CodeQL, least-privilege workflows, and deterministic full-SHA Action validation.
- Accepted shared-program versus dedicated-application Project topology, with Project #13 as the canonical source and additive field/view/link reconciliation.
- Disabled-by-default loop outcome telemetry that emits to stdout, rejects content-bearing input,
  and keeps written summaries local and caller-managed.
- A repository marketplace and generated `agentic-engineering-harness` plugin whose per-file
  provenance binds canonical skill sources to collision-safe namespaced distribution files.
- A sanitized correction ledger and dry-run-first Projects v2 item-membership path prevent agents
  from repeating deprecated classic-Projects command routing.
- ADR-0008 and `harness/model-stress.json` make a paired local Qwen canary due after ten loops,
  agent-control changes, or minor/major release assessment. The offline status gate and disposable
  paired runner are implemented; live evidence remains supplemental and cannot self-approve.
- ADR-0009 adds a credential-isolated ChatGPT subscription relay for an optional exact GPT-5.6 Sol
  control. Generated Pi configuration stays read-only, runtime state is ephemeral, the host OAuth
  credential never enters the model sandbox, and API-key auth is rejected.

## Open decisions

- Whether Pi should omit an empty `tools` array for OpenAI-compatible continuations remains an
  upstream/provider concern. The adapter documents a tested least-authority continuation pattern.
- Which live GitHub security settings should be reconciled automatically after the first dogfood audit.

## Active dogfood evidence

- Macro Technical Pulse Issue #6 at `b41e3bc` is the isolated application snapshot.
- Adoption preserved tracked application bytes, passed all 44 original tests, and emitted explicit
  reconciliation gaps instead of copying merge-required policy.
- Pi 0.84.1 ran intake-to-report through local SparkRun Qwen with no external spend or GitHub
  writes; research accuracy, invalid tool calls, and empty-tools compatibility gaps are recorded in
  `docs/reports/issue-3-macro-technical-pulse-dogfood.md`.
- Issue #23 added strict questionnaire sampling, a three-call unavailable-tool ceiling, and a
  reproducible live-model probe before another application dogfood begins.
- Macro Technical Pulse adopted MIT for its original source and documentation through
  [MTP PR #31](https://github.com/stauntonjr/macro-technical-pulse/pull/31), merged on 2026-08-23 as
  `1f06504d`; its default-branch CI passed and GitHub detects SPDX `MIT`. Provider, market-data,
  exchange-observation, and third-party artifact rights remain separate.
- Procurement Intelligence Lab adopt mode preserved every tracked application file at `0f9d1a4`,
  then reported 44 unresolved reconciliation gaps. Application unit, HTTP integration, clean-wheel,
  sparse-input, and all eleven executable known-bad challenge boundaries passed independently.
- Its live Project #6 audit reports no missing fields, labels, milestones, or managed views; a
  disposable pagination shim was required because host GitHub CLI 2.45 lacks `gh api --slurp`.
- The Procurement overlay remains provisional because its 44 policy and reconciliation gaps still
  require human decisions. Issues #25-#27 now cover false-active state, application tool-module
  shadowing, and copied-file quality discovery. The authoritative application checkout, separate
  wiki, GitHub Project #6, and product behavior remain unchanged.
- Issue #25 now separates context readiness from activation: adopt mode records lifecycle `adopt`,
  exact disposition counts, `context_readiness`, reconciliation status, and overall project
  activation independently. Project activation stays `provisional` until both intake context and
  every reconciliation category are clear; validation and reported completion fail closed until
  then.
- Issue #26 moves the Actions supply-chain implementation into the harness-owned
  `harness.runtime` namespace. The historical tools entrypoint remains a compatibility wrapper,
  while copied validation bypasses an incompatible application-owned module with the same filename
  and returns structured provisional-adoption evidence.
- Issue #27 exercises Procurement's exact `make check` command before and after adoption. Both
  checks pass at `0f9d1a4`; adoption records status `compatible`, while the separate 44-gap
  reconciliation state correctly remains provisional. The reusable copied Python paths also pass
  its locked Ruff 0.16.3 format and lint commands without application policy changes.
- Issue #2 pins S3NTINEL main `14ba0416` and draft PR #54 head `356281f`. A local SparkRun Pi
  routing probe read the reusable loop skill plus S3NTINEL's `AGENTS.md` and `pyproject.toml`, then
  kept its Spark execution rules repository-local. Separate zero-tool verifier and release-steward
  sessions approved inspected PR content only and returned `NOT_READY` for release. Projects #3,
  #4, and #5 have disjoint Issue membership for proposal, implementation, and GPU-migration work.
- Issue #14 adds disposable dirty-worktree, partial-loop, stale-branch, process-loss,
  retry-exhaustion, and resumable-handoff fixtures. The third failure now persists `blocked`
  without attempt four; a `human:IDENTITY` handoff starts a new evidence revision and preserves
  partial bytes. Two minimized public dogfood failures are executable challenge candidates but are
  excluded from default replay until an owner reviews their exact promotion.
- Issue #15 pins Kortex's public `master` at `e0bf62b` separately from a five-commit-ahead local
  head and three pre-existing dirty paths. Its fixture traces code, memory, preference, and
  architecture authority; keeps a directive-review lifecycle as an unapplied Kortex-local
  proposal; and replays sanitized process-loss and human-reviewed recovery without touching
  Kortex, deploying a model, or reading or writing memory stores.
- Agentic Repo Auditor Issue #8 pins S3NTINEL at `14ba0416`, publishes canonical JSON and Markdown
  with 4 pass, 8 warn, and 1 fail findings, and triages all nine non-pass results. Follow-up Issue
  #13 resolves the literal-keyword false warning; Issues #12 and #14 resolve the template-specific
  evidence limitations through explicit, fail-closed configuration. The audit changed no S3NTINEL
  file or planning state and does not claim full-application review.
- Agentic Repo Auditor Issue #19 pins Procurement Intelligence Lab at `0f9d1a45`, exercises the
  schema-1.2 primary-check declaration, and publishes canonical JSON and Markdown with 9 pass and
  4 warn findings. Three warnings remain target governance/security decisions; the false
  instruction warning is isolated in Auditor Issue #20. Neither the authoritative Procurement
  checkout, its separate wiki, nor Procurement GitHub state changed.

## Refresh protocol

Update this index only when current state, settled decisions, active work, or the recommended next loop changes materially. Link to authoritative evidence instead of duplicating it.
