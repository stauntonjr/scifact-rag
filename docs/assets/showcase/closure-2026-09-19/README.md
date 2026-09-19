# Public-demo closure evidence — 2026-09-19

This packet retains statuses, counts, timestamps, hashes, and masked browser captures. Magenta
masks cover submitted claim, answer text, and evidence text. No response bodies, operational logs,
model output, or credentials are retained. Browser: Chrome 153.0.8010.48 through Playwright;
viewports 1440×1000 and 390×844. Full-page captures naturally exceed viewport height.

Procedures:

- `supported` and `search`: submit the fixed q30 acceptance case using the existing default
  retrieval and whole-document context, limit 5. Inspect successful result/evidence rendering at
  both widths. Activate a citation using keyboard Enter. These runs precede the JS deployment;
  success rendering did not change. The renderer enforces citation membership in returned evidence.
- `insufficient`: submit the fixed q92 case after the ten-minute Answer bucket refills; assert
  exact insufficiency, zero citations and successful rendering at both widths.
- `contract`: intercept Search with network failure, upstream 502, dependency 503, application busy
  429, edge 429, malformed success, and validation 422. Use the reviewed candidate JS. Assert fixed
  text, preserved claim, restored controls, no sentinel disclosure, and no horizontal overflow.
  These fourteen cases do not claim live inference, concurrency, or dependency interruption.
- `outage-failed`: original actual Serve outage restored successfully but failed link visibility.
  `outage`: after deployed CSS repair, disconnect only Serve 18090, verify genuine HTTP 502 and
  exact Pages offline body, then verify Pages hides the live link and plays the captioned recording.
  Always restore the original mapping and verify readiness in a finally block. No 504 is claimed
  as separately exercised.
- `rollback`: isolate Serve 18090; recreate only API with public mode false using its current image;
  verify disabled config, 404 readiness and loopback binding; restore public mode true, readiness
  and Serve. Compare image/configuration/port identity and dependency container IDs before/after.
- `deployment`: build integrated revision bd4591e and recreate only API. Assert served JS digest,
  enabled readiness, exact Compose configuration, unchanged dependency IDs and restored Serve.
- `source-parity`: hash the 36 tracked source files other than the repaired web JS using ordered
  path/NUL/content-digest entries. Compare prior source, integrated source, and live container.
  Also verified `git diff 3b64f083..c72c4f05 -- src pyproject.toml uv.lock Dockerfile compose.yaml`
  is empty; the same check for the recorded matrix revision 243b739f..c72c4f05 is also empty.
  c72c4f05..bd4591e changes only the web JS in that scope; see `source-bridge.json`.
- `privacy`: one valid request for an unavailable strategy returns fixed 503 without inference.
  Search bounded current API and VPS log windows for the harmless sentinel and fixed acceptance
  claims; retain line/match counts only. This check precedes the final q92 case.
- `isolation`: probe the declared private-service ports from the opposite external host. Retain
  the DGX public-address digest only; only the VPS 80/443 endpoints may accept connections.

The reviewed live edge/configuration remained unchanged. Prior busy-slot, independent token-bucket,
actual dependency interruption/restoration, and kill-switch checks are retained in both acceptance
ledgers. They are reusable because backend/runtime inputs, dependency images, route middleware,
Traefik identity, and restored configuration are unchanged; the UI repair affects only failure
messaging and hidden-link styling. The old-image rollback remains applicable at that same unchanged
backend/runtime boundary. Final repository revisions and checks are bound by the issue closure
comments, after independent review; this packet alone does not authorize closure.
