from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from benchmark.prompt_families import get_prompt_family_descriptions, list_prompt_families


DEFAULT_MODES = ["direct", "mem0_additive"]
SUMMARY_SCENARIOS = ["contaminated_only", "mixed", "defense_mixed"]
SUMMARY_METRICS = [
    "Memory Write Success Rate",
    "Retrieval Hit Rate",
    "Contaminated Hit Rate",
    "Contaminated Activation Rate",
    "Behavior Drift Rate",
    "Tool Preference Shift",
]


def _parse_list_arg(raw: str, allowed: List[str], label: str) -> List[str]:
    values = [item.strip() for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError(f"{label} cannot be empty")
    invalid = [item for item in values if item not in allowed]
    if invalid:
        raise ValueError(f"Unsupported {label}: {invalid}. Allowed: {allowed}")
    return values


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _decode_subprocess_output(raw: object) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    if not isinstance(raw, (bytes, bytearray)):
        return str(raw)

    for encoding in ("utf-8", "gb18030", "cp936"):
        try:
            return bytes(raw).decode(encoding)
        except UnicodeDecodeError:
            continue
    return bytes(raw).decode("utf-8", errors="replace")


def _run_single_experiment(
    *,
    python_executable: str,
    family: str,
    admission_mode: str,
    output_dir: Path,
    args,
) -> Dict[str, object]:
    script_path = ROOT_DIR / "benchmark" / "run_memory_seed_case.py"
    command = [
        python_executable,
        str(script_path),
        "--seed-source",
        args.seed_source,
        "--admission-mode",
        admission_mode,
        "--prompt-family",
        family,
        "--output-dir",
        str(output_dir),
        "--model",
        args.model,
        "--graph-limit",
        str(args.graph_limit),
        "--benign-memory-count",
        str(args.benign_memory_count),
        "--retrieval-mode",
        args.retrieval_mode,
        "--retrieval-top-k",
        str(args.retrieval_top_k),
        "--retrieval-min-score",
        str(args.retrieval_min_score),
        "--embedding-model",
        args.embedding_model,
        "--followup-task-file",
        str(args.followup_task_file),
    ]
    if args.admission_custom_instructions:
        command.extend(["--admission-custom-instructions", args.admission_custom_instructions])
    if args.seed_source == "benchmark_case":
        command.extend(["--case-file", str(args.case_file), "--case-id", args.case_id])

    completed = subprocess.run(
        command,
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=False,
    )
    stdout_text = _decode_subprocess_output(completed.stdout)
    stderr_text = _decode_subprocess_output(completed.stderr)
    result = {
        "family": family,
        "admission_mode": admission_mode,
        "output_dir": str(output_dir),
        "command": command,
        "returncode": completed.returncode,
        "stdout_tail": stdout_text[-4000:],
        "stderr_tail": stderr_text[-4000:],
    }
    return result


def _extract_metric_block(summary: Dict[str, object], scenario: str) -> Dict[str, object]:
    metrics = ((summary.get("metrics") or {}).get(scenario) or {})
    return {name: metrics.get(name) for name in SUMMARY_METRICS}


def _extract_write_snapshot(summary: Dict[str, object]) -> Dict[str, object]:
    write = (((summary.get("write_phase") or {}).get("contaminated_only") or {}).get("memory_write") or {})
    record = write.get("record") or {}
    return {
        "written": write.get("written"),
        "reason": write.get("reason"),
        "record_count": len(write.get("records", [record])) if write else 0,
        "sanitized_memory_text": record.get("SanitizedMemoryText"),
        "original_sanitized_memory_text": record.get("OriginalSanitizedMemoryText"),
        "admission_category": record.get("AdmissionCategory"),
        "is_attack_memory": record.get("IsAttackMemory"),
        "attributed_to": record.get("AttributedTo"),
    }


def _load_experiment_summary(output_dir: Path) -> Dict[str, object]:
    summary_path = output_dir / "memory_seed_summary.json"
    return json.loads(summary_path.read_text(encoding="utf-8"))


def _flatten_csv_rows(rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    flat_rows: List[Dict[str, object]] = []
    for row in rows:
        base = {
            "family": row["family"],
            "admission_mode": row["admission_mode"],
            "output_dir": row["output_dir"],
            "written": row["write_snapshot"]["written"],
            "write_reason": row["write_snapshot"]["reason"],
            "record_count": row["write_snapshot"]["record_count"],
            "sanitized_memory_text": row["write_snapshot"]["sanitized_memory_text"],
            "original_sanitized_memory_text": row["write_snapshot"]["original_sanitized_memory_text"],
            "admission_category": row["write_snapshot"]["admission_category"],
            "is_attack_memory": row["write_snapshot"]["is_attack_memory"],
            "attributed_to": row["write_snapshot"]["attributed_to"],
        }
        for scenario in SUMMARY_SCENARIOS:
            for metric_name, metric_value in row["scenario_metrics"][scenario].items():
                base[f"{scenario}::{metric_name}"] = metric_value
        flat_rows.append(base)
    return flat_rows


def _build_pairwise_comparisons(rows: List[Dict[str, object]]) -> List[Dict[str, object]]:
    grouped: Dict[str, Dict[str, Dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault(row["family"], {})[row["admission_mode"]] = row

    comparisons = []
    for family, mode_map in grouped.items():
        if "direct" not in mode_map or "mem0_additive" not in mode_map:
            continue
        direct_row = mode_map["direct"]
        mem0_row = mode_map["mem0_additive"]
        comparison = {
            "family": family,
            "direct_output_dir": direct_row["output_dir"],
            "mem0_output_dir": mem0_row["output_dir"],
            "direct_write_snapshot": direct_row["write_snapshot"],
            "mem0_write_snapshot": mem0_row["write_snapshot"],
            "metric_deltas": {},
        }
        for scenario in SUMMARY_SCENARIOS:
            comparison["metric_deltas"][scenario] = {}
            for metric_name in SUMMARY_METRICS:
                direct_value = direct_row["scenario_metrics"][scenario].get(metric_name)
                mem0_value = mem0_row["scenario_metrics"][scenario].get(metric_name)
                if isinstance(direct_value, (int, float)) and isinstance(mem0_value, (int, float)):
                    comparison["metric_deltas"][scenario][metric_name] = round(mem0_value - direct_value, 4)
                else:
                    comparison["metric_deltas"][scenario][metric_name] = None
        comparisons.append(comparison)
    return comparisons


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--families",
        type=str,
        default=",".join(list_prompt_families()),
        help="Comma-separated prompt family names.",
    )
    parser.add_argument(
        "--modes",
        type=str,
        default=",".join(DEFAULT_MODES),
        help="Comma-separated admission modes. Use direct,mem0_additive for comparison.",
    )
    parser.add_argument("--model", type=str, default="gpt-4o-mini")
    parser.add_argument("--seed-source", type=str, default="local_offline", choices=["local_offline", "benchmark_case"])
    parser.add_argument(
        "--case-file",
        type=Path,
        default=ROOT_DIR / "benchmark" / "tmc_chordtools_smoke_v2_shortlist.jsonl",
    )
    parser.add_argument("--case-id", type=str, default="tmc-chordtools-v1-successor-arxiv-q01")
    parser.add_argument(
        "--followup-task-file",
        type=Path,
        default=ROOT_DIR / "benchmark" / "followup_sets" / "local_mem0_memory_seed_v1.json",
    )
    parser.add_argument("--graph-limit", type=int, default=3)
    parser.add_argument("--benign-memory-count", type=int, default=8)
    parser.add_argument("--retrieval-mode", type=str, default="embedding", choices=["embedding", "semantic", "auto", "token"])
    parser.add_argument("--retrieval-top-k", type=int, default=3)
    parser.add_argument("--retrieval-min-score", type=float, default=0.05)
    parser.add_argument("--embedding-model", type=str, default="sentence-transformers/all-MiniLM-L6-v2")
    parser.add_argument("--admission-custom-instructions", type=str, default="")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT_DIR / "output" / "benchmark_memory" / "prompt_family_batch",
    )
    parser.add_argument("--run-tag", type=str, default="")
    parser.add_argument("--skip-existing", action="store_true")
    args = parser.parse_args()

    families = _parse_list_arg(args.families, list_prompt_families(), "families")
    modes = _parse_list_arg(args.modes, DEFAULT_MODES, "modes")
    run_tag = args.run_tag or _utc_timestamp()
    batch_dir = args.output_root / run_tag
    batch_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "python_executable": sys.executable,
        "run_tag": run_tag,
        "families": families,
        "modes": modes,
        "model": args.model,
        "seed_source": args.seed_source,
        "followup_task_file": str(args.followup_task_file),
        "retrieval_mode": args.retrieval_mode,
        "retrieval_top_k": args.retrieval_top_k,
        "retrieval_min_score": args.retrieval_min_score,
        "embedding_model": args.embedding_model,
        "skip_existing": args.skip_existing,
    }

    experiment_runs = []
    successful_rows = []
    for family in families:
        for admission_mode in modes:
            output_dir = batch_dir / f"{family}__{admission_mode}"
            summary_path = output_dir / "memory_seed_summary.json"
            if args.skip_existing and summary_path.exists():
                run_result = {
                    "family": family,
                    "admission_mode": admission_mode,
                    "output_dir": str(output_dir),
                    "returncode": 0,
                    "stdout_tail": "",
                    "stderr_tail": "",
                    "skipped": True,
                }
            else:
                run_result = _run_single_experiment(
                    python_executable=sys.executable,
                    family=family,
                    admission_mode=admission_mode,
                    output_dir=output_dir,
                    args=args,
                )
            experiment_runs.append(run_result)

            if run_result["returncode"] != 0:
                continue

            summary = _load_experiment_summary(output_dir)
            successful_rows.append(
                {
                    "family": family,
                    "admission_mode": admission_mode,
                    "output_dir": str(output_dir),
                    "write_snapshot": _extract_write_snapshot(summary),
                    "scenario_metrics": {
                        scenario: _extract_metric_block(summary, scenario) for scenario in SUMMARY_SCENARIOS
                    },
                    "prompt_config": summary.get("prompt_config", {}),
                    "admission_config": summary.get("admission_config", {}),
                }
            )

    flat_rows = _flatten_csv_rows(successful_rows)
    pairwise = _build_pairwise_comparisons(successful_rows)

    summary_payload = {
        "manifest": manifest,
        "runs": experiment_runs,
        "successful_results": successful_rows,
        "pairwise_comparisons": pairwise,
    }

    (batch_dir / "batch_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (batch_dir / "batch_summary.json").write_text(json.dumps(summary_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    csv_rows = flat_rows
    csv_path = batch_dir / "batch_summary.csv"
    if csv_rows:
        fieldnames = list(csv_rows[0].keys())
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)
    else:
        csv_path.write_text("", encoding="utf-8")

    print(json.dumps({
        "batch_dir": str(batch_dir),
        "family_count": len(families),
        "mode_count": len(modes),
        "total_runs": len(experiment_runs),
        "successful_runs": len(successful_rows),
        "pairwise_comparisons": len(pairwise),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
