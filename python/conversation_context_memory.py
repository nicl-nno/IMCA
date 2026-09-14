"""Model-free conversational context retrieval over immutable source turns.

Neighbors provide search context, not inferred subjects or facts. Every returned
ID is one original turn; no window is silently packed into a top-5 slot.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass

from conversation_memory import ConversationMemory, LexicalIndex, terms
from temporal_language import extract_times

VERSION = "conversation-context-v3"


@dataclass(frozen=True)
class ContextPolicy:
    context_weight: float = 0.5
    rrf_k: int = 10
    preserve: int = 2
    radius: int = 1
    participant_guard: bool = True
    bridge: bool = False
    max_tail_ratio: float = 1.0
    min_anchor_coverage: float = 0.0
    calendar: bool = False
    min_question_coverage: float = 0.0
    alignment_tail_ratio: float = 0.0


POLICIES = {
    "context_only": ContextPolicy(context_weight=1.0, preserve=0, participant_guard=False),
    "context_rrf": ContextPolicy(preserve=0),
    "context_rescue": ContextPolicy(preserve=3),
    "context_wide": ContextPolicy(radius=2),
    "context_balanced": ContextPolicy(context_weight=0.7, radius=2, preserve=3),
    "context_cautious": ContextPolicy(context_weight=0.7, radius=2, preserve=4),
    "answer_bridge": ContextPolicy(preserve=4, bridge=True),
    "bridge_safe": ContextPolicy(preserve=4, bridge=True, max_tail_ratio=0.4),
    "bridge_medium": ContextPolicy(preserve=4, bridge=True, max_tail_ratio=0.6),
    "bridge_aligned": ContextPolicy(preserve=4, bridge=True, min_anchor_coverage=0.6),
    "bridge_strict": ContextPolicy(preserve=4, bridge=True, min_anchor_coverage=0.8),
    "bridge_focused": ContextPolicy(preserve=4, bridge=True, min_question_coverage=0.5),
    "bridge_adaptive": ContextPolicy(
        preserve=4, bridge=True, min_question_coverage=0.5, alignment_tail_ratio=0.4
    ),
    "calendar_unique": ContextPolicy(preserve=4, calendar=True),
    "bridge_calendar": ContextPolicy(
        preserve=4, bridge=True, min_question_coverage=0.5, alignment_tail_ratio=0.4, calendar=True
    ),
}
PROFILES = ("bm25", "guarded", *POLICIES)


class ContextConversationMemory:
    def __init__(self, memory: ConversationMemory):
        self.memory = memory
        self.positions = {episode.id: i for i, episode in enumerate(memory.episodes)}
        self.dated = [
            (episode, event)
            for episode in memory.episodes
            for event in episode.events
            if event["times"]
        ]
        self.windows = {}
        self.indexes = {}
        for radius in {p.radius for p in POLICIES.values()}:
            windows, texts = [], []
            for i, episode in enumerate(memory.episodes):
                neighbors = [
                    other
                    for other in memory.episodes[max(0, i - radius) : i + radius + 1]
                    if other.session == episode.session
                ]
                windows.append([other.id for other in neighbors])
                texts.append(" ".join(f"{other.speaker}: {other.text}" for other in neighbors))
            self.windows[radius] = windows
            self.indexes[radius] = LexicalIndex(texts)

    def search(self, question: str, *, profile: str, limit: int = 5) -> dict:
        if profile not in PROFILES or not 1 <= limit <= 5:
            raise ValueError("invalid profile or top-k")
        if profile in {"bm25", "guarded"}:
            return self.memory.search(question, profile=profile, limit=limit)
        policy = POLICIES[profile]
        base = self.memory.search(question, profile="guarded")
        if policy.calendar:
            query_times = extract_times(question, None)
            if query_times or not policy.bridge:
                return self._calendar(question, query_times, base, policy, profile, limit)
        if policy.bridge:
            return self._bridge(question, base, policy, profile, limit)
        scores = self.indexes[policy.radius].scores(question)
        # Use only each target turn's explicit participant information. Context
        # never transfers another person's subject onto the target.
        unknown_when = question.lstrip().lower().startswith("when ") and not extract_times(
            question, None
        )
        if policy.participant_guard and not unknown_when:
            for i in scores:
                if (
                    self.memory.participant_relation(base["subject"], self.memory.episodes[i])
                    == "mismatch"
                ):
                    scores[i] *= 0.5
        context_order = sorted(scores, key=lambda i: (-scores[i], i))
        context_ranks = {
            self.memory.episodes[i].id: rank for rank, i in enumerate(context_order, 1)
        }
        base_ranks = {eid: rank for rank, eid in enumerate(base["ids"], 1)}
        union = set(context_ranks) | set(base_ranks)
        fused = {}
        for eid in union:
            direct = (
                (1 - policy.context_weight) / (policy.rrf_k + base_ranks[eid])
                if eid in base_ranks
                else 0.0
            )
            context = (
                policy.context_weight / (policy.rrf_k + context_ranks[eid])
                if eid in context_ranks
                else 0.0
            )
            fused[eid] = direct + context
        ordered = sorted(union, key=lambda eid: (-fused[eid], self.positions[eid]))
        retained = base["ids"][: min(policy.preserve, limit)]
        selected = (
            retained + [eid for eid in ordered if eid not in retained][: limit - len(retained)]
        )
        return {
            "ids": selected,
            "hits": [
                {
                    "id": eid,
                    "score": fused[eid],
                    "guarded_rank": base_ranks.get(eid),
                    "context_rank": context_ranks.get(eid),
                    "context_ids": self.windows[policy.radius][self.positions[eid]],
                    "retained": eid in retained,
                }
                for eid in selected
            ],
            "profile": profile,
            "policy": asdict(policy),
            "subject": base["subject"],
            "index_hash": base["index_hash"],
        }

    def _bridge(
        self, question: str, base: dict, policy: ContextPolicy, profile: str, limit: int
    ) -> dict:
        """Follow a retrieved question to its immediately following response."""
        options = []
        content = set(terms(question)) - {t for person in self.memory.people for t in terms(person)}
        total = len(self.memory.episodes)
        importance = {
            token: math.log(
                1 + (total + 0.5) / (len(self.memory.raw.postings.get(token, [])) + 0.5)
            )
            for token in content
        }
        tail_ratio = (
            base["hits"][-1]["score"] / base["hits"][0]["score"]
            if len(base["hits"]) >= limit and base["hits"][0]["score"] > 0
            else 0.0
        )
        for rank, eid in enumerate(base["ids"][:2], 1):
            if tail_ratio > policy.max_tail_ratio:
                break
            i = self.positions[eid]
            anchor = self.memory.episodes[i]
            if not anchor.text.rstrip().endswith("?") or i + 1 >= len(self.memory.episodes):
                continue
            matched = set(terms(anchor.text)) & content
            coverage = sum(importance[t] for t in sorted(matched)) / (
                sum(importance[t] for t in sorted(content)) or 1.0
            )
            if coverage < policy.min_anchor_coverage:
                continue
            question_clause = re.split(r"[.!?]\s+|\s[-–—]\s", anchor.text.strip())[-1]
            clause_matches = content & set(terms(question_clause))
            question_coverage = sum(importance[t] for t in sorted(clause_matches)) / (
                sum(importance[t] for t in sorted(content)) or 1.0
            )
            if (
                tail_ratio > policy.alignment_tail_ratio
                and question_coverage < policy.min_question_coverage
            ):
                continue
            answer = self.memory.episodes[i + 1]
            if answer.session != anchor.session or answer.speaker == anchor.speaker:
                continue
            if base["subject"] and answer.speaker != base["subject"]:
                continue
            if answer.text.rstrip().endswith("?") or len(set(terms(answer.text))) < 3:
                continue
            if self.memory.participant_relation(base["subject"], answer) == "mismatch":
                continue
            options.append((rank, answer.id, eid, coverage, question_coverage))
        retained = base["ids"][: min(policy.preserve, limit)]
        selected = retained.copy()
        bridges = {}
        for rank, eid, source, coverage, question_coverage in options:
            if eid not in selected and len(selected) < limit:
                selected.append(eid)
                bridges[eid] = {
                    "anchor": source,
                    "anchor_rank": rank,
                    "anchor_coverage": coverage,
                    "question_coverage": question_coverage,
                }
        for eid in base["ids"]:
            if eid not in selected and len(selected) < limit:
                selected.append(eid)
        return {
            "ids": selected,
            "hits": [
                {"id": eid, "bridge": bridges.get(eid), "retained": eid in retained}
                for eid in selected
            ],
            "profile": profile,
            "policy": asdict(policy),
            "subject": base["subject"],
            "tail_ratio": tail_ratio,
            "route": "question_response",
            "index_hash": base["index_hash"],
        }

    def _calendar(
        self,
        question: str,
        query_times: list,
        base: dict,
        policy: ContextPolicy,
        profile: str,
        limit: int,
    ) -> dict:
        """Rescue one unambiguous explicitly attributed event in the query interval."""
        subject = base["subject"]
        planned = bool(
            re.search(r"\b(will|plan|plans|planning|want|wants|hope|hopes)\b", question, re.I)
        )
        matches = {}
        for episode, event in self.dated:
            if not subject or subject not in event["subjects"]:
                continue
            if (event["modality"] == "planned") != planned:
                continue
            # Require containment: a vague year-long event cannot establish
            # that something happened on the exact day asked about.
            spans = [
                t
                for t in event["times"]
                if any(q.start <= t["start"] <= t["end"] <= q.end for q in query_times)
            ]
            if spans:
                matches.setdefault(episode.id, []).extend(spans)
        selected = base["ids"][:limit]
        rescued = None
        if len(matches) == 1 and not set(matches) & set(selected):
            rescued = next(iter(matches))
            selected = selected[: min(policy.preserve, limit)]
            if len(selected) < limit:
                selected.append(rescued)
        return {
            "ids": selected,
            "hits": [
                {"id": eid, "calendar_rescue": matches[eid] if eid == rescued else None}
                for eid in selected
            ],
            "profile": profile,
            "policy": asdict(policy),
            "subject": subject,
            "calendar_candidates": len(matches),
            "route": "unique_calendar_event",
            "index_hash": base["index_hash"],
        }
