"""Export curated benchmark subsets for staged execution."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from benchmark.curated_subsets import CURATED_SUBSETS, materialize_subset, write_json, write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--subset",
        required=True,
        choices=sorted(CURATED_SUBSETS.keys()),
        help="Name of the curated subset to export.",
    )
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        default=None,
        help="Optional destination JSONL file for the selected subset.",
    )
    parser.add_argument(
        "--output-manifest",
        type=Path,
        default=None,
        help="Optional destination JSON file for the selected subset manifest.",
    )
    args = parser.parse_args()

    cases, manifest = materialize_subset(args.subset)
    output_jsonl = args.output_jsonl or ROOT_DIR / "benchmark" / f"{args.subset}.jsonl"
    output_manifest = args.output_manifest or ROOT_DIR / "benchmark" / f"{args.subset}_manifest.json"

    write_jsonl(output_jsonl, cases)
    write_json(output_manifest, manifest)

    print(
        json.dumps(
            {
                "subset": args.subset,
                "output_jsonl": str(output_jsonl),
                "output_manifest": str(output_manifest),
                "selected_case_count": manifest["selected_case_count"],
                "missing_case_ids": manifest["missing_case_ids"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
