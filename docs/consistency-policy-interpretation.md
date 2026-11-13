# Interpretation of matched-condition consistency policy comparison

## Research question

The experiment studies the trade-off between temporal consistency and preservation of useful historical evidence.

Five retrieval policies are compared under matched conditions:

- `flat_bm25`;
- `strict_temporal`;
- `query_aware`;
- `transition_aware`;
- `before_aware`.

All policies receive the same HaluMem-Medium question, the same memory corpus, the same BM25 index and the same top-k=5 retrieval budget. Only the temporal retrieval policy differs.

The analysis is performed on 27 selected `Memory Conflict` error cases where flat BM25 previously retrieved benchmark evidence that strict temporal retrieval missed. Therefore the results characterize this failure subset and must not be interpreted as benchmark-wide accuracy.

## Main trade-off

The experiment shows a clear trade-off between temporal filtering and preservation of reference evidence.

### Flat BM25

`flat_bm25` retrieves benchmark evidence in all 27 selected cases:

- Hit@5: 100%;
- Recall@5: 82.72%.

However, it also returns 101 out-of-slice slots, and every one of the 27 cases contains at least one temporally invalid result.

Therefore flat retrieval maximizes evidence recovery on this subset but provides the weakest temporal filtering.

### Strict temporal retrieval

`strict_temporal` produces:

- Hit@5: 0%;
- Recall@5: 0%;
- out-of-slice slots: 0.

This is expected because the subset was specifically selected from cases where strict temporal retrieval loses evidence found by flat BM25.

The result demonstrates the failure mode under investigation: a strict temporal slice can completely remove benchmark evidence that is still useful for answering a temporal question.

### Query-aware retrieval

`query_aware` recovers the largest part of the lost evidence among the temporal-aware alternatives:

- Hit@5: 44.44% overall;
- 12 of 27 cases improve over strict temporal;
- on transition/retrospective questions, Hit@5 reaches 70.59%.

The cost is weaker temporal filtering:

- 17 out-of-slice slots;
- 17 of 27 cases contain at least one out-of-slice result.

Thus query-aware retrieval occupies the most permissive intermediate position between flat BM25 and strict temporal filtering.

### Transition-aware retrieval

`transition_aware` is more conservative:

- Hit@5: 11.11%;
- 3 cases improve over strict temporal;
- 15 out-of-slice slots.

The policy only admits an external candidate when it participates in an explicit update/replacement relation.

The relatively small recovery rate supports the earlier observation that explicit replacement links explain only a minority of the strict-temporal failures.

### Before-aware retrieval

`before_aware` is the most conservative relaxation:

- Hit@5: 3.70%;
- only 1 of 27 cases improves over strict temporal;
- only 1 out-of-slice slot is introduced.

This means the policy preserves temporal validity almost completely, but recovers very little of the lost evidence on the full 27-case subset.

Its value is therefore not broad evidence recovery, but a narrow correction for selected retrospective `before` questions.

## Query-type asymmetry

The distinction between query types is important.

Among the 17 transition/retrospective questions:

- `query_aware` recovers evidence in 12 cases;
- `transition_aware` in 3;
- `before_aware` in 1.

Among the 10 state-at-time questions:

- `strict_temporal`;
- `query_aware`;
- `transition_aware`;
- `before_aware`

all have Hit@5 equal to 0 on this selected failure subset.

This is expected because the relaxed policies largely preserve strict temporal behaviour for state-at-time queries.

The result supports the hypothesis that temporal retrieval policy should depend on query semantics rather than using the same relaxation for every temporal question.

## Reference evidence after question time

In 24 of the 27 cases, the benchmark reference evidence occurs after the interpreted question time.

For these cases:

- strict temporal filtering removes the evidence by construction;
- query-aware retrieval recovers evidence in 10 cases;
- transition-aware retrieval in 1;
- before-aware retrieval in 1.

This confirms that a timestamp later than the interpreted question time does not automatically make a memory item useless.

For retrospective questions, later evidence may be necessary to infer whether an event had already happened before the queried date.

## Important limitation

An out-of-slice result is not automatically a harmful contradiction.

The deterministic metrics used here establish only:

- whether benchmark reference evidence is retrieved;
- how much of that evidence is retrieved;
- whether retrieved memories are valid at the interpreted question time.

They do not establish whether an out-of-slice fact is:

- useful historical evidence;
- a legitimate temporal update;
- a true contradiction;
- harmful stale information;
- or sufficient for answering the question.

Therefore `query_aware` should not yet be described as the best consistency policy merely because it recovers the most benchmark evidence.

The semantic consistency layer must be evaluated separately using the existing AutoJudge and evidence-vs-inference framework.

## Current conclusion

The results support the central research hypothesis:

> Temporal consistency and answer-supporting evidence retrieval are competing objectives.

Strict temporal filtering maximizes temporal validity but can discard useful historical evidence.

Flat BM25 preserves the most evidence but also introduces the most temporally invalid context.

The query-aware, transition-aware and before-aware policies occupy different points between these two extremes.

Among the tested relaxations:

- `query_aware` maximizes recovery of lost evidence;
- `before_aware` minimizes additional temporal invalidity;
- `transition_aware` provides a conservative update-linked relaxation but covers relatively few failure cases.

The next step is to evaluate which out-of-slice memories are actually useful, harmful or contradictory, rather than treating every temporally invalid slot as equally undesirable.
