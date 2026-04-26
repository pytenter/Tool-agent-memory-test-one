"""Export the TMC-Mem0Bench v2 seed cases and manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from benchmark.tmc_mem0bench_v2 import (
    ROOT_DIR,
    DOMAIN_SPECS,
    SUPPORTED_PROMPT_FAMILIES,
    build_tmc_mem0bench_v2_cases,
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
        "--domains",
        type=_csv_arg,
        default=list(DOMAIN_SPECS.keys()),
        help="Comma-separated domain ids to export.",
    )
    parser.add_argument(
        "--prompt-families",
        type=_csv_arg,
        default=list(SUPPORTED_PROMPT_FAMILIES),
        help="Comma-separated prompt families to include.",
    )
    parser.add_argument(
        "--max-tau2-tasks",
        type=int,
        default=3,
        help="Maximum number of τ² task seeds per τ² domain.",
    )
    parser.add_argument(
        "--output-jsonl",
        type=Path,
        default=ROOT_DIR / "benchmark" / "tmc_mem0bench_v2_seed.jsonl",
        help="Destination JSONL file for benchmark cases.",
    )
    parser.add_argument(
        "--output-manifest",
        type=Path,
        default=ROOT_DIR / "benchmark" / "tmc_mem0bench_v2_seed_manifest.json",
        help="Destination JSON file for the benchmark manifest.",
    )
    args = parser.parse_args()

    cases, manifest = build_tmc_mem0bench_v2_cases(
        domains=args.domains,
        prompt_families=args.prompt_families,
        max_tau2_tasks=args.max_tau2_tasks,
    )
    write_jsonl(args.output_jsonl, cases)
    write_json(args.output_manifest, manifest)

    print(
        json.dumps(
            {
                "output_jsonl": str(args.output_jsonl),
                "output_manifest": str(args.output_manifest),
                "total_cases": manifest["total_cases"],
                "domain_case_counts": manifest["domain_case_counts"],
                "prompt_family_counts": manifest["prompt_family_counts"],
                "placeholder_audit": manifest["placeholder_audit"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
