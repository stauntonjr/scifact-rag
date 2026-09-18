# ADR-0035: Publish an opt-in public demo edge

- Status: accepted
- Date: 2026-09-18
- Decider: Jack Rory Staunton, human owner
- Governing issue: [#25](https://github.com/stauntonjr/scifact-rag/issues/25)

## Context

The accepted SciFact prototype is a DGX-local application. The project now needs a public,
reviewable showcase without moving inference, PostgreSQL, or the application image onto the small
VPS. GitHub Pages can host the durable recording, while a separate HTTPS edge can expose the live
application only when the owner enables it.

## Decision

Keep the Pages showcase static and make the live path explicitly opt-in through the existing
single-worker `api` service. The API reads `SCIFACT_PUBLIC_DEMO_ENABLED` (default `false`) and an
exact Pages origin. When disabled, the existing loopback application contract is unchanged.
When enabled, the API exposes readiness and capability metadata, permits one in-flight inference,
and returns fixed unavailable or busy envelopes without exposing exception details.

The VPS hosts only the reverse-proxy edge and Tailscale connectivity. The DGX remains the compute
host. The Pages page performs one short, credential-free readiness check and otherwise presents
the recorded media; it never claims a live result from a failed check. No analytics, cookies,
background polling, frontend build system, or public database/model endpoint is added.

## Consequences

- The recording remains available when the DGX or edge is stopped.
- Public live behavior is reversible by one environment setting and bounded to one worker.
- The VPS has no SciFact runtime or model dependency.
- A live request still consumes DGX inference capacity and is not a production service.

## Verification

Focused tests cover capability/readiness contracts, one-at-a-time admission, exact-origin CORS,
fixed failure envelopes, static showcase fallback, and Compose's API-only opt-in defaults. The
deployment plan and live VPS configuration are maintained in the separate `vps-srv` repository.
