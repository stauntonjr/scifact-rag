# ADR-0034: Serve the evidence inspector from the HTTP adapter

- Status: accepted
- Date: 2026-09-17
- Decider: Jack Rory Staunton, human owner
- Governing issue: [#13](https://github.com/stauntonjr/scifact-rag/issues/13)

## Context

Issues #10, #11, and #12 accepted the CLI, loopback HTTP, and loopback MCP interfaces over one
common `RagApplication` boundary. The final Phase 6 interface is a small browser surface for a
developer, researcher, or hiring manager to inspect an answer together with the exact parent
documents supplied as evidence.

The accepted FastAPI process already exposes versioned search and answer requests on DGX loopback
port 8090. It already owns validation, fixed error envelopes, strategy defaults, exact
`insufficient evidence`, ordered evidence, and citation mapping. Native HTML, CSS, DOM, and
`fetch` APIs can present those contracts without another application or runtime dependency.

## Decision

Serve one packaged evidence-inspection page from the existing FastAPI process at `/`, with CSS and
JavaScript at `/assets/scifact.css` and `/assets/scifact.js`. Browser calls are same-origin requests
to the existing `/v1/search` and `/v1/ask` endpoints. The presentation router receives no
application resolver and owns no retrieval, ranking, context-selection, generation, prompt,
evidence, or citation behavior.

The server derives the browser's retrieval and context-strategy choices and defaults from the
existing enums. The browser renders response data only as text, preserves evidence order, and
requires each answer citation to resolve to a supplied evidence document. Exact insufficiency is
presented only when the answer text is `insufficient evidence` and citations are empty; valid
retrieved evidence remains visible because the application retains the context it evaluated. A
non-insufficient answer requires at least one evidence-resolving citation. Response-shape
mismatches and request failures produce fixed presentation errors without raw exception or
response-body text.

Keep the current `api` Compose service, image, one-worker runtime, and
`127.0.0.1:8090:80` publication. Add no frontend framework, Node build, external browser asset,
runtime dependency, container, port, CORS policy, authentication, TLS, or non-loopback listener.
The UI is read-only with respect to the corpus, database, models, and configuration; Answer still
consumes configured model compute.

## Consequences

### Positive

- A reviewer can inspect answers, citations, scores, and complete supplied evidence in one page.
- CLI, HTTP, MCP, and browser interfaces retain one application and composition boundary.
- Same-origin calls avoid a new proxy or CORS decision.
- Packaged assets work from the source checkout, wheel, and existing application image.
- The deployment topology and runtime dependency set do not expand.

### Negative

- Interactive use requires JavaScript.
- UI deployment follows the API image rather than an independent frontend release cadence.
- The page is intentionally single-user and local; it supplies no identity, persistence, or
  production operations.
- Native JavaScript keeps dependencies small but does not provide a component framework if the UI
  later grows substantially.

### Risks and mitigations

- **A second application architecture:** the browser calls only the existing versioned HTTP
  operations; the presentation router cannot resolve an application.
- **Citation drift:** browser acceptance and rendering logic require all citations to occur in the
  returned evidence IDs.
- **Untrusted text becoming markup:** corpus and model fields are assigned through DOM text
  properties rather than interpreted as HTML.
- **Misleading failure detail:** validation, unavailable, and response-contract states use fixed
  messages and do not display exception text or raw bodies.
- **Packaging drift:** wheel-content and installed-distribution probes require all three assets.
- **Topology drift:** Compose validation and live port inspection retain the existing loopback
  publication and single `api` service.

## Alternatives considered

| Alternative | Reason not selected |
|---|---|
| Separate static container | Adds a service, deployment boundary, port, and proxy/CORS choice without product value |
| Server-render search and answer results | Duplicates the accepted JSON request/result flow and couples presentation to backend handlers |
| React, Vue, or another SPA framework | Adds Node, build, and dependency machinery disproportionate to one bounded page |
| Keep CLI/API only | Does not satisfy the approved interactive evidence-inspection workflow or complete Phase 6 |

## Verification and revisit trigger

Focused ASGI tests cover resource delivery, media types, resolver isolation, complete page
controls, self-contained assets, and exact strategy configuration. Existing HTTP/interface tests
continue to cover application behavior. A wheel build/install probe covers packaged resources.
Live browser acceptance covers supported, exact-insufficiency, validation, unavailable, citation,
keyboard-focus, responsive-layout, and reduced-motion states on the loopback service. The full
repository gate and affected integrations must pass before integration.

Revisit before adding multiple pages, persistent browser state, streaming, a frontend build system,
an independent deployment cadence, non-loopback users, authentication, or any browser-owned
application policy. Such a change requires a new Issue and a superseding ADR.
