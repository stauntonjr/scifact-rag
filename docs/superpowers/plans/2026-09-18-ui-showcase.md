# SciFact UI showcase implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish one honest 22-second animated GIF of the live SciFact UI, linked to a full-length
GitHub Pages video derived from the same uninterrupted master recording.

**Architecture:** Record the existing loopback UI as a fixed 1280x720 region while it calls the
real FastAPI, PostgreSQL, ColBERT, and Qwen services. Keep the lossless master outside Git; derive
one optimized GIF, MP4, poster, and WebVTT transcript as static documentation assets. Publish the
existing `docs/` directory from `main` through GitHub Pages branch deployment, with no application
or runtime change.

**Tech Stack:** Existing SciFact web UI and Docker Compose services; operating-system region
recording; ephemeral pinned FFmpeg authoring tool; static HTML/CSS; GitHub Pages from `main:/docs`.

**Spec:** [GitHub Issue #25](https://github.com/stauntonjr/scifact-rag/issues/25)

## Global constraints

- Use the corrected claim: `Side effects associated with antidepressants increase the risk of stroke.`
- Record the actual running application; never mock, inject, or replace a response or citation.
- Record one uninterrupted 1280x720 master and derive every published asset from it.
- Keep the master outside Git and commit no more than 25 MB of optimized showcase media in total.
- Produce one 960x540 GIF lasting 22 seconds and one 1280x720 MP4 preserving the complete master.
- Keep the existing DGX services loopback-only; Pages contains static media only.
- Add no frontend framework, application endpoint, Compose service, runtime dependency, or narration.
- Stop if the corrected claim does not return a valid cited answer whose citation resolves to
  displayed evidence.

---

### Task 1: Freeze capture provenance and confirm the live path

**Files:**
- Create: `docs/reports/issue-25-ui-showcase.md`

**Interfaces:**
- Consumes: exact source revision, running Compose API/PostgreSQL, hosted ColBERT and Qwen endpoints.
- Produces: frozen capture manifest containing revision, image, service health, query, strategies,
  citations, evidence IDs, and the master-file SHA-256.

- [ ] **Step 1: Inspect before changing any service**

  Record `git rev-parse HEAD`, `docker compose -p scifact-rag ps api postgres`, the API container
  image digest, `GET /healthz`, the ColBERT health endpoint, and Qwen `/v1/models`. Do not restart a
  healthy service.

- [ ] **Step 2: Preflight the corrected claim through the real answer endpoint**

  Submit one `ask-request/v1` with the accepted retrieval and whole-document context defaults.
  Require `answer/v1`, non-empty citations, and every citation in the returned evidence ID set.
  Record latency, citations, and evidence IDs. Stop on exact insufficiency or invalid citation.

- [ ] **Step 3: Confirm a recording surface**

  Prefer the connected browser-control runtime for repeatable typing and clicks while an operating-
  system region recorder captures the visible browser. If no browser is connected, require the
  human owner to record the same visible live tab with a native region recorder and provide the
  uninterrupted master; do not substitute a headless or reconstructed demo.

- [ ] **Step 4: Create the initial report boundary**

  Record the provenance fields and explicitly mark capture/media fields pending until the master
  exists. Do not claim acceptance from API evidence alone.

### Task 2: Capture one uninterrupted master

**Files:**
- External, uncommitted input: `/home/jrs/scifact-rag-showcase-master/scifact-ui-master.mov`
- Modify: `docs/reports/issue-25-ui-showcase.md`

**Interfaces:**
- Consumes: clean live page and validated corrected claim from Task 1.
- Produces: one 1280x720 master with the complete real interaction.

- [ ] **Step 1: Prepare the visible page**

  Use 150% browser zoom, collapse Advanced controls, hide unrelated browser chrome, and define an
  exact 1280x720 recording region. Reload `/` so the page begins at `Ready for a claim.`

- [ ] **Step 2: Record the fixed interaction sequence at live speed**

  - Hold on the clean page for two seconds.
  - Enter the corrected claim over roughly three seconds, then click **Answer with evidence**.
  - Preserve the complete real loading interval without cutting or accelerating it.
  - Pause on the answer, model, strategies, and citations for six seconds.
  - Click the first citation, then pause on its parent evidence card for ten seconds.
  - Hold on the evidence boundary for four seconds, then end the recording.

- [ ] **Step 3: Validate the master before editing**

  Require one continuous file, 1280x720 dimensions, the complete live loading interval, readable
  answer/evidence text, visible first-citation click, and no unrelated desktop content. Compute its
  duration and SHA-256 and record both without committing the master.

### Task 3: Derive the optimized media

**Files:**
- Create: `docs/assets/showcase/scifact-ui-answer-evidence.gif`
- Create: `docs/showcase/scifact-ui/scifact-ui-full.mp4`
- Create: `docs/showcase/scifact-ui/scifact-ui-poster.png`
- Create: `docs/showcase/scifact-ui/scifact-ui-full.vtt`
- Modify: `docs/reports/issue-25-ui-showcase.md`

**Interfaces:**
- Consumes: exact master SHA-256 from Task 2 and a recorded FFmpeg authoring version.
- Produces: 22-second GIF, full-length H.264 MP4, 1280x720 poster, and matching captions.

- [ ] **Step 1: Resolve one pinned ephemeral FFmpeg authoring binary**

  Use an isolated, pinned authoring environment rather than adding FFmpeg to project dependencies.
  Record package version, binary version, and binary SHA-256 in the report before conversion.

- [ ] **Step 2: Encode the full video**

  Re-encode the complete master to 1280x720 H.264, `yuv420p`, web-optimized MP4 with no audio,
  preserving its exact timeline. Target 10-15 MB.

- [ ] **Step 3: Encode the GIF from master seconds 0-22**

  Scale to 960x540 at 12 fps, generate one optimized palette, apply that palette with bounded
  dithering, and loop continuously. Preserve claim entry, submission, the start of the real loading
  state, the answer pause, and the first-citation evidence reveal. If the live loading interval
  prevents those events from fitting in 22 seconds, remove only a middle section of unchanged
  loading frames and disclose the elapsed-time edit in the GIF and page captions. Do not accelerate
  inference, alter result frames, or reconstruct application behavior. Target 8-10 MB.

- [ ] **Step 4: Extract the poster and write captions**

  Extract the poster from the answer-pause interval. Write WebVTT cues for claim entry, live answer
  generation, answer/citations, first evidence, and the research-only boundary.

- [ ] **Step 5: Verify media mechanically and visually**

  Require the exact durations and dimensions above, combined committed media below 25 MB, matching
  master-derived content, readable text at README width, and correct citation/evidence identity.

### Task 4: Build the static Pages showcase

**Files:**
- Create: `docs/.nojekyll`
- Create: `docs/showcase/scifact-ui/index.html`
- Create: `docs/showcase/scifact-ui/showcase.css`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/project/handoff.md`

**Interfaces:**
- Consumes: media from Task 3.
- Produces: self-contained static showcase at
  `https://stauntonjr.github.io/scifact-rag/showcase/scifact-ui/` and a linked README hero.

- [ ] **Step 1: Write the self-contained showcase page**

  Use native HTML and CSS only. Include a `<video controls preload="metadata">` element, poster,
  WebVTT captions, corrected claim, exact recording revision/date, repository link, public-corpus
  description, and research-only/non-clinical limitation.

- [ ] **Step 2: Add the linked README hero**

  Add a concise `Live UI showcase` section after `What the project demonstrates`. Wrap the GIF in
  a Markdown link to the Pages URL and provide an adjacent text link for accessibility.

- [ ] **Step 3: Reconcile durable project documentation**

  Record the showcase and static-publication boundary in the changelog and handoff. Do not describe
  the DGX service as public or production-ready.

- [ ] **Step 4: Verify static routes locally**

  Serve `docs/` through a local static server and require HTTP 200 for the page, GIF, MP4, poster,
  captions, and stylesheet. Parse every local link and media reference; require all files to exist.

### Task 5: Verify, publish, and reconcile

**Files:**
- Modify: `docs/reports/issue-25-ui-showcase.md`

**Interfaces:**
- Consumes: stable candidate, complete report, approved publication target.
- Produces: exact public Pages evidence, independent verdict, integrated main revision, and closed
  Issue/Done Project item.

- [ ] **Step 1: Run targeted artifact checks**

  Check HTML semantics and links, media duration/dimensions/codecs, total size, SHA-256 manifest,
  README target, `git diff --check`, and the repository harness.

- [ ] **Step 2: Record release impact and run the final full gate once**

  Record `none` product release impact because this adds static showcase documentation without
  changing the declared application contracts. Run `make smoke` exactly once on the final candidate.

- [ ] **Step 3: Obtain independent review**

  Review the actual media and page for claim correctness, live-result provenance, citation/evidence
  consistency, readability, accessibility, static-only boundary, documentation accuracy, and link
  integrity.

- [ ] **Step 4: Integrate the approved candidate**

  Fast-forward `main` under the owner's standing option 1, push, and wait for exact-SHA Harness and
  CodeQL success.

- [ ] **Step 5: Enable and verify GitHub Pages**

  Configure GitHub Pages to deploy from `main:/docs`, as recommended for a static site with no build
  process. Poll the Pages deployment and require the public page and all four media assets to return
  successfully. This external publication is already authorized by the owner for Issue #25.

- [ ] **Step 6: Close planning and clean the workspace**

  Update the report with public URLs and deployment evidence, reconcile Issue #25 and Project #17
  to Done, then remove the clean worktree and local feature branch. Preserve a protected remote
  branch if repository rules refuse deletion.
