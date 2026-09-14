"""Rule-based conversational event memory and label-free BM25 retrieval.

Only a conversation is accepted at construction; QA/evidence/answers are never
part of the retrieval interface. Raw utterances remain available historically.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import timezone

from inspectable_memory import Fact, InspectableMemory, Scope, digest
from temporal_language import extract_times, session_datetime, time_tokens

STOP = frozenset(
    (
        "a an the and or of to in on at for with as is are was were be been "
        "did does do has have had "
        "when what which who how would could should might can will about from by his her their "
        "its he she they it i me my you your we our s t"
    ).split()
)
LEMMA = {
    "lost": "lose",
    "left": "leave",
    "went": "go",
    "got": "get",
    "bought": "buy",
    "began": "begin",
    "met": "meet",
    "told": "tell",
    "married": "marry",
    "reading": "read",
    "wrote": "write",
    "won": "win",
    "children": "child",
}
PROFILES = ("bm25", "provenance", "temporal", "combined", "guarded")
RULES_VERSION = "conversation-rules-v3"
PARTICIPANT_MISMATCH_MULTIPLIER = 0.5
TEMPORAL_OVERLAP_MULTIPLIER = 1.2


def terms(text: str) -> list[str]:
    result = []
    for word in re.findall(r"[a-z]+|\d+", text.lower()):
        if word in STOP:
            continue
        if word in LEMMA:
            word = LEMMA[word]
        elif len(word) > 5 and word.endswith("ing"):
            word = word[:-3]
        elif len(word) > 4 and word.endswith("ed"):
            word = word[:-2]
        elif len(word) > 4 and word.endswith("s"):
            word = word[:-1]
        result.append(word)
    return result


class LexicalIndex:
    def __init__(self, texts: list[str]):
        self.lengths = []
        self.postings = defaultdict(list)
        for i, text in enumerate(texts):
            tokens = terms(text)
            self.lengths.append(len(tokens))
            for token, count in Counter(tokens).items():
                self.postings[token].append((i, count))
        self.average = sum(self.lengths) / max(1, len(texts)) or 1.0

    def scores(self, query: str) -> dict[int, float]:
        scores = defaultdict(float)
        total = len(self.lengths)
        for term in sorted(set(terms(query))):
            postings = self.postings.get(term, [])
            idf = math.log(1 + (total - len(postings) + 0.5) / (len(postings) + 0.5))
            for index, count in postings:
                denominator = count + 1.2 * (0.25 + 0.75 * self.lengths[index] / self.average)
                scores[index] += idf * count * 2.2 / denominator
        return scores


@dataclass(frozen=True)
class Episode:
    id: str
    speaker: str
    text: str
    session: int
    source_time: str
    subjects: tuple[str, ...]
    events: tuple[dict, ...]
    context_ids: tuple[str, ...]


def sentence_subjects(text: str, speaker: str, people: tuple[str, ...]) -> tuple[str, ...]:
    found = {p for p in people if re.search(rf"\b{re.escape(p)}\b", text, re.I)}
    if re.search(r"\b(I|I'm|I've|my|me|we|our)\b", text, re.I):
        found.add(speaker)
    if re.search(r"\b(you|your|you're|you've)\b", text, re.I):
        found.update(p for p in people if p != speaker)
    # A short reply is not automatically an assertion about the speaker.
    return tuple(sorted(found))


def event_fragments(
    text: str, speaker: str, people: tuple[str, ...], reference
) -> tuple[dict, ...]:
    events = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if not sentence.strip() or sentence.rstrip().endswith("?"):
            continue
        modality = (
            "planned"
            if re.search(
                r"\b(will|gonna|planning|plan to|want to|hope to|thinking of|"
                r"next month|tomorrow)\b",
                sentence,
                re.I,
            )
            else "reported"
        )
        dates = extract_times(sentence, reference)
        events.append(
            {
                "text": sentence,
                "subjects": list(sentence_subjects(sentence, speaker, people)),
                "modality": modality,
                "times": [d.to_dict() for d in dates],
                "normalized_time": " ".join(time_tokens(d) for d in dates),
            }
        )
    return tuple(events)


class ConversationMemory:
    def __init__(
        self, conversation_id: str, conversation: dict, journal: InspectableMemory | None = None
    ):
        self.id = conversation_id
        self.people = (conversation["speaker_a"], conversation["speaker_b"])
        self.episodes: list[Episode] = []
        self.journal = journal
        self.scope = Scope(conversation_id, "conversation-history", "source-local-time")
        self.state_assertions = 0
        self.state_replacements = 0
        raw_texts, augmented_texts = [], []
        previous = None
        state_ids = {}
        session_keys = sorted(
            (k for k in conversation if re.fullmatch(r"session_\d+", k)),
            key=lambda k: int(k.split("_")[1]),
        )
        seen = set()
        for session_key in session_keys:
            number = int(session_key.split("_")[1])
            stamp = conversation[session_key + "_date_time"]
            reference = session_datetime(stamp)
            # A surrogate UTC knowledge clock for sequential replay, not an
            # assertion that the source conversation actually occurred in UTC.
            recorded = reference.replace(tzinfo=timezone.utc).isoformat()
            previous = None  # never link pronouns across session boundaries
            facts = []
            for turn in conversation[session_key]:
                if turn["dia_id"] in seen:
                    raise ValueError("duplicate dialogue ID")
                seen.add(turn["dia_id"])
                speaker, text = turn["speaker"], turn["text"]
                if speaker not in self.people:
                    raise ValueError("unknown speaker")
                events = event_fragments(text, speaker, self.people, reference.date())
                subjects = tuple(sorted({s for e in events for s in e["subjects"]}))
                # Preserve a reference to context; do NOT resolve her/it to a guessed entity.
                links = (
                    (previous.id,)
                    if previous and re.search(r"\b(it|her|him|they|them|that)\b", text, re.I)
                    else ()
                )
                episode = Episode(
                    turn["dia_id"], speaker, text, number, stamp, subjects, events, links
                )
                self.episodes.append(episode)
                raw = f"{speaker}: {text}"
                augmented = raw + " " + " ".join(e["normalized_time"] for e in events)
                raw_texts.append(raw)
                augmented_texts.append(augmented)
                if journal is not None:
                    facts.append(
                        Fact(
                            f"{conversation_id}::{speaker}",
                            "episode",
                            asdict(episode),
                            self.scope,
                            0,
                            None,
                            recorded,
                            {
                                "source": f"{conversation_id}/{episode.id}",
                                "text": text,
                                "source_time": stamp,
                                "clock": "surrogate_UTC",
                            },
                        )
                    )
                    # Narrow explicit employment facts. Never infer unemployment
                    # from losing one job, nor an occupation from an aspiration.
                    match = re.search(
                        r"\bI (no longer work|work) at "
                        r"([A-Z][\w'-]*(?: (?:[A-Z][\w'-]*|&))*)(?=[.!?,]|$)",
                        text,
                    )
                    if match:
                        employer = match[2].strip()
                        entity = (
                            f"{conversation_id}::{speaker}::employment_at::{employer.casefold()}"
                        )
                        active = match[1] == "work"
                        state = Fact(
                            entity,
                            "exists",
                            active,
                            self.scope,
                            number,
                            None,
                            recorded,
                            {
                                "source": f"{conversation_id}/{episode.id}",
                                "text": text,
                                "validity_basis": "observed_at_session_not_exact_transition",
                            },
                        )
                        state_id = journal.save([state])[0]
                        self.state_assertions += 1
                        if entity in state_ids:
                            journal.supersede(
                                state_ids[entity], state_id, effective=number, recorded_at=recorded
                            )
                            self.state_replacements += 1
                        state_ids[entity] = state_id
                previous = episode
            if journal is not None:
                journal.save(facts)
        self.raw = LexicalIndex(raw_texts)
        self.augmented = LexicalIndex(augmented_texts)
        self.by_id = {e.id: e for e in self.episodes}
        self.index_hash = digest(
            {"rules": RULES_VERSION, "id": self.id, "episodes": [asdict(e) for e in self.episodes]}
        )

    def query_subject(self, question: str) -> str | None:
        people = [p for p in self.people if re.search(rf"\b{re.escape(p)}\b", question, re.I)]
        return people[0] if len(people) == 1 else None

    @staticmethod
    def participant_relation(subject: str | None, item: Episode) -> str:
        if subject is None:
            return "not_requested"
        event_subjects = [set(event["subjects"]) for event in item.events]
        if any(subject in subjects for subjects in event_subjects):
            return "supported"
        # A salutation can name the other participant while the following
        # answer omits its subject. Preserve that answer as unknown rather than
        # treating the whole turn as evidence about the addressee.
        if not event_subjects or any(not subjects for subjects in event_subjects):
            return "unknown"
        return "mismatch"

    def search(self, question: str, *, profile: str = "combined", limit: int = 5) -> dict:
        if profile not in PROFILES or not 1 <= limit <= 5:
            raise ValueError("invalid profile or top-k")
        guarded = profile == "guarded"
        temporal = profile in {"temporal", "combined"} or guarded
        provenance = profile in {"provenance", "combined"}
        # The guarded arm keeps raw BM25 as its control surface. Calendar and
        # participant evidence may rerank it, but neither changes document
        # length or deletes an unknown-subject candidate.
        scores = (self.augmented if temporal and not guarded else self.raw).scores(question)
        subject = self.query_subject(question)
        query_times = extract_times(question, None) if temporal else []
        asks_for_unknown_time = bool(re.match(r"^when\b", question, re.I) and not query_times)
        candidates = []
        for position, score in scores.items():
            item = self.episodes[position]
            relation = self.participant_relation(subject, item)
            if provenance and subject and subject not in item.subjects:
                continue
            matching_events = [
                e
                for e in item.events
                if not subject or subject in e["subjects"] or (guarded and not e["subjects"])
            ]
            spans = [t for e in matching_events for t in e["times"]]
            # A soft feature, not destructive filtering: undated evidence stays
            # eligible and a date in an unrelated clause does not prove relevance.
            overlap = bool(
                query_times
                and any(
                    t["start"] <= q.end and q.start <= t["end"] for t in spans for q in query_times
                )
            )
            multiplier = TEMPORAL_OVERLAP_MULTIPLIER if overlap else 1.0
            participant_guard_applied = bool(
                guarded and relation == "mismatch" and not asks_for_unknown_time
            )
            if participant_guard_applied:
                multiplier *= PARTICIPANT_MISMATCH_MULTIPLIER
            candidates.append(
                {
                    "id": item.id,
                    "score": score * multiplier,
                    "raw_score": score,
                    "time_overlap": overlap,
                    "speaker": item.speaker,
                    "subject_supported": not subject or subject in item.subjects,
                    "participant_relation": relation,
                    "participant_guard_applied": participant_guard_applied,
                }
            )
        candidates.sort(
            key=lambda item: (
                -item["score"],
                int(item["id"].split(":")[0][1:]),
                int(item["id"].split(":")[1]),
            )
        )
        return {
            "ids": [c["id"] for c in candidates[:limit]],
            "hits": candidates[:limit],
            "candidate_count": len(candidates),
            "profile": profile,
            "subject": subject,
            "index_hash": self.index_hash,
        }

    def date_answer(self, question: str, retrieved_ids: list[str]) -> dict:
        """Same abstaining date reader for every retriever; no benchmark labels."""
        if not re.match(r"^when\b", question, re.I) or not retrieved_ids:
            return {"answer": None, "reason": "unsupported_question_or_no_evidence"}
        subject = self.query_subject(question)
        query_terms = set(terms(question)) - {p.lower() for p in self.people}
        requested_modality = (
            "planned"
            if re.search(r"\b(will|plan|plans|planning|want|wants|hope|hopes)\b", question, re.I)
            else "reported"
        )
        options = []
        # Strict top-1 reader: no searching beyond the frozen retrieval result.
        item = self.by_id[retrieved_ids[0]]
        for event in item.events:
            if subject and subject not in event["subjects"]:
                continue
            if event["modality"] != requested_modality:
                continue
            overlap = len(query_terms & set(terms(event["text"])))
            if overlap == 0:
                continue
            for span in event["times"]:
                options.append((overlap, span))
        if not options:
            return {"answer": None, "reason": "no_supported_time"}
        maximum = max(score for score, _ in options)
        best = [span for score, span in options if score == maximum]
        dates = {s["start"] for s in best if s["precision"] == "day"}
        if len(dates) != 1 or any(s["precision"] != "day" for s in best):
            return {"answer": None, "reason": "non_day_or_ambiguous_time", "intervals": best}
        return {"answer": next(iter(dates)), "source": item.id, "intervals": best}
