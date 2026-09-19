# Issue #27 public live-demo acceptance ledger

Status: shared public acceptance executed; eleven rows are provisionally accepted and M09 is pending.
Final closure remains gated on exact-SHA checks, independent cross-repository approval, the
remaining result/error-state public-browser review described below, and an authorized API-only disabled-mode
rollback/restoration exercise. That API rollback has not been exercised.

## Identity and boundary

- Governing issue: [scifact-rag #27](https://github.com/stauntonjr/scifact-rag/issues/27)
- Coordinated edge issue: [vps-srv #4](https://github.com/stauntonjr/vps-srv/issues/4)
- Application revision at ledger creation: `932961122b3f9efb5d2a0ff782764dd770deaed1`
- Integrated and deployed application revision: `3b64f083056a1262692b4f1306310f39c0b69562`
- Integrated SciFact revision: `243b739f6773db73ee130e26c5111e9a355e8c25`.
- Final integrated VPS revision: `61b3be855cb7ee3e1dcbfa5b706ff86c4cd52339`; its integrated
  static gate passed and no repository CI workflows are configured.
- Recorded Pages entry point: `https://stauntonjr.github.io/scifact-rag/showcase/scifact-ui/`
- Best-effort live URL: `https://scifact.ediacarian.dedyn.io/`
- Accepted architecture: ADR-0035 and the approved public live-demo design.
- Release-impact recommendation: `minor` under the pre-1.0 policy; this is not release authority.

The recorded Pages showcase is the durable public artifact. The anonymous live path is optional,
has no uptime promise, and is not a clinical system or supported third-party API. SciFact owns the
single-worker application boundary; `vps-srv` owns TLS, public routing, tailnet transport, traffic
controls, metadata-only retention, and the edge kill switch. Passing deterministic checks does not
establish public availability.

## Preliminary application review

Candidate `0f0b54abb2af5d707f686a6654e737b5b1ceeb60` passed the 70-test focused
public-demo suite. Independent review then found one medium browser-contract defect: malformed or
unexpected responses were collapsed into dependency unavailability, and an unversioned HTTP 429
body could be mistaken for the application's fixed busy envelope. Attempt 2 adds behavior-level
coverage and narrows classification as required by the approved design: only an exact
`error/v1` busy envelope is application busy, every other 429 is edge rate limiting, and malformed
or unsupported responses use the fixed contract-mismatch state. No raw body is displayed.

The repaired candidate passed the 71-test focused suite, the full local smoke gate, independent
re-review, and exact-SHA Harness, CodeQL, and Pages workflows before deployment. These results and
the DGX evidence below establish only the application boundary. VPS evidence and all twelve public
rows remain required.

## DGX application acceptance

The owner authorized an API-only deployment on 2026-09-18. The deployed source was clean,
integrated `main` revision `3b64f083056a1262692b4f1306310f39c0b69562`. Inspection before
mutation confirmed the existing API was already opt-in enabled, ran one Uvicorn worker, and
published only `127.0.0.1:8090`. The API image was rebuilt first, then only the API was recreated
with `docker compose up -d --no-deps api`; PostgreSQL, late-interaction retrieval, Qwen, MCP, and
unrelated workloads were not restarted.

Immutable deployment identity:

| Field | Recorded value |
|---|---|
| Deployment timestamp | `2026-09-19T03:03:56.757304318Z` |
| API container ID | `0da4751bf229a4368211176e52bbc1cfcfe9c720d55bcac0ddb5df1659b507c2` |
| API image ID | `sha256:5f7d77b3c955ccc29fb865dabec8fd02930167532a0846a9ff03e974040cd989` |
| API image creation time | `2026-09-18T23:03:35.679994592-04:00` |
| Compose service configuration hash | `6e15c4740086e9ffab346d4bbcbc1ea2b7e7c1b199a804364a7638038ce54ed2` |
| Enabled Compose configuration digest | `sha256:b03d3e00b0e22ae382ab287649912f1ee183599f6799ab021282f0eb76ea5bea` |
| Non-secret public settings | `SCIFACT_PUBLIC_DEMO_ENABLED=true`; `SCIFACT_PUBLIC_DEMO_PAGES_ORIGIN=https://stauntonjr.github.io` |
| Listener and worker boundary | `127.0.0.1:8090 -> 80/tcp`; one Uvicorn worker |

Unchanged dependency identities after the API recreation:

| Workload | Container ID | Image ID | Start time |
|---|---|---|---|
| PostgreSQL | `27275ceda6b6b94cd244199972c0dc583acc08c867038ea08d4111fb4da29eaf` | `sha256:f9542714f92ce110c49dc3ebc1c6cff74a9138257295f20e71a81a9aa6082686` | `2026-09-18T19:34:46.216013959Z` |
| Late interaction | `0edbb9a905ae2d21e129ad5c9b71475bf4b4d70ae9460db14e34641715a75a73` | `sha256:59f44d868668552a6d63a5fa3425fa8d63591bf0b9cc1eba1dc0624371068af7` | `2026-09-18T19:34:46.218653446Z` |
| Qwen | `bc9e75e45b59601fbaf758e57d4fdef35b5f2c54f5221bbb4b3099c4c5d0da79` | `sha256:a71834dea8f397350f037feb84269a07d76e7843d5380cc3d82d792ea0ec119f` | `2026-09-18T21:21:14.158149436Z` |

Bounded loopback acceptance ran immediately after recreation. `/healthz`, `/readyz`, and
`/v1/capabilities` returned their versioned healthy/ready envelopes. Capabilities advertised 33
retrieval strategies and three context strategies; the four unavailable optional retrieval
strategies remained explicit. The retained request evidence contains schemas, status, timings,
counts, and identifiers only:

| Case | Result |
|---|---|
| Unavailable optional strategy | HTTP 503 `error/v1` `unavailable` in 0.029466 seconds, fixed message, no details |
| Shared busy slot | Overlapping valid operations produced HTTP 429 `error/v1` `busy` in 0.008732 seconds for the rejected request, fixed message, no details |
| Supported Answer | HTTP 200 `answer/v1` in 12.219210 seconds; three citation IDs (`24341590`, `13069283`, `20454006`) all resolved to displayed evidence |
| Slot recovery Search | HTTP 200 in 0.680542 seconds with five ordered evidence IDs (`12438901`, `24341590`, `20454006`, `13069283`, `31311495`) |
| Exact insufficiency | HTTP 200 `answer/v1` in 1.448155 seconds; exact `insufficient evidence`, zero citations, five displayed evidence records |

The post-deployment API log window contained 17 lines and six request-route lines. Searches for
the unique sentinel `SCIFACT_PRIVACY_20260919T0305Z_7F2A` and both accepted claim texts each
returned zero matches. No request or response body was retained in this report. This is DGX-side
privacy evidence only; matrix row M12 still requires the coordinated bounded VPS log search.

Rollback is confined to the API: recreate only that service with
`SCIFACT_PUBLIC_DEMO_ENABLED=false` and `docker compose up -d --no-deps api`, then verify readiness
and the loopback listener. Do not stop or recreate PostgreSQL, model services, MCP, or unrelated
workloads. The rollback command is recorded but was not exercised in this stage.

## Shared public acceptance session

The ordered public session `SCIFACT_PUBLIC_20260919T0516Z_A4C9` ran on 2026-09-19 from the DGX
client vantage. Its manifest froze SciFact revision `243b739f6773db73ee130e26c5111e9a355e8c25`,
VPS revision `5cc87394b11dcb4416eed29406bcf7096ea75ea6`, API image
`sha256:5f7d77b3c955ccc29fb865dabec8fd02930167532a0846a9ff03e974040cd989`, API service
configuration `sha256:6e15c4740086e9ffab346d4bbcbc1ea2b7e7c1b199a804364a7638038ce54ed2`,
enabled Compose `sha256:b03d3e00b0e22ae382ab287649912f1ee183599f6799ab021282f0eb76ea5bea`,
Traefik image `sha256:ee69e8120b64a420b5deca1cf46db0e4188ef76c7807a45c0f26d8a5ac2ab2bd`,
and live route `sha256:f3592272564a8c48f3310bd709e72f18f717bce16a6c6845ba9852ec8b2ea85b`.
Pages run `35419671279` was green for that exact SciFact revision. Retention is limited to
timestamps, statuses, schemas, timings, counts, identifiers, and digests; no answer body or raw
model output is retained.

Capabilities returned HTTP 200 `capabilities/v1`: 33 retrieval strategies, three context
strategies, and the four expected unavailable options. Live and candidate UI JavaScript shared
digest `sha256:9e0243e5f5a3480bdbe5c376a17591328b3b196bd12fe0c6d54cb2b559e3c56e`.
The four-test UI suite passed; source inspection found one read and zero assignments of the claim
input plus fixed unavailable-message and disabled-option handling. The managed browser runtime was
unavailable, so no fresh visual desktop or narrow-layout observation is claimed; that Task 9 check
remains outstanding.

| Boundary | Timestamp and redacted result |
|---|---|
| Supported Answer | 05:38:24-05:38:33 UTC; HTTP 200 `answer/v1` in 9.339843 seconds; citations `24341590`, `13069283`, and `20454006` all occurred in the five returned evidence IDs. |
| Shared busy slot | During that Answer, overlapping Search returned HTTP 429 `error/v1` `busy` in 0.084744 seconds with fixed text and no details. |
| Exact insufficiency | 05:49:01 UTC; the single preselected q92 request returned HTTP 200 `answer/v1` in 1.190375 seconds, exact `insufficient evidence`, zero citations, and five evidence IDs. |
| Search | Recovery returned HTTP 200 in 0.760 seconds with five ordered IDs; post-dependency restoration Search also returned HTTP 200 with five ordered IDs. |
| Separate edge buckets | A second Answer was edge-limited with HTTP 429 and `Retry-After: 593` while Search recovered with HTTP 200; later Answer succeeded while the independently consumed Search bucket returned edge HTTP 429. |
| Request size | A 32 KiB-plus request returned HTTP 413. |
| Dependency loss/restoration | At 05:22 UTC only late interaction was paused. Capabilities degraded, fallback Search remained available, selected ColBERT returned HTTP 503 `error/v1` `unavailable` in 0.858 seconds with fixed text and no details, and restoration returned Search HTTP 200. Identity and start time were unchanged; final state was healthy and unpaused. |
| DGX outage/fallback | The current-digest 04:26 UTC Serve outage preserved HTTP 502 with the exact Pages offline body; Turn stayed HTTP 301; Serve and readiness restored. |
| Kill switch | The current-digest 04:26 UTC watched-file exercise changed only SciFact to Pages fallback and back; Turn stayed HTTP 301 and Traefik did not restart. |
| External isolation | VPS-to-DGX probes found 5432, 8000, 8081-8085, 8090, 8091, and 18090 closed. DGX-to-VPS probes found only 80/443 open. The DGX public address was retained only as digest `sha256:ad634a12d7d31e15764a62b8fd68a9a744b50fc46f6e3afc462a10d0557a6f0e`. |
| Log privacy | A bounded 22-line API window and 709-line current VPS window each had zero matches for both session sentinels, the dependency sentinel, and both fixed claims. |

Afterward public and private readiness were HTTP 200. API container
`0da4751bf229a4368211176e52bbc1cfcfe9c720d55bcac0ddb5df1659b507c2`, late-interaction
`0edbb9a905ae2d21e129ad5c9b71475bf4b4d70ae9460db14e34641715a75a73`, and Traefik
`7684b3cda7c93b131763ec6e2d94a35b985b4b0fcd97d01cf30daf8306ba50e2` retained their
images and start times. The live route digest remained frozen.

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
| M01 DNS and TLS | live non-inference | vps-srv | provisionally passed | VPS edge report: DNS answer, certificate identity and expiry | Public hostname resolves to the intended VPS and serves a valid certificate for the exact hostname | Wrong address, invalid/expired certificate, or unverified DNS authority |
| M02 Supported answer and citations | live inference | shared | provisionally passed | This report: timestamped request/result packet plus displayed evidence IDs | One bounded public Answer succeeds and every citation resolves to evidence displayed in that response | Any unresolved/fabricated citation, raw internal error, or unbounded retry |
| M03 Exact insufficiency | live inference | shared | provisionally passed | This report: timestamped fixed-case packet | One bounded public Answer returns exact `insufficient evidence` with zero citations | Fabricated citation, altered exact result, or repeated model selection/tuning |
| M04 Search | live inference | shared | provisionally passed | This report: timestamped Search packet | Search succeeds with one accepted, currently available strategy and ordered result evidence | Unavailable strategy accepted, contract mismatch, or unbounded retry |
| M05 Optional strategy unavailable | deterministic | scifact-rag | provisionally passed | Focused capability/UI test output and captured capability payload | An unavailable optional strategy remains visible, disabled, and has a fixed reason without inference | Hidden strategy, enabled unavailable control, or probe invokes application work |
| M06 Shared busy slot | deterministic | scifact-rag | provisionally passed | Focused overlapping-request test output | Two overlapping valid Search/Answer operations produce one active operation and one fixed HTTP 429 `busy`, with no second resolver/application call | Queue/retry appears, slot leaks, or more than one worker is required |
| M07 Separate edge rate limits | live non-inference | vps-srv | provisionally passed | VPS edge report: bounded Answer and Search probes | Frozen Answer and Search token buckets act independently at their specified boundaries | Shared bucket, client-header identity, excessive probe, or unexpected upstream work |
| M08 Dependency loss and restoration | deterministic | scifact-rag | provisionally passed | Focused health/capability/UI tests; optional bounded live confirmation | Loss returns fixed unavailable state without claim loss or raw detail, and restoration succeeds without code/config drift | Raw error/claim disclosure, lifecycle automation, or failure to restore |
| M09 DGX outage and Pages fallback | live non-inference | shared | pending | Public browser capture plus VPS response metadata | Pages recording remains usable; live hostname serves the intended failure status/fallback without claiming success | Pages depends on DGX, failure becomes success, or fallback leaks upstream detail |
| M10 Kill switch and restoration | live non-inference | vps-srv | provisionally passed | VPS edge report: config digests and before/after probes | SciFact route disables and restores without changing another VPS service | Unrelated route changes, manual dirty-checkout edit, or restoration uncertainty |
| M11 External port isolation | live non-inference | shared | provisionally passed | Timestamped external inspection and DGX listener inventory | PostgreSQL, MCP, model services, and DGX loopback port 8090 are not publicly reachable | Any unintended public listener or inability to identify the exact target |
| M12 Log privacy | live non-inference | vps-srv | provisionally passed | Sentinel request plus bounded application/VPS log search | Unique harmless claim sentinel and request/response bodies are absent; retained metadata matches the seven-day policy | Claim/body retention, credential/internal-detail exposure, or unbounded log inspection |

## Closure gate

Do not enable or advertise the live link as available, close Issue #27, or move its Project item to
Done until all twelve rows pass, both repositories record exact-SHA green CI, the deployed image
and configuration digests are retained, rollback has been exercised, and independent application
and infrastructure reviews approve the same stable candidates. A failure is not waived unless the
human owner explicitly accepts the risk; otherwise keep the row and issue open.

## Supplemental public layout observation — 2026-09-19

A non-inference Chrome 153.0.8010.48 session at 15:36 UTC loaded the public Pages showcase and
live inspector at desktop 1440×1000 and narrow 390×844 viewports. Both returned HTTP 200 and
reported document widths equal to viewport widths. Visual inspection found readable headings,
claim-field labels, stacked narrow-layout actions, readiness text, and the recorded-showcase link.
The Pages video played and loaded six English caption cues.

Evidence: [desktop live](../assets/showcase/acceptance-2026-09-19/live-desktop.png),
[narrow live](../assets/showcase/acceptance-2026-09-19/live-narrow.png),
[desktop Pages](../assets/showcase/acceptance-2026-09-19/pages-desktop.png),
[narrow Pages](../assets/showcase/acceptance-2026-09-19/pages-narrow.png), and
[observations](../assets/showcase/acceptance-2026-09-19/observations.json).

This resolves the absence of any fresh public landing-page layout observation. It does not
complete result/error-state layout, keyboard/accessibility acceptance, M09 outage/fallback,
API-only rollback/restoration, or independent cross-repository release approval. No Search or
Answer was submitted and no service was interrupted. The exact deployed application/image was
not re-inspected in this browser-only session; the earlier frozen deployment identities remain
the authoritative release evidence. Latest repository main was `c72c4f0566718046445b3da74aec091a05e38cad`,
whose Harness, CodeQL and Pages checks passed; that is not a fresh deployed-image attestation.
Issue #27 remains open with its twelve-row closure gate unchanged.

## Closure repair checkpoint — 2026-09-19

The next bounded acceptance pass found two UI defects: a rejected network fetch used the dependency
unavailable message instead of the offline message, and showcase button styling overrode the live
link's `hidden` attribute. The narrow repairs preserve HTTP 503 handling, submitted claims, and
readiness-driven link visibility. Nine focused tests passed with Node enabled, and an independent
review approved the four-file repair. Fourteen intercepted browser failure cases across 1440px and
390px widths retained claims, restored controls, hid raw details, and avoided horizontal overflow.
Those intercepted cases are deterministic UI evidence, not successful live inference evidence.

The real outage returned HTTP 502 with the Pages offline body, then failed the hidden-link browser
assertion. Its recovery restored the identical Serve mapping and public readiness. This failed
attempt is not M09 acceptance. Repeat the browser exercise after the stylesheet is deployed.
