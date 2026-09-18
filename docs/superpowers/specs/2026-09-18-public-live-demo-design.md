# SciFact public live-demo design

Date: 2026-09-18  
Status: approved by the human owner; implementation and deployment unverified  
Application issue: [scifact-rag #27](https://github.com/stauntonjr/scifact-rag/issues/27)  
Edge issue: [vps-srv #4](https://github.com/stauntonjr/vps-srv/issues/4)  
Human decider: repository owner

## Objective

Publish the accepted SciFact evidence-inspection UI as a bounded, anonymous, best-effort live
demonstration at `https://scifact.ediacarian.dedyn.io`. A visitor must be able to enter a claim,
receive a grounded answer or exact insufficient-evidence result, and open the supplied evidence.

The deployment must keep SciFact application and model compute on the DGX, leave the accepted
Compose host publication bound to DGX loopback, and keep the existing static GitHub Pages showcase
available when the live service is offline. Public exposure does not turn the HTTP operations into
a generally supported third-party API or create a production-uptime commitment.

## Current evidence boundary

The following starting state was inspected before this design was frozen:

- `scifact-rag` main was clean at `0c23bbc`; the accepted FastAPI UI remains published by Compose
  only at `127.0.0.1:8090`.
- The static showcase is available at
  `https://stauntonjr.github.io/scifact-rag/showcase/scifact-ui/`.
- The VPS runs the existing Traefik v2.10 service on public ports 80 and 443, has a watched file
  provider, and already uses a deSEC certificate resolver.
- The VPS is connected to the official tailnet as `ediacarian.tail64bbe0.ts.net` with tailnet IPv4
  address `100.96.194.66`.
- The DGX is already connected to the same official tailnet.
- The VPS has about 1 GiB RAM and its active `vps-srv` checkout contains unrelated operational
  drift. This work must not absorb or clean that drift.

No Tailscale Serve mapping, public SciFact DNS record, Traefik SciFact route, certificate, or public
acceptance result existed when this design was written. This document records approved intent and
verified starting state, not deployment completion.

## Solution assessment and capability reuse

Disposition: **adapt**.

Adapt the active `application-composition-root`, `http-api-interface`, and `web-interface`
capabilities. The common application layer remains authoritative; the FastAPI and browser adapters
gain only public-demo readiness, capability, concurrency, and presentation behavior. No inactive
capability is activated and no parallel HTTP, web, deployment, or model-management implementation
is created.

Adapt the existing Traefik edge, official Tailscale, deSEC resolver, and GitHub Pages publication.
Do not add another reverse proxy, VPS application, database, queue, cache, account system, or
monitoring stack.

Relevant primary sources inspected on 2026-09-18:

- [Tailscale Serve CLI](https://tailscale.com/docs/reference/tailscale-cli/serve) documents
  tailnet-only proxying to a local `127.0.0.1` HTTP service and persistent background mode.
- [Traefik v2.10 RateLimit](https://doc.traefik.io/traefik/v2.10/middlewares/http/ratelimit/)
  documents token-bucket limits and the direct remote address as the default source criterion.
- [Traefik v2.10 Errors](https://doc.traefik.io/traefik/v2.10/middlewares/http/errorpages/)
  supports an externally hosted error page; Traefik itself does not host that page.
- [deSEC dynamic DNS guidance](https://desec.readthedocs.io/en/latest/dyndns/configure.html)
  covers record updates for the existing deSEC-managed zone.

Traefik v2.10.7 constructs each router's middleware chain independently. Its
[`InFlightReq` implementation](https://github.com/traefik/traefik/blob/v2.10.7/pkg/middlewares/inflightreq/inflight_req.go)
creates a counter when the middleware instance is constructed, while the
[`router` implementation](https://github.com/traefik/traefik/blob/v2.10.7/pkg/server/router/router.go)
builds a chain for each router. A shared named middleware on separate Search and Answer routers
therefore cannot be treated as proof of one cross-route slot. The owner approved putting that
single slot in the existing one-worker application instead.

## Scope

### Included

- The live hostname `scifact.ediacarian.dedyn.io`.
- Tailnet-only transport from the existing VPS Traefik service to Tailscale Serve on the DGX.
- Public-demo readiness and per-strategy capability contracts that perform no model inference.
- One application-level, non-blocking inference slot shared by HTTP Search and Answer.
- Existing UI controls, with unavailable strategies shown but disabled.
- Per-source-IP edge limits, a bounded request body, metadata-only access logs, seven-day log
  retention, and a SciFact-specific kill switch.
- Exact-origin readiness access from the GitHub Pages showcase and a Pages-hosted offline fallback.
- Two repository-owned implementation slices followed by one public end-to-end acceptance gate.

### Excluded

- A supported general-purpose public API, user accounts, authentication, billing, quotas backed by
  durable storage, Redis, queues, analytics, or saved claims.
- A new application, Python runtime, proxy, database, fallback server, or monitoring service on the
  VPS.
- NetBird, Cloudflare Tunnel, Tailscale Funnel, home-router forwarding, or a public DGX listener.
- Public PostgreSQL, model, reranker, MCP, or Compose application ports.
- Automatic startup, restart, repair, or shutdown of DGX workloads from the VPS.
- Retrieval, ranking, generation, evidence, citation, model, or scientific-evaluation changes.
- Broad VPS cleanup, unrelated Traefik upgrades, multi-node operation, or production uptime.

Discovery of any excluded requirement requires a design revision rather than incremental scope
growth.

## Architecture

```text
Public browser
    |
    | HTTPS scifact.ediacarian.dedyn.io
    v
Existing Traefik on the VPS
    |  TLS, path routing, per-IP rate limits, body bound, access metadata
    |
    | encrypted official Tailscale network
    v
Tailscale Serve on the DGX
    |
    | HTTP to 127.0.0.1:8090 only
    v
Existing one-worker FastAPI process
    |  readiness, capabilities, one shared inference slot, UI and HTTP adapters
    v
Existing RagApplication composition root and DGX-hosted dependencies
```

The VPS terminates public TLS but runs no SciFact code. Tailscale Serve exposes only the existing
loopback HTTP service inside the tailnet. It does not expose MCP or any model/database port and does
not manage container lifecycle.

## Responsibility split

| Boundary | Responsibility |
|---|---|
| GitHub Pages | Durable recorded showcase, live readiness check, live-demo link, and offline content |
| VPS Traefik | Public TLS, hostname/path routing, per-IP token buckets, body limit, fallback response, metadata logs, and kill switch |
| Tailscale | Encrypted private transport between the VPS and DGX and tailnet-only Serve publication |
| SciFact HTTP adapter | Readiness/capability contracts, exact-origin readiness CORS, validation, fixed errors, and the shared inference slot |
| SciFact web adapter | Capability-aware controls and understandable busy, limited, unavailable, and offline states |
| Existing application layer | Search, answer, evidence, citations, defaults, and exact insufficient-evidence behavior |
| Human operator | DGX workload lifecycle, route enablement, acceptance, rollback, and release decisions |

## Application contracts

### Liveness, readiness, and capabilities

Keep `GET /healthz` as process liveness. It must not probe PostgreSQL, model services, or
application composition.

Add `GET /readyz` as the narrow public-demo readiness operation. It returns a versioned success
body with HTTP 200 when the browser can perform at least one accepted Search path and one accepted
Answer path. It returns a fixed versioned unavailable body with HTTP 503 otherwise. Checks may use
bounded database connectivity and dependency health endpoints, but must not embed text, retrieve
documents, rerank candidates, or generate an answer.

Add `GET /v1/capabilities` as a same-origin, versioned status contract. It reports:

- overall state: `ready`, `degraded`, or `unavailable`;
- Search and Answer availability;
- every existing retrieval and generation-context strategy;
- each strategy's availability and a stable public reason code when unavailable;
- the configured default and effective available default for each strategy family.

Responses expose no internal URLs, hostnames, exception text, credentials, or raw health payloads.
Availability is advisory: a dependency can fail after the probe, and request handlers retain fixed
unavailable behavior.

Strategy names and defaults continue to come from the existing enums and default constants. A
dependency map may extend the composition/configuration boundary, but it must be keyed by those
authoritative names rather than copy the strategy catalog into the UI. If the configured default
is unavailable, the server identifies the existing supported fast fallback as the effective
default when it is healthy. If no valid path exists, the corresponding operation is disabled.

Only `/readyz` receives cross-origin access, limited to the exact GitHub Pages origin
`https://stauntonjr.github.io` with `Vary: Origin`. Search, Answer, capabilities, and UI routes do
not gain general CORS support. The public hostname remains the same-origin interactive surface.

### Public-demo configuration

Public behavior is explicitly enabled by deployment configuration rather than silently changing
every installed instance. The configuration supplies the exact Pages origin and enables the
shared HTTP inference slot. Absence of public-demo configuration preserves the accepted local
interface boundary. The implementation plan must expose the smallest typed environment contract
that represents this choice and test enabled and disabled behavior.

### Shared inference slot

The existing one-worker FastAPI process owns one non-blocking slot shared by `POST /v1/search` and
`POST /v1/ask` when public-demo mode is enabled.

Validation still occurs before handler work. A valid request attempts to acquire the slot before
resolving or composing an application. If occupied, the handler returns the existing versioned
error envelope with HTTP 429, a stable `busy` code, and no resolver or inference call. The slot is
released on every success and failure path. There is no queue and no retry.

This limit applies to HTTP Search and Answer in the public-demo process. CLI and MCP behavior is
unchanged. The accepted one-worker runtime is required; multiple workers would create multiple
process-local slots and trigger a design revisit.

### Browser behavior

The live UI always displays all existing controls. On load it reads `/v1/capabilities`, disables
unavailable options, supplies a short public explanation, and selects the effective available
default. Capability checks do not submit a claim or consume the inference slot.

The UI retains the entered claim across retryable failures and maps responses without displaying
raw bodies:

| Condition | Public behavior |
|---|---|
| Current versioned validation failure | Fixed validation explanation; preserve the existing HTTP 422 contract |
| Application `429 busy` envelope | Explain that another live request is running and invite a retry |
| Edge-generated HTTP 429 | Explain that the anonymous request allowance is exhausted and invite a later retry |
| HTTP 503 | Explain that a required dependency is temporarily unavailable |
| Network or upstream HTTP 502/504 | Explain that the live service is offline; link to the recorded showcase |
| Malformed or unexpected response | Existing fixed contract-mismatch behavior; never echo the response body |

Supported answers, exact insufficient evidence, citation resolution, and evidence ordering remain
the existing application contracts.

## Public edge

### Routing and transport

The deSEC-managed record for `scifact.ediacarian.dedyn.io` points to the VPS. Existing Traefik
serves the hostname on HTTPS and obtains its certificate through the existing deSEC resolver.

On the DGX, persistent Tailscale Serve configuration exposes an HTTP reverse proxy inside the
tailnet to `http://127.0.0.1:8090`. Traefik targets that tailnet-only listener. Public traffic is
encrypted from the browser to the VPS by TLS and from the VPS to the DGX by Tailscale. Compose
continues to publish the application only on DGX loopback.

Traefik uses separate high-priority routers for `POST /v1/ask` and `POST /v1/search`, plus a router
for readiness, capabilities, and presentation assets. No route forwards to MCP, PostgreSQL,
generator, reranker, or other model services.

### Traffic controls

Traefik applies token buckets only to inference operations:

| Operation | Average | Period | Burst |
|---|---:|---:|---:|
| Answer | 6 | 1 hour | 1 |
| Search | 30 | 1 hour | 5 |

These are replenishing token buckets, not calendar-hour accounting. UI assets, `/healthz`,
`/readyz`, and `/v1/capabilities` do not consume them.

The source criterion is Traefik's direct remote address. Do not configure a client-controlled
request header or positive `X-Forwarded-For` depth as the rate-limit identity. Requests to Search
and Answer are bounded to 32 KiB, which accommodates the existing 4,096-character claim contract
and its small JSON envelope without admitting large bodies.

The edge does not retry inference requests. Application busy and dependency failures remain
application responses; Traefik does not turn them into a queue.

### Offline fallback and kill switch

The static Pages showcase is the durable entry point. It calls `/readyz` once on page load and only
again when the visitor requests a retry. It enables **Open live demo** only on readiness success;
otherwise it retains the recording and explains that live operation is unavailable.

For unexpected upstream HTTP 502 or 504 responses, Traefik's Errors middleware obtains a small
offline page from the existing GitHub Pages publication. Traefik preserves the failure status; the
fallback body does not claim that the live request succeeded. Application HTTP 503 responses are
not replaced, so an already loaded UI can present dependency-specific unavailability.

The kill switch is a SciFact-specific dynamic-routing change that replaces the tailnet upstream
with a redirect or response to the Pages showcase. It must not stop DGX services, reset Tailscale,
reload unrelated VPS configuration, or alter another hostname. Normal and fallback routing are
repository-owned and mutually exclusive so rollback does not depend on editing the dirty active
checkout by hand.

## Privacy and retention

Submitted claims and response bodies are never written to application or VPS logs. Retained
operational fields are limited to timestamp, route, status, latency, selected public strategies,
and anonymous rate-limit behavior. Do not add cookies, browser storage, accounts, analytics, or a
usage database.

Traefik access logs retain metadata only and rotate after seven days. Error handling must not log
rejected values, raw model output, upstream bodies, internal exception text, or credentials.

## Operator lifecycle

The public edge never manages DGX workloads. The human-operated startup sequence is:

1. Start the required SciFact and model services on the DGX.
2. Confirm loopback liveness, readiness, and capabilities.
3. Confirm the Tailscale Serve mapping and the private VPS-to-DGX request path.
4. Enable the live Traefik route.
5. Run bounded public acceptance before enabling the Pages live-demo link.

For planned shutdown, switch the hostname to the fallback route before stopping DGX workloads.
For an incident, the kill switch may be applied immediately and independently of DGX access.
Neither flow grants the VPS authority to start, restart, or repair the application.

## Repository ownership

### `scifact-rag` Issue #27

Owns the public-demo application configuration, readiness and capability contracts, the shared
inference slot, capability-aware UI behavior, exact readiness CORS, Pages live-status/fallback
assets, focused tests, a new ADR superseding the applicable non-public boundaries of ADR-0032 and
ADR-0034, and project documentation reconciliation.

### `vps-srv` Issue #4

Owns official-tailnet transport configuration, the SciFact Traefik dynamic routes and services,
deSEC TLS, token buckets, body limit, access-log rotation, Pages error service, kill switch,
operator instructions, and VPS-side acceptance.

The VPS implementation must be prepared in a clean worktree. Integration copies only reviewed,
SciFact-owned files into the active operational paths. Unrelated NetBird-era files, secrets,
backups, and local drift remain untouched and uncommitted.

The two issues produce separate commits and plans. Neither may claim deployment success until the
shared public acceptance gate passes.

## Rollout

1. Implement and verify Issue #27 without changing the accepted loopback Compose publication.
2. Rebuild the DGX API service and verify local public-demo behavior.
3. Implement Issue #4 in a clean `vps-srv` worktree with the live route disabled.
4. Configure Tailscale Serve on the DGX and verify the private VPS-to-DGX path.
5. Add the DNS record, obtain the certificate, and enable the live route.
6. Run the complete public acceptance matrix.
7. Enable the Pages live-demo link only after that matrix passes.
8. Exercise the kill switch and restoration path, then retain exact acceptance evidence.

Every infrastructure mutation and public enablement remains a human-authorized action. The VPS
tailnet enrollment is already complete; it must be verified again at deployment time rather than
assumed from this design snapshot.

## Verification and acceptance

### Deterministic application checks

- `/healthz` remains isolated from dependency probes and application resolution.
- `/readyz` and `/v1/capabilities` perform no embedding, retrieval, reranking, or generation.
- Capability output contains every authoritative strategy name exactly once and exposes no
  internal endpoint or exception detail.
- Public-demo configuration is explicit and disabled-mode behavior remains compatible.
- The exact Pages origin can read readiness; arbitrary origins cannot; Search and Answer remain
  without general CORS.
- One concurrent Search or Answer occupies the shared slot; a second valid operation returns the
  fixed busy response with zero resolver/application calls; the slot is released after failure.
- The browser shows all controls, disables unavailable ones, selects the effective default, keeps
  the claim on retryable failure, and distinguishes structured busy from edge rate limiting.
- Claim and response text are absent from captured logs.
- Existing HTTP, UI, CLI, MCP, packaging, Compose, and interface-parity checks remain green.

### Deterministic VPS checks

- Traefik v2.10 accepts the exact dynamic configuration before deployment.
- Only the SciFact hostname and intended paths target the tailnet service.
- Answer and Search use their specified token buckets and direct remote-address identity.
- A body above 32 KiB is rejected before reaching the DGX.
- The Pages fallback preserves 502/504 failure status and requires no local fallback process.
- Normal and kill-switch configurations are mutually exclusive and do not alter other routes.
- Log configuration excludes bodies and rotates after seven days.

### Public end-to-end acceptance

Run against the exact integrated revisions and deployed configurations:

1. DNS and certificate validation for `https://scifact.ediacarian.dedyn.io`.
2. One supported answer with every citation resolving to displayed evidence.
3. One exact insufficient-evidence answer with no fabricated citation.
4. Search using an accepted available strategy.
5. One unavailable optional strategy displayed but disabled.
6. Two overlapping operations proving one shared inference slot and a fixed busy result.
7. Separate Answer and Search rate-limit probes at their frozen boundaries.
8. Dependency loss and restoration without claim loss or raw-error disclosure.
9. DGX unavailability with the Pages showcase still usable and the live hostname serving the
   intended failure fallback.
10. Kill-switch activation and restoration without affecting another VPS service.
11. External port inspection proving that PostgreSQL, MCP, model services, and DGX loopback port
    8090 are not public.
12. Access-log inspection proving that submitted claim text and bodies were not retained.

Acceptance evidence must distinguish deterministic fixtures from bounded live inference. Passing
configuration validation does not prove public routing; a public browser result does not prove
retention or port isolation.

## Alternatives considered

| Alternative | Reason not selected |
|---|---|
| Bind Compose directly to the DGX tailnet address | Expands the application listener boundary and couples Compose to network identity when Tailscale Serve can preserve loopback |
| Put a second SciFact application or proxy on the VPS | Consumes scarce VPS memory and duplicates runtime ownership without product value |
| GitHub Pages UI calling a cross-origin public API | Requires broad CORS and creates a separate frontend deployment contract; the accepted UI already works same-origin |
| Tailscale Funnel | Makes the DGX the public edge and bypasses the existing hostname, deSEC certificate, and Traefik controls |
| Cloudflare Tunnel | Requires a different DNS/control-plane relationship and adds an unnecessary provider |
| NetBird | Explicitly rejected by the owner in favor of official Tailscale |
| Traefik-only shared concurrency | Separate routers instantiate separate middleware chains in v2.10.7, so it does not establish one cross-route slot |
| Redis or a durable quota database | Disproportionate to one process, one DGX, anonymous best-effort availability, and non-durable limits |
| Automatic VPS-driven DGX lifecycle | Gives the edge authority over expensive workloads and conflicts with the manual operating boundary |

## Risks and mitigations

- **Anonymous resource exhaustion:** separate edge token buckets, a 32 KiB body bound, and one
  non-blocking application slot bound accepted GPU work without durable identity infrastructure.
- **Stale availability:** capability state is advisory; request handlers still fail closed with
  fixed errors, and the UI retains the claim for retry.
- **DGX outage:** Pages remains independent, the live link follows readiness, and Traefik uses the
  Pages-hosted failure body for upstream loss.
- **Sensitive log growth:** bodies are never logged, metadata rotates after seven days, and
  acceptance searches for the submitted claim.
- **VPS resource pressure:** no SciFact process, cache, queue, database, or local fallback service
  runs there.
- **Dirty operational checkout:** development occurs in a clean worktree and deployment copies
  only named reviewed files.
- **Accidental API commitment:** the UI is the supported public consumer; same-origin endpoints are
  technically reachable but remain undocumented for third-party use and receive no broad CORS or
  uptime promise.
- **Process-count drift:** the public mode requires one Uvicorn worker; multiple workers trigger a
  revisit of concurrency ownership rather than silently multiplying the slot.

## Release impact and revisit triggers

The design commit itself has no product release impact. The completed SciFact implementation is a
recommended **minor** pre-1.0 change because it adds public-demo HTTP contracts and deployment
configuration while preserving existing request/result schemas.

Revisit this design before adding authentication, durable quotas, multiple application workers,
multiple DGX nodes, streaming, background jobs, automatic lifecycle management, a supported
third-party API, independent frontend deployment, broader CORS, another public hostname, or a
production availability objective.
