"""Compare a newly executed run to the paper's frozen rankings and metrics."""

import argparse
import gzip
import json
from pathlib import Path

from locomo_context_eval import ROOT, read_json, verify


def compare(output, dataset):
    verify(dataset, output)
    reference = read_json(ROOT / "results/locomo_reference.json")
    actual = read_json(output / "results.json")
    # Timing and the execution environment naturally differ across machines.
    for name, profile in reference["profiles"].items():
        for field in ("evidence", "by_category", "lure_at_5", "calendar_qa"):
            if field in profile and actual["profiles"][name][field] != profile[field]:
                raise AssertionError(f"metric changed: {name}/{field}")
    if actual["paired"] != reference["paired"]:
        raise AssertionError("paired wins/losses changed")
    expected = json.loads(gzip.decompress((ROOT / "results/locomo_top5.json.gz").read_bytes()))
    frozen = read_json(output / "retrieval.json")["rows"]
    actual_ids = [{key: row[key] for key in ("question_id", "profile", "ids")} for row in frozen]
    if actual_ids != expected:
        raise AssertionError("frozen question order or top-5 changed")
    print(f"Exact reproduction: {len(expected)} top-5 lists, all 17 profiles and paired metrics")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, default=ROOT / "external/locomo/locomo10.json")
    args = parser.parse_args()
    compare(args.output, args.dataset)
