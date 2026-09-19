# Issue #27 public live-demo acceptance ledger

Status: application governance reconciliation in progress; every public acceptance row is pending.

## Identity and boundary

- Governing issue: [scifact-rag #27](https://github.com/stauntonjr/scifact-rag/issues/27)
- Coordinated edge issue: [vps-srv #4](https://github.com/stauntonjr/vps-srv/issues/4)
- Application revision at ledger creation: `932961122b3f9efb5d2a0ff782764dd770deaed1`
- Final SciFact and VPS revisions: pending; replace only with exact integrated revisions.
- Recorded Pages entry point: `https://stauntonjr.github.io/scifact-rag/showcase/scifact-ui/`
- Best-effort live URL: `https://scifact.ediacarian.dedyn.io/`
- Accepted architecture: ADR-0035 and the approved public live-demo design.
- Release-impact recommendation: `minor` under the pre-1.0 policy; this is not release authority.

The recorded Pages showcase is the durable public artifact. The anonymous live path is optional,
has no uptime promise, and is not a clinical system or supported third-party API. SciFact owns the
single-worker application boundary; `vps-srv` owns TLS, public routing, tailnet transport, traffic
controls, metadata-only retention, and the edge kill switch. Passing deterministic checks does not
establish public availability.

## Rollback boundary

First activate the SciFact-specific VPS kill switch or fallback route without touching another
hostname. Then, if needed, set `SCIFACT_PUBLIC_DEMO_ENABLED=false` and rebuild only the DGX `api`
service. Keep Compose publication on `127.0.0.1:8090`; do not stop unrelated DGX services, alter
Tailscale globally, or let the VPS start or repair model workloads. Restore the live route only
after private-path readiness and the affected matrix rows pass again.

## Acceptance matrix

Evidence classes are `deterministic`, `live non-inference`, and `live inference`. A row may move
from `pending` to `passed` only with timestamped evidence tied to both exact integrated revisions.

| ID | Evidence class | Owner | Status | Evidence location | Exact pass condition | Stop condition |
|---|---|---|---|---|---|---|
| M01 DNS and TLS | live non-inference | vps-srv | pending | VPS edge report: DNS answer, certificate identity and expiry | Public hostname resolves to the intended VPS and serves a valid certificate for the exact hostname | Wrong address, invalid/expired certificate, or unverified DNS authority |
| M02 Supported answer and citations | live inference | shared | pending | This report: timestamped request/result packet plus displayed evidence IDs | One bounded public Answer succeeds and every citation resolves to evidence displayed in that response | Any unresolved/fabricated citation, raw internal error, or unbounded retry |
| M03 Exact insufficiency | live inference | shared | pending | This report: timestamped fixed-case packet | One bounded public Answer returns exact `insufficient evidence` with zero citations | Fabricated citation, altered exact result, or repeated model selection/tuning |
| M04 Search | live inference | shared | pending | This report: timestamped Search packet | Search succeeds with one accepted, currently available strategy and ordered result evidence | Unavailable strategy accepted, contract mismatch, or unbounded retry |
| M05 Optional strategy unavailable | deterministic | scifact-rag | pending | Focused capability/UI test output and captured capability payload | An unavailable optional strategy remains visible, disabled, and has a fixed reason without inference | Hidden strategy, enabled unavailable control, or probe invokes application work |
| M06 Shared busy slot | deterministic | scifact-rag | pending | Focused overlapping-request test output | Two overlapping valid Search/Answer operations produce one active operation and one fixed HTTP 429 `busy`, with no second resolver/application call | Queue/retry appears, slot leaks, or more than one worker is required |
| M07 Separate edge rate limits | live non-inference | vps-srv | pending | VPS edge report: bounded Answer and Search probes | Frozen Answer and Search token buckets act independently at their specified boundaries | Shared bucket, client-header identity, excessive probe, or unexpected upstream work |
| M08 Dependency loss and restoration | deterministic | scifact-rag | pending | Focused health/capability/UI tests; optional bounded live confirmation | Loss returns fixed unavailable state without claim loss or raw detail, and restoration succeeds without code/config drift | Raw error/claim disclosure, lifecycle automation, or failure to restore |
| M09 DGX outage and Pages fallback | live non-inference | shared | pending | Public browser capture plus VPS response metadata | Pages recording remains usable; live hostname serves the intended failure status/fallback without claiming success | Pages depends on DGX, failure becomes success, or fallback leaks upstream detail |
| M10 Kill switch and restoration | live non-inference | vps-srv | pending | VPS edge report: config digests and before/after probes | SciFact route disables and restores without changing another VPS service | Unrelated route changes, manual dirty-checkout edit, or restoration uncertainty |
| M11 External port isolation | live non-inference | shared | pending | Timestamped external inspection and DGX listener inventory | PostgreSQL, MCP, model services, and DGX loopback port 8090 are not publicly reachable | Any unintended public listener or inability to identify the exact target |
| M12 Log privacy | live non-inference | vps-srv | pending | Sentinel request plus bounded application/VPS log search | Unique harmless claim sentinel and request/response bodies are absent; retained metadata matches the seven-day policy | Claim/body retention, credential/internal-detail exposure, or unbounded log inspection |

## Closure gate

Do not enable or advertise the live link as available, close Issue #27, or move its Project item to
Done until all twelve rows pass, both repositories record exact-SHA green CI, the deployed image
and configuration digests are retained, rollback has been exercised, and independent application
and infrastructure reviews approve the same stable candidates. A failure is not waived unless the
human owner explicitly accepts the risk; otherwise keep the row and issue open.
