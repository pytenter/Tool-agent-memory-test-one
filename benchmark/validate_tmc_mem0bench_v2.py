"""Validate exported TMC-Mem0Bench v2 seed files."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from benchmark.tmc_mem0bench_v2 import PLACEHOLDER_TOKENS


def _contains_placeholder(value: object) -> bool:
    if isinstance(value, str):
        upper = value.upper()
        return any(token in upper for token in PLACEHOLDER_TOKENS)
    if isinstance(value, list):
        return any(_contains_placeholder(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_placeholder(item) for item in value.values())
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--case-file",
        type=Path,
        default=ROOT_DIR / "benchmark" / "tmc_mem0bench_v2_seed.jsonl",
    )
    parser.add_argument(
        "--manifest-file",
        type=Path,
        default=ROOT_DIR / "benchmark" / "tmc_mem0bench_v2_seed_manifest.json",
    )
    args = parser.parse_args()

    rows = [
        json.loads(line)
        for line in args.case_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    manifest = json.loads(args.manifest_file.read_text(encoding="utf-8"))

    case_ids = [row["case_id"] for row in rows]
    duplicate_case_ids = [case_id for case_id, count in Counter(case_ids).items() if count > 1]
    placeholder_failures = [
        row["case_id"]
        for row in rows
        if _contains_placeholder(row.get("payload_text") or {})
    ]

    required_fields = [
        "domain",
        "prompt_family",
        "attacker_benefit_hypothesis",
        "attacker_gain_if_activated",
        "future_task",
        "expected_clean_tools",
        "payload_text",
    ]
    missing_field_failures = []
    for row in rows:
        missing = [field for field in required_fields if field not in row or row[field] in ("", None, [], {})]
        if missing:
            missing_field_failures.append({"case_id": row["case_id"], "missing": missing})

    validation = {
        "case_count": len(rows),
        "manifest_total_cases": manifest.get("total_cases"),
        "case_count_matches_manifest": len(rows) == manifest.get("total_cases"),
        "duplicate_case_ids": duplicate_case_ids,
        "placeholder_failures": placeholder_failures,
        "missing_field_failures": missing_field_failures,
        "passed": (
            len(rows) == manifest.get("total_cases")
            and not duplicate_case_ids
            and not placeholder_failures
            and not missing_field_failures
        ),
    }
    print(json.dumps(validation, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
