# Issue #25 live UI showcase

Date: 2026-09-18  
Governing issue: [#25](https://github.com/stauntonjr/scifact-rag/issues/25)  
Capture candidate: `ee011ee8ad58f2ded0518522e5dbe192db39d5df`  
Host: `spark-3a8f`, AArch64 NVIDIA DGX Spark  
Browser path: Codex in-app browser proxy `http://localhost:61266/` to the DGX loopback service

## Boundary

This report will authenticate a documentation-only recording of the existing SciFact evidence
inspector. The recording must show the real UI calling the existing API, PostgreSQL corpus,
ColBERT ranker, and Qwen generator. It does not authorize a mock response, a reconstructed
citation, a public RAG endpoint, or a retrieval/generation change. GitHub Pages will publish only
the derived static media and explanatory page.

The lossless master remains outside Git. All media identities, durations, checksums, and public
routes remain pending until the master is supplied and validated. API evidence below establishes
that the chosen claim can complete through the live application, but it is not a substitute for
the required visible recording.

## Frozen live preflight

| Field | Frozen value |
|---|---|
| Corrected claim | `Side effects associated with antidepressants increase the risk of stroke.` |
| Request | `ask-request/v1`; limit 5; `pooled-coref-interval-content-max-colbert`; `whole-document` |
| Response | HTTP 200; `answer/v1` |
| Model | `nvidia/Qwen3.6-35B-A3B-NVFP4` |
| Citations | `5691302`, `37619697`, `10984005`, `14606752` |
| Supplied evidence IDs | `5691302`, `10984005`, `23627419`, `14606752`, `37619697` |
| Citation integrity | passed; every citation resolves to a supplied evidence ID |
| Answer boundary | concludes that the evidence is insufficient for the claim's causal wording |
| Completion evidence | API access log recorded HTTP 200 at `2026-09-18T14:13:02.421691968Z` |

The preflight client reached its 30-second command boundary after the complete response body had
been written but before its timing footer was retained. The exact request duration is therefore
not claimed. The API log shows that first-request model initialization began before completion;
the continuous master must preserve whatever loading interval the visible warm request actually
takes. If the 22-second GIF cannot contain the whole interval, it may remove only middle loading
frames and must disclose that elapsed-time edit; the longer MP4 remains continuous.

## Runtime provenance

| Component | Evidence |
|---|---|
| API | `health/v1`, `ok`; container image ID `sha256:03f52076e78d2359fe05f466843d7241a387cf5e0690c13e0271e9cbb305823c` |
| API publication | `127.0.0.1:8090->80/tcp`; no public listener added |
| PostgreSQL | `scifact-rag-postgres:pg17-pgvector0.8.6-vchord-bm250.3.0`; healthy |
| ColBERT | `answerdotai/answerai-colbert-small-v1` revision `c72aa89bc61afdd85373643f3a1a75b2aad6e0fe`; loopback port 8082; healthy |
| Qwen | `nvidia/Qwen3.6-35B-A3B-NVFP4`; loopback port 8000; model listing succeeded |

## Capture status

The browser-control runtime reported no connected browser even though the human-visible in-app tab
is open. The DGX shell has no graphical session or screen-recording/encoding tool. The honest
capture path is therefore the approved native-region-recorder fallback: the human owner records
the visible live tab and places the uninterrupted master at
`/home/jrs/scifact-rag-showcase-master/scifact-ui-master.mov`. No media acceptance or publication
claim is made until that file exists and passes the plan's checks.
