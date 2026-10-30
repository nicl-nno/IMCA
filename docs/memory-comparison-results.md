# Memory systems for a coding agent

The aim is to test whether memory helps an agent find relevant code and resolve issues under the same resource limits.

## System selection

Papers and open implementations of MemGovern, Codebase-Memory, SWE-Exp, ExpeRepair, A-MEM and Mem0 were reviewed. MemGovern was selected for experiments with previous repair experience. Codebase-Memory was selected for source retrieval over the same repository files. These tracks are kept separate because they use different information.

## Retrieval comparison

All 425 LongMemCode tasks were evaluated on the same FastAPI source snapshot.

| Method | Full-score retrieval checks |
| --- | ---: |
| IMCA | 272 / 425 |
| Structural queries over the Codebase-Memory graph | 261 / 425 |
| BM25 | 142 / 425 |

Codebase-Memory was evaluated through a fixed structural-query adapter. The result concerns this retrieval configuration, not the complete system. All 228 distinct native queries were validated against the actual index. The saved results were independently reproduced.

These are retrieval tasks over one repository previously used in development. The counts are not software issues repaired or evidence of general superiority.

## Agent pilots

On one Flask issue, the agent without memory produced a patch that passed the task's tests. Of three attempts with MemGovern, two were interrupted by connection or request-rate failures. The third reached the client step limit without changing code.

Three attempts were then run on one Sphinx issue using the same GLM-5.3-flash agent: without memory, with IMCA and with Codebase-Memory. Both memory systems received the same 182 Python files. The attempts used 23 model requests. The agent called memory tools in both memory conditions.

All three attempts produced empty patches. Two reached the client step limit; one ended at the response-length limit. Repair tests were not executed because no changes were submitted.

## Conclusion and next step

The work provides a reproducible retrieval comparison and verifies the connection of two memory systems to a common agent. A repair benefit from memory has not been established. The next step is to test revised common limits on development tasks before the main comparison.
