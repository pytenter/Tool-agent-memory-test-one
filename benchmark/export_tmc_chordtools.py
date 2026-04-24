"""Export the TMC-ChordTools v1 benchmark suite or filtered subsets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from benchmark.tmc_chordtools import (
    ROOT_DIR,
    build_tmc_chordtools_cases,
    write_json,
    write_jsonl,
)


def _csv_arg(value: str) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--attack-surface",
        default="all",
        choices=["all", "predecessor", "successor"],
        help="Filter cases by attack surface.",
    )
    parser.add_argument(
        "--target-tools",
        type=_csv_arg,
        default=[],
        help="Comma-separated list of target tools to keep.",
    )
    parser.add_argument(
        "--tool-domains",
        type=_csv_arg,
        default=[],
        help="Comma-separated list of tool domains to keep.",
    )
    parser.add_argument(
        "--defense-ready-only",
        action="store_true",
        help="Export only the cases whose target tool already appears in tools_in_defense.",
    )
    parser.add_argument(
        "--max-queries-per-tool",
        type=int,
        default=None,
        help="Optional cap on the number of queries retained per target tool.",
    )
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        default=ROOT_DIR / "benchmark" / "tmc_chordtools_v1.jsonl",
        help="Destination JSONL file for benchmark cases.",
    )
    parser.add_argument(
        "--output-manifest",
        type=Path,
        default=ROOT_DIR / "benchmark" / "tmc_chordtools_v1_manifest.json",
        help="Destination JSON file for the benchmark manifest.",
    )
    args = parser.parse_args()

    cases, manifest = build_tmc_chordtools_cases(
        attack_surface=args.attack_surface,
        target_tools=args.target_tools or None,
        tool_domains=args.tool_domains or None,
        defense_ready_only=args.defense_ready_only,
        max_queries_per_tool=args.max_queries_per_tool,
    )

    write_jsonl(args.output_jsonl, cases)
    write_json(args.output_manifest, manifest)

    print(
        json.dumps(
            {
                "output_jsonl": str(args.output_jsonl),
                "output_manifest": str(args.output_manifest),
                "total_cases": manifest["total_cases"],
                "attack_surface_counts": manifest["attack_surface_counts"],
                "domain_counts": manifest["domain_counts"],
                "validation": manifest["validation"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
