# Free Decider vs Jev representative evaluation

## Goal

Check whether a free decision model can be used as a semantic judge for the temporal-consistency experiments.

The free judge was evaluated on the same representative subset previously evaluated with Jev.

## Setup

- Representative contexts: 25
- Retrieval policies: 5
- Free judge: `perplexity/pplx-decider-v1.3:free`
- Comparison judge: Jev
- Shared Decider/Jev-v4 contexts: 20

The consistency judge was blinded to:
- retrieval-policy identity;
- benchmark reference evidence.

The evidence judge separately evaluated:
- reference evidence presence;
- answer inferability.

## Agreement with Jev

On the 20 shared contexts:

- `consistency_status`: 19/20 (95%)
- `conflict_type`: 16/20 (80%)
- `out_of_slice_evidence`: 20/20 (100%)
- `reference_evidence_present`: 17/20 (85%)
- `answer_inferable`: 15/20 (75%)
- exact agreement across all five fields: 12/20 (60%)

The highest agreement is observed for the two dimensions most directly related to the consistency task:
`consistency_status` and `out_of_slice_evidence`.

## Manual disagreement analysis

Manual inspection showed several systematic patterns.

### Decider errors

The free judge sometimes marks `answer_inferable=true` when a retrieved memory contains a general fact related to the query but does not establish that the fact applies to the specific requested date.

It also sometimes uses `temporal_update` too broadly for related events that are not clearly successive values of the same underlying state.

### Jev errors or ambiguous cases

In some cases Jev marks benchmark reference evidence as present even when the retrieved memories contain only a semantically related but less specific statement.

For the health-status example, Decider also gives a more coherent interpretation of successive state changes as `temporal_update` rather than a true contradiction.

## Current conclusion

The free Decider is sufficiently close to Jev to justify further validation, especially for:
- consistency classification;
- relevant versus harmful out-of-slice information.

However, the first prompt is too permissive for:
- date-specific answer inference;
- classification of temporal updates.

A second prompt version therefore adds two stricter rules:

1. A general fact is not enough for a date-specific query unless retrieved temporal information supports that it applies to the requested date.
2. `temporal_update` is used only for successive values or states of the same underlying attribute or condition.

The refined version should be validated again on the same 25 representative contexts before being used for the full 135-context evaluation.
