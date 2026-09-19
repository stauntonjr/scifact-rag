# Generation confirmation custody v1

## Current status

Status: **incomplete** as of 2026-09-19.

This document specifies the required confirmation-custody design without selecting, downloading,
viewing, or hashing any real confirmation content. It does not claim that a cohort exists or that
access separation is operational. Acquisition and confirmation execution remain blocked until the
owner provisions and rehearses a separately permissioned environment.

## Authority and role separation

- **Human owner, custody authority, and release approver:** Jack Rory Staunton. Only the owner may
  approve the storage account, grant or revoke access, accept the powered sample and run budget,
  authorize acquisition, break the seal after locked review, or promote a result.
- **Development coordinator:** the Issue #28 Codex task and its successors. It may receive only the
  developer-visible opaque manifest. It must never receive confirmation questions, evidence,
  sources, answers, mappings, logs containing content, or storage credentials.
- **Future custodian agent C-confirm:** a fresh owner-launched session in the separate custody
  account. It owns eligibility checks, article-family exclusions, sampling, sealing, access logs,
  and approved reviewer exports. It cannot implement or select Candidate A and shares no
  conversation or readable storage with developer agents.
- **Future confirmation reviewers CR1/CR2:** fresh sessions using the exact panel models and frozen
  protocol accepted after Issue #28. They receive one opaque case at a time through the custody
  environment and no developer artifacts, candidate identity, or peer result.
- **Future confirmation adjudicator CA:** a separate fresh session using the frozen staged
  evidence-first protocol. It does not approve release.
- **Candidate developers:** all agents or humans that can read the development repository,
  development artifacts, Candidate A prompt, or candidate outputs. They are denied custody content
  and credentials and cannot also serve as C-confirm, CR1, CR2, or CA for that run.

The exact custodian and reviewer session IDs and model labels must be frozen in a later accepted
preparation issue. Ordinary agents in this shared worktree do not satisfy custody.

## Required storage and access boundary

Before status can become `operationally-rehearsed`, the owner must provide a separate account or
environment with all of these properties:

- content and mapping storage are encrypted and permissioned to the owner and C-confirm only;
- reviewer identities can read only assigned opaque case packages and write only attributable
  review exports;
- developers have no filesystem, object-store, database, browser-session, backup, API-token,
  tracing, log, or administrator route to content or mappings;
- reviewer model calls, prompt logging, browser storage, crash dumps, telemetry, and support logs
  are either content-denied or contained inside the custody boundary;
- mappings are more restricted than opaque manifests and never copied into the development repo;
- backups inherit the same access rules and deletion/retention schedule; and
- access grants, denials, export events, and owner release are timestamped and retained.

If developer administrators can technically read the custody account, that residual access must be
recorded and the cohort cannot be described as access-enforced or untouched without an owner risk
decision. Hashing a public source ID is identity evidence, not secrecy or anonymization.

## Future source eligibility and exclusions

C-confirm constructs the sampling frame only after Candidate A development is frozen. Every source
must have documented lawful project use, stable full text or abstract evidence, source identity,
publication state, and sufficient metadata to resolve article families.

Exclude an entire article family when any member, correction, preprint, conference abstract,
supplement, secondary analysis, shared study population, paraphrased prompt, or derived question was
used in:

- product development, retrieval or generation validation, stress tests, fictional fixtures, prompt
  examples, manual debugging, or model demonstrations;
- the 42 historical Issue #5 responses or any later development-review pilot;
- Candidate A design, repair, comparison, or reviewer clarification; or
- any artifact, chat, cache, log, report, or external workspace readable by candidate developers.

Resolve families using durable bibliographic identifiers, titles/authors/year, trial or cohort
identity, corrections and version links, and semantic/manual review by C-confirm. Ambiguous lineage
is excluded, not guessed. Sampling preserves all context-policy variants within a family and never
splits a family across tuning and confirmation.

## Sampling and power

The later preparation issue must calculate sample size before confirmation outcomes exist. Inputs
are development estimates of paired baseline/candidate discordance, anticipated effect size,
non-inferiority or superiority margins, family-cluster dependence, target power, type-I error, and
attrition/failure allowances. Every binding criterion, including groundedness improvement and
answer-adequacy preservation, must be powered. If the required cases or model-call budget are not
affordable, stop or revise prospectively; do not inspect partial outcomes and reduce the target.

The owner accepts the calculation, exact family count, response count, reviewer/adjudication task
budget, and stopping rule before C-confirm selects the final cohort.

## Sealing and developer-visible manifest

C-confirm freezes immutable content and inclusion manifests containing source bytes, question,
evidence, expected metadata, family mapping, selection rationale, and access declaration. Each file
and the manifest receive SHA-256 digests and an owner-observed UTC seal timestamp. No developer-open
timestamp is permitted before locked review and adjudication finish.

Developers may receive only a `generation-fidelity-manifest/v1` containing opaque cohort/run IDs,
counts, article-family digests, candidate and baseline prompt digests, software/runtime identities,
budget, seal timestamp, and custody declaration. It contains no source IDs, questions, evidence,
answers, annotations, mappings, or reversible low-entropy hashes.

## Dummy custody rehearsal

Before any real content is acquired, the owner and C-confirm use fabricated sentinel files under
representative credentials to demonstrate:

1. owner and C-confirm can write and seal content and mappings;
2. a candidate developer cannot list, read, search, back up, trace, or retrieve the sentinel;
3. CR1/CR2 can read only assigned opaque cases and cannot read mappings or peer exports;
4. CA can complete staged evidence-first adjudication without premature peer access;
5. approved exports contain no hidden source identity or unapproved content;
6. developers can read only the opaque manifest before release; and
7. the owner can revoke grants and record an authorized release.

Retain commands, identities, timestamps, access logs, sentinel digests, and denied-access results.
The rehearsal tests controls only; it is not scientific evidence. Because no separate permissioned
environment is currently named or available to this implementation, this rehearsal has not run.

## One-run confirmation boundary

Before execution, freeze baseline and candidate prompts, model/runtime labels and available
revisions, code commit, dependencies, retrieval/context inputs, cohort, pairing, rubric, role
prompts, decoding controls, thresholds, statistical analysis, unresolved handling, failure policy,
and request/continuation ceiling. Candidate A cannot change after this freeze.

There is one blinded run. Transport or malformed-output handling follows the prospectively accepted
policy; no semantic retries, best-of sampling, outcome-driven replacement, added families, or
developer-visible interim aggregate is permitted. All first-pass reviews freeze before peer access;
all adjudications lock before the owner releases outputs. The strongest intended future claim is
“improvement on a development-unexposed cohort under the frozen automated review protocol,” with
model-panel bias and uncalibrated scientific accuracy stated as limitations.

## Incident handling

On unexpected content, mapping, label, peer-output, or aggregate disclosure:

1. stop acquisition and model execution immediately;
2. revoke affected access without deleting logs or artifacts;
3. preserve the exposure identity, time, route, actor, and affected family set;
4. mark every affected family exposed;
5. have the owner decide whether the complete cohort is compromised; and
6. report the incident and disposition before any replacement design.

No silent substitution, continued use under an untouched label, or post-outcome resealing is
allowed.

## Readiness checklist

Custody remains `incomplete` until all missing prerequisites are resolved:

- a named separately permissioned account/environment;
- actual C-confirm, CR1, CR2, and CA session/model identities;
- developer-denied credentials and administrator boundary;
- logging, tracing, browser, backup, and retention controls;
- completed fabricated-sentinel rehearsal with retained evidence;
- accepted source-use policy and family-resolution procedure; and
- prospectively accepted sample-size calculation and run budget.

`specified` means every assignment and procedure above has a concrete implementation. Only a
successful dummy rehearsal permits `operationally-rehearsed`. Neither status means a real cohort
exists, may be acquired, or may be run without a separate accepted issue and owner authorization.
