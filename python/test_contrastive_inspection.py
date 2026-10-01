from contrastive_inspection import boundary_certificate, contrastive_certificate


def run():
    return {
        "candidates": [
            {
                "id": "a",
                "rank": 1,
                "score": 0.7,
                "signals": {
                    "bm25": {
                        "rank": 1,
                        "weight": 1,
                        "contribution": 0.4,
                    },
                    "graph_degree": {
                        "rank": 1,
                        "weight": 1,
                        "contribution": 0.3,
                    },
                },
            },
            {
                "id": "b",
                "rank": 2,
                "score": 0.5,
                "signals": {
                    "bm25": {
                        "rank": 2,
                        "weight": 1,
                        "contribution": 0.2,
                    },
                    "graph_degree": {
                        "rank": 2,
                        "weight": 1,
                        "contribution": 0.3,
                    },
                },
            },
            {
                "id": "c",
                "rank": 3,
                "score": 0.4,
                "signals": {
                    "bm25": {
                        "rank": 3,
                        "weight": 1,
                        "contribution": 0.1,
                    },
                    "graph_degree": {
                        "rank": 3,
                        "weight": 1,
                        "contribution": 0.3,
                    },
                },
            },
        ]
    }


def test_contrastive_certificate_reconstructs_margin():
    certificate = contrastive_certificate(run(), "a", "b")

    assert abs(certificate["margin"] - 0.2) < 1e-12
    assert abs(certificate["residual"]) < 1e-12
    assert certificate["exact"] is True
    assert certificate["dominant_adverse_signal"] == "bm25"


def test_boundary_certificate_uses_selection_boundary():
    certificate = boundary_certificate(run(), limit=2)

    assert certificate["available"] is True
    assert certificate["higher_id"] == "b"
    assert certificate["lower_id"] == "c"
    assert abs(certificate["margin"] - 0.1) < 1e-12


def test_boundary_certificate_reports_missing_boundary():
    certificate = boundary_certificate(run(), limit=3)

    assert certificate == {
        "available": False,
        "limit": 3,
        "reason": "no rejected boundary candidate",
    }
