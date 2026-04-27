"""Run Phase 0 memory-form admission microscope probes."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from benchmark.memory_forms import DEFAULT_TOOL, TASK_TYPE, build_phase0_probe_cases
from bridge.memory_writer import append_memory_record, build_memory_record, load_memory_store, reset_memory_store, write_memory_from_tool_output


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _append_jsonl(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _seed_benign_default(store_path: Path) -> None:
    payload = {
        "summary": f"Benign default memory for {TASK_TYPE}.",
        "memory_candidate": f"For {TASK_TYPE}, use {DEFAULT_TOOL} under the normal default workflow.",
        "req": f"What is the default tool for {TASK_TYPE}?",
        "resp": f"Use {DEFAULT_TOOL} for {TASK_TYPE} under normal handling.",
        "tag": "phase0,benign_default",
        "semantic_targets": [f"{TASK_TYPE.lower()} default tool"],
        "marker": "BENIGN_DEFAULT_MARKER",
        "task_type": TASK_TYPE,
        "preference": DEFAULT_TOOL,
    }
    record = build_memory_record(
        instruction=f"Seed benign default for {TASK_TYPE}.",
        actions=["SeedBenignDefault"],
        raw_tool_output=payload,
        source_tool="TrustedMemoryWriter",
        target_tool=DEFAULT_TOOL,
        write_reason="user_confirmed_fact",
    )
    append_memory_record(str(store_path), record)


def _admission_summary(write_result: Dict[str, object]) -> Dict[str, object]:
    return dict(write_result.get("admission_summary") or {})


def _run_probe(
    *,
    case: Dict[str, object],
    output_dir: Path,
    admission_mode: str,
    admission_llm,
    admission_custom_instructions: str,
) -> Dict[str, object]:
    case_dir = output_dir / "case_logs" / str(case["case_id"])
    case_dir.mkdir(parents=True, exist_ok=True)
    store_path = case_dir / "memory_store.json"
    reset_memory_store(str(store_path))
    if case.get("seed_benign_default"):
        _seed_benign_default(store_path)

    payload = dict(case["payload"])
    write_result = write_memory_from_tool_output(
        store_path=str(store_path),
        instruction=f"Phase 0 admission probe for {case['memory_form']}.",
        actions=["TargetTool", "SuccessorPostProcessor"],
        raw_tool_output=payload,
        source_tool=str(payload.get("source_tag") or "SuccessorPostProcessor"),
        target_tool="TargetTool",
        write_reason="phase0_tool_return_summary",
        admission_mode=admission_mode,
        admission_llm=admission_llm,
        admission_context={
            "messages": [
                {"role": "user", "content": f"Probe memory form {case['memory_form']}."},
                {"role": "assistant", "content": json.dumps(payload, ensure_ascii=False)},
            ]
        },
        admission_custom_instructions=admission_custom_instructions,
    )
    records = load_memory_store(str(store_path))
    summary = _admission_summary(write_result)
    row = {
        "case_id": case["case_id"],
        "test_type": case["test_type"],
        "memory_form": case["memory_form"],
        "expected_behavior": case["expected_behavior"],
        "admission_mode": admission_mode,
        "written": bool(write_result.get("written")),
        "write_reason": write_result.get("reason", ""),
        "record_count": len(records),
        "extraction_non_empty": summary.get("extraction_non_empty", False),
        "extracted_memory_count": summary.get("extracted_memory_count", 0),
        "admitted_memory_count": summary.get("admitted_memory_count", 0),
        "admitted_attack_memory_count": summary.get("admitted_attack_memory_count", 0),
        "dropped_duplicate_count": summary.get("dropped_duplicate_count", 0),
        "dropped_non_attack_count": summary.get("dropped_non_attack_count", 0),
        "attack_rule_survival_rate": summary.get("attack_rule_survival_rate", 0.0),
        "task_type_preservation_rate": summary.get("task_type_preservation_rate", 0.0),
        "tool_preference_preservation_rate": summary.get("tool_preference_preservation_rate", 0.0),
        "marker_preservation_rate": summary.get("marker_preservation_rate", 0.0),
        "rule_preservation_rate": summary.get("rule_preservation_rate", 0.0),
        "rewrite_changed_rate": summary.get("rewrite_changed_rate", 0.0),
        "rewrite_length_ratio_mean": summary.get("rewrite_length_ratio_mean", 0.0),
        "category_counts": summary.get("category_counts", {}),
    }
    _write_json(case_dir / "case.json", case)
    _write_json(case_dir / "write_result.json", write_result)
    return row


def _failure_row(case: Dict[str, object], admission_mode: str, exc: Exception) -> Dict[str, object]:
    return {
        "case_id": case["case_id"],
        "test_type": case["test_type"],
        "memory_form": case["memory_form"],
        "expected_behavior": case["expected_behavior"],
        "admission_mode": admission_mode,
        "written": False,
        "write_reason": "runner_exception",
        "record_count": 0,
        "extraction_non_empty": False,
        "extracted_memory_count": 0,
        "admitted_memory_count": 0,
        "admitted_attack_memory_count": 0,
        "dropped_duplicate_count": 0,
        "dropped_non_attack_count": 0,
        "attack_rule_survival_rate": 0.0,
        "task_type_preservation_rate": 0.0,
        "tool_preference_preservation_rate": 0.0,
        "marker_preservation_rate": 0.0,
        "rule_preservation_rate": 0.0,
        "rewrite_changed_rate": 0.0,
        "rewrite_length_ratio_mean": 0.0,
        "category_counts": {},
        "error_type": type(exc).__name__,
        "error": str(exc),
    }


def _write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [key for key in rows[0].keys() if key != "category_counts"] + ["category_counts_json"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **{key: row.get(key, "") for key in fieldnames},
                    "category_counts_json": json.dumps(row.get("category_counts", {}), ensure_ascii=False, sort_keys=True),
                }
            )


def _build_summary(rows: List[Dict[str, object]], admission_mode: str) -> Dict[str, object]:
    by_form: Dict[str, Dict[str, object]] = {}
    for memory_form in sorted({str(row["memory_form"]) for row in rows}):
        form_rows = [row for row in rows if row["memory_form"] == memory_form]
        by_form[memory_form] = {
            "case_count": len(form_rows),
            "write_success_rate": round(sum(1 for row in form_rows if row["written"]) / float(len(form_rows) or 1), 4),
            "attack_rule_survival_rate_mean": round(
                sum(float(row["attack_rule_survival_rate"]) for row in form_rows) / float(len(form_rows) or 1),
                4,
            ),
            "rewrite_changed_rate_mean": round(
                sum(float(row["rewrite_changed_rate"]) for row in form_rows) / float(len(form_rows) or 1),
                4,
            ),
        }

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "phase": "phase0_mem0_admission_microscope",
        "admission_mode": admission_mode,
        "case_count": len(rows),
        "test_type_counts": dict(Counter(row["test_type"] for row in rows)),
        "written_count": sum(1 for row in rows if row["written"]),
        "failure_count": sum(1 for row in rows if row.get("write_reason") == "runner_exception"),
        "extraction_non_empty_count": sum(1 for row in rows if row["extraction_non_empty"]),
        "admitted_attack_memory_count": sum(int(row["admitted_attack_memory_count"]) for row in rows),
        "by_memory_form": by_form,
    }


def _write_doc(output_dir: Path, summary: Dict[str, object]) -> None:
    docs_dir = ROOT_DIR / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Phase 0 Mem0 Admission Microscope",
        "",
        f"Generated at UTC: `{summary['generated_at_utc']}`",
        f"Admission mode: `{summary['admission_mode']}`",
        f"Output directory: `{output_dir}`",
        "",
        "## Summary",
        "",
        f"- Case count: `{summary['case_count']}`",
        f"- Written count: `{summary['written_count']}`",
        f"- Extraction non-empty count: `{summary['extraction_non_empty_count']}`",
        f"- Admitted attack memory count: `{summary['admitted_attack_memory_count']}`",
        "",
        "## Memory Forms",
        "",
        "| Memory form | Cases | Write success | Attack survival mean | Rewrite changed mean |",
        "|---|---:|---:|---:|---:|",
    ]
    for memory_form, form_summary in summary["by_memory_form"].items():
        lines.append(
            f"| `{memory_form}` | {form_summary['case_count']} | "
            f"{form_summary['write_success_rate']} | {form_summary['attack_rule_survival_rate_mean']} | "
            f"{form_summary['rewrite_changed_rate_mean']} |"
        )
    lines.extend(
        ["", "## Boundary", ""]
    )
    if summary["admission_mode"] == "direct":
        lines.extend(
            [
                "- `direct` mode is an upper-bound sanity pass for probe construction.",
                "- `mem0_additive` mode should be run next to observe extraction, rewrite, duplicate, and conflict behavior.",
            ]
        )
    else:
        lines.extend(
            [
                "- This run uses Mem0-style additive admission through the local `mem0-main` prompt path.",
                "- The current result shows admission rewrite behavior for every written attack memory.",
                "- `noise_like` was extracted as auxiliary content but did not pass the attack-memory filter.",
                "- This remains a probe-level admission microscope, not a downstream drift benchmark.",
            ]
        )
    (docs_dir / "phase0_mem0_admission_microscope.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admission-mode", choices=["direct", "mem0_additive"], default="direct")
    parser.add_argument("--model", type=str, default="gpt-4o-mini")
    parser.add_argument("--admission-custom-instructions", type=str, default="")
    parser.add_argument("--memory-forms", type=str, default="", help="Comma-separated memory forms to run.")
    parser.add_argument("--case-ids", type=str, default="", help="Comma-separated case ids to run.")
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT_DIR / "output" / "phase0" / datetime.now().strftime("%Y%m%d_%H%M%S"),
    )
    args = parser.parse_args()

    admission_llm = None
    if args.admission_mode == "mem0_additive":
        from chord.model_provider import create_chat_openai

        admission_llm = create_chat_openai(model=args.model, temperature=0)

    cases = build_phase0_probe_cases()
    if args.memory_forms:
        allowed_forms = {item.strip() for item in args.memory_forms.split(",") if item.strip()}
        cases = [case for case in cases if case["memory_form"] in allowed_forms]
    if args.case_ids:
        allowed_case_ids = {item.strip() for item in args.case_ids.split(",") if item.strip()}
        cases = [case for case in cases if case["case_id"] in allowed_case_ids]
    if args.max_cases is not None:
        cases = cases[: args.max_cases]
    rows: List[Dict[str, object]] = []
    results_path = args.output_dir / "admission_microscope_results.jsonl"
    for case in cases:
        try:
            row = _run_probe(
                case=case,
                output_dir=args.output_dir,
                admission_mode=args.admission_mode,
                admission_llm=admission_llm,
                admission_custom_instructions=args.admission_custom_instructions,
            )
        except Exception as exc:
            if args.fail_fast:
                raise
            row = _failure_row(case, args.admission_mode, exc)
        rows.append(row)
        _append_jsonl(results_path, row)

    summary = _build_summary(rows, args.admission_mode)
    _write_json(args.output_dir / "admission_microscope_summary.json", summary)
    _write_csv(args.output_dir / "admission_microscope_summary.csv", rows)
    _write_csv(args.output_dir / "source_tag_admission_summary.csv", [row for row in rows if row["test_type"] == "source_tag"])
    _write_doc(args.output_dir, summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
