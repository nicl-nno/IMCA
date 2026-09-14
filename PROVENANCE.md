# Artifact provenance and reproducibility boundary

This repository is a standalone research implementation, not a plugin release.
It has its own Python environment, retrieval adapter, scoring module and entry
points. It neither imports nor requires any other agent-memory implementation.

## Included material

1. Research code authored for inspectable assertion memory, conversation memory,
   source-backed code relations, immutable replay, and the local demo.
2. Newly generated standalone BM25/RRF execution, benchmark scoring, data
   verification, environment configuration, and release-specific tests.
3. The MIT-licensed public FastAPI source snapshot, source excerpts, public
   LongMemCode scenarios and projected SCIP. Licenses and source pins are retained.
4. Derived experimental rankings and aggregate measurements. No credentials,
   model weights, user conversations or session logs are included. The only
   conversation benchmark data are fetched explicitly from the public upstream.

No server bootstrap, original plugin/configuration code, embedding engine,
provider configuration, archive, or development repository history is included.
Source files were selected explicitly and checked against excluded source
archives before publication; this is not a blanket repository copy or rename.

## What is independent and what is recorded

The demo, SQLite memory and LoCoMo experiment execute independently. The six
LoCoMo source files are byte-identical to the frozen research versions referenced
in `results/locomo_reference.json`, preserving the published rule behavior.

Code search reconstructs all graph edges and witnesses from the bundled public
source and projected SCIP. Its ranking implementation is standalone. To retain
the exact historical comparison, the fallback can consume a **recorded dense
ranking** as data. This is not a new embedding call and is not claimed to
reproduce the dense engine. `--fresh-bm25` removes that dependency for a new
fully lexical/structural experiment; results must be labeled separately.

Historical reader responses are records from the original frozen top-5 only.
The release does not call a model or regenerate those responses. Source graph
rebuilding does not recreate the authored temporal scenario schedule; that
schedule is an explicit fixture and is tested independently of retrieval.

`data/manifest.json` hashes bundled source/data assets. Code and dependency
versions are pinned by Git and `uv.lock`. Fresh evaluations record their own
source hashes; do not overwrite the historical reference files to make a test pass.

The supplemental storage microbenchmark is not a main-paper experiment and is
not part of this release. No claim is made that this artifact reproduces all
earlier exploratory algorithms or the runtime of a different implementation.
