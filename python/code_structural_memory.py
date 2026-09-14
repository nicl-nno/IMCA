"""Operation-aware structural retrieval over a projected SCIP index.

The module is deliberately independent from LongMemCode ground truth.  It only
uses repository artefacts available to a code agent: stable symbol IDs, source
locations, SCIP occurrences/relationships, and source text.  Dense and lexical
retrievers can be supplied by the caller as a fallback after the deterministic
router has answered high-confidence structural operations.

The raw SCIP protobuf is projected to JSON by
``experiments/export_scip_structure.ts``.  Keeping protobuf decoding in the
TypeScript bridge avoids adding a protobuf generator to the Python runtime.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFINITION_ROLE = 1

_DESCRIPTOR_NAME = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)(?=[#.:()]|$)")
_DIRECT_DESCRIPTOR = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:#|\.|\([^()]*\)\.)$")
_METHOD_SUFFIX = re.compile(r"\([^()]*\)\.$")
_PARAMETER_SUFFIX = re.compile(r"\.\([A-Za-z_][A-Za-z0-9_]*\)$")


def normalize_path(value: str) -> str:
    return str(value).replace("\\", "/").lstrip("./")


def strip_package_root(value: str, package_root: str = "fastapi") -> str:
    path = normalize_path(value)
    prefix = f"{package_root.strip('/')}/"
    return path[len(prefix) :] if path.startswith(prefix) else path


def display_name(stable_id: str) -> str:
    tail = stable_id.rsplit("/", 1)[-1]
    names = _DESCRIPTOR_NAME.findall(tail)
    return names[-1] if names else tail


def descriptor_path(stable_id: str) -> str:
    """Return a queryable path such as ``Query#__init__`` from a SCIP ID."""
    tail = stable_id.rsplit("/", 1)[-1].strip()
    if _PARAMETER_SUFFIX.search(tail):
        return ""
    tail = _METHOD_SUFFIX.sub("", tail)
    return tail.rstrip("#.")


def symbol_kind(stable_id: str) -> str:
    if stable_id.startswith("file:"):
        return "file"
    tail = stable_id.rsplit("/", 1)[-1].strip()
    if _PARAMETER_SUFFIX.search(tail) or (tail.startswith("(") and tail.endswith(")")):
        return "parameter"
    if _METHOD_SUFFIX.search(tail):
        return "function"
    if tail.endswith("#"):
        return "struct"
    if tail.endswith(":"):
        return "module"
    if tail.endswith("."):
        return "term"
    return "symbol"


def _range4(value: Sequence[int]) -> tuple[int, int, int, int] | None:
    if len(value) == 3:
        return int(value[0]), int(value[1]), int(value[0]), int(value[2])
    if len(value) >= 4:
        return int(value[0]), int(value[1]), int(value[2]), int(value[3])
    return None


def _contains_position(bounds: tuple[int, int, int, int], line: int, column: int) -> bool:
    start_line, start_column, end_line, end_column = bounds
    return (line, column) >= (start_line, start_column) and (line, column) < (
        end_line,
        end_column,
    )


def _span_size(bounds: tuple[int, int, int, int]) -> tuple[int, int]:
    return bounds[2] - bounds[0], bounds[3] - bounds[1]


def _node_span(node: ast.AST) -> tuple[int, int, int, int] | None:
    line = getattr(node, "lineno", None)
    column = getattr(node, "col_offset", None)
    end_line = getattr(node, "end_lineno", None)
    end_column = getattr(node, "end_col_offset", None)
    if None in (line, column, end_line, end_column):
        return None
    return int(line) - 1, int(column), int(end_line) - 1, int(end_column)


def _call_target_span(node: ast.AST) -> tuple[int, int, int, int] | None:
    """Return the identifier span that denotes the invoked callable.

    ``ast.Attribute`` spans cover the receiver as well as the attribute.  Using
    that whole span would turn ``request`` in ``request.form()`` into a callee.
    SCIP occurrences point at identifiers, so narrowing the span to ``form``
    keeps only the actual call target.
    """
    span = _node_span(node)
    if span is None:
        return None
    if isinstance(node, ast.Attribute):
        end_line, end_column = span[2], span[3]
        return end_line, end_column - len(node.attr), end_line, end_column
    if isinstance(node, ast.Name):
        return span
    return None


def _call_target_spans(source: str) -> list[tuple[int, int, int, int]]:
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    spans = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            span = _call_target_span(node.func)
            if span is not None:
                spans.append(span)
    return spans


def _append_unique(mapping: dict[str, list[str]], key: str, value: str) -> None:
    values = mapping[key]
    if value not in values:
        values.append(value)


@dataclass(frozen=True)
class StructuralResult:
    ids: tuple[str, ...]
    route: str
    confidence: float


class ScipStructuralIndex:
    """A small heterogeneous code graph with a confidence-gated query router."""

    def __init__(
        self,
        projection: dict[str, Any],
        source_root: str | Path,
        stable_ids: Sequence[str],
        metadata: Sequence[dict[str, Any]],
        *,
        package_root: str = "fastapi",
        collect_witnesses: bool = False,
    ):
        if len(stable_ids) != len(metadata):
            raise ValueError("stable_ids and metadata must have equal lengths")
        self.source_root = Path(source_root)
        self.collect_witnesses = collect_witnesses
        self.witnesses: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        self.definitions: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self.package_root = package_root
        self.stable_ids = tuple(str(value) for value in stable_ids)
        self.id_set = set(self.stable_ids)
        self.order = {stable_id: index for index, stable_id in enumerate(self.stable_ids)}
        self.symbols_by_file: dict[str, list[str]] = defaultdict(list)
        self.bare_names: dict[str, list[str]] = defaultdict(list)
        self.descriptor_paths: dict[str, list[str]] = defaultdict(list)
        self.contains: dict[str, list[str]] = defaultdict(list)
        self.implementors: dict[str, list[str]] = defaultdict(list)
        self.references_out: dict[str, list[str]] = defaultdict(list)
        self.references_in: dict[str, list[str]] = defaultdict(list)
        self.calls_out: dict[str, list[str]] = defaultdict(list)
        self.calls_in: dict[str, list[str]] = defaultdict(list)
        self.reference_frequency: Counter[tuple[str, str]] = Counter()
        self.call_frequency: Counter[tuple[str, str]] = Counter()

        for stable_id, item in zip(self.stable_ids, metadata, strict=True):
            source_path = strip_package_root(str(item.get("sourcePath", "")), package_root)
            if source_path:
                _append_unique(self.symbols_by_file, source_path, stable_id)
            if symbol_kind(stable_id) not in {"file", "parameter"}:
                _append_unique(self.bare_names, display_name(stable_id), stable_id)
                path = descriptor_path(stable_id)
                if path:
                    _append_unique(self.descriptor_paths, path, stable_id)

        for parent in self.stable_ids:
            if symbol_kind(parent) not in {"struct", "module"}:
                continue
            for child in self.stable_ids:
                if child.startswith(parent) and _DIRECT_DESCRIPTOR.fullmatch(child[len(parent) :]):
                    _append_unique(self.contains, parent, child)

        documents = projection.get("documents", [])
        for document in documents:
            self._add_relationships(document)
            self._add_occurrences(document)

    @classmethod
    def from_json(
        cls,
        projection_path: str | Path,
        source_root: str | Path,
        stable_ids: Sequence[str],
        metadata: Sequence[dict[str, Any]],
        *,
        package_root: str = "fastapi",
        collect_witnesses: bool = False,
    ) -> ScipStructuralIndex:
        payload = json.loads(Path(projection_path).read_text(encoding="utf-8"))
        return cls(
            payload,
            source_root,
            stable_ids,
            metadata,
            package_root=package_root,
            collect_witnesses=collect_witnesses,
        )

    def _add_relationships(self, document: dict[str, Any]) -> None:
        for symbol in document.get("symbols", []):
            source = str(symbol.get("symbol", ""))
            if source not in self.id_set:
                continue
            for relationship in symbol.get("relationships", []):
                target = str(relationship.get("symbol", ""))
                if relationship.get("isImplementation") and target in self.id_set:
                    _append_unique(self.implementors, target, source)

    def _source_text(self, relative_path: str) -> str:
        path = self.source_root.joinpath(*normalize_path(relative_path).split("/"))
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return ""

    def _add_occurrences(self, document: dict[str, Any]) -> None:
        relative_path = normalize_path(str(document.get("relativePath", "")))
        file_id = f"file:{strip_package_root(relative_path, self.package_root)}"
        occurrences = list(document.get("occurrences", []))
        scopes: list[tuple[tuple[int, int, int, int], str]] = []
        for occurrence in occurrences:
            symbol = str(occurrence.get("symbol", ""))
            enclosing = _range4(occurrence.get("enclosingRange", []))
            if (
                int(occurrence.get("symbolRoles", 0)) & DEFINITION_ROLE
                and enclosing is not None
                and symbol in self.id_set
                and symbol_kind(symbol) == "function"
            ):
                scopes.append((enclosing, symbol))
        source_text = self._source_text(relative_path)
        call_spans = _call_target_spans(source_text)
        source_lines = source_text.splitlines()
        source_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

        def witness(occurrence: dict[str, Any]) -> dict[str, Any]:
            bounds = _range4(occurrence.get("range", []))
            start = bounds[0] if bounds else 0
            stop = bounds[2] + 1 if bounds else 0
            return {
                "source": relative_path,
                "source_sha256": source_hash,
                "range_zero_based": list(bounds) if bounds else None,
                "line_start": start + 1,
                "line_end": stop,
                "text": "\n".join(source_lines[start:stop]),
                "kind": "scip_occurrence",
                "source_available": bool(source_text),
            }

        if self.collect_witnesses:
            for occurrence in occurrences:
                symbol = str(occurrence.get("symbol", ""))
                if (
                    int(occurrence.get("symbolRoles", 0)) & DEFINITION_ROLE
                    and symbol in self.id_set
                ):
                    self.definitions[symbol].append(witness(occurrence))

        for occurrence in occurrences:
            if int(occurrence.get("symbolRoles", 0)) & DEFINITION_ROLE:
                continue
            target = str(occurrence.get("symbol", ""))
            bounds = _range4(occurrence.get("range", []))
            if target not in self.id_set or bounds is None:
                continue
            line, column = bounds[0], bounds[1]
            enclosing = [item for item in scopes if _contains_position(item[0], line, column)]
            caller = (
                min(enclosing, key=lambda item: _span_size(item[0]))[1] if enclosing else file_id
            )
            if caller not in self.id_set or caller == target:
                continue
            _append_unique(self.references_out, caller, target)
            _append_unique(self.references_in, target, caller)
            self.reference_frequency[caller, target] += 1
            if self.collect_witnesses:
                self.witnesses[caller, "references", target].append(witness(occurrence))
            if any(_contains_position(span, line, column) for span in call_spans):
                _append_unique(self.calls_out, caller, target)
                _append_unique(self.calls_in, target, caller)
                self.call_frequency[caller, target] += 1
                if self.collect_witnesses:
                    self.witnesses[caller, "calls", target].append(
                        {**witness(occurrence), "kind": "scip_occurrence+ast_call_target"}
                    )

    def _ordered(self, values: Iterable[str]) -> list[str]:
        return sorted(set(values), key=lambda value: self.order.get(value, len(self.order)))

    def relation_frequency(self, operation: str, source: str, target: str) -> int:
        """Return occurrence support for a directed structural relation."""
        if operation == "callers":
            return self.reference_frequency[source, target]
        if operation == "callees":
            return self.call_frequency[source, target]
        return 0

    def graph_degree(self, stable_id: str) -> int:
        """Unweighted heterogeneous degree used as a label-free rank feature."""
        neighbours = {
            *self.references_out.get(stable_id, ()),
            *self.references_in.get(stable_id, ()),
            *self.calls_out.get(stable_id, ()),
            *self.calls_in.get(stable_id, ()),
            *self.contains.get(stable_id, ()),
            *self.implementors.get(stable_id, ()),
        }
        return len(neighbours)

    def _lookup(self, query: dict[str, Any]) -> StructuralResult:
        name = str(query.get("name", "")).strip()
        if not query.get("bare_name"):
            ids = (name,) if name in self.id_set else ()
            return StructuralResult(ids, "exact_stable_id", 1.0)

        candidates = list(self.descriptor_paths.get(name, ()))
        if not candidates:
            candidates = list(self.bare_names.get(name, ()))
        requested_kind = str(query.get("kind", "")).lower()
        if requested_kind:
            candidates = [
                stable_id
                for stable_id in candidates
                if symbol_kind(stable_id) == requested_kind
                or (requested_kind == "class" and symbol_kind(stable_id) == "struct")
            ]
        return StructuralResult(tuple(self._ordered(candidates)), "exact_symbol_name", 0.98)

    def search(
        self,
        query: dict[str, Any],
        *,
        limit: int = 5,
        caller_mode: str = "calls",
    ) -> StructuralResult:
        op = str(query.get("op", ""))
        if op == "lookup":
            result = self._lookup(query)
        elif op == "file_symbols":
            path = strip_package_root(str(query.get("file_path", "")), self.package_root)
            values = [
                stable_id
                for stable_id in self.symbols_by_file.get(path, ())
                if symbol_kind(stable_id) not in {"module", "parameter"}
            ]
            result = StructuralResult(tuple(values), "file_scope", 1.0)
        elif op == "contained_by":
            target = str(query.get("sym_stable_id", ""))
            values = list(self.contains.get(target, ()))
            if symbol_kind(target) == "struct":
                values.sort(
                    key=lambda value: (
                        symbol_kind(value) != "function",
                        self.order.get(value, len(self.order)),
                    )
                )
            result = StructuralResult(tuple(values), "containment", 1.0)
        elif op == "implementors":
            target = str(query.get("sym_stable_id", ""))
            result = StructuralResult(
                tuple(self.implementors.get(target, ())), "implementation", 1.0
            )
        elif op == "callers":
            target = str(query.get("sym_stable_id", ""))
            mapping = self.references_in if caller_mode == "references" else self.calls_in
            if target.startswith("file:"):
                values = [
                    stable_id
                    for stable_id in self.symbols_by_file.get(target.removeprefix("file:"), ())
                    if symbol_kind(stable_id) not in {"module", "parameter", "term"}
                ]
            else:
                values = [
                    stable_id
                    for stable_id in mapping.get(target, ())
                    if symbol_kind(stable_id) not in {"module", "parameter", "term"}
                ]
                for stable_id in self.implementors.get(target, ()):
                    if (
                        symbol_kind(stable_id)
                        not in {
                            "module",
                            "parameter",
                            "term",
                        }
                        and stable_id not in values
                    ):
                        values.append(stable_id)
            result = StructuralResult(tuple(values), f"{caller_mode}_incoming", 0.95)
        elif op == "callees":
            target = str(query.get("sym_stable_id", ""))
            mapping = self.references_out if caller_mode == "references" else self.calls_out
            values = [
                stable_id
                for stable_id in mapping.get(target, ())
                if symbol_kind(stable_id) not in {"module", "parameter", "term", "file"}
            ]
            result = StructuralResult(tuple(values), f"{caller_mode}_outgoing", 0.95)
        elif op == "orphans":
            requested_kind = str(query.get("kind", "function"))
            values = [
                stable_id
                for stable_id in self.stable_ids
                if symbol_kind(stable_id) == requested_kind and not self.calls_in.get(stable_id)
            ]
            values.sort(
                key=lambda stable_id: (
                    "#" in descriptor_path(stable_id),
                    display_name(stable_id).startswith("_"),
                    -self.graph_degree(stable_id),
                    self.order.get(stable_id, len(self.order)),
                )
            )
            result = StructuralResult(tuple(values), "orphan_scan", 0.9)
        else:
            result = StructuralResult((), "unsupported", 0.0)
        return StructuralResult(result.ids[: max(0, limit)], result.route, result.confidence)
