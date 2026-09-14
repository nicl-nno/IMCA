# Standalone release verification

Verified September 15, 2026 on Windows, Python 3.13.7, in the standalone
repository's new virtual environment. No memory service or LLM was configured.

- 52 tests passed, including HTTP, real SQLite and full 425-task graph parity.
- Source graph/BM25/RRF reconstruction with recorded dense rank input matched
  all 425 historical top-5 lists. Its independently implemented scorer gave
  272 fully passed tasks, weighted 0.7152121855, raw 0.6976862745.
- Removing recorded dense ranks (`--fresh-bm25`) matched 398 historical lists,
  but retained the same aggregate scores. This is a distinct new run.
- Rebuilt demo fixture loaded successfully through the same runtime.
- Temporal evaluation reproduced all four rule-setting summaries: 36/36 exact
  selections for temporal/combined rules; six true conflicts and zero false
  alarms for combined rules; 24 false alarms for conflict-only rules.
- LoCoMo was downloaded from its pinned public source and re-executed with
  three calls per question/profile. All 33,762 ordered top-5 lists, paired
  results, category metrics and narrow calendar results matched the historical
  reference. Final Hit@5: 0.634765625, 75 wins and no Hit@5 losses versus BM25.
- Six frozen LoCoMo research source hashes matched their reference exactly.
- A release scan checked prospective Git files for excluded identifiers,
  credential patterns, local development paths, 16-line normalized source
  matches and exact substantial Python functions against excluded archives
  (246 source files). No matches required review. Public licensed FastAPI
  source is handled separately through source pins and retained licensing.

These checks support reproducibility and provenance review, not a mathematical
proof of absence of confidential material. New timings are not substituted for
the historical paper timings. The benchmark selection-bias and replay limits
in README/PROVENANCE remain applicable.
