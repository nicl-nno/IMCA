from conversation_memory import ConversationMemory
from inspectable_memory import InspectableMemory


def conversation():
    return {
        "speaker_a": "Alice",
        "speaker_b": "Bob",
        "session_1_date_time": "1:00 pm on 6 January, 2024",
        "session_1": [
            {"dia_id": "D1:1", "speaker": "Alice", "text": "I work at Acme."},
            {"dia_id": "D1:2", "speaker": "Bob", "text": "I bought a bike yesterday."},
            {"dia_id": "D1:3", "speaker": "Alice", "text": "It looks good!"},
        ],
        "session_2_date_time": "1:00 pm on 7 January, 2024",
        "session_2": [{"dia_id": "D2:1", "speaker": "Alice", "text": "I no longer work at Acme."}],
    }


def test_events_and_explicit_supersession_survive_repeated_ingestion(tmp_path):
    journal = InspectableMemory(tmp_path / "memory.sqlite")
    first = ConversationMemory("chat-a", conversation(), journal)
    revision = journal.revision
    second = ConversationMemory("chat-a", conversation(), journal)
    assert first.index_hash == second.index_hash
    assert journal.revision == revision
    entity = "chat-a::Alice::employment_at::acme"
    result = journal.recall(at=2, known_at="2024-01-08T00:00:00Z", scope=first.scope, entity=entity)
    assert len(result["selected_ids"]) == 1
    assert len(result["facts"]) == 2
    old = journal.recall(at=1, known_at="2024-01-06T14:00:00Z", scope=first.scope, entity=entity)
    assert len(old["facts"]) == 1 and old["facts"][0]["value"] is True
    journal.close()


def test_provenance_dates_context_links_and_conversation_identity():
    memory = ConversationMemory("chat-a", conversation())
    run = memory.search("When did Bob buy a bike?", profile="combined")
    assert run["ids"][0] == "D1:2"
    assert memory.date_answer("When did Bob buy a bike?", run["ids"])["answer"] == "2024-01-05"
    wrong = memory.search("When did Alice buy a bike?", profile="combined")
    assert "D1:2" not in wrong["ids"]
    assert memory.by_id["D1:3"].context_ids == ("D1:2",)
    assert memory.by_id["D1:3"].subjects == ()  # never guess who 'it' is
    assert memory.by_id["D2:1"].context_ids == ()
    assert ConversationMemory("chat-b", conversation()).index_hash != memory.index_hash


def test_rehire_keeps_history_without_current_conflict(tmp_path):
    data = conversation()
    data["session_3_date_time"] = "1:00 pm on 8 January, 2024"
    data["session_3"] = [{"dia_id": "D3:1", "speaker": "Alice", "text": "I work at Acme."}]
    journal = InspectableMemory(tmp_path / "rehire.sqlite")
    memory = ConversationMemory("chat", data, journal)
    result = journal.recall(
        at=3,
        known_at="2024-01-09T00:00:00Z",
        scope=memory.scope,
        entity="chat::Alice::employment_at::acme",
    )
    assert len(result["selected_ids"]) == 1
    assert len(result["facts"]) == 3
    assert memory.state_replacements == 2
    journal.close()


def test_date_reader_does_not_turn_intentions_into_completed_events():
    data = conversation()
    data["session_2"].append(
        {"dia_id": "D2:2", "speaker": "Bob", "text": "I plan to buy a bike tomorrow."}
    )
    memory = ConversationMemory("chat", data)
    assert memory.date_answer("When did Bob buy a bike?", ["D2:2"])["answer"] is None
    assert (
        memory.date_answer("When does Bob plan to buy a bike?", ["D2:2"])["answer"] == "2024-01-08"
    )
    assert memory.date_answer("When did Bob buy a bike?", ["D1:2"])["answer"] == "2024-01-05"


def test_month_precision_is_not_invented_as_exact_date():
    data = conversation()
    data["session_1"][1]["text"] = "I bought a bike last month."
    memory = ConversationMemory("chat", data)
    answer = memory.date_answer("When did Bob buy a bike?", ["D1:2"])
    assert answer["answer"] is None
    assert answer["intervals"][0]["start"] == "2023-12-01"
    assert answer["intervals"][0]["end"] == "2023-12-31"


def test_guarded_retrieval_keeps_implicit_subject_evidence():
    data = conversation()
    data["session_1"].insert(
        0,
        {
            "dia_id": "D1:0",
            "speaker": "Alice",
            "text": "Researching adoption agencies takes patience.",
        },
    )
    memory = ConversationMemory("chat", data)
    assert "D1:0" not in memory.search("What did Alice research?", profile="combined")["ids"]
    assert memory.search("What did Alice research?", profile="guarded")["ids"][0] == "D1:0"


def test_guarded_retrieval_is_a_noop_without_person_or_time_signal():
    memory = ConversationMemory("chat", conversation())
    question = "What looks good?"
    assert (
        memory.search(question, profile="guarded")["ids"]
        == memory.search(question, profile="bm25")["ids"]
    )


def test_guarded_retrieval_demotes_explicit_wrong_person():
    data = conversation()
    data["session_1"].append(
        {"dia_id": "D1:4", "speaker": "Alice", "text": "I bought a bike last year."}
    )
    memory = ConversationMemory("chat", data)
    result = memory.search("What did Alice buy?", profile="guarded")
    assert result["ids"].index("D1:4") < result["ids"].index("D1:2")
    wrong = next(hit for hit in result["hits"] if hit["id"] == "D1:2")
    assert wrong["participant_relation"] == "mismatch"
    assert wrong["participant_guard_applied"] is True


def test_guarded_retrieval_does_not_apply_participant_penalty_to_unknown_when():
    data = conversation()
    data["session_1"].append(
        {"dia_id": "D1:4", "speaker": "Alice", "text": "I bought a bike last year."}
    )
    memory = ConversationMemory("chat", data)
    result = memory.search("When did Alice buy a bike?", profile="guarded")
    wrong = next(hit for hit in result["hits"] if hit["id"] == "D1:2")
    assert wrong["participant_relation"] == "mismatch"
    assert wrong["participant_guard_applied"] is False
    assert wrong["score"] == wrong["raw_score"]
