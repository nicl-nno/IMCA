import copy
import sys
from pathlib import Path

import pytest

from conversation_context_memory import POLICIES, ContextConversationMemory
from conversation_memory import ConversationMemory
from inspectable_memory import InspectableMemory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
from locomo_context_eval import freeze, score  # noqa: E402


def dialogue():
    return {
        "speaker_a": "Alice",
        "speaker_b": "Bob",
        "session_1_date_time": "1:00 pm on 6 January, 2024",
        "session_1": [
            {"dia_id": "D1:1", "speaker": "Bob", "text": "How will you share the recipe?"},
            {"dia_id": "D1:2", "speaker": "Alice", "text": "Write it down and mail it."},
            {"dia_id": "D1:3", "speaker": "Bob", "text": "Great, thank you!"},
        ],
        "session_2_date_time": "1:00 pm on 7 January, 2024",
        "session_2": [
            {"dia_id": "D2:1", "speaker": "Bob", "text": "I bought a telescope."},
        ],
    }


def test_context_finds_an_answer_with_no_query_word_without_resolving_its_subject():
    memory = ContextConversationMemory(ConversationMemory("chat", dialogue()))
    query = "How will Alice share the recipe?"
    context = memory.search(query, profile="context_only")
    assert "D1:2" in context["ids"]
    hit = next(hit for hit in context["hits"] if hit["id"] == "D1:2")
    assert "D1:1" in hit["context_ids"]
    assert memory.memory.by_id["D1:2"].subjects == ()


def test_neighbors_never_cross_sessions_and_each_id_consumes_a_slot():
    memory = ContextConversationMemory(ConversationMemory("chat", dialogue()))
    for radius, windows in memory.windows.items():
        assert radius >= 1
        for ids in windows:
            assert len({memory.memory.by_id[eid].session for eid in ids}) == 1
    for profile in POLICIES:
        run = memory.search("recipe telescope", profile=profile, limit=2)
        assert len(run["ids"]) <= 2
        assert len(set(run["ids"])) == len(run["hits"])
    assert memory.windows[1][-1] == ["D2:1"]


def test_controls_and_retained_head_are_identical_after_repeated_ingestion(tmp_path):
    journal = InspectableMemory(tmp_path / "journal.sqlite")
    try:
        first = ContextConversationMemory(ConversationMemory("chat", dialogue(), journal))
        revision = journal.revision
        second = ContextConversationMemory(ConversationMemory("chat", dialogue(), journal))
        assert journal.revision == revision
        query = "How will Alice share the recipe?"
        for profile in ("bm25", "guarded", *POLICIES):
            result = first.search(query, profile=profile)
            assert result == second.search(query, profile=profile)
            if profile in {"bm25", "guarded"}:
                assert result == first.memory.search(query, profile=profile)
            else:
                n = min(
                    POLICIES[profile].preserve, len(first.search(query, profile="guarded")["ids"])
                )
                assert result["ids"][:n] == first.search(query, profile="guarded")["ids"][:n]
    finally:
        journal.close()


def test_new_profiles_never_receive_annotations_and_scorer_checks_completeness(tmp_path):
    data = [
        {
            "sample_id": "chat",
            "conversation": dialogue(),
            "qa": [
                {
                    "question": "How will Alice share the recipe?",
                    "answer": "mail",
                    "category": 4,
                    "evidence": ["D1:2"],
                }
            ],
        }
    ]
    before, inventories = freeze(data, 1, tmp_path)
    mutated = copy.deepcopy(data)
    mutated[0]["qa"][0].update(answer="marker", evidence=["D9:999"], category=5)
    after, _ = freeze(mutated, 1, tmp_path)

    def strip(rows):
        return [{k: v for k, v in row.items() if k != "search_ms"} for row in rows]

    assert strip(before) == strip(after)
    frozen = {"rows": before, "inventories": inventories}
    report = score(data, frozen)
    assert report == score(data, frozen)
    assert report["profiles"]["context_only"]["evidence"]["hit_at_5"] == 1
    with pytest.raises(ValueError, match="incomplete"):
        score(data, {**frozen, "rows": before[:-1]})
    with pytest.raises(ValueError, match="duplicate"):
        score(data, {**frozen, "rows": before + before[:1]})


def test_bridge_retrieves_only_a_response_to_a_same_session_question():
    memory = ContextConversationMemory(ConversationMemory("chat", dialogue()))
    # Freeze a plausible seed list without any scoring labels. It intentionally
    # omits the answer, making the source of the extra candidate observable.
    base = {
        "ids": ["D1:1", "D1:3", "D2:1"],
        "hits": [
            {"id": "D1:1", "score": 10},
            {"id": "D1:3", "score": 2},
            {"id": "D2:1", "score": 1},
        ],
        "subject": "Alice",
        "index_hash": memory.memory.index_hash,
    }
    result = memory._bridge(
        "How will Alice share the recipe?", base, POLICIES["answer_bridge"], "answer_bridge", 5
    )
    assert result["ids"][-1] == "D1:2"
    assert result["hits"][-1]["bridge"]["anchor"] == "D1:1"
    # Asking about the other person cannot inherit Alice's answer.
    wrong = memory._bridge(
        "How will Bob share the recipe?",
        {**base, "subject": "Bob"},
        POLICIES["answer_bridge"],
        "answer_bridge",
        5,
    )
    assert "D1:2" not in wrong["ids"]


def test_focused_bridge_rejects_a_topic_change_inside_the_anchor():
    data = dialogue()
    data["session_1"][0]["text"] = "We talked about the recipe. What is your favorite planet?"
    data["session_2"].extend(
        [
            {"dia_id": "D2:2", "speaker": "Alice", "text": "The stars look bright."},
            {"dia_id": "D2:3", "speaker": "Bob", "text": "The sky is clear."},
        ]
    )
    memory = ContextConversationMemory(ConversationMemory("chat", data))
    base = {
        "ids": ["D1:1", "D1:3", "D2:1", "D2:2", "D2:3"],
        "hits": [{"score": 10}, {"score": 9}, {"score": 8}, {"score": 7}, {"score": 6}],
        "subject": "Alice",
        "index_hash": memory.memory.index_hash,
    }
    # A topic word in an earlier statement cannot establish the topic of the
    # final question. The low-score escape hatch is disabled at this margin.
    result = memory._bridge(
        "How will Alice share the recipe?", base, POLICIES["bridge_adaptive"], "bridge_adaptive", 5
    )
    assert all(hit["bridge"] is None for hit in result["hits"])


def test_calendar_rescue_requires_unique_attributed_and_precise_event():
    data = dialogue()
    data["session_1"][1]["text"] = "I baked a cake yesterday."
    memory = ContextConversationMemory(ConversationMemory("chat", data))
    from temporal_language import extract_times

    query = "What did Alice do on 5 January 2024?"
    base = {"ids": ["D1:1"], "subject": "Alice", "index_hash": memory.memory.index_hash}
    run = memory._calendar(
        query, extract_times(query, None), base, POLICIES["calendar_unique"], "calendar_unique", 5
    )
    assert run["ids"] == ["D1:1", "D1:2"]
    assert run["hits"][-1]["calendar_rescue"][0]["start"] == "2024-01-05"
    data["session_1"].append(
        {"dia_id": "D1:4", "speaker": "Alice", "text": "I bought a bicycle yesterday."}
    )
    ambiguous = ContextConversationMemory(ConversationMemory("chat", data))
    run = ambiguous._calendar(
        query, extract_times(query, None), base, POLICIES["calendar_unique"], "calendar_unique", 5
    )
    assert run["calendar_candidates"] == 2
    assert run["ids"] == base["ids"]


def test_bridge_keeps_the_original_turns_when_response_is_in_next_session():
    data = dialogue()
    data["session_1"] = [
        {"dia_id": "D1:1", "speaker": "Bob", "text": "How will you share the recipe?"}
    ]
    data["session_2"] = [
        {"dia_id": "D2:1", "speaker": "Alice", "text": "Write it down and mail it."}
    ]
    memory = ContextConversationMemory(ConversationMemory("chat", data))
    base = {
        "ids": ["D1:1"],
        "hits": [{"score": 10}],
        "subject": "Alice",
        "index_hash": memory.memory.index_hash,
    }
    result = memory._bridge("recipe", base, POLICIES["answer_bridge"], "answer_bridge", 5)
    assert result["ids"] == ["D1:1"]


def test_calendar_never_infers_subject_or_turns_a_plan_into_a_report():
    from temporal_language import extract_times

    query = "What did Alice do on 7 January 2024?"
    for text in ("A cake was baked on 7 January 2024.", "I plan to bake a cake tomorrow."):
        data = dialogue()
        data["session_1"][1]["text"] = text
        memory = ContextConversationMemory(ConversationMemory("chat", data))
        base = {"ids": ["D1:1"], "subject": "Alice", "index_hash": memory.memory.index_hash}
        run = memory._calendar(
            query,
            extract_times(query, None),
            base,
            POLICIES["calendar_unique"],
            "calendar_unique",
            5,
        )
        assert run["calendar_candidates"] == 0
        assert run["ids"] == base["ids"]


def test_coarse_calendar_date_cannot_prove_an_event_on_one_specific_day():
    from temporal_language import extract_times

    data = dialogue()
    data["session_1"][1]["text"] = "I baked a cake last month."
    coarse = ContextConversationMemory(ConversationMemory("chat", data))
    base = {"ids": ["D1:1"], "subject": "Alice", "index_hash": coarse.memory.index_hash}
    day = "What did Alice do on 5 December 2023?"
    run = coarse._calendar(
        day, extract_times(day, None), base, POLICIES["calendar_unique"], "calendar_unique", 5
    )
    assert run["calendar_candidates"] == 0
    assert run["ids"] == base["ids"]
