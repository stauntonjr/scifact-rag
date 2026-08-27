# Coreference solution assessment for SciFact retrieval

- Date: 2026-08-26
- Disposition: adapt
- Scope: abstract-side coreference resolution before sentence embedding

## Requirements

The experiment needs a maintained Python library that can process abstracts in batches, expose
character-offset mention clusters, run in the existing Python 3.12 Compose image, and permit an MIT
application to redistribute its own code without importing a non-commercial implementation. The
retrieval experiment—not an intrinsic coreference benchmark—is the acceptance boundary.

## Options reviewed

| Option | Evidence | Disposition |
|---|---|---|
| FastCoref with FCoref | Maintained Python implementation; batched prediction; character-offset clusters; MIT code and checkpoint | Adapt |
| FastCoref with LingMess | Supported by the same library, but larger and unnecessary for the first retrieval comparison | Defer |
| Maverick | Current neural coreference system, but code and OntoNotes checkpoint are CC BY-NC-SA 4.0 | Reject for this MIT prototype |
| spaCy experimental coreference | Experimental pipeline with an older ecosystem boundary and no advantage for this experiment | Reject |
| Bio-SCoRes | Domain-oriented historical Java/CoreNLP path, but adds a separate runtime and integration boundary | Reject |

## Decision

Use FastCoref's FCoref model through a small adapter owned by this project. Pin the source archive
to commit `ae224139196d122b225af5a7e73b5fc0b6e1076d` and use the `biu-nlp/f-coref` checkpoint. The
adapter exposes only text, mention spans, POS tags, and sentence splitting to the application. Two
project-owned canonicalization policies then choose either a proper noun or an explicit nominal
mention; FastCoref does not own that retrieval policy.

The immutable source archive is used instead of the lagging PyPI release and avoids adding Git to
the runtime image. `en_core_web_sm` is pinned separately for POS tags and sentence boundaries.
FastCoref and FCoref are licensed MIT. Maverick's non-commercial share-alike license is not
compatible with the selected dependency boundary.

## Cost and limitations

- The lock grows from 75 to 122 packages because FastCoref exposes training-oriented transitive
  dependencies in addition to inference requirements.
- The application image grows from 10.69 GB to 11.71 GB on this host.
- FCoref is a general-domain model, not a biomedical coreference model. Retrieval metrics on the
  full SciFact qrels determine usefulness here; no claim is made that the model improves intrinsic
  biomedical coreference accuracy.
- Coreference is loaded lazily and is required only for coreference ingestion. Searching,
  evaluating stored rows, and using token windows do not initialize it.

## Primary sources

- FastCoref repository and license: <https://github.com/shon-otmazgin/fastcoref>
- FastCoref dependency metadata: <https://github.com/shon-otmazgin/fastcoref/blob/main/pyproject.toml>
- FCoref checkpoint card: <https://huggingface.co/biu-nlp/f-coref>
- Maverick repository and license: <https://github.com/SapienzaNLP/maverick-coref>
- Maverick OntoNotes checkpoint card: <https://huggingface.co/sapienzanlp/maverick-mes-ontonotes>
