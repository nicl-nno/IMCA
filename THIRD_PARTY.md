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

## MemoryAgentBench

- Source: https://github.com/HUST-AI-HYZ/MemoryAgentBench
- Dataset revision: `7ea066982b140a19337e17e60d45d4076e042faf`.
- Evaluated file SHA-256:
  `24d5c3f09ce0ce15625cb9f8a98f44f0d864ca6c94d7b4ad04eb697ca3a5ff45`.
- License: MIT. Raw Parquet data is downloaded to ignored `outputs/`; only
  aggregate metrics and numeric row identifiers are retained in the artifact.

## HaluMem

- Source: https://github.com/MemTensor/HaluMem
- Dataset revision: `cb04336aa1b732d4b24f5186c552456b4099806e`.
- Evaluated file SHA-256:
  `486fbc130a5c8781a2af27ffa508a1d7855245137aa449c193ac4d29c45634e7`.
- License: CC-BY-NC-ND-4.0. The dataset is not redistributed. The downloader
  stores it only in ignored `outputs/`; the committed reference contains
  aggregate counts and metrics, not dialogue, questions, answers, or evidence.

## Libraries

The demo and conversation runtime use only Python's standard library. Code
retrieval uses NumPy; tests use pytest. Optional raw-SCIP projection uses the
public `@scip-code/scip` and `@bufbuild/protobuf` libraries. Their packages retain
their respective licenses; they are not vendored in this repository.
The additional MemoryAgentBench adapter uses PyArrow from the optional
`benchmark` dependency group to read the pinned public Parquet file.
