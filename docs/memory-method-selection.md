# Memory system selection

Six systems with papers and open implementations were reviewed. Selection considers the information stored and the feasibility of connecting each system to a common coding agent.

| System | Memory content | Role |
| --- | --- | --- |
| Codebase-Memory | Source code and relationships between code elements | Selected for retrieval over the current repository. |
| MemGovern | Previous repair experience | Selected for a separate historical-experience track. |
| SWE-Exp | Experience from successful and unsuccessful attempts | Additional candidate with its own experience-selection procedure. |
| ExpeRepair | Repair examples and generalized guidance | Additional candidate coupled to its own repair and testing agents. |
| A-MEM | Linked text notes | Possible additional method for a shared set of records. |
| Mem0 | Facts extracted from messages | Possible additional method. Managed-service results cannot automatically be attributed to the open library. |

Codebase-Memory was selected for the first current-source comparison because it supports a local index and queries without supplying repair history. A pinned implementation is used. Reproduction of the paper's results is not claimed.

MemGovern is considered separately because it uses a different information source. A main historical-experience comparison requires a common set of available records and exclusion of information about solutions to the evaluated tasks.

SWE-Exp, ExpeRepair, A-MEM and Mem0 were reviewed during selection but were not run in the reported experiments. BM25 is used as a retrieval baseline.

## Sources

| System | Paper | Implementation |
| --- | --- | --- |
| Codebase-Memory | [Paper](https://arxiv.org/abs/2603.27277v1) | [Code](https://github.com/DeusData/codebase-memory-mcp) |
| MemGovern | [Paper](https://arxiv.org/abs/2601.06789v2) | [Code](https://github.com/QuantaAlpha/MemGovern) |
| SWE-Exp | [Paper](https://arxiv.org/abs/2507.23361v2) | [Code](https://github.com/cslsolow/SWE-Exp) |
| ExpeRepair | [Paper](https://arxiv.org/abs/2506.10484v2) | [Code](https://github.com/ExpeRepair/ExpeRepair) |
| A-MEM | [Paper](https://arxiv.org/abs/2502.12110v11) | [Code](https://github.com/WujiangXu/A-mem-sys) |
| Mem0 | [Paper](https://arxiv.org/abs/2504.19413v1) | [Code](https://github.com/mem0ai/mem0) |
