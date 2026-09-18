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
not claimed. The API log shows that first-request model initialization began before completion.
The supplied recording independently captures the visible warm request and matching result.

## Runtime provenance

| Component | Evidence |
|---|---|
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
| `docs/assets/showcase/scifact-ui-answer-evidence.gif` | 24.00 s; 960x540; 12 fps; actual segments 00:07–00:16, 00:28–00:32, 00:39–00:44, and 01:02–01:08 | 11,392,308 | `170acf25d886766a17ec61c9e4f7dae14d663b46237e4a707517bc678be339eb` |
| `docs/showcase/scifact-ui/scifact-ui-full.mp4` | complete edited master; 100.80 s; 1280x720; H.264 High; 30 fps; no audio | 12,713,699 | `8459520127d2e3cd0e6fb5047c0923fcbd78a397a7b780c2e99f1f02e48dc7bc` |
| `docs/showcase/scifact-ui/scifact-ui-poster.png` | answer-state poster; 1280x720 | 441,047 | `dc13382b1d772408bb9521a96bddcb1ed349ebbd6c54df5f7687e7fd1a7c0c07` |
| `docs/showcase/scifact-ui/scifact-ui-full.vtt` | five English descriptive cues with the time-edit disclosure | 780 | `ac2674b100486a873fd8f3c807455db74c308420d2d922b5c4b850d5b3e13532` |

The combined committed media is 24,547,054 bytes (23.41 MiB), below the frozen 25 MiB ceiling.
The GIF further condenses idle and scrolling intervals but uses only frames from the edited master.
The Pages copy and captions disclose both boundaries. Mechanical and public route verification are
recorded separately below when complete.

## Verification status

| Check | Result |
|---|---|
| Cut-transition contact sheet | passed; unchanged waiting is followed by the actual completed answer |
| Poster and GIF frame inspection | passed; corrected claim/result remain legible at published dimensions |
| Static reference parser | passed; all four local page references resolve to committed files |
| Local HTTP routes | passed; page, CSS, GIF, MP4, poster, and VTT returned HTTP 200 with exact byte counts |
| Repository harness | passed through `python3 tools/harness_check.py` |
| Whitespace check | passed through `git diff --check` |
| Public Pages routes | pending integration and Pages activation |

This evidence validates the assets and static publication shape, not cross-browser playback or a
public deployment. Those claims require the integrated exact revision and live Pages responses.

## Attempt 1 independent review

Independent review rejected commit `8f23f6c` before the final gate or publication. Frame-level
inspection showed that the recorded UI actually submitted `Side effects of antidepressants
increase the risk of stroke.`, omitting the required words `associated with`. The recording also
shows evidence document `24494539`, while the corrected-claim preflight supplied `23627419` in its
place. The media therefore cannot be relabeled as the corrected request and is not eligible for
integration or Pages publication.

The same review found that the GIF ended at the `Supplied evidence` heading before the cited parent
card became visible, the MP4 exceeded Issue #25's retained 45-60 second boundary, the public edit
copy omitted the source endpoint trim, the page lacked an authenticated exact source revision, and
the VTT lacked a final research-only cue. Attempt 2 requires a replacement live capture and new
derivatives. The existing files remain only as preserved failed-attempt evidence until replacement.
