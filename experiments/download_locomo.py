"""Download only the pinned public benchmark; keep it out of Git."""

import argparse
import hashlib
import urllib.request
from pathlib import Path

from locomo_memory_eval import DATA_SHA256, ROOT, SOURCE_URL


def download(path):
    if path.exists():
        raw = path.read_bytes()
    else:
        with urllib.request.urlopen(SOURCE_URL, timeout=60) as response:
            raw = response.read()
    if hashlib.sha256(raw).hexdigest() != DATA_SHA256:
        raise ValueError("dataset hash mismatch; existing file was not overwritten")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    print(f"Verified public LoCoMo dataset: {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "external/locomo/locomo10.json")
    download(parser.parse_args().output)
