# Issue #13 web UI acceptance

Date: 2026-09-17
Governing issue: [#13](https://github.com/stauntonjr/scifact-rag/issues/13)
Deployed repair candidate: `e3bf3b3df4eb0211483fac4b1ec650af3bda36ae`
Host: `spark-3a8f`, AArch64 NVIDIA DGX Spark
API image: `03f52076e78d` (`linux/arm64`)
Publication: `127.0.0.1:8090->80/tcp`
Browser path: Codex in-app browser proxy `http://localhost:61266/` to the DGX loopback service

## Boundary

This acceptance covers the small packaged evidence inspector served by the existing FastAPI
process. It verifies presentation of the accepted search and answer contracts without changing
retrieval, ranking, context selection, generation, prompts, citations, models, or Compose
topology. The live examples are operational checks over already-inspected SciFact claims, not new
model-quality evidence.

The browser-control runtime could not attach to the visible in-app tab, so the human owner
performed and reported the visible interactions while the agent controlled and verified the API
container, endpoint, candidate, and restoration boundary. API responses below corroborate the
same deployed endpoint but are not represented as captured browser network traces.
The owner also approved deterministic delivered-document and CSS verification for semantic
structure, focus-visible styling, the sub-760 pixel layout, and reduced motion in place of
unavailable browser automation for those presentation contracts.

## Candidate and package evidence

The source checkout was clean at `e3bf3b3` before the repaired image was built. The API image was
built from that candidate by replacing only the existing `api` container. PostgreSQL remained the
same healthy container; MCP and GPU model services were not restarted. The deployed JavaScript and
the candidate source both have SHA-256
`3263685d9802a700d2290903d3ef7a5f183b35e61234ff0e30c1834ea263699e`.

| Check | Result | Elapsed |
|---|---|---:|
| Focused web, HTTP, and interface contracts | 34 passed | 0.63 s |
| Isolated source/wheel build and installation | passed as `scifact-rag 0.1.0` | 2.47 s |
| Compose configuration | passed; no new service or publication | 0.05 s |
| Live affected integrations | 3 passed, 333 deselected | 14.49 s |
| Browser JavaScript syntax, Python lint/types, and diff check | passed | 3.00 s |
| Deployed root, CSS, and JavaScript | HTTP 200; all use `Cache-Control: no-store` | bounded |

The package-resource probe confirms that `index.html`, `scifact.css`, and `scifact.js` are present
in the wheel. The deployed JavaScript response is non-cacheable so an ordinary page reload cannot
continue using the pre-repair renderer.

## Browser observations

| State | Browser observation | Corroborating boundary |
|---|---|---|
| Supported answer | The human owner confirmed a grounded answer with working citation links for query 1084, `Side effects associated with antidepressants increases risk of stroke.` | The same deployed API returned citations `5691302` and `14606752`; the five evidence IDs in order were `5691302`, `23627419`, `37619697`, `10984005`, and `14606752` in 5.884661 s. Every citation belongs to that set. |
| Insufficient evidence | The browser displayed `Evidence boundary reached`, exact `insufficient evidence`, zero citations, model and strategy metadata, and five supplied documents for `Rapamycin delays onset of alzheimers`. | Visible evidence IDs in order were `4434951`, `116792`, `26244918`, `6690087`, and `16233471`. This proves that an insufficiency result preserves the evidence the application evaluated. |
| Validation | The human owner confirmed the fixed validation state after submitting a whitespace-only query. | The UI maps the existing HTTP 422 boundary to `Request validation failed. Check the claim and controls, then try again.` without response-body detail. |
| Service unavailable | With the already-loaded page retained, only the `api` container was stopped. The browser displayed exact `The service is temporarily unavailable. Try again after it has recovered.` and no backend detail. | A first timed attempt restored before submission and showed Ready, so it was not counted. The second attempt verified port 8090 unavailable before submission; afterward the API was restored and `/healthz` returned 200. PostgreSQL remained healthy throughout. |

The original insufficiency probe exposed a real presentation defect: the API correctly retained
evidence with exact insufficiency, while the browser validator incorrectly required an empty
evidence array. Commit `6089dee` aligned the validator with the accepted application contract.
Commit `d04fda5` added `no-store` to packaged assets so the repaired JavaScript is not stale after
an API-image replacement.

Independent review then found that adaptive evidence containing two contexts from one parent
created two DOM cards with the same ID and reported them as two documents. The bounded renderer
probe reproduced the defect as two `evidence-123` cards and `2 documents`. After repair, the same
probe returns one `evidence-123` parent card, two ordered passage sections, and
`1 document · 2 supplied passages`. The repair adds no browser framework or Node project
dependency.

## Accessibility and responsive boundary

The exact delivered document contains a main landmark, explicit labels, native form controls, and
a polite live status region. The exact delivered CSS contains explicit focus-visible styling, a
sub-760 pixel stacking rule, and a reduced-motion media query that removes transitions. These are
the owner-approved deterministic checks because automation could not attach to the visible browser;
no claim is made about assistive-technology certification or broad cross-browser coverage.

## Decision and limitations

**Accept the browser behavior for the final Phase 6 composition adapter.** It reuses the existing
application and versioned HTTP operations, preserves ordered evidence and parent citation
integrity, distinguishes cited answers from exact insufficiency, rejects invalid input with a
bounded message, and recovers after an API-only outage.

This is a single-user DGX-loopback prototype. There is no authentication, TLS, public or Mac
connection-path acceptance, availability target, persistent client state, administration, or
production-readiness claim. The examples do not establish a retrieval or generation quality gain.
Integration remains contingent on the current-candidate full repository gate and independent
review required by the engineering loop.
