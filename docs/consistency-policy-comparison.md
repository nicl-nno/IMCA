# Matched-condition consistency policy comparison

This report compares five retrieval policies on the same 27 selected HaluMem-Medium `Memory Conflict` cases.

All policies use the same question, memory corpus, BM25 index and top-k=5 retrieval budget. Only the temporal retrieval policy differs.

These 27 cases were selected because flat BM25 previously retrieved benchmark evidence that strict temporal retrieval missed. Therefore this is an error-analysis subset, not an unbiased estimate over all HaluMem questions.

## Overall: 27 selected error cases

| Policy | N | Hit@5 | Recall@5 | Out-of-slice slots | Cases with out-of-slice |
|---|---:|---:|---:|---:|---:|
| `flat_bm25` | 27 | 100.00% | 82.72% | 101 | 27 (100.00%) |
| `strict_temporal` | 27 | 0.00% | 0.00% | 0 | 0 (0.00%) |
| `query_aware` | 27 | 44.44% | 33.33% | 17 | 17 (62.96%) |
| `transition_aware` | 27 | 11.11% | 11.11% | 15 | 15 (55.56%) |
| `before_aware` | 27 | 3.70% | 3.70% | 1 | 1 (3.70%) |

### Paired comparison vs strict temporal

| Policy | Hit wins | Hit losses | Hit ties | Recall wins | Recall losses | Recall ties |
|---|---:|---:|---:|---:|---:|---:|
| `flat_bm25` | 27 | 0 | 0 | 27 | 0 | 0 |
| `query_aware` | 12 | 0 | 15 | 12 | 0 | 15 |
| `transition_aware` | 3 | 0 | 24 | 3 | 0 | 24 |
| `before_aware` | 1 | 0 | 26 | 1 | 0 | 26 |

## Transition / retrospective questions

| Policy | N | Hit@5 | Recall@5 | Out-of-slice slots | Cases with out-of-slice |
|---|---:|---:|---:|---:|---:|
| `flat_bm25` | 17 | 100.00% | 85.29% | 64 | 17 (100.00%) |
| `strict_temporal` | 17 | 0.00% | 0.00% | 0 | 0 (0.00%) |
| `query_aware` | 17 | 70.59% | 52.94% | 17 | 17 (100.00%) |
| `transition_aware` | 17 | 17.65% | 17.65% | 15 | 15 (88.24%) |
| `before_aware` | 17 | 5.88% | 5.88% | 1 | 1 (5.88%) |

### Paired comparison vs strict temporal

| Policy | Hit wins | Hit losses | Hit ties | Recall wins | Recall losses | Recall ties |
|---|---:|---:|---:|---:|---:|---:|
| `flat_bm25` | 17 | 0 | 0 | 17 | 0 | 0 |
| `query_aware` | 12 | 0 | 5 | 12 | 0 | 5 |
| `transition_aware` | 3 | 0 | 14 | 3 | 0 | 14 |
| `before_aware` | 1 | 0 | 16 | 1 | 0 | 16 |

## State-at-time questions

| Policy | N | Hit@5 | Recall@5 | Out-of-slice slots | Cases with out-of-slice |
|---|---:|---:|---:|---:|---:|
| `flat_bm25` | 10 | 100.00% | 78.33% | 37 | 10 (100.00%) |
| `strict_temporal` | 10 | 0.00% | 0.00% | 0 | 0 (0.00%) |
| `query_aware` | 10 | 0.00% | 0.00% | 0 | 0 (0.00%) |
| `transition_aware` | 10 | 0.00% | 0.00% | 0 | 0 (0.00%) |
| `before_aware` | 10 | 0.00% | 0.00% | 0 | 0 (0.00%) |

### Paired comparison vs strict temporal

| Policy | Hit wins | Hit losses | Hit ties | Recall wins | Recall losses | Recall ties |
|---|---:|---:|---:|---:|---:|---:|
| `flat_bm25` | 10 | 0 | 0 | 10 | 0 | 0 |
| `query_aware` | 0 | 0 | 10 | 0 | 0 | 10 |
| `transition_aware` | 0 | 0 | 10 | 0 | 0 | 10 |
| `before_aware` | 0 | 0 | 10 | 0 | 0 | 10 |

## Reference evidence after interpreted question time

| Policy | N | Hit@5 | Recall@5 | Out-of-slice slots | Cases with out-of-slice |
|---|---:|---:|---:|---:|---:|
| `flat_bm25` | 24 | 100.00% | 82.64% | 97 | 24 (100.00%) |
| `strict_temporal` | 24 | 0.00% | 0.00% | 0 | 0 (0.00%) |
| `query_aware` | 24 | 41.67% | 29.17% | 15 | 15 (62.50%) |
| `transition_aware` | 24 | 4.17% | 4.17% | 13 | 13 (54.17%) |
| `before_aware` | 24 | 4.17% | 4.17% | 1 | 1 (4.17%) |

### Paired comparison vs strict temporal

| Policy | Hit wins | Hit losses | Hit ties | Recall wins | Recall losses | Recall ties |
|---|---:|---:|---:|---:|---:|---:|
| `flat_bm25` | 24 | 0 | 0 | 24 | 0 | 0 |
| `query_aware` | 10 | 0 | 14 | 10 | 0 | 14 |
| `transition_aware` | 1 | 0 | 23 | 1 | 0 | 23 |
| `before_aware` | 1 | 0 | 23 | 1 | 0 | 23 |

## Reference evidence not after interpreted question time

| Policy | N | Hit@5 | Recall@5 | Out-of-slice slots | Cases with out-of-slice |
|---|---:|---:|---:|---:|---:|
| `flat_bm25` | 3 | 100.00% | 83.33% | 4 | 3 (100.00%) |
| `strict_temporal` | 3 | 0.00% | 0.00% | 0 | 0 (0.00%) |
| `query_aware` | 3 | 66.67% | 66.67% | 2 | 2 (66.67%) |
| `transition_aware` | 3 | 66.67% | 66.67% | 2 | 2 (66.67%) |
| `before_aware` | 3 | 0.00% | 0.00% | 0 | 0 (0.00%) |

### Paired comparison vs strict temporal

| Policy | Hit wins | Hit losses | Hit ties | Recall wins | Recall losses | Recall ties |
|---|---:|---:|---:|---:|---:|---:|
| `flat_bm25` | 3 | 0 | 0 | 3 | 0 | 0 |
| `query_aware` | 2 | 0 | 1 | 2 | 0 | 1 |
| `transition_aware` | 2 | 0 | 1 | 2 | 0 | 1 |
| `before_aware` | 0 | 0 | 3 | 0 | 0 | 3 |

## Expired reference evidence

| Policy | N | Hit@5 | Recall@5 | Out-of-slice slots | Cases with out-of-slice |
|---|---:|---:|---:|---:|---:|
| `flat_bm25` | 3 | 100.00% | 83.33% | 4 | 3 (100.00%) |
| `strict_temporal` | 3 | 0.00% | 0.00% | 0 | 0 (0.00%) |
| `query_aware` | 3 | 66.67% | 66.67% | 2 | 2 (66.67%) |
| `transition_aware` | 3 | 66.67% | 66.67% | 2 | 2 (66.67%) |
| `before_aware` | 3 | 0.00% | 0.00% | 0 | 0 (0.00%) |

### Paired comparison vs strict temporal

| Policy | Hit wins | Hit losses | Hit ties | Recall wins | Recall losses | Recall ties |
|---|---:|---:|---:|---:|---:|---:|
| `flat_bm25` | 3 | 0 | 0 | 3 | 0 | 0 |
| `query_aware` | 2 | 0 | 1 | 2 | 0 | 1 |
| `transition_aware` | 2 | 0 | 1 | 2 | 0 | 1 |
| `before_aware` | 0 | 0 | 3 | 0 | 0 | 3 |

## Zero-length validity interval

| Policy | N | Hit@5 | Recall@5 | Out-of-slice slots | Cases with out-of-slice |
|---|---:|---:|---:|---:|---:|
| `flat_bm25` | 1 | 100.00% | 100.00% | 1 | 1 (100.00%) |
| `strict_temporal` | 1 | 0.00% | 0.00% | 0 | 0 (0.00%) |
| `query_aware` | 1 | 100.00% | 100.00% | 1 | 1 (100.00%) |
| `transition_aware` | 1 | 100.00% | 100.00% | 1 | 1 (100.00%) |
| `before_aware` | 1 | 0.00% | 0.00% | 0 | 0 (0.00%) |

### Paired comparison vs strict temporal

| Policy | Hit wins | Hit losses | Hit ties | Recall wins | Recall losses | Recall ties |
|---|---:|---:|---:|---:|---:|---:|
| `flat_bm25` | 1 | 0 | 0 | 1 | 0 | 0 |
| `query_aware` | 1 | 0 | 0 | 1 | 0 | 0 |
| `transition_aware` | 1 | 0 | 0 | 1 | 0 | 0 |
| `before_aware` | 0 | 0 | 1 | 0 | 0 | 1 |

## Interpretation boundary

This deterministic analysis measures retrieval of benchmark reference evidence and temporal validity of retrieved slots. It does not by itself determine whether the retrieved context contains a true semantic contradiction, whether an out-of-slice fact is useful rather than harmful, or whether the answer can still be inferred without the benchmark reference evidence.

Those properties require the separate consistency / evidence-vs-inference evaluation.
