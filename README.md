# Agentic Project Template

A provider-neutral engineering harness for projects developed substantially or entirely by coding agents. It turns project intent, authority, engineering loops, GitHub planning, verification, and reporting into durable repository artifacts.

This is a working v0.5, not a claim of autonomous software delivery. Humans still own product intent, risk acceptance, external side effects, and release authorization.

Current priority: the harness is feature-frozen while Issue
[#51](https://github.com/stauntonjr/agentic-project-template/issues/51) tests one small ordinary
greenfield application. Security/settings reconciliation, additional adapters, orchestration,
model analytics, and semantic merge assistance are deferred. See the
[MVP reset](docs/project/mvp-reset.md).

## Start a project

From GitHub after this repository is published as a template:

```bash
gh repo create OWNER/NEW-REPOSITORY \
  --template stauntonjr/agentic-project-template \
  --private \
  --clone
cd NEW-REPOSITORY
python3 tools/project_intake.py --interactive --mode new --apply
make check
```

For a local trial:

```bash
python3 tools/project_intake.py \
  --answers harness/fixtures/intake.answers.json \
  --target /tmp/example-agent-project \
  --apply
python3 /tmp/example-agent-project/tools/harness_check.py
```

The initializer is idempotent: it inspects existing state, preserves confirmed answers, and only
replaces generated project documents when `--apply` is used. Use `--mode adopt` for an existing
repository; it copies only missing harness files, preserves collisions, and writes
`docs/project/adoption-gaps.md` for deliberate reconciliation. Complete project context may be
sufficient for bounded planning while the harness adoption remains explicitly `provisional` until
every recorded reconciliation gap is resolved. Conversely, resolved file reconciliation does not
activate the overall harness while essential intake context is still missing. Generated intake
records expose `context_readiness`, `adoption.reconciliation_status`, and overall
`adoption.status` separately. Use `--mode gap-only` to ask only unresolved questions.

For an existing application, explicitly name its authoritative non-mutating quality command so
the adopter can compare the clean baseline with the copied overlay:

```bash
python3 tools/project_intake.py \
  --answers harness/fixtures/intake.answers.json \
  --target /path/to/existing-application \
  --mode adopt \
  --adoption-check 'make check' \
  --apply
```

The command is never inferred or run without `--adoption-check`. Its exact text, before/after exit
codes, compatibility status, and any copied paths named by the failing output are recorded in the
intake and adoption-gap report. A missing, failing baseline, timeout, or post-copy regression keeps
adoption provisional. The adopter does not edit application quality configuration, dependency
locks, or ignore rules to manufacture a pass; universal copied Python sources conform to the
locked Ruff boundary exercised by Procurement Intelligence Lab.

Copied validators import harness-owned implementations from `harness/runtime/`, not from the
application's `tools` module namespace. Historical commands under `tools/` remain thin CLI
wrappers in repositories where those paths are available. During adoption, an existing
application tool with the same filename is preserved and reported as a reconciliation collision;
the copied harness validator does not import it merely because the names match.

## What is included

| Surface | Purpose |
|---|---|
| `AGENTS.md` | Short instruction map, authority rules, source precedence, and skill routing |
| `harness/project.yaml` | Machine-readable project intent, autonomy, product version, quality, security, evidence, and lifecycle contract |
| `harness/roles/` | Provider-neutral role contracts with distinct authority and handoffs |
| `harness/loops/` | State machines with inputs, outputs, gates, retries, and stop conditions |
| `harness/runtime/` | Isolated harness-owned validator implementations used by copied entrypoints |
| `.agents/skills/` | Intake, research, execution, reporting, planning, ADR, and release workflows |
| `plugins/agentic-engineering-harness/` | Versioned Codex plugin generated from the reusable skill source |
| `.agents/plugins/marketplace.json` | Installable repository marketplace entry for the skill plugin |
| `.codex/agents/` | Thin Codex adapters for the canonical role contracts |
| `.pi/` | Experimental Pi settings, workflow prompts, and structured context-readiness questions |
| `harness/adapters/` | Machine-readable provider capabilities, mappings, limitations, and security boundaries |
| `tools/` | Dependency-free intake, validation, loop evidence, report, and GitHub audit tools |
| `.github/planning.json` | Selected GitHub Project topology plus expected labels, milestones, fields, views, and repository link |
| `harness/challenges/` | Executable historical failure-case contract |
| `docs/project/correction-log.md` | Sanitized repeatable failures, verified correction paths, and recurrence guards |
| `harness/version.json` | Version and dry-run migration boundary for derived repositories |
| `harness.lock` | Pinned upstream release, commit, per-file checksums, and ownership classes |
| `harness/ownership.json` | Upgrade policy separating upstream-owned, project-owned, and merge-required paths |
| `harness/evals/` | Forward-test scenarios for skill routing and safety behavior |
| `harness/model-stress.json` | Supplemental local-model canary, cadence, paired-lane, and evidence contract |
| `harness/model-stress/tasks/` | Versioned held-out task inputs and executable oracle contracts for paired model trials |
| `harness/telemetry.json` | Disabled-by-default, content-free outcome telemetry and retention contract |
| `docs/project/handoff.md` | Concise orientation index for fresh humans and agents |
| `docs/project/engineering-baseline.md` | Portable capability contract and profile-selected tooling boundary |

## Default engineering loop

```text
Intake -> Understand -> Plan -> Authorize -> Implement
       -> Verify -> Adversarial review -> Proportionality review
       -> Integrate -> Report -> Learn
```

The loop is evidence-producing and revision-aware. Parallel work is reserved for independent, bounded lanes. Shared Git operations, planning state, and integration remain serialized through the orchestrator.

Before each loop, the main agent performs a context-readiness gate: inspect discoverable facts,
identify gaps in intent/evidence/authority/acceptance, ask focused questions only when needed, and
record any low-risk assumptions. Each run binds included work, explicit exclusions, an assurance
boundary, complexity/budget constraints, and revision triggers. Before planning, it records a
`build`, `adopt`, `adapt`, or `defer` assessment; the separate `research-existing-solutions` skill
handles prior art, standards, licensing, security, and integration evidence when material.
Each trigger has one active assessment within a revision. Blocked research prevents planning, but
a later evidence-backed assessment can explicitly supersede it without erasing the original record.
When candidate identity changes, the same trigger may be reassessed and supersede the stale active
record; a second assessment for the same current candidate remains invalid.

Start and close a loop with:

```bash
python3 tools/loop.py start --issue 123 \
  --objective "Deliver the smallest accepted slice" \
  --criterion "AC1=The accepted behavior is demonstrated" \
  --in-scope "Implement the accepted local behavior" \
  --out-of-scope "Deployment and unrelated refactoring" \
  --assurance-boundary "One stable local repository candidate" \
  --budget-constraint "Use existing project primitives" \
  --scope-revision-trigger "New dependency or subsystem" \
  --write-path src/example.py --write-path tests/test_example.py \
  --implementer codex/implementer-session
python3 tools/loop.py record-solution-assessment --run RUN_ID \
  --trigger initial --disposition adapt --research-status completed \
  --source https://example.com/canonical-source \
  --rationale "Existing project and ecosystem primitives cover the requirement"
python3 tools/loop.py record-check --run RUN_ID --name unit \
  --command "python3 -m unittest discover -s tests -v" --status passed \
  --evidence "All targeted tests passed" --criterion AC1
python3 tools/loop.py record-release-impact --run RUN_ID \
  --level patch --reason "Backward-compatible correction to documented behavior"
python3 tools/loop.py record-verdict --run RUN_ID \
  --reviewer codex/separate-verifier-session --verdict approve \
  --criterion AC1 --evidence "Diff and raw test output independently reviewed"
python3 tools/loop.py finish --run RUN_ID
```

`start` fingerprints pre-existing dirty and untracked paths; staged index blobs and modes; `assume-unchanged` and `skip-worktree` paths; and recursively inspected submodules or embedded Git repositories. Submodule visibility is forced even when `.gitmodules` requests `ignore = all`; unsafe directory entries fail closed. Completion compares the current tree, index, nested repositories, and committed paths with that baseline; rejects undeclared writes; requires passed evidence for every unwaived criterion; requires a current product release-impact assessment; and rejects approvals made against an older requirement revision, attempt, commit, or candidate digest. Contract revisions invalidate prior waivers. A new waiver requires recorded `human:IDENTITY` provenance and a reason. The generated executive report distinguishes verified repository evidence, reported facts, and inference.

After a finding batch, the verifier's minimum repair is input rather than authorization. Every
finding must be dispositioned and a proportionality decision must record objective alignment,
scope and complexity delta, budget status, alternatives, and whether to proceed, simplify, defer,
revise the contract, or escalate. Complexity triggers and a second failed repair require an
independent scope reviewer. Contract expansion cannot proceed as an ordinary implementation retry.
Each trigger requires a matching current completed solution assessment. In-scope repair,
simplification, and narrowed claims use a new attempt; contract changes use a new revision;
candidate-bound deferral, human-accepted risk, and emergency stop use an explicit no-code batch
resolution before any later clean review. A mixed emergency batch preserves every disposition and
records exactly one next transition: contract revision when any finding requires it, otherwise a
new attempt. Neither transition can be substituted for the recorded one.

Retries are executable policy rather than prompt guidance. Failures one and two start attempts two
and three; the third consecutive failure persists the run as `blocked` without creating attempt
four. `loop.py recovery-status` inspects preserved work and optional integration ancestry without
changing Git. A retry-exhausted run resumes only from a structured `human:IDENTITY` handoff, under
a new revision whose evidence must be rebuilt. See [ADR-0007](docs/adr/0007-recovery-semantics-and-challenge-promotion.md)
and the [recovery coverage matrix](docs/project/recovery-matrix.md).

## Product versioning and engineering baseline

`harness_version` tracks the reusable control plane. `engineering.versioning.current` tracks the derived product. An upgrade of the harness never implies an application release.

Intake identifies the product's public compatibility contract and selects SemVer, CalVer, independently versioned components, or no formal product version. SemVer is not selected until an API, CLI, configuration, schema, artifact, or user-visible behavior contract is declared. Agents record a `none`, `patch`, `minor`, or `major` recommendation for each completed loop; humans retain version and release authority.

Profiles select concrete tools behind a portable capability contract: one authoritative local/CI command, runtime and dependency reproducibility, formatting, linting, type checking, tests, coverage policy, and clean package or build smoke. The Python data profile uses pinned `uv` commands with Ruff, Pyright, pytest, pytest-cov, and Hypothesis. It requires a branch-coverage baseline before release; projects ratchet that measured baseline rather than inheriting an unearned threshold. See `docs/project/engineering-baseline.md` and [ADR-0005](docs/adr/0005-product-version-and-engineering-baseline.md).

## Core commands

```bash
make check                 # Harness structure and contract validation
make test                  # Deterministic unit tests
make actions-supply-chain  # Immutable Actions and least-privilege workflow check
make smoke                 # Contracts, Actions, compilation, tests, and selected-profile checks
python3 tools/github_planning.py audit --offline
python3 tools/github_planning.py bootstrap-project       # Dry run
python3 tools/github_planning.py bootstrap-project --yes # Explicit create/copy
python3 tools/github_planning.py add-item --url ISSUE_URL       # Projects v2 dry run
python3 tools/github_planning.py add-item --url ISSUE_URL --yes # Authorized membership write
python3 tools/github_planning.py audit
python3 tools/github_planning.py apply       # Dry run
python3 tools/github_planning.py apply --yes # Explicit live mutation
python3 tools/harness_upgrade.py status
python3 tools/product_version.py           # Product source/contract drift
python3 tools/product_version.py --tag v1.2.3
python3 tools/evaluate_harness.py
python3 tools/model_stress.py check  # Validate supplemental Qwen canary policy
python3 tools/model_stress.py status # Report whether a live paired run is due; invokes no model
python3 tools/model_stress_runner.py check # Validate held-out task and runner capability; invokes no model
python3 tools/recovery_scenarios.py       # Six disposable recovery fixtures
python3 tools/run_challenges.py           # Validate candidates and approved challenges
python3 tools/run_challenges.py --run --include-candidates # Review-only candidate replay
python3 tools/loop_telemetry.py summarize --run RUN_ID # Opt-in, stdout-only by default
make pi-runtime-check       # Optional: offline Pi resource-load test, no model call
make plugin-check           # Plugin mirror, provenance, and marketplace validation
```

The live model-stress runner is deliberately separate from `make smoke`. It creates identical
disposable bare and harness-enabled repositories, limits Pi to `read` and `edit`, sanitizes its
environment, and evaluates generated code in a networkless resource-bounded Bubblewrap oracle.
It retains no raw model transcript. A one-trial run is only smoke evidence; release-candidate use
requires at least three paired trials plus independent review and human acceptance. See
[Local model-diversity canary](docs/project/model-stress.md).

Outcome telemetry is never collected automatically. The local CLI derives only loop-record facts,
accepts optional strictly allowlisted observations, distinguishes measured, provider-reported,
inferred, and unavailable values, and writes only under ignored `.harness/telemetry/` when an
output is explicitly requested. Aggregates remove run IDs and keep origins and unlike cost units
separate; there is no provider billing access, token collection, remote export, or organization
analytics. See [Outcome telemetry](docs/project/outcome-telemetry.md).

No GitHub mutation occurs without both the mutating subcommand and `--yes`. Project bootstrap can create or copy a Project, link it to the repository, and create missing fields and basic saved views. Repeated bootstrap is a no-op once state matches. Existing field/view mismatches, complex layout settings, permissions, workflows, insights, and destructive cleanup remain manual. See [GitHub planning topology](docs/project/github-planning.md) and [ADR-0006](docs/adr/0006-github-project-topology.md).

## Installable skill bundle

The seven reusable workflows are also available as the versioned
`agentic-engineering-harness` Codex plugin. `.agents/skills/` remains the canonical editable
source; the plugin contains only a generated, checksum-verified, namespace-adjusted mirror. It
does not package `AGENTS.md`, project contracts, roles, planning, provider adapters, or other
project policy.

```bash
codex plugin marketplace add stauntonjr/agentic-project-template --ref main
codex plugin add agentic-engineering-harness@agentic-project-template
```

Start a new thread and select the plugin or invoke a qualified skill such as
`$agentic-engineering-harness:project-intake`. Repository-local skills retain their unqualified
names and project scope; tested Codex 0.149.0 keeps the two namespaces distinct. See the
[installation, upgrade, collision, and uninstall contract](docs/project/skill-plugin.md).

## Pi adapter

Pi 0.84.1 is the exercised reference runtime for the experimental adapter. From the repository root, review the project-local resources and then start Pi:

```bash
pi --offline --approve
```

Pi discovers `AGENTS.md` and `.agents/skills/` natively. The adapter adds these prompt templates:

- `/harness-intake [new|adopt|refresh|gap-only]`
- `/harness-research <decision or problem>`
- `/harness-loop <accepted objective>`
- `/harness-report [run-id]`

Run `/harness-adapter` to confirm that the repository-local extension loaded.

`make pi-runtime-check` starts an isolated, offline, sessionless Pi RPC process and verifies project prompts, skills, and the extension command without invoking a model or installing packages.

The `harness_questionnaire` tool collects one to three material follow-up answers after repository inspection. It does not replace the canonical `project-intake` skill or write project state by itself.

`.pi/settings.json` deliberately does not select a model, provider, or thinking level and installs no packages. Project-local Pi extensions execute with the launching user's permissions, so trust the repository only after review and use an external sandbox for untrusted code. The adapter also does not claim Pi core supplies subagents: an authoring session cannot independently verify its own work. See `harness/adapters/pi.json` and [ADR-0003](docs/adr/0003-pi-reference-adapter.md).

## One-repository lifecycle and upgrades

The generated application repository is the operating root. The template is an upstream factory, not a submodule. Application code, `AGENTS.md`, repository-local skills, GitHub configuration, evidence, and project policy evolve together through normal pull requests. [ADR-0002](docs/adr/0002-one-repository-harness-lifecycle.md) records this boundary.

`harness.lock` provides the common base for a three-way comparison:

```text
locked upstream release + current project + newer upstream release
                         -> ownership-aware upgrade plan
```

The ownership classes are:

- `upstream-owned`: replace automatically only when the local file still matches the locked base;
- `project-owned`: never replace silently;
- `merge-required`: require an explicit reviewed resolution even when locally unchanged.

Prepare an upgrade from a local release checkout:

```bash
python3 tools/harness_upgrade.py status
python3 tools/harness_upgrade.py plan \
  --source-root /path/to/agentic-project-template-release \
  --output /tmp/harness-upgrade-plan.json
python3 tools/harness_upgrade.py apply \
  --plan /tmp/harness-upgrade-plan.json \
  --source-root /path/to/agentic-project-template-release \
  --resolve 'AGENTS.md=merged' \
  --yes
```

Every manual operation requires `PATH=keep-local`, `PATH=use-upstream`, or `PATH=merged`. Apply rechecks local and upstream hashes, updates the project version and lock, and writes a backup receipt under `.harness/upgrades/`. Rollback refuses to overwrite files changed after the upgrade:

```bash
python3 tools/harness_upgrade.py rollback \
  --receipt .harness/upgrades/VERSION/TIMESTAMP/receipt.json \
  --yes
```

For an explicitly authorized network path, `latest` reads the newest GitHub release and `fetch --ref TAG --yes` creates an isolated checkout under `.harness/upgrades/sources/`. Fetch also requires the release's `harness.release.lock` asset, verifies its repository and tag, and uses its post-commit provenance instead of trusting an embedded mutable-branch lock. The manually dispatched `Prepare harness upgrade` workflow can produce an upgrade pull request after all required resolutions are supplied. It is intentionally not scheduled.

The manually dispatched `Publish harness release` workflow is the release boundary. It requires a typed confirmation, requires the tag to match `harness/version.json`, runs the full smoke suite, generates `harness.release.lock` against the already-known source commit, and then creates the GitHub Release. No release is published merely by merging template changes.

## v0.5 boundaries

Implemented now:

- Idempotent, status-aware intake rendering.
- Context-readiness and prior-art research gates.
- Provider-neutral roles, one executable engineering loop, thin Codex adapters, and an experimental Pi adapter.
- Machine-readable provider mappings that expose native capabilities and unsupported boundaries.
- Pi-native workflow prompts and a dependency-free structured-question extension.
- Git-boundary collection and evidence-labeled executive reports.
- Local and live GitHub drift audit, shared/dedicated Project topology, idempotent create/copy, repository linking, basic saved views, missing-field creation, and non-destructive label/milestone reconciliation.
- Six deterministic recovery fixtures, a persisted three-failure stop, reviewed handoff resume,
  and candidate-versus-approved historical challenge manifests.
- Provenance locks, ownership-aware three-way upgrade plans, explicit apply, receipts, rollback, and an optional manually dispatched upgrade-PR workflow.
- Independent product-version contracts and current-revision release-impact evidence.
- Profile-driven engineering capability contracts with concrete Python defaults.
- Dependabot, dependency review, CodeQL, secret-control expectations, least-privilege permissions, and immutable Action enforcement.
- A versioned installable Codex plugin generated from the canonical reusable skills, with
  per-file transformation provenance and isolated install/collision/uninstall verification.

Deliberately deferred:

- Destructive or full-fidelity Project mutation: existing field/view replacement, permissions, workflows, insights, and complex view layout remain reviewed manual work.
- Repository rulesets, environments, secrets, permissions, and branch-protection reconciliation.
- Additional provider adapters beyond Codex and Pi.
- Automated Pi subagent/worktree orchestration; independent verification still requires a separate trusted session or reviewed extension.
- Live model scoring of the harness scenarios.
- Automatic token/cost ingestion and organization-wide analytics.
- Automatic semantic merging of project-owned or merge-required files.

These are explicit next-version candidates, not implied capabilities.

## Durable state and preferences

Repository policy belongs in `AGENTS.md`, `harness/project.yaml`, ADRs, code, tests, Issues, and pull requests. Conversation history is exploratory and non-authoritative.

Project-wide working agreements may be committed in `docs/project/working-agreements.md`. Personal preferences belong in `.harness/preferences.local.json`, which is ignored by Git, unless the user deliberately promotes one into public project policy.

## Profiles and adoption

The template ships with `generic`, `python-data`, `web-service`, and `agent-system` profiles. Profiles supply capability and tool defaults; the intake record captures every override and its status as `confirmed`, `provisional`, `assumed`, `TBD`, or `not-applicable`. A successful no-op is not a valid substitute for an unresolved check.

Dogfood a new profile on one repository before making it a template default. A useful progression is:

1. Start a greenfield project with `new` mode.
2. Adopt a mature repository with `adopt` mode.
3. Supply the application's authoritative check with `--adoption-check` and review the recorded
   before/after evidence.
4. Convert escaped defects into challenge manifests.
5. Measure human corrections, retries, escaped defects, cycle time, and accepted-change cost.

Cross-repository routing is layered, not copied wholesale. The reusable skill supplies the
governance workflow; the target repository's `AGENTS.md`, accepted Issues, code contracts, and
validation evidence supply domain authority. For example, the S3NTINEL routing evaluation keeps
its conda environment, Spark storage format, host profiling, Py4J elevation, canonical Spark path,
and generated-architecture rules local while routing the bounded change through
`execute-engineering-loop`. Project membership is an operational view and never grants repository
write, merge, or release authority. The pinned evaluation is in
`harness/fixtures/s3ntinel-routing-evaluation.json`.

Governed learning follows the same boundary. The Kortex evaluation separates published Git,
local committed, and uncommitted evidence; traces code, memory, preference, and architecture
authority; and keeps an observed directive-review improvement as an unapplied Kortex-local
proposal. Its durable handoff is sanitized and its recovery exercises run only in disposable
template repositories. No Kortex file, model, service, GitHub object, transcript, or memory store
is mutated by the evaluation. See
`harness/fixtures/kortex-governed-learning-evaluation.json` and
`docs/reports/issue-15-kortex-governed-learning.md`.

## Design influences

The research snapshot in `docs/research/landscape.md` records the current ecosystem, sources, licenses, and what this template borrows conceptually. It intentionally reimplements a small coherent control plane rather than copying another framework.

## License

MIT. See `LICENSE`.
