"""Audit Git's prospective release files; optional excluded-source similarity check.

This is a heuristic review aid, not a proof of authorship or legal clearance.
Excluded archives remain local and their contents are never written to output.
"""

import argparse
import ast
import gzip
import hashlib
import re
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SUFFIXES = {".py", ".ts", ".js"}


def windows(text, size=16):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return {
        hashlib.sha256("\n".join(lines[i : i + size]).encode()).digest()
        for i in range(max(0, len(lines) - size + 1))
    }


def functions(text):
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()
    return {
        hashlib.sha256(ast.dump(node).encode()).digest()
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and sum(1 for _ in ast.walk(node)) >= 100
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--excluded-archive", type=Path, action="append", default=[])
    parser.add_argument("--forbid", action="append", default=[])
    args = parser.parse_args()
    names = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
        )
        .decode()
        .split("\0")
    )
    archived_windows, archived_functions, excluded_sources = set(), set(), 0
    for path in args.excluded_archive:
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if Path(name).suffix not in SOURCE_SUFFIXES:
                    continue
                source = archive.read(name).decode("utf-8", errors="replace")
                archived_windows.update(windows(source))
                if name.endswith(".py"):
                    archived_functions.update(functions(source))
                excluded_sources += 1
    issues, checked = [], 0
    secret = re.compile(
        r"(?:ghp_|github_pat_|sk-)[A-Za-z0-9_\-]{24,}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    )
    local_path = re.compile(r"[A-Za-z]:[\\/](?:Users|agents)[\\/]", re.I)
    for name in sorted(set(names) - {""}):
        path = ROOT / name
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            issues.append((name, "unexpected symlink/outside file"))
            continue
        raw = path.read_bytes()
        if name.endswith(".gz"):
            raw = gzip.decompress(raw)
        text = raw.decode("utf-8", errors="replace")
        checked += 1
        if secret.search(text) or local_path.search(text):
            issues.append((name, "credential pattern or local absolute path"))
        for forbidden in args.forbid:
            if forbidden.casefold() in text.casefold():
                issues.append((name, "excluded identifier"))
        if path.suffix in SOURCE_SUFFIXES and not name.startswith("data/code/source/"):
            if windows(text) & archived_windows:
                issues.append((name, "16-line source overlap requires review"))
            if path.suffix == ".py" and functions(text) & archived_functions:
                issues.append((name, "substantial exact function overlap requires review"))
    if issues:
        raise SystemExit(str(issues))
    print(f"Release scan passed: {checked} files; {excluded_sources} excluded source files checked")


if __name__ == "__main__":
    main()
