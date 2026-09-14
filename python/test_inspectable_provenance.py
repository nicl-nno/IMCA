import code_structural_memory as csm


def test_witness_identifies_call_source_without_changing_search(tmp_path):
    source = "def caller():\n    target()\n    reference = target\n"
    (tmp_path / "api.py").write_text(source, encoding="utf-8")
    caller, target = "pkg `api`/caller().", "pkg `api`/target()."
    projection = {
        "documents": [
            {
                "relativePath": "api.py",
                "occurrences": [
                    {
                        "symbol": caller,
                        "symbolRoles": 1,
                        "range": [0, 4, 10],
                        "enclosingRange": [0, 0, 2, 22],
                    },
                    {"symbol": target, "symbolRoles": 0, "range": [1, 4, 10]},
                    {"symbol": target, "symbolRoles": 0, "range": [2, 16, 22]},
                ],
            }
        ]
    }
    args = (projection, tmp_path, [caller, target], [{}, {}])
    plain = csm.ScipStructuralIndex(*args)
    traced = csm.ScipStructuralIndex(*args, collect_witnesses=True)
    query = {"op": "callees", "sym_stable_id": caller}
    assert plain.search(query) == traced.search(query)
    assert not plain.witnesses
    assert len(traced.witnesses[caller, "references", target]) == 2
    call = traced.witnesses[caller, "calls", target]
    assert len(call) == 1
    assert call[0]["line_start"] == 2
    assert call[0]["text"] == "    target()"
    assert call[0]["source_available"]
    assert traced.definitions[caller][0]["line_start"] == 1
