"""Standalone code retrieval: public source graph, BM25, and auditable RRF.

No model, service or plugin implementation is needed. The optional dense order
is an explicitly recorded input channel. Omitting it gives a new BM25-fallback
experiment, NOT a reproduction of the historical dense system.
"""

import math
import re
from collections import Counter, defaultdict

import numpy as np
from code_structural_memory import ScipStructuralIndex

# Frozen exploratory policy, not a claim that weights were never tuned.
POLICY = {
    "file_symbols": (10, (1, 4, 0, 8, 0)),
    "contained_by": (60, (1, 0, 0, 0, 0)),
    "implementors": (60, (1, 4, 0, 4, 8)),
    "callers": (60, (1, 1, 1, 4, 0)),
    "callees": (10, (1, 0.25, 8, 0, 0)),
    "orphans": (60, (1, 0, 0, 0, 0)),
}
CHANNELS = ("structural_order", "bm25", "edge_frequency", "graph_degree", "id_overlap")


def tokens(text):
    parts = []
    for word in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text):
        parts.append(word.lower())
        split = re.findall(r"[A-Z]+(?=[A-Z][a-z]|\b)|[A-Z]?[a-z]+|[A-Za-z_][A-Za-z0-9_]*|\d+", word)
        parts.extend(piece.lower() for piece in split if piece.lower() != word.lower())
        if "_" in word:
            parts.extend(piece.lower() for piece in word.split("_") if piece)
    return parts


class BM25:
    def __init__(self, texts):
        counts = [Counter(tokens(text)) for text in texts]
        self.lengths = np.array([sum(c.values()) for c in counts], dtype=np.float32)
        self.average = float(self.lengths.mean()) or 1
        self.postings = defaultdict(list)
        for i, counter in enumerate(counts):
            for token, frequency in counter.items():
                self.postings[token].append((i, frequency))
        self.idf = {
            token: math.log(1 + (len(texts) - len(rows) + 0.5) / (len(rows) + 0.5))
            for token, rows in self.postings.items()
        }

    def scores(self, question):
        scores = np.zeros(len(self.lengths), dtype=np.float32)
        for term, query_frequency in Counter(tokens(question)).items():
            rows = self.postings.get(term)
            if not rows:
                continue
            indices = np.array([row[0] for row in rows], dtype=np.int64)
            frequencies = np.array([row[1] for row in rows], dtype=np.float32)
            denominator = frequencies + 1.2 * (0.25 + 0.75 * self.lengths[indices] / self.average)
            scores[indices] += self.idf[term] * (frequencies * 2.2 / denominator) * query_frequency
        return scores


def fuse(rankings, weights, constant):
    scores = defaultdict(float)
    for ranking, weight in zip(rankings, weights, strict=True):
        if weight:
            for rank, index in enumerate(ranking, 1):
                scores[index] += weight / (constant + rank)
    return sorted(scores, key=lambda i: (-scores[i], i)), scores


class CodeSearch:
    def __init__(self, documents, projection, source_root):
        self.documents = documents
        self.ids = [doc["id"] for doc in documents]
        self.positions = {sid: i for i, sid in enumerate(self.ids)}
        self.graph = ScipStructuralIndex(
            projection, source_root, self.ids, documents, collect_witnesses=True
        )
        self.lexical = BM25([doc["text"] for doc in documents])

    def route(self, query, question, *, relation="references", dense_order=None):
        """Inputs deliberately contain no expected answers or scoring labels."""
        result = self.graph.search(query, limit=512, caller_mode=relation)
        indices = [self.positions[sid] for sid in result.ids]
        op, target = query.get("op"), query.get("sym_stable_id", "")
        lexical = self.lexical.scores(question)
        fallback = not indices and op != "lookup"
        if fallback:
            sparse = sorted(range(len(self.ids)), key=lambda i: (-float(lexical[i]), i))[:200]
            rankings = [sparse] if dense_order is None else [list(dense_order), sparse]
            ordered, scores = fuse(rankings, [1] * len(rankings), 60)
            candidates = [
                {"id": self.ids[i], "score": scores[i], "signals": {}} for i in ordered[:200]
            ]
        else:

            def support(i):
                sid = self.ids[i]
                a, b = (sid, target) if op == "callers" else (target, sid)
                return self.graph.relation_frequency(op, a, b)

            target_words = set(tokens(target))
            rankings = [
                indices,
                sorted(indices, key=lambda i: (-float(lexical[i]), i)),
                sorted(indices, key=lambda i: (-support(i), i)),
                sorted(indices, key=lambda i: (-self.graph.graph_degree(self.ids[i]), i)),
                sorted(indices, key=lambda i: (-len(target_words & set(tokens(self.ids[i]))), i)),
            ]
            constant, weights = POLICY.get(op, (60, (1, 0, 0, 0, 0)))
            _, scores = fuse(rankings, weights, constant)
            ranks = [{i: r for r, i in enumerate(order, 1)} for order in rankings]
            candidates = [
                {
                    "id": self.ids[i],
                    "score": scores.get(i, 0),
                    "rrf_constant": constant,
                    "signals": {
                        name: {
                            "rank": ranks[j][i],
                            "weight": weights[j],
                            "contribution": weights[j] / (constant + ranks[j][i]),
                        }
                        for j, name in enumerate(CHANNELS)
                    },
                }
                for i in indices
            ]
        for item in candidates:
            i = self.positions[item["id"]]
            doc = self.documents[i]
            a, b = (item["id"], target) if op == "callers" else (target, item["id"])
            evidence = self.graph.witnesses.get((a, relation, b), [])
            item.update(
                corpus_order=i,
                text=doc["text"],
                source=doc["sourcePath"],
                definition_line=doc["definitionLine"],
                witnesses=evidence,
                definitions=self.graph.definitions.get(item["id"], []),
                edge={"source": a, "relation": relation, "target": b} if evidence else None,
            )
        return {
            "route": "recorded_dense_bm25_fallback"
            if fallback and dense_order is not None
            else "bm25_fallback"
            if fallback
            else result.route,
            "fallback": fallback,
            "candidates": candidates,
        }
