# Capability matrix

Date: 2026-08-25

This matrix preserves useful capabilities observed in four source projects without copying their
implementations into every derived repository. `harness/capabilities.json` is authoritative for
IDs, aliases, triggers, claimed responsibilities, and activation state. Every entry starts
`inactive`: it contributes no implementation path, runtime dependency, or CI check until the human
owner approves activation for a demonstrated project need.

| Capability skeleton | S3NTINEL | Kortex | Procurement Intelligence Lab | Macro Technical Pulse | First activation cue |
|---|---|---|---|---|---|
| Python AST, dependency, LOC, and architecture drift analysis | Source | — | — | — | The package is too large to inspect reliably by hand |
| Workload-specific computational-complexity review | Source | — | — | — | Scale or algorithm choice affects feasibility |
| Product validation challenge corpus | Source | — | Related evidence challenges | Related replay discipline | Stable product results and a real known-bad example exist |
| Durable chat, artifact, and directive memory | — | Source | — | — | Repository artifacts no longer provide sufficient continuity |
| Governed reflection and directive promotion | — | Source | — | — | Durable memory exists and repeated observations need reviewed promotion |
| Append-oriented semantic evidence ledger | Related validation evidence | — | Source | Related provenance chain | Sources can support, contradict, or revise a derived result |
| Application composition root with constructor DI | — | Related contracts | Source | Related modular boundaries | The first use case and replaceable ports are known |
| CLI interface | Existing tools | Existing tools | Source architecture | Existing tools | A deterministic local interface is the smallest useful boundary |
| HTTP API interface | Existing services | Existing gateway | Source architecture | — | A network consumer needs a proven CLI-backed use case |
| MCP interface | — | Related agent gateway | Planned common-layer consumer | — | An external agent needs a stable use case, not direct storage access |
| Small web interface | Existing dashboards | — | Planned common-layer consumer | Reports | A bounded interactive workflow cannot be served adequately by CLI or API |
| Point-in-time and revision provenance | Related artifact lineage | Related source metadata | Related evidence lineage | Source | Mutable sources or historical as-of evaluation make look-ahead possible |
| Role-separated parallel domain analysis | Related component ownership | Related agent boundaries | Related vertical ownership | Source | Independent lanes and approval separation materially improve a real workflow |

## Duplicate-prevention contract

An inactive skeleton still owns its cataloged responsibility. Before planning, an agent searches
the catalog by ID, alias, and claimed responsibility and records one disposition:

- `use-active`: use the existing active project implementation;
- `propose-activation`: adapt the cataloged skeleton after explicit human approval;
- `not-applicable`: explain why the responsibility is outside the current slice.

The agent must not create an independent replacement merely because a capability is inactive. A
deliberate replacement requires the human owner to approve supersession and update the catalog so
only one capability owns each responsibility.

## SciFact activation state

`scifact-rag` initially activated `application-composition-root` and `cli-interface`. After the
public qrels exposed stable retrieval failures, the human owner approved
`product-validation-challenges`. Its implementation is limited to 12 rescued queries and one
focused integration oracle; the full 300-query benchmark remains authoritative. After Issue #10
accepted the CLI proof, the owner activated `http-api-interface` for Issue #11's three-operation,
loopback-only FastAPI adapter with explicit CLI parity.

MCP, web, durable memory, architecture analysis, complexity review, and role parallelism remain
inactive. The increase to 3.72 chunk vectors per document is below the accepted four-vector budget
and does not yet justify activating a separate complexity-analysis capability.
