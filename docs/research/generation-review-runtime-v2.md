# Generation-review runtime admission v2

Date: 2026-09-19. Governing work: [Issue #35](https://github.com/stauntonjr/scifact-rag/issues/35).
Disposition: **adapt** the existing source validators and official subscription runtime; no new
framework, paid API or custom authentication adapter.

The installed Codex CLI is `0.155.0-alpha.9.2`. Its local help exposes schema-constrained output,
ephemeral execution, user-config suppression, explicit models and JSON events. The official
[noninteractive documentation](https://learn.chatgpt.com/docs/non-interactive-mode) describes these
execution/output mechanisms; the [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
and [schema](https://learn.chatgpt.com/docs/config-schema.json) describe individual feature controls.
Those interfaces are not themselves proof of an empty tool surface or case-only context.

## Options and decision

| Approach | Fit and limitation | Disposition |
|---|---|---|
| Existing validators plus official subscription CLI | Reuses available access and strict source checks; runtime isolation must be observed | Adapt, with admission gate |
| Ordinary shared-workspace agent instructions | Easy invocation, but no enforced denial of unrelated context/tools | Reject for this revision |
| Separately billed structured-output API | Could offer a different tool boundary; outside the accepted subscription-only scope | Defer to owner decision |
| Bespoke authentication or sandbox implementation | Adds a security subsystem rather than completing the narrow reviewer workflow | Do not build |

No third-party prompt or executable was copied. The tool is an external installed dependency;
no provider source or credentials are vendored. Repository judgment/validation code is reused under
the existing project license. Model capability/CLI configuration claims can drift, so admission
must bind the executable and effective configuration rather than relying on this document alone.

## Observations

- A no-model prompt inspection with memory/skills and known tool feature controls disabled omitted
  the memory and skill catalogs. Generic multi-agent instructions remained.
- The generated installed app-server protocol supports `environments=[]` to disable environment
  access. It does not expose a documented global tool allowlist; `dynamicTools` adds tools rather
  than demonstrating removal of built-ins.
- `read-only` permits filesystem reads and cannot by itself establish case-only review access.
- A counted fictional probe used `--ignore-user-config`, `--strict-config`, `--ephemeral`, an empty
  working directory, JSON Schema output and explicit disabled feature settings. It completed with
  valid JSON and reported no ability to read the fabricated sentinel. It nevertheless reported
  collaboration and patch tools, despite disabled shell/multi-agent settings. This is a model
  report, not independent proof that the tools were callable or denied.

- A second counted fabricated probe added `agents.enabled=false` and `features.goals=false`.
  The actual event stream reported that Code Mode was unavailable and would fail closed; the
  runtime router logged `code-mode host is disabled`. This establishes denial of the attempted
  route. It does not establish a complete inventory of other possible routes.
- The local `debug prompt-input --help` has no full-snapshot option. Its output contains input
  items, not the complete tool schemas or base instructions. The upstream
  [open snapshot request](https://github.com/openai/codex/issues/35706) describes this same
  observability gap; it is a reported limitation corroborated by local output, not a shipped fix.
- Both probe streams provide a session ID and usage but no per-turn returned model identity.
  Requested model configuration must not be relabeled as provider-observed execution identity.

Independent scope review corrected the initial demand for complete tool enumeration and mandatory
provider-returned model metadata: those demands exceeded the accepted contract. A reviewed map
from each prohibited capability to supported enforcement controls can satisfy admission. Requested,
runtime-configured and provider-observed model identities must remain distinguishable; unavailable
provider metadata stays null. No silent fallback is authorized.

## Capability control mapping

| Capability | Candidate controls and evidence |
|---|---|
| Files and commands | Shell, unified execution and image reading disabled; actual Code Mode router denial |
| Browser, network tools and connectors | Browser, computer use, apps and image generation disabled; web search disabled |
| Peer tasks | Agents and both multi-agent features disabled; fresh session for each request |
| Memories and skills | Feature and injection settings disabled; model-free inspection lacks memory and skill catalogs |
| Plugins | Plugin feature disabled |
| Local and orchestrator MCP | Orchestrator MCP disabled; local configuration-source check described below |

A no-model local MCP inspection found that `mcp_servers={}` does **not** clear an inherited map.
All three listed local server names matched user configuration; checked system/managed configuration
files were absent. The scientific `exec` launch uses `--ignore-user-config`, removing the only
observed source of those definitions. This is configuration-source evidence, not an exact-launch
MCP listing: the listing command does not accept that flag. A separate supported per-server-disable
check produced zero enabled servers with user configuration loaded. Do not add incomplete server
definitions blindly to the ignored-user-config launch.

The current evidence and configuration-source bindings require independent review before profile
admission. Bind the executable, exact overrides, launch flags, current source checks and evidence
artifacts; stop on drift or a known identity mismatch. No need to intercept authentication traffic,
inspect credentials, invent an execution identity, build a sandbox or obtain a complete base prompt.
The [configuration precedence documentation](https://learn.chatgpt.com/docs/config-file/config-basic)
supports the layer interpretation; the retained local inspection establishes the actual named
configuration sources on this host.

The two completed probes, the bounded diagnostic and all three rehearsal rounds remain counted. Their
success is not scientific qualification. Admission still precedes the clarification assessment
and real cases. No product, global configuration,
credential, model service or scientific output was changed by these inspections.


## Reviewed admission

The independent verifier approved profile `mac-subscription-review-v2` for bounded fictional
execution after checking the full capability map, all 24 evidence digests, executable identity,
configuration-source bindings and revised adapter. A final model-free inspection under the sanitized
child environment covered all three frozen models and contained only permission instructions,
environment context and fabricated user text. Memory, skills, project instructions and peer content
were absent from that inspected input surface.

The registered descriptor SHA-256 is
`efcac1165c37115354b7e34cd12783cbd2975b820f5b5f79c5bed6deaf8dd389`.
The executable SHA-256 is
`9280c0754e8f1f6b72f495d30c8c82a006dbc4995bf0492916fa0901f6bfd1f9`.
The adapter rechecks the binary, evidence and configuration sources before dispatch, sets the pinned
subscription home, removes inherited provider overrides, and uses fresh empty working directories.
The admission CLI returned `runtime_admitted` with zero model calls. Initial stopped admission
records remain retained; the later decision supersedes their unverified-control conclusion.

This is configuration-based admission for the enumerated capabilities and pinned environment.
It is not provider attestation or proof of an empty tool surface. Development requires a complete
passing frozen fictional rehearsal; the [execution report](../reports/generation-review-workflow-v2.md)
records whether that additional gate was met.
