from datetime import datetime

from additional_benchmark_eval import (
    BM25,
    endpoints,
    graph_needed,
    graph_rank,
    question_time,
)


def test_graph_expands_a_two_hop_chain_without_labels():
    facts = [
        "The author of Our Mutual Friend is Charles Dickens.",
        "The author of Our Mutual Friend is Charles Darwin.",
        "Charles Dickens is married to Catherine Dickens.",
        "Catherine Dickens is a citizen of United Kingdom.",
        "Charles Darwin is famous for On the Origin of Species.",
        "The capital of France is Paris.",
    ]
    query = "What is the citizenship of the spouse of the author of Our Mutual Friend?"
    ranked = graph_rank(query, facts, BM25(facts), k=5)
    assert 3 in ranked


def test_fact_endpoints_are_normalized():
    assert endpoints("The author of Our Mutual Friend is Charles Dickens.") == (
        "our mutual friend",
        "charles dickens",
    )


def test_bm25_allowed_set_is_a_hard_filter():
    index = BM25(["old preference coffee", "new preference tea"])
    assert index.top("preference coffee", 5, {1}) == [1]


def test_graph_router_only_sends_nested_relations():
    assert graph_needed("What is the citizenship of the spouse of the author of this book?")
    assert not graph_needed("What is the capital of France?")


def test_question_time_uses_the_latest_explicit_date():
    value = question_time(
        "What changed between Dec 01, 2025 and Mar 15, 2026?",
        "Apr 01, 2030, 12:00:00",
    )
    assert datetime.fromtimestamp(value).date().isoformat() == "2026-03-15"
