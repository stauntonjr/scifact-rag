# SciFact public live-demo closure plan

> **For implementation:** Use `superpowers:executing-plans` and execute this plan in order. Use a
> three explicit engineering loops: SciFact repair/application acceptance, VPS edge acceptance,
> and shared public acceptance/closure. Keep one write-capable owner per worktree, obtain an
> independent verifier for each candidate, and do not close either issue until the shared gate is
> green.

**Goal:** Resolve the remaining governance, CI, deployment-evidence, and end-to-end acceptance gaps
so `vps-srv` Issue #4 can close first and SciFact RAG Issue #27 can close second without overstating
the bounded best-effort live demo.

**Architecture:** Adapt the implementation already on `scifact-rag/main` and the deployed edge
already on `vps-srv/master`. The closure work has three ordered stages: repair and accept the
SciFact application candidate; complete and independently verify the VPS edge evidence; then run
one shared twelve-case public matrix and reconcile both repositories. Do not redesign retrieval,
generation, the browser, Traefik, Tailscale, or the public hostname.

**Tech stack:** Python 3.12, FastAPI, native HTML/CSS/JavaScript, Docker Compose, pytest, Ruff,
Pyright, GitHub Actions, GitHub Pages, Traefik v2.10, Tailscale Serve, curl, OpenSSL, and GitHub CLI.

**Governing artifacts:**

- [SciFact RAG Issue #27](https://github.com/stauntonjr/scifact-rag/issues/27)
- [VPS Issue #4](https://github.com/stauntonjr/vps-srv/issues/4)
- [Approved public-demo design](../specs/2026-09-18-public-live-demo-design.md)
- [Application implementation plan](2026-09-18-public-live-demo-application.md)
- `/home/jrs/vps-srv/docs/superpowers/plans/2026-09-18-scifact-public-edge.md`

## Verified starting state

- SciFact `main` is at `4ad2c89748d84eb2345c90207b3dcc8a02f1aada`; the focused public-demo
  implementation is present and a clean-worktree `make smoke` passes 496 non-integration tests.
- The exact-main Harness workflow fails only because `git show --check --format= HEAD` rejects the
  two-space Markdown line endings in the approved design header. CodeQL and Pages pass.
- The Pages showcase and public `/readyz` currently return HTTP 200, but those probes do not prove
  all Issue #27 acceptance criteria.
- `docs/reports/issue-27-public-live-demo.md` does not exist, Issue #27 is absent from Project #17,
  and the project/capability contracts still describe only the loopback product boundary.
- Two files claim ADR-0035. The public-demo decision was committed first; the generation-fidelity
  decision must move to ADR-0036 with every internal reference updated.
- VPS `master` is clean at `16d8fd1`; its retained report records deployed TLS, routing, body and
  rate limits, fallback, port isolation, log retention, and privacy checks. It still needs an
  independent infrastructure review and exact coverage of the shared matrix gaps.

## Frozen scope and capability disposition

- Disposition: **adapt** the current candidates; do not build replacement application or edge
  capabilities.
- `application-composition-root`, `http-api-interface`, and `web-interface` are `use-active`.
  Reconcile their existing active contracts with the already-implemented public-demo paths.
- `cli-interface` and `mcp-interface` are `use-active but unchanged`.
- Every inactive capability is `not-applicable`. Do not activate deployment, queue, authentication,
  memory, observability, or policy substitutes.
- Preserve the existing hostname, exact Pages origin, one-worker process-local slot, loopback DGX
  publication, Tailscale transport, and VPS-only public listener.
- Preserve retrieval, generation, evidence, citation, exact insufficiency, data, model, and
  scientific-evaluation semantics.
- A new hostname, dependency, service, public listener, general-purpose API promise, multi-worker
  runtime, durable quota, broad CORS, or acceptance criterion is a design-revision trigger.

## Evidence and authority rules

- Repository tests prove only deterministic contracts. Live checks prove only the exact deployed
  revisions, configuration digests, timestamps, and paths recorded with them.
- Reuse expensive or rate-limited VPS evidence only when the report records its immutable source,
  applicable configuration digest, timestamp, and unchanged behavior boundary. Otherwise rerun the
  smallest missing check.
- Never retain claim bodies, answer text, raw model output, credentials, private addresses not
  already part of the approved topology, or unredacted operational logs.
- Deployment, DNS/TLS changes, service restart, kill-switch exercise, dependency interruption,
  GitHub Project mutation, issue comments, and issue closure require explicit human authorization.
- A failed full gate ends that attempt. Batch repairs, start a new attempt, run affected checks,
  and execute exactly one new final full gate on the stable candidate.

## Engineering-loop boundaries

1. **Loop A — SciFact repair and application acceptance:** Tasks 1-5. It ends only after the DGX
   evidence report is committed, one final SciFact full gate passes, independent application review
   is approved, and exact-SHA CI is green.
2. **Loop B — VPS edge acceptance:** Tasks 6-7 in `/home/jrs/vps-srv`. It ends only after the edge
   report is committed, the exact VPS gate passes once, independent infrastructure review is
   approved, and exact-SHA CI is green when configured.
3. **Loop C — shared public acceptance and closure:** Tasks 8-10, recorded in the SciFact
   repository with an explicit VPS handoff. It owns the shared matrix, post-matrix report commits in
   both repositories, final exact-SHA checks, Project reconciliation, and ordered issue closure.

Do not treat a gate from one loop as the final gate for another. A repository mutation after a
loop's final gate requires a new attempt in that loop or belongs to the explicitly started next
loop. Final verifier approval always binds exact pushed commit and evidence digests; no tracked file
may change between that approval and the corresponding integration or closure action.

---

## Stage 1: Repair and accept the SciFact candidate

### Task 1: Add regression coverage for ADR identity and the public-demo contract catalog

**Files:**

- Modify: `tests/test_interface_contracts.py`
- Modify: `tools/harness_check.py`

- [ ] **Step 1: Write a failing ADR-identity test**

  Add a focused test that loads every `docs/adr/[0-9][0-9][0-9][0-9]-*.md`, extracts the
  filename number and first ADR heading, and requires each number and heading identifier to be
  unique and equal. Add narrow exact governing-URL assertions only for the public-demo ADR and the
  generation-fidelity ADR repaired by this plan; do not normalize historical ADR prose. Run it
  against the current duplicate ADR-0035 state and retain the failure.

  ```bash
  uv run pytest tests/test_interface_contracts.py -q
  ```

  Expected: fail with duplicate ADR-0035.

- [ ] **Step 2: Extend the existing active-contract test first**

  Update `test_http_capability_is_active_with_exact_delivery_contract` and add an equivalent exact
  assertion for `web-interface`. Require the public-demo policy, health adapter, browser assets,
  showcase assets, tests, approved design, and public-demo ADR in the appropriate implementation
  paths, plus the focused public-demo checks. Run the tests and retain the failure against the stale
  catalog.

- [ ] **Step 3: Implement the smallest portable ADR validation**

  Put the filesystem-independent parsing in `tools/harness_check.py` and invoke it from the harness
  validation path. Do not add a Markdown parser dependency or impose formatting rules unrelated to
  identifier uniqueness and explicit governing links.

- [ ] **Step 4: Run the focused red-to-green check**

  ```bash
  uv run pytest tests/test_interface_contracts.py -q
  python3 tools/harness_check.py
  uv run ruff check tools/harness_check.py tests/test_interface_contracts.py
  git diff --check
  ```

  Expected at this step: the duplicate remains red until Task 2; all other new assertions must have
  a precise, understood failure.

### Task 2: Reconcile ADR numbering, governing links, and latest-commit CI hygiene

**Files:**

- Modify: `docs/adr/0035-public-live-demo-edge.md`
- Rename: `docs/adr/0035-generation-fidelity-evaluation.md` to
  `docs/adr/0036-generation-fidelity-evaluation.md`
- Modify: `docs/project/handoff.md`
- Modify: `docs/superpowers/plans/2026-09-18-generation-fidelity-foundation.md`
- Modify: `docs/superpowers/specs/2026-09-18-generation-fidelity-foundation-design.md`
- Modify: `docs/superpowers/plans/2026-09-18-public-live-demo-application.md`
- Modify: `docs/superpowers/specs/2026-09-18-public-live-demo-design.md`

- [ ] **Step 1: Preserve the first durable decision as ADR-0035**

  Keep `0035-public-live-demo-edge.md`, change its governing Issue from #25 to #27, and preserve
  its accepted decision content. Update the older application plan's nonexistent
  `0035-bounded-public-live-demo.md` path to the actual public-demo ADR path.

- [ ] **Step 2: Move generation fidelity to ADR-0036**

  Rename the generation-fidelity ADR, change its title to ADR-0036, and update every repository
  reference. Use `rg -n '0035-generation-fidelity|ADR-0035'` to prove no generation-fidelity
  reference still claims ADR-0035. Do not alter the accepted generation-fidelity decision.

- [ ] **Step 3: Remove only the CI-breaking trailing whitespace**

  Replace the four Markdown hard-break endings in the public-demo design header with ordinary
  line breaks. Do not reflow or rewrite the approved design.

- [ ] **Step 4: Prove the regression is repaired**

  ```bash
  uv run pytest tests/test_interface_contracts.py -q
  python3 tools/harness_check.py
  git diff --check
  ```

  The working-tree whitespace check must pass. The exact latest-commit check runs only after the
  repairing commit in Task 3 because the current base commit is known to fail it.

### Task 3: Reconcile project and capability contracts and create the acceptance ledger

**Files:**

- Modify: `harness/capabilities.json`
- Modify: `harness/project.yaml`
- Create: `docs/reports/issue-27-public-live-demo.md`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/project/technical-reference.md`
- Modify: `docs/project/roadmap.md`
- Modify: `docs/project/handoff.md`
- Modify: `tests/test_interface_contracts.py`

- [ ] **Step 1: Make the contract tests fail against stale metadata**

  Require `http-api-interface` and `web-interface` to enumerate their current public-demo code,
  test, UI/showcase, ADR, and design paths. Assert the project contract describes an opt-in,
  anonymous, best-effort demo while retaining supported public API, uptime, production,
  multi-node operation, and automated DGX lifecycle as out of scope.

- [ ] **Step 2: Update only active capability contracts**

  Add the already-implemented paths and focused checks to `http-api-interface` and
  `web-interface`. Do not create or activate a deployment capability, and do not change CLI or MCP
  contracts.

- [ ] **Step 3: Reconcile the project boundary**

  Update the summary, in-scope list, deployment constraint, and public compatibility contract to
  include readiness, capabilities, fixed public-demo errors, the two environment variables, and
  Pages live-status behavior. Keep the live demo explicitly best-effort and pre-1.0.

- [ ] **Step 4: Create the durable Issue #27 ledger**

  Record current application revision, Pages URL, live URL, accepted architecture, release-impact
  recommendation `minor`, rollback boundary, and a twelve-row matrix with status `pending`. Give
  each row an evidence owner (`scifact-rag`, `vps-srv`, or `shared`), evidence location, exact
  pass condition, and stop condition. Separate deterministic, live non-inference, and live
  inference evidence.

- [ ] **Step 5: Reconcile user/operator documentation**

  Describe the recorded showcase first and the best-effort live link second. Document the two
  environment variables, endpoint/failure contracts, one-worker requirement, ownership split,
  rollback, and absence of uptime, clinical, or supported-third-party-API claims.

- [ ] **Step 6: Verify and commit the governance repair**

  ```bash
  uv run pytest tests/test_interface_contracts.py tests/test_showcase.py -q
  python3 tools/harness_check.py
  docker compose config --quiet
  python3 -m json.tool harness/capabilities.json >/dev/null
  python3 tools/github_planning.py audit --offline
  python3 tools/product_version.py
  git diff --check
  git add tools/harness_check.py tests/test_interface_contracts.py \
    docs/adr/0035-public-live-demo-edge.md \
    docs/adr/0036-generation-fidelity-evaluation.md \
    docs/adr/0035-generation-fidelity-evaluation.md \
    docs/reports/issue-27-public-live-demo.md \
    harness/capabilities.json harness/project.yaml README.md CHANGELOG.md \
    docs/project/technical-reference.md docs/project/roadmap.md docs/project/handoff.md \
    docs/superpowers/plans/2026-09-18-generation-fidelity-foundation.md \
    docs/superpowers/specs/2026-09-18-generation-fidelity-foundation-design.md \
    docs/superpowers/plans/2026-09-18-public-live-demo-application.md \
    docs/superpowers/specs/2026-09-18-public-live-demo-design.md
  git commit -m "docs: reconcile public demo closure contracts"
  git show --check --format= HEAD
  git push
  ```

### Task 4: Stabilize and independently approve the SciFact application candidate

**Files:**

- Modify only if a focused test exposes a defect: `src/scifact_rag/public_demo.py`
- Modify only if a focused test exposes a defect: `src/scifact_rag/adapters/health.py`
- Modify only if a focused test exposes a defect: `src/scifact_rag/http_api.py`
- Modify only if a focused test exposes a defect: `src/scifact_rag/web/`
- Modify only if a focused test exposes a defect: `docs/showcase/scifact-ui/`
- Modify: `docs/reports/issue-27-public-live-demo.md`

- [ ] **Step 1: Run the complete focused suite**

  ```bash
  uv run pytest tests/test_public_demo.py tests/test_health_adapters.py tests/test_http_api.py tests/test_web_ui.py tests/test_showcase.py tests/test_interface_contracts.py -q
  ```

  If it fails, use `superpowers:systematic-debugging`; add a failing regression test before code,
  repair one batch, and record a new loop attempt. Do not change accepted semantics to make a test
  pass.

- [ ] **Step 2: Record release impact and run the affected predeployment checks**

  Record `minor`: the public-demo endpoints, errors, and environment settings extend the public
  compatibility contract without breaking existing schemas. Re-run the focused suite and static
  checks on the stable predeployment candidate; this is not Loop A's final full gate:

  ```bash
  uv run pytest tests/test_public_demo.py tests/test_health_adapters.py tests/test_http_api.py tests/test_web_ui.py tests/test_showcase.py tests/test_interface_contracts.py -q
  python3 tools/product_version.py
  git diff --check
  git status --short
  ```

- [ ] **Step 3: Collect preliminary independent application findings**

  The verifier must inspect no-inference readiness, complete enum coverage, capability fallback,
  validation-before-gate ordering, zero-work busy rejection, release in every path, exact CORS,
  disabled-mode compatibility, one-worker enforcement, fixed UI errors, log privacy, and Pages
  fallback. This collection informs the repair batch but is not Loop A's final approval. Disposition
  every finding before repair.

- [ ] **Step 4: Push the reviewed predeployment candidate and inspect exact-SHA CI**

  Push the reviewed candidate and require the checks configured for the feature branch or PR,
  normally Harness and CodeQL. Defer Pages proof to the integrated `main` SHA in Step 5. A green
  run for an ancestor is insufficient. Record run URLs and SHA in the Issue #27 report:

  ```bash
  scifact_sha=$(git rev-parse HEAD)
  gh run list --repo stauntonjr/scifact-rag --commit "$scifact_sha" \
    --json databaseId,workflowName,status,conclusion,url,headSha
  ```

- [ ] **Step 5: Integrate the predeployment candidate into `main`**

  Use `superpowers:finishing-a-development-branch`: detect the worktree, confirm `main` as the base,
  present the exact merge/PR/keep choices, and obtain the human integration decision. The keep
  choice pauses this plan; deployment cannot continue from an unintegrated feature branch. For a
  local merge or merged PR, first preserve the feature commit with
  `scifact_candidate_sha=$(git rev-parse HEAD)`, then fetch the remote and prove it is an ancestor
  of the new remote `main`:

  ```bash
  git fetch origin
  scifact_main_sha=$(git rev-parse origin/main)
  git merge-base --is-ancestor "$scifact_candidate_sha" "$scifact_main_sha"
  test "$(git rev-parse origin/main)" = "$scifact_main_sha"
  gh run list --repo stauntonjr/scifact-rag --commit "$scifact_main_sha" \
    --json databaseId,workflowName,status,conclusion,url,headSha
  ```

  Require Harness, CodeQL, and Pages green on `scifact_main_sha`. Record that integrated SHA and
  deploy only source checked out at that SHA. A merge-produced SHA replaces the feature SHA as the
  candidate identity.

### Task 5: Deploy and verify only the DGX application boundary

**Files:**

- Modify: `docs/reports/issue-27-public-live-demo.md`

- [ ] **Step 1: Obtain explicit deployment authorization and inspect current state**

  Record current container/image IDs, API revision, Compose configuration, one-worker command,
  loopback binding, dependency health, GPU/workload state, and current public-demo settings. Stop
  if deployment would restart PostgreSQL, a model service, MCP, or an unrelated workload.

- [ ] **Step 2: Rebuild and enable only `api`**

  ```bash
  SCIFACT_PUBLIC_DEMO_ENABLED=true SCIFACT_PUBLIC_DEMO_PAGES_ORIGIN=https://stauntonjr.github.io docker compose up -d --build api
  ```

  Confirm only the API container changed and port 8090 remains bound to `127.0.0.1`.

- [ ] **Step 3: Run bounded loopback acceptance**

  Verify `/healthz`, `/readyz`, `/v1/capabilities`, one supported Search, one supported Answer with
  every citation resolving to displayed evidence, exact `insufficient evidence`, one unavailable
  strategy, one overlapping Search/Answer pair yielding a structured application `busy` with zero
  work for the rejected request, and post-request slot recovery. Use harmless unique identifiers
  and retain only schemas, status, citation identifiers, counts, timings, and redacted excerpts.

- [ ] **Step 4: Verify privacy and record immutable deployment evidence**

  Search API/Uvicorn logs for the unique identifiers and require zero claim/body matches. Record
  exact app revision, built image digest, container ID, settings names and non-secret values,
  Compose digest, timestamps, commands, results, and rollback command.

- [ ] **Step 5: Commit the Loop A evidence candidate**

  ```bash
  git add docs/reports/issue-27-public-live-demo.md
  git commit -m "docs: record public demo application acceptance"
  git show --check --format= HEAD
  ```

- [ ] **Step 6: Integrate the Loop A report commit into `main`**

  Use `superpowers:finishing-a-development-branch` again and obtain the human merge/PR/keep
  decision. The keep choice pauses Loop A. Record `scifact_report_candidate_sha=$(git rev-parse
  HEAD)` before integration. After the local merge or PR merge and authorized push, require:

  ```bash
  git -C /home/jrs/scifact-rag fetch origin
  scifact_main_sha=$(git -C /home/jrs/scifact-rag rev-parse origin/main)
  git -C /home/jrs/scifact-rag merge-base --is-ancestor "$scifact_report_candidate_sha" "$scifact_main_sha"
  test "$(git -C /home/jrs/scifact-rag rev-parse main)" = "$scifact_main_sha"
  ```

- [ ] **Step 7: Run Loop A's one final full gate on integrated `main`**

  Stop if the main worktree contains unrelated changes. Run exactly once on `scifact_main_sha`:

  ```bash
  cd /home/jrs/scifact-rag
  make smoke
  python3 tools/product_version.py
  git diff --check
  git status --short
  gh run list --repo stauntonjr/scifact-rag --commit "$scifact_main_sha" \
    --json databaseId,workflowName,status,conclusion,url,headSha
  ```

  Require Harness, CodeQL, and Pages green on `scifact_main_sha`, and require the Pages deployment
  to identify that same integrated revision.

- [ ] **Step 8: Obtain final independent approval of Loop A's immutable candidate**

  Give the verifier the exact pushed commit, report digest, deployed app/image/config digests, and
  exact-SHA CI results. Record the verdict in the engineering-loop record, not by modifying a
  tracked file. If the verdict requires a tracked repair, start a new attempt and repeat the final
  gate, commit, push, CI, and review. Finish Loop A only when the verifier approves the exact
  immutable candidate.

---

## Stage 2: Complete and independently verify the VPS edge

### Task 6: Open a fresh VPS closure loop and qualify retained evidence

**Files in `/home/jrs/vps-srv`:**

- Modify: `docs/reports/scifact-public-edge.md`

- [ ] **Step 1: Start from a clean `master` worktree**

  Fetch and record the exact local and remote revision. Preserve unrelated live-checkout drift.
  Start a fresh engineering loop scoped to Issue #4 closure evidence; do not reopen architecture or
  mutate live infrastructure during intake.

- [ ] **Step 2: Inventory the deployed edge immutably**

  Record repository revision, live Traefik image/version, live/fallback file SHA-256 digests,
  watched-file digest, static configuration digest, certificate identity/expiry, DNS answer,
  Tailscale Serve status, resolver configuration, installed logrotate digest, and last-restart
  time. Redact secrets.

- [ ] **Step 3: Disposition every retained check**

  For TLS, public readiness/Search/Answer, 32 KiB rejection, separate rate buckets, fallback,
  external-port isolation, rotation, and privacy, mark `reuse-valid` only when the current inventory
  proves its behavioral inputs unchanged. Otherwise mark `rerun-required`. Do not consume a live
  rate bucket merely to refresh a timestamp.

### Task 7: Fill the edge-specific evidence gaps and obtain independent review

**Files in `/home/jrs/vps-srv`:**

- Modify: `docs/reports/scifact-public-edge.md`

- [ ] **Step 1: Run deterministic edge checks**

  ```bash
  python3 tests/scifact-edge/check_static.py
  git diff --check
  git status --short
  ```

- [ ] **Step 2: Verify the true upstream-outage fallback**

  With explicit authorization and a pre-recorded rollback, interrupt only the SciFact upstream path
  so Traefik receives 502 or 504. Require the public response to preserve that 502/504 status while
  serving the Pages offline body via `scifact-offline`; a deliberate fallback-file swap alone does
  not prove this middleware path. Restore the upstream and require `/readyz` 200. Stop if the
  isolation cannot guarantee unrelated routes and workloads remain untouched.

- [ ] **Step 3: Verify the kill switch and unrelated-route invariant**

  Activate the SciFact fallback file, require the recorded offline page, verify one named unrelated
  HTTPS route before and after, restore the exact live-file digest, and require public readiness.
  Record timestamps and digests, not configuration secrets.

- [ ] **Step 4: Collect preliminary independent infrastructure findings**

  The verifier must inspect router/middleware scope, TLS/DNS, direct-remote-address rate identity,
  body bound, separate Search/Answer buckets, 502/504-only fallback, mutual exclusion of live and
  fallback files, persistent Tailscale DNS, no public DGX/model/database/MCP ports, log retention,
  privacy, rollback, and unrelated-service isolation. This is a collection pass, not Loop B's final
  approval. Disposition and repair findings in one batch.

- [ ] **Step 5: Finalize and commit the VPS report**

  Record exact commands, evidence reuse decisions, live revision/digests, review verdict, residual
  best-effort risks, and rollback. Run affected checks and commit the stable candidate:

  ```bash
  python3 tests/scifact-edge/check_static.py
  git diff --check
  git add docs/reports/scifact-public-edge.md
  git commit -m "docs: complete SciFact edge acceptance"
  git show --check --format= HEAD
  ```

- [ ] **Step 6: Integrate the Loop B candidate into `master`**

  Use `superpowers:finishing-a-development-branch`, confirm `master` as the base, and obtain the
  human merge/PR/keep decision. The keep choice pauses Loop B. Record
  `vps_candidate_sha=$(git rev-parse HEAD)` before integration. After the local merge or PR merge
  and authorized push, require:

  ```bash
  git -C /home/jrs/vps-srv fetch origin
  vps_master_sha=$(git -C /home/jrs/vps-srv rev-parse origin/master)
  git -C /home/jrs/vps-srv merge-base --is-ancestor "$vps_candidate_sha" "$vps_master_sha"
  test "$(git -C /home/jrs/vps-srv rev-parse master)" = "$vps_master_sha"
  ```

- [ ] **Step 7: Run Loop B's one final gate on integrated `master`**

  Stop if the master worktree contains unrelated changes. Run exactly once:

  ```bash
  cd /home/jrs/vps-srv
  python3 tests/scifact-edge/check_static.py
  git diff --check
  git status --short
  gh run list --repo stauntonjr/vps-srv --commit "$vps_master_sha" \
    --json databaseId,workflowName,status,conclusion,url,headSha
  ```

  Require configured exact-SHA CI to be green.

- [ ] **Step 8: Obtain final independent approval of Loop B's immutable candidate**

  Give the verifier the exact pushed commit, edge-report digest, deployed Traefik/config digests,
  and exact-SHA CI result when configured. Record the verdict in the engineering-loop record without
  changing tracked files. A required tracked repair starts a new attempt and repeats the final gate,
  commit, push, CI, and review. Finish Loop B only after approval. Leave Issue #4 open until Stage 3
  passes.

---

## Stage 3: Run shared acceptance and close in dependency order

### Task 8: Execute the shared twelve-case public matrix

**Files:**

- Modify: `docs/reports/issue-27-public-live-demo.md`
- Modify in `/home/jrs/vps-srv`: `docs/reports/scifact-public-edge.md`

Use a single dated session and the exact deployed revisions/digests from Tasks 5 and 7. Run the
cases in the order below to avoid exhausting rate buckets before functional checks.

| # | Case | Exact pass condition | Owner |
|---:|---|---|---|
| 1 | DNS and TLS | Public DNS resolves as designed; trusted certificate matches hostname and is current | `vps-srv` |
| 2 | Supported Answer | HTTP 200 `answer/v1`; every citation ID resolves to evidence displayed in that response | shared |
| 3 | Insufficiency | Exact accepted `insufficient evidence`; no fabricated citation or evidence linkage | `scifact-rag` |
| 4 | Search | HTTP 200 `search/v1` through the public edge using an advertised available strategy | shared |
| 5 | Unavailable strategy | Capability is visible and disabled in UI; direct valid request returns fixed 503 `unavailable` | `scifact-rag` |
| 6 | Shared slot | Overlapping Search and Answer produce one structured app 429 `busy`; rejected request performs zero probe/resolution/inference work | `scifact-rag` |
| 7 | Separate limits | Retained or fresh evidence proves Search and Answer use distinct configured buckets and edge 429 includes bounded retry behavior | `vps-srv` |
| 8 | Dependency recovery | Owner-selected dependency loss yields fixed degraded/unavailable behavior without inference, preserves the submitted claim in the UI, and exposes no raw body/internal error; restoration returns ready and the preserved claim can be retried successfully | shared |
| 9 | DGX outage | Real upstream failure preserves HTTP 502/504 while serving the Pages offline body; direct Pages showcase stays HTTP 200; restoration returns ready | shared |
| 10 | Kill switch | SciFact fallback works and restores by digest; named unrelated VPS route is unchanged | `vps-srv` |
| 11 | Port isolation | External scan exposes only intended VPS 80/443; DGX app, DB, MCP, and model ports remain closed | `vps-srv` |
| 12 | Log privacy | Unique harmless identifiers appear in neither VPS access logs nor DGX API logs; no body/raw output retained | shared |

- [ ] **Step 1: Start Loop C and freeze the session manifest**

  Start the shared public acceptance/closure loop in the SciFact repository and record the completed
  Loop A and Loop B handoffs. Record date/time, client vantage, SciFact commit/image/config digest,
  VPS commit/Traefik/config digest, Pages deployment SHA, and evidence-retention rules before the
  first request.

- [ ] **Step 2: Run cases 1-6**

  Use unique harmless identifiers and enough timing metadata to distinguish application `busy`
  from edge rate limiting. Stop on a schema mismatch, unresolved citation, fabricated citation,
  unexpected inference, or changed deployed revision.

- [ ] **Step 3: Run or cite cases 7-12**

  Reuse only Task 6 evidence marked `reuse-valid`. Obtain explicit authorization immediately before
  dependency interruption, upstream outage, or kill-switch mutation. Restore and verify after each
  mutation before proceeding.

- [ ] **Step 4: Assemble the cross-repository verification packet**

  Assemble both reports, the immutable revision/digest manifest, redacted results, and the accepted
  design. Do not request the final verdict until both repositories have committed and pushed these
  files and their exact-SHA checks are complete.

- [ ] **Step 5: Mark rows accepted only from evidence**

  Each provisionally accepted row must name its command/procedure, timestamp, revision/digest, and
  redacted result. Leave unsupported rows `pending` or `failed`; never convert availability or a
  smoke probe into acceptance of a different row. Final acceptance remains contingent on the
  immutable-candidate verdict in Task 9.

- [ ] **Step 6: Commit the post-matrix VPS evidence**

  In `/home/jrs/vps-srv`, run the affected deterministic checks, commit the finalized shared rows,
  and bind the report to its new exact revision:

  ```bash
  python3 tests/scifact-edge/check_static.py
  git diff --check
  git add docs/reports/scifact-public-edge.md
  git commit -m "docs: record shared SciFact public acceptance"
  git show --check --format= HEAD
  ```

- [ ] **Step 7: Integrate the post-matrix VPS commit into `master`**

  Use `superpowers:finishing-a-development-branch` and obtain the human merge/PR/keep decision; the
  keep choice pauses Loop C. Record `vps_matrix_candidate_sha=$(git rev-parse HEAD)` before
  integration. After the local merge or PR merge and authorized push, require:

  ```bash
  git -C /home/jrs/vps-srv fetch origin
  vps_matrix_master_sha=$(git -C /home/jrs/vps-srv rev-parse origin/master)
  git -C /home/jrs/vps-srv merge-base --is-ancestor "$vps_matrix_candidate_sha" "$vps_matrix_master_sha"
  test "$(git -C /home/jrs/vps-srv rev-parse master)" = "$vps_matrix_master_sha"
  ```

- [ ] **Step 8: Run Loop C's final VPS gate on integrated `master`**

  Stop on unrelated worktree changes, then run exactly once:

  ```bash
  cd /home/jrs/vps-srv
  python3 tests/scifact-edge/check_static.py
  git diff --check
  git status --short
  gh run list --repo stauntonjr/vps-srv --commit "$vps_matrix_master_sha" \
    --json databaseId,workflowName,status,conclusion,url,headSha
  ```

  Require configured exact-SHA CI to be green. Record `vps_matrix_master_sha` in the SciFact report;
  the earlier Loop B SHA is not sufficient for closure after matrix evidence changes.

### Task 9: Reconcile final SciFact evidence and require exact-SHA gates

**Files:**

- Modify: `docs/reports/issue-27-public-live-demo.md`
- Modify: `docs/project/handoff.md`
- Modify: `docs/project/roadmap.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Record the accepted boundary**

  State the final URLs, both repository revisions, deployment/config/image digests, twelve
  provisionally accepted rows, verification packet, best-effort limitations, rollback, and
  no-release decision. Keep the release-impact recommendation `minor`; do not tag, publish, or bump
  a version without separate human release authority.

- [ ] **Step 2: Recheck Pages and the live UI in a public browser**

  Verify desktop and narrow layouts, live readiness state, recorded showcase access, evidence
  expansion, disabled options, busy/limited/unavailable/offline messages, and no raw error body.
  Record observations without screenshots containing claim text unless explicitly authorized.

- [ ] **Step 3: Commit the final SciFact evidence candidate**

  ```bash
  git add docs/reports/issue-27-public-live-demo.md docs/project/handoff.md docs/project/roadmap.md CHANGELOG.md
  git commit -m "docs: accept the bounded public live demo"
  git show --check --format= HEAD
  ```

- [ ] **Step 4: Integrate the final SciFact commit into `main`**

  Use `superpowers:finishing-a-development-branch` and obtain the human merge/PR/keep decision; the
  keep choice pauses closure. Record `scifact_closure_candidate_sha=$(git rev-parse HEAD)` before
  integration. After the local merge or PR merge and authorized push, require:

  ```bash
  git -C /home/jrs/scifact-rag fetch origin
  scifact_closure_main_sha=$(git -C /home/jrs/scifact-rag rev-parse origin/main)
  git -C /home/jrs/scifact-rag merge-base --is-ancestor "$scifact_closure_candidate_sha" "$scifact_closure_main_sha"
  test "$(git -C /home/jrs/scifact-rag rev-parse main)" = "$scifact_closure_main_sha"
  ```

- [ ] **Step 5: Run Loop C's final SciFact gate on integrated `main`**

  Stop on unrelated main-worktree changes. Run exactly once on `scifact_closure_main_sha`:

  ```bash
  cd /home/jrs/scifact-rag
  make smoke
  python3 tools/product_version.py
  git diff --check
  git status --short
  gh run list --repo stauntonjr/scifact-rag --commit "$scifact_closure_main_sha" \
    --json databaseId,workflowName,status,conclusion,url,headSha
  ```

  Require Harness, CodeQL, and Pages green on `scifact_closure_main_sha`. Re-read the deployed Pages
  revision and confirm it matches that integrated SHA before any closure action.

- [ ] **Step 6: Obtain final cross-repository approval against exact immutable commits**

  Give the verifier the final SciFact and VPS commit SHAs, both report digests, deployed
  image/config/Pages digests, exact-SHA CI results, and all twelve row packets. Require one
  deduplicated verdict by row plus an overall approval. Record it in Loop C without modifying either
  repository. If any tracked file or behavior-affecting deployment input changes, invalidate the
  affected evidence, start a new attempt, and repeat its gate, commit, push, CI, and review.

### Task 10: Reconcile GitHub planning and close the dependency chain

**External state:** GitHub Issues and SciFact Project #17.

- [ ] **Step 1: Re-read both open issues and current Project membership**

  Confirm no new comments or acceptance changes appeared. Audit Project #17. Do not repair
  unrelated label, milestone, field, or view drift as part of this closure.

  ```bash
  gh issue view 27 --repo stauntonjr/scifact-rag --json number,state,title,body,comments,projectItems,url
  gh issue view 4 --repo stauntonjr/vps-srv --json number,state,title,body,comments,projectItems,url
  python3 tools/github_planning.py audit
  ```

- [ ] **Step 2: Add Issue #27 to Project #17 with the supported workflow**

  Preview first, obtain explicit authorization, then execute:

  ```bash
  python3 tools/github_planning.py add-item --url https://github.com/stauntonjr/scifact-rag/issues/27
  python3 tools/github_planning.py add-item --url https://github.com/stauntonjr/scifact-rag/issues/27 --yes
  ```

  Inspect the returned item and resolve live IDs rather than copying guessed IDs. Set only these
  contract-backed values: `Status=Done`, `Area=Operations`, `Work Type=Feature`, `Priority=P1`,
  `Risk=High`, `Agentability=Human Only`, and `Evidence Required=Yes`:

  ```bash
  (
    set -euo pipefail
    gh project view 17 --owner stauntonjr --format json > /tmp/scifact-project.json
    gh project field-list 17 --owner stauntonjr --format json > /tmp/scifact-fields.json
    gh project item-list 17 --owner stauntonjr --limit 200 --format json > /tmp/scifact-items.json
    project_id=$(jq -er 'if (.id | type == "string") and (.id | length > 0) then .id else error("project id") end' /tmp/scifact-project.json)
    item_id=$(jq -er '[.items[] | select(.content.repository == "stauntonjr/scifact-rag" and .content.number == 27)] | if length == 1 then .[0].id else error("Issue 27 item count") end' /tmp/scifact-items.json)
    : > /tmp/scifact-field-edits.tsv
    for assignment in "Status=Done" "Area=Operations" "Work Type=Feature" "Priority=P1" \
      "Risk=High" "Agentability=Human Only" "Evidence Required=Yes"; do
      field_name=${assignment%%=*}
      option_name=${assignment#*=}
      field_id=$(jq -er --arg name "$field_name" '[.fields[] | select(.name == $name)] | if length == 1 then .[0].id else error("field count") end' /tmp/scifact-fields.json)
      option_id=$(jq -er --arg field "$field_name" --arg option "$option_name" '[.fields[] | select(.name == $field) | .options[] | select(.name == $option)] | if length == 1 then .[0].id else error("option count") end' /tmp/scifact-fields.json)
      printf '%s\t%s\t%s\t%s\n' "$field_name" "$option_name" "$field_id" "$option_id" >> /tmp/scifact-field-edits.tsv
    done
    test "$(wc -l < /tmp/scifact-field-edits.tsv)" -eq 7
    awk -F '\t' 'NF != 4 || $1 == "" || $2 == "" || $3 == "" || $4 == "" {exit 1}' /tmp/scifact-field-edits.tsv
    while IFS=$'\t' read -r field_name option_name field_id option_id; do
      gh project item-edit --id "$item_id" --project-id "$project_id" \
        --field-id "$field_id" --single-select-option-id "$option_id"
    done < /tmp/scifact-field-edits.tsv
    gh project item-list 17 --owner stauntonjr --limit 200 --format json > /tmp/scifact-items-final.json
    jq -e '[.items[] | select(.content.repository == "stauntonjr/scifact-rag" and .content.number == 27)] | if length == 1 then .[0] else error("final Issue 27 item count") end | select(.status == "Done" and .area == "Operations" and .["work Type"] == "Feature" and .priority == "P1" and .risk == "High" and .agentability == "Human Only" and .["evidence Required"] == "Yes")' /tmp/scifact-items-final.json
  )
  ```

  Every `jq -e` lookup must yield exactly one nonempty ID before the first mutation. If any lookup
  fails or is ambiguous, stop without calling `gh project item-edit` and record the current JSON for
  review.

- [ ] **Step 3: Close VPS Issue #4 first**

  Post a concise evidence comment naming the VPS revision, edge report, shared matrix, independent
  infrastructure verdict, rollback, and residual best-effort risks. Close #4 only if all edge-owned
  and shared rows are accepted. From `/home/jrs/vps-srv`:

  ```bash
  git fetch origin
  vps_sha=$(git rev-parse origin/master)
  test "$(git rev-parse master)" = "$vps_sha"
  gh issue close 4 --repo stauntonjr/vps-srv --comment \
    "Accepted at ${vps_sha}. Evidence: docs/reports/scifact-public-edge.md. The shared twelve-case matrix, independent infrastructure verdict, rollback, and residual best-effort risks are recorded there."
  gh issue view 4 --repo stauntonjr/vps-srv --json number,state,url
  ```

  Require state `CLOSED`.

- [ ] **Step 4: Close SciFact Issue #27 second**

  Post a concise evidence comment naming the SciFact revision, exact-SHA CI runs, application
  report, VPS closure, shared matrix, Pages/live URLs, independent verdicts, rollback, and no-release
  boundary. Close #27 only after #4 is closed and every row is accepted. From the SciFact
  worktree:

  ```bash
  git fetch origin
  scifact_sha=$(git rev-parse origin/main)
  test "$(git rev-parse main)" = "$scifact_sha"
  gh issue close 27 --repo stauntonjr/scifact-rag --comment \
    "Accepted at ${scifact_sha}. Evidence: docs/reports/issue-27-public-live-demo.md. Exact-SHA CI, VPS Issue #4 closure, the shared matrix, Pages/live URLs, independent verdicts, rollback, and the no-release boundary are recorded there."
  gh issue view 27 --repo stauntonjr/scifact-rag --json number,state,projectItems,url
  gh project item-list 17 --owner stauntonjr --limit 200 --format json
  ```

  Require state `CLOSED` plus the Project item `Done`.

- [ ] **Step 5: Finish all three engineering loops and preserve reports**

  Generate the loop reports from Git, recorded checks, review/verdict records, GitHub state, and
  retained reports—not conversation recollection. Clean up worktrees only after branches are
  integrated and remote evidence is confirmed. Preserve protected remote branches unless the human
  owner explicitly authorizes deletion.

## Closure blockers and stop conditions

Do not close either issue while any of these is true:

- duplicate ADR identifiers, stale governing links, or exact-main Harness failure;
- stale project/capability contracts or a missing Issue #27 acceptance report;
- no independent application or infrastructure verdict;
- an unaccepted, failed, waived without owner approval, or untraceable matrix row;
- missing deployed revision/image/config digest or a candidate changed after evidence collection;
- public citation mismatch, fabricated evidence, leaked claim/body/raw model output, or unexpected
  inference during readiness, rejection, or failure handling;
- uncertain restoration after dependency, upstream, or kill-switch exercise;
- VPS Issue #4 still open when SciFact Issue #27 closure is attempted;
- accepted feature commits are not integrated, or local/remote SciFact `main` and VPS `master` do
  not equal the recorded closure SHAs;
- exact-SHA Harness, CodeQL, or Pages not green;
- a required GitHub or infrastructure mutation lacks current explicit authorization.

If a closure blocker exposes a defect inside the accepted contract, repair it in a new attempt with
a failing regression test and rerun only affected evidence plus one final full gate. If it changes
scope, architecture, risk, or acceptance, stop and obtain a new owner decision.
