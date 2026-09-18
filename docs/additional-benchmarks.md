# Additional benchmark selection and results

## Why these two

The demo method has two claims that the earlier LoCoMo and LongMemCode runs do
not isolate cleanly: relational traversal through conflicting facts, and
time-valid recall after explicit replacement. Two public benchmarks were fixed
before evaluation:

| Benchmark | Fixed scope | What it tests here | Why it fits |
|---|---:|---|---|
| MemoryAgentBench Conflict Resolution | official `factconsolidation_sh_6k` and `factconsolidation_mh_6k`, 100 questions each | answer-bearing fact in top 5 | contradictory fact chains and multi-hop adjacency traversal |
| HaluMem-Medium | all 20 users, 3,467 questions; 2,639 have positive evidence | evidence Hit@5/Recall@5 and invalid result slots | explicit updates, dated queries, provenance, memory conflicts and boundaries |

MemoryArena and MemGym are stronger choices for a later end-to-end agent study,
especially for an interactive demo or a coding agent. They were not used here:
their scores mix memory with planning, tool use and model reasoning, whereas the
current question is whether the memory rules themselves help. PersonaMem is a
good third choice for preference drift but requires a common response model to
score choices. The two selected diagnostics run without a model.

## Protocol

Both source files are commit- and SHA-256-pinned by
`experiments/download_additional_benchmarks.py`. Expected answers and evidence
are accessed only after a top-5 list is frozen.

MemoryAgentBench compares lexical BM25 with a typed adjacency list. The graph
keeps the three strongest direct facts, expands from the strongest seed for up
to three hops, and uses a syntax-only gate for nested relational questions. It
does not inspect answers, question IDs or the benchmark's single/multi-hop label
when routing. The metric is an answer-string evidence proxy, not the official
reader accuracy.

HaluMem compares a flat lexical store with a bitemporal view. Upstream
`memory_points` are treated as structured writes; `original_memories` closes a
half-open validity interval. The date in the question selects a snapshot, and
the session timestamp is the fallback. This is an **oracle-writer diagnostic**:
it isolates storage and retrieval after extraction, so it is not comparable to
HaluMem leaderboard extraction, update or LLM-judged QA scores.

All rows were used while developing the adapters and the syntax/date rules.
They are development results, not held-out generalization. In particular, the
HaluMem question date is an interpretation of event validity, not a timezone-
aware timestamp supplied by the benchmark.

## Results

Reference machine: Windows 11, Python 3.13.7. No model calls were made.

### MemoryAgentBench

| Scope | n | BM25 Hit@5 | guarded graph Hit@5 |
|---|---:|---:|---:|
| single-hop 6k | 100 | 100.0% | 100.0% |
| multi-hop 6k | 100 | 12.0% | 24.0% |
| combined | 200 | 56.0% | 62.0% |

Paired outcome: 13 wins, 1 loss, 186 ties. BM25 latency was 0.21 ms p50 / 0.35
ms p95. Routed graph queries were approximately 2.5 ms p95. The useful result is
the doubled multi-hop evidence hit rate with no aggregate regression on the
single-hop half; it is not proof that a reader will double answer accuracy.

### HaluMem-Medium

| Metric, evidence-bearing questions only (n=2,639) | flat | bitemporal |
|---|---:|---:|
| Hit@5 | 74.88% | 74.95% |
| Recall@5 | 59.94% | 60.02% |
| result slots invalid at interpreted question date | 1,173 | 0 |
| query latency p50 / p95 | 0.44 / 0.90 ms | 0.41 / 0.85 ms |

The quality change is essentially neutral: 42 paired wins and 40 losses. The
strong result is safety and interpretability—invalid assertions disappear from
the returned context without reducing aggregate evidence retrieval. Dynamic
Update moves from 69.44% to 70.00% Hit@5 and Multi-hop Inference from 70.71% to
73.74%. Memory Conflict drops from 84.92% to 83.22%; some questions require both
old and new assertions, so a future version should return an explicit
transition bundle instead of only the fact valid at one instant.

## Reproduce

```bash
uv sync --frozen --group benchmark
uv run --frozen --group benchmark python experiments/download_additional_benchmarks.py
uv run --frozen --group benchmark python experiments/additional_benchmark_eval.py \
  --output outputs/additional-benchmarks.json
```

The raw benchmark files remain under ignored `outputs/`. The compact aggregate
reference is `benchmark_artifacts/additional_benchmarks_reference.json`.
