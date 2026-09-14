import code_structural_memory as csm

IDS = [
    "file:api.py",
    "pkg `pkg.api`/Base#",
    "pkg `pkg.api`/Base#run().",
    "pkg `pkg.api`/Base#run().(self)",
    "pkg `pkg.api`/Child#",
    "pkg `pkg.api`/caller().",
]
METADATA = [{"sourcePath": "pkg/api.py"} for _ in IDS]


def projection():
    return {
        "documents": [
            {
                "relativePath": "pkg/api.py",
                "symbols": [
                    {
                        "symbol": IDS[4],
                        "relationships": [{"symbol": IDS[1], "isImplementation": True}],
                    }
                ],
                "occurrences": [],
            }
        ]
    }


def test_descriptor_helpers_distinguish_members_from_parameters():
    assert csm.display_name(IDS[2]) == "run"
    assert csm.descriptor_path(IDS[2]) == "Base#run"
    assert csm.descriptor_path(IDS[3]) == ""
    assert csm.symbol_kind(IDS[1]) == "struct"
    assert csm.symbol_kind(IDS[2]) == "function"
    assert csm.symbol_kind(IDS[3]) == "parameter"


def test_exact_router_abstains_instead_of_fuzzy_matching():
    index = csm.ScipStructuralIndex(projection(), ".", IDS, METADATA, package_root="pkg")

    assert index.search({"op": "lookup", "name": IDS[1], "bare_name": False}).ids == (IDS[1],)
    assert index.search({"op": "lookup", "name": "Bsae", "bare_name": True}).ids == ()


def test_composite_name_containment_and_implementation_routes():
    index = csm.ScipStructuralIndex(projection(), ".", IDS, METADATA, package_root="pkg")

    assert index.search({"op": "lookup", "name": "Base#run", "bare_name": True}).ids == (IDS[2],)
    assert index.search({"op": "contained_by", "sym_stable_id": IDS[1]}).ids == (IDS[2],)
    assert index.search({"op": "implementors", "sym_stable_id": IDS[1]}).ids == (IDS[4],)
    assert index.search(
        {"op": "callers", "sym_stable_id": IDS[1]}, caller_mode="references"
    ).ids == (IDS[4],)


def test_file_scope_is_bounded_by_requested_limit():
    index = csm.ScipStructuralIndex(projection(), ".", IDS, METADATA, package_root="pkg")

    assert index.search({"op": "file_symbols", "file_path": "api.py"}, limit=2).ids == (
        IDS[0],
        IDS[1],
    )


def test_call_graph_uses_attribute_not_its_receiver(tmp_path):
    source_root = tmp_path
    package_dir = source_root / "pkg"
    package_dir.mkdir()
    (package_dir / "api.py").write_text(
        "def caller(request):\n    request.form()\n", encoding="utf-8"
    )
    caller = "pkg `pkg.api`/caller()."
    receiver = "pkg `pkg.api`/caller().(request)"
    callee = "pkg `pkg.api`/form()."
    ids = ["file:api.py", caller, receiver, callee]
    metadata = [{"sourcePath": "pkg/api.py"} for _ in ids]
    projected = {
        "documents": [
            {
                "relativePath": "pkg/api.py",
                "symbols": [],
                "occurrences": [
                    {
                        "range": [0, 4, 10],
                        "enclosingRange": [0, 0, 1, 18],
                        "symbol": caller,
                        "symbolRoles": csm.DEFINITION_ROLE,
                    },
                    {"range": [1, 4, 11], "symbol": receiver, "symbolRoles": 0},
                    {"range": [1, 12, 16], "symbol": callee, "symbolRoles": 0},
                ],
            }
        ]
    }

    index = csm.ScipStructuralIndex(projected, source_root, ids, metadata, package_root="pkg")

    assert index.search({"op": "callees", "sym_stable_id": caller}).ids == (callee,)
    assert index.search({"op": "callers", "sym_stable_id": receiver}).ids == ()


def test_orphans_prioritize_public_module_functions():
    ids = [
        "pkg `pkg.api`/Owner#method().",
        "pkg `pkg.api`/_private().",
        "pkg `pkg.api`/public().",
    ]
    metadata = [{"sourcePath": "pkg/api.py"} for _ in ids]
    index = csm.ScipStructuralIndex({"documents": []}, ".", ids, metadata, package_root="pkg")

    assert index.search({"op": "orphans", "kind": "function"}).ids == (
        ids[2],
        ids[1],
        ids[0],
    )
