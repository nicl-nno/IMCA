# Manual interpretation of IMCA vs Codebase-Memory retrieval disagreements

This document provides manual interpretation of representative disagreement cases identified by the reproducible quantitative analysis in `memory-retrieval-disagreement-causes.md`.

## Manual interpretation of representative cases


The quantitative analysis shows that the two retrieval methods do not differ uniformly across all query types.

### 1. IMCA is stronger on targeted symbol-to-symbol structural relations

Among the 41 comparable unique inputs where IMCA scores higher, 30 use a concrete symbol as the query anchor. The largest groups are `callers` and `callees`.

Representative cases include:

- `cross_module_callers-001`: the query asks for callers of `APIRouter#on_event`. IMCA returns the expected `FastAPI#on_event`, while Codebase-Memory returns no result.
- `cross_module_callers-003`: IMCA returns the expected `FastAPI#get`, while Codebase-Memory returns no result.
- `cross_module_callers-009`: IMCA returns the expected `FastAPI#include_router`, while Codebase-Memory returns no result.
- `callees_of_symbol-017`: IMCA retrieves all four expected callees of `FastAPI#setup`, while Codebase-Memory returns no result.

This suggests that, in the evaluated configuration, IMCA is often better at recovering targeted structural relations between concrete symbols, including cross-module relations.

### 2. Some Codebase-Memory losses are caused by empty or incompletely mapped structural results

In 10 of the 41 IMCA-higher cases, Codebase-Memory returns an empty result.

In another 10 IMCA-higher cases, its result contains at least one `unmapped-native` node, with 21 such occurrences in total.

For example, in `cross_module_sibling-008`, Codebase-Memory retrieves several relevant items from `encoders.py`, but one returned node remains unmapped and only three of five benchmark targets are recovered. IMCA retrieves all five expected targets.

These cases indicate that part of the observed difference is associated with graph-to-benchmark identifier mapping or missing structural candidates, rather than ranking alone.

### 3. Codebase-Memory is stronger in several broader file-level neighbourhood queries

Among the 9 comparable unique inputs where Codebase-Memory scores higher, 7 use a file as the query anchor.

For example:

- for `dependencies/utils.py`, IMCA finds one expected target, while Codebase-Memory finds two;
- for `security/http.py`, IMCA finds two of five expected targets, while Codebase-Memory finds four;
- for `openapi/models.py`, Codebase-Memory retrieves more expected model entities than IMCA.

In these cases IMCA is not empty. Instead, both methods retrieve plausible candidates, but Codebase-Memory covers a larger part of the expected local entity set.

This suggests that Codebase-Memory can be advantageous for broader file-level neighbourhood retrieval, where several related entities from the same local region are required.

## Interpretation

The comparison does not support a simple claim that one memory system is uniformly better.

The observed pattern is more specific:

- IMCA more often wins on targeted symbol-level structural queries, especially `callers` and `callees`;
- Codebase-Memory more often wins on broader file-level queries requiring several related entities;
- some IMCA wins are associated with empty Codebase-Memory results or unmapped native graph nodes.

These results describe the evaluated LongMemCode configuration only. They should not be interpreted as a general superiority claim for either complete memory system.

The next step is to test whether these retrieval differences also affect end-to-end agent task success under matched agent conditions.
