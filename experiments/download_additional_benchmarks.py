"""Download and verify the two pinned public benchmark inputs.

Raw benchmark data stays under outputs/ and is never redistributed by this
repository.  The hashes are the experiment contract, not a moving branch URL.
"""

from __future__ import annotations

import argparse
import hashlib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "mab_conflict.parquet": (
        "https://huggingface.co/datasets/ai-hyz/MemoryAgentBench/resolve/"
        "7ea066982b140a19337e17e60d45d4076e042faf/data/"
        "Conflict_Resolution-00000-of-00001.parquet",
        "24d5c3f09ce0ce15625cb9f8a98f44f0d864ca6c94d7b4ad04eb697ca3a5ff45",
    ),
    "halumem-medium.jsonl": (
        "https://huggingface.co/datasets/IAAR-Shanghai/HaluMem/resolve/"
        "cb04336aa1b732d4b24f5186c552456b4099806e/HaluMem-Medium.jsonl",
        "486fbc130a5c8781a2af27ffa508a1d7855245137aa449c193ac4d29c45634e7",
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/benchmarks")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for name, (url, expected) in SOURCES.items():
        target = args.output / name
        if not target.exists() or sha256(target) != expected:
            temporary = target.with_suffix(target.suffix + ".part")
            urllib.request.urlretrieve(url, temporary)  # noqa: S310 -- pinned HTTPS + hash
            if sha256(temporary) != expected:
                temporary.unlink(missing_ok=True)
                raise RuntimeError(f"hash mismatch for {name}")
            temporary.replace(target)
        print(f"{expected}  {target}")


if __name__ == "__main__":
    main()
