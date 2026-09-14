# Third-party material

Original research code is covered by the repository's existing BSD-3-Clause
[LICENSE](LICENSE). That license does not replace upstream data/source licenses.

## FastAPI

- Source: https://github.com/fastapi/fastapi
- Revision: `a84001000e59ff362e74f93b8d9a58a4309dac2d` (0.117.0).
- Material: `data/code/source/`, excerpts in `data/code/documents.json` and
  `demo/inspectable/fixture.json`.
- License: [MIT](demo/inspectable/LICENSE.fastapi), retained unmodified.

## LongMemCode

- Source: https://github.com/CataDef/LongMemCode
- Revision: `0c89128fcf7215d0996d7bff6f571589d573081b`.
- Material: public scenario specifications, stable symbol identifiers,
  derived projected SCIP and evaluation metadata.
- License: [MIT](demo/inspectable/LICENSE.longmemcode), retained unmodified.
- The scorer in `python/code_metrics.py` is an independent implementation of
  the public expected-answer contract, not a copy of an agent-memory backend.

## LoCoMo

- Source: https://github.com/snap-research/locomo
- Revision: `3eb6f2c585f5e1699204e3c3bdf7adc5c28cb376`.
- Dataset SHA-256:
  `79fa87e90f04081343b8c8debecb80a9a6842b76a7aa537dc9fdf651ea698ff4`.
- The dataset itself is not distributed here. The downloader checks the public
  pinned file before accepting it. See the upstream `LICENSE.txt` and dataset
  usage terms; the research-code license does not relicense that dataset.
- Committed references contain question identifiers, retrieved turn identifiers
  and aggregate statistics, not raw conversations or questions.

## Libraries

The demo and conversation runtime use only Python's standard library. Code
retrieval uses NumPy; tests use pytest. Optional raw-SCIP projection uses the
public `@scip-code/scip` and `@bufbuild/protobuf` libraries. Their packages retain
their respective licenses; they are not vendored in this repository.
