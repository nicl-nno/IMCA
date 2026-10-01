# Consistency Analysis: Temporal Retrieval Failure Cases

## Goal

This analysis studies temporal retrieval failure cases related to consistency-sensitive HaluMem questions in IMCA.

The current HaluMem diagnostic compares:

- flat retrieval — lexical retrieval over all available memory points;
- temporal retrieval — retrieval restricted to memory points considered valid at the interpreted question time.

The goal of this analysis is to understand cases where temporal filtering removes information required to answer a memory-conflict question.

## Reproduced HaluMem results

| Metric | Flat retrieval | Temporal retrieval |
|---|---:|---:|
| Hit@5 | 74.88% | 74.95% |
| Recall@5 | 59.94% | 60.02% |
| Invalid result slots | 1173 | 0 |
| Memory Conflict Hit@5 | 84.92% | 83.22% |

Temporal filtering removes all result slots considered invalid at the interpreted question date while preserving overall retrieval quality.

However, on the Memory Conflict subset, Hit@5 decreases from 84.92% to 83.22%.

There are:

- 14 cases where temporal retrieval improves over flat retrieval;
- 27 cases where flat retrieval succeeds but temporal retrieval fails.

## Error analysis

All 27 cases where flat retrieval achieved Hit@5 and temporal retrieval did not were inspected.

| Error group | Cases | Share |
|---|---:|---:|
| Transition or retrospective questions | 17 | 63.0% |
| State-at-time questions | 10 | 37.0% |
| Total | 27 | 100% |

Additionally, in 24 of the 27 failures, the required evidence has a memory timestamp later than the date mentioned in the question.

Three cases are associated with an explicitly linked memory update, and one case contains a zero-length validity interval.

## Observed limitation

The current HaluMem adapter interprets a date mentioned in the question as the target time and restricts retrieval to facts active at that time.

This works well for removing stale information, but it can be too restrictive for retrospective and transition questions.

For example:

> Did Donna establish EcoStrategic Consulting before March 01, 2038?

Relevant evidence states that Donna launched the company on July 1, 2038.

Although this evidence refers to a later time, it is necessary to establish that the company had not been launched before March.

Therefore, evidence occurring after the queried date is not always inconsistent or irrelevant.

## Working hypothesis

A single point-in-time filtering rule is insufficient for all temporal questions.

The next experiment will investigate query-aware temporal retrieval that distinguishes between:

1. state-at-time queries;
2. retrospective queries;
3. state-transition queries;
4. conflict/update queries.

The aim is to preserve the consistency benefit of temporal filtering while retaining historical or later evidence when it is necessary to reason about a state transition.

## Relation to IMCA

IMCA distinguishes valid time (when an assertion holds) from recorded/knowledge time (when the assertion became known).

The current HaluMem adapter uses a simplified temporal representation. The next step is to test whether separating temporal semantics and query intent reduces the observed Memory Conflict retrieval losses.
