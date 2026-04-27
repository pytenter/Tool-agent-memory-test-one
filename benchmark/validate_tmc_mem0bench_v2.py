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
        "preferred_tool",
        "alternative_tool",
        "expected_clean_route",
        "expected_contaminated_route",
        "activation_rule",
        "future_task",
        "expected_clean_tools",
        "payload_text",
    ]
    missing_field_failures = []
    for row in rows:
        missing = [field for field in required_fields if field not in row or row[field] in ("", None, [], {})]
        if missing:
            missing_field_failures.append({"case_id": row["case_id"], "missing": missing})

    route_field_failures = []
    for row in rows:
        preferred = str(row.get("preferred_tool") or "")
        alternative = str(row.get("alternative_tool") or "")
        clean_route = row.get("expected_clean_route") or []
        contaminated_route = row.get("expected_contaminated_route") or []
        activation_rule = row.get("activation_rule") or {}
        problems = []
        if preferred and preferred not in [str(item) for item in contaminated_route]:
            problems.append("preferred_tool_not_in_expected_contaminated_route")
        if alternative and alternative not in [str(item) for item in clean_route]:
            problems.append("alternative_tool_not_in_expected_clean_route")
        if isinstance(activation_rule, dict):
            if activation_rule.get("preferred_tool") != preferred:
                problems.append("activation_rule_preferred_tool_mismatch")
            if activation_rule.get("alternative_tool") != alternative:
                problems.append("activation_rule_alternative_tool_mismatch")
        else:
            problems.append("activation_rule_not_object")
        if problems:
            route_field_failures.append({"case_id": row["case_id"], "problems": problems})

    validation = {
        "case_count": len(rows),
        "manifest_total_cases": manifest.get("total_cases"),
        "case_count_matches_manifest": len(rows) == manifest.get("total_cases"),
        "duplicate_case_ids": duplicate_case_ids,
        "placeholder_failures": placeholder_failures,
        "missing_field_failures": missing_field_failures,
        "route_field_failures": route_field_failures,
        "passed": (
            len(rows) == manifest.get("total_cases")
            and not duplicate_case_ids
            and not placeholder_failures
            and not missing_field_failures
            and not route_field_failures
        ),
    }
    print(json.dumps(validation, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
