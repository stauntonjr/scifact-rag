# Issue #25 live UI showcase

Date: 2026-09-18

Governing issue: [#25](https://github.com/stauntonjr/scifact-rag/issues/25)

Showcase plan candidate: `ee011ee8ad58f2ded0518522e5dbe192db39d5df`

Host: `spark-3a8f`, AArch64 NVIDIA DGX Spark

Capture path: Mac Firefox through an SSH local forward to the DGX loopback service

## Boundary

This report will authenticate a documentation-only recording of the existing SciFact evidence
inspector. The recording must show the real UI calling the existing API, PostgreSQL corpus,
ColBERT ranker, and Qwen generator. It does not authorize a mock response, a reconstructed
citation, a public RAG endpoint, or a retrieval/generation change. GitHub Pages will publish only
the derived static media and explanatory page.

The human owner supplied the native browser recording after the browser-control runtime could not
attach to the visible in-app tab. The untouched source and edited high-resolution master remain
outside Git; only the optimized GIF, MP4, poster, captions, and static page are committed. Public
route verification remains pending until the branch is integrated and Pages is enabled.

## Recorded-query authentication

| Field | Authenticated value |
|---|---|
| Recorded claim | `Side effects of antidepressants increase the risk of stroke.` |
| Authentication request | `search-request/v1`; limit 5; `pooled-coref-interval-content-max-colbert` |
| Authentication response | HTTP 200 in 2.162447 s; `search-response/v1`; SHA-256 `22bcdfb232ee97339c4c4f6524e191c1136db15ccb625fbc199306c21086cc1a` |
| Model | `nvidia/Qwen3.6-35B-A3B-NVFP4` |
| Recorded citations | `5691302`, `14606752`, `24494539`, `37619697`, `10984005` |
| Ordered evidence IDs | `5691302`, `24494539`, `14606752`, `37619697`, `10984005` |
| Citation integrity | passed; every recorded citation resolves to one of the five displayed and independently reproduced parent IDs |
| Answer boundary | concludes that the evidence is insufficient for the claim's causal wording |

The response text visible in the recording cites all five retrieved parents and distinguishes an
association between antidepressant use and stroke from the unsupported mechanism claim that side
effects cause that risk. The authentication request reproduces the exact displayed parent set and
order without making a second generative request.

## Runtime provenance

| Component | Evidence |
|---|---|
| Application source | `e3bf3b3a802d813ab7c4bf6f5d3b4fe6fdbdc17c`; GitHub and local history resolve it, and its 2026-09-18T01:57:56Z commit precedes the API image creation by about 78 seconds |
| API | `health/v1`, `ok`; container image ID `sha256:03f52076e78d2359fe05f466843d7241a387cf5e0690c13e0271e9cbb305823c` |
| API publication | `127.0.0.1:8090->80/tcp`; no public listener added |
| PostgreSQL | `scifact-rag-postgres:pg17-pgvector0.8.6-vchord-bm250.3.0`; healthy |
| ColBERT | `answerdotai/answerai-colbert-small-v1` revision `c72aa89bc61afdd85373643f3a1a75b2aad6e0fe`; loopback port 8082; healthy |
| Qwen | `nvidia/Qwen3.6-35B-A3B-NVFP4`; loopback port 8000; model listing succeeded |

## Capture and edit provenance

The browser-control runtime reported no connected browser even though the human-visible in-app tab
was open, and the DGX shell had no graphical session. The owner therefore used the approved native
region-recorder fallback against Firefox over an SSH local forward. The source shows claim entry,
the live waiting state, the qualified answer, its citations, and the supplied evidence.

| Artifact | Boundary | SHA-256 |
|---|---|---|
| Untouched source MOV | 152.65 s; 2844x1532; H.264 Main; no audio | `5437479387c3e3262fb88802517f1c5d6ee748d34c9d0674a5956c2ee1c734cf` |
| External edited master | source `[00:00,00:39)` + `[00:47,01:50)`; 100.80 s; 2844x1532; H.264 High; no audio | `8fb88d6ef4ed7e4eb34f89b408111a6f8e2c6a8b4edd55e651814e8472e64bab` |

The owner explicitly selected source time 00:39–00:47 for removal and 01:50 as the endpoint.
Those eight seconds contain only an unchanged `Answer in progress…` state. The cut-transition
contact sheet shows the waiting state immediately followed by `Request complete.` and the actual
answer; no result, citation, or evidence frame was altered. The edited duration is 100.80 rather
than the arithmetic 102 seconds because the source's final decoded frame timestamps run short of
its 152.65-second container duration.

The authoring environment is an isolated `imageio-ffmpeg==0.6.0` resolution outside the project.
It supplies FFmpeg 7.0.2 at binary SHA-256
`6bb182d0d75d23028db82e9e4f723ca69b853d055698486e6984ddb2c06fb8ce`; no project dependency or
runtime image changed.

## Derived static media

| Published file | Contract | Bytes | SHA-256 |
|---|---|---:|---|
| `docs/assets/showcase/scifact-ui-answer-evidence.gif` | 24.00 s; 960x540; 12 fps; actual segments 00:07–00:15, 00:28–00:31, 00:39–00:44, and 01:03–01:11 | 11,679,794 | `bc03164b72dc0beb4456ef5bab648961cbb87471a61ed1b292f3789a4ea9abba` |
| `docs/showcase/scifact-ui/scifact-ui-full.mp4` | complete edited master; 100.80 s; 1280x720; H.264 High; 30 fps; no audio | 12,713,699 | `8459520127d2e3cd0e6fb5047c0923fcbd78a397a7b780c2e99f1f02e48dc7bc` |
| `docs/showcase/scifact-ui/scifact-ui-poster.png` | answer-state poster; 1280x720 | 441,047 | `dc13382b1d772408bb9521a96bddcb1ed349ebbd6c54df5f7687e7fd1a7c0c07` |
| `docs/showcase/scifact-ui/scifact-ui-full.vtt` | six English descriptive cues with both edit boundaries and the research-only limitation | 989 | `a9633c4c1896f52739e1b2eb522959f219052176caa50d75c37a7ba024d2692a` |

The combined committed media is 24,835,529 bytes (23.68 MiB), below the frozen 25 MiB ceiling.
The GIF further condenses idle and scrolling intervals but uses only frames from the edited master.
The Pages copy and captions disclose both boundaries. Mechanical and public route verification are
recorded separately below when complete.

## Verification status

| Check | Result |
|---|---|
| Cut-transition contact sheet | passed; unchanged waiting is followed by the actual completed answer |
| Poster and GIF frame inspection | passed; the recorded claim/result remain legible and the GIF visibly follows citation `5691302` into its parent evidence card before holding on the evidence |
| Static reference parser | passed; all four local page references resolve to committed files |
| Local HTTP routes | passed; page, CSS, GIF, MP4, poster, and VTT returned HTTP 200 with exact byte counts |
| Repository harness | passed through `python3 tools/harness_check.py` |
| Whitespace check | passed through `git diff --check` |
| Public Pages routes | pending integration and Pages activation |

This evidence validates the assets and static publication shape, not cross-browser playback or a
public deployment. Those claims require the integrated exact revision and live Pages responses.

## Independent review and owner disposition

Independent review of commit `8f23f6c` correctly found that its page described a different planned
query than the one visibly recorded. The owner clarified that the actual wording is grammatically
correct, materially suitable for the showcase, and should be accepted rather than rerecorded.
Issue #25 and the engineering-loop contract now name the actual request, result, and owner-selected
source edit. A fresh exact-query search reproduced all five recorded evidence parents in order.

The first review found four independent presentation defects: the GIF ended before the cited parent
card became visible, public copy omitted the 01:50 source endpoint, the page lacked the exact source
revision, and the VTT lacked a final research-only cue. Revision 2 repairs each defect without
changing the recording, answer, application, runtime, or publication topology. A second review
found that the GIF jumped directly from the answer to already-visible evidence and that this report
understated the caption cue count. Attempt 2 repairs both by retaining the real citation activation
and anchor scroll from the same master and by recording all six cues. It remains pending fresh
independent review, the final repository gate, and public Pages verification.
