"""Run TMC-ChordTools benchmark cases and emit structured results."""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from benchmark.langchain_tools import load_langchain_tools, validate_langchain_tool_imports


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _append_jsonl(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _csv_arg(value: str) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _sanitize_case_id(case_id: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in case_id)


def _parse_fraction(value: Optional[str]) -> Optional[Dict[str, object]]:
    if not value or "/" not in value:
        return None
    left, right = value.split("/", 1)
    try:
        success = int(left)
        total = int(right)
    except ValueError:
        return None
    return {
        "success": success,
        "total": total,
        "rate": round(success / float(total or 1), 4),
        "raw": value,
    }


def _read_json_lines(path: Path) -> List[Dict[str, object]]:
    if not path.exists():
        return []
    rows: List[Dict[str, object]] = []
    payload = path.read_text(encoding="utf-8")
    decoder = json.JSONDecoder()
    index = 0
    length = len(payload)
    while index < length:
        while index < length and payload[index].isspace():
            index += 1
        if index >= length:
            break
        try:
            row, offset = decoder.raw_decode(payload, index)
        except json.JSONDecodeError:
            next_newline = payload.find("\n", index)
            if next_newline == -1:
                break
            index = next_newline + 1
            continue
        if isinstance(row, dict):
            rows.append(row)
        index = offset
    return rows


def _extract_metrics_from_final_log(final_log: str) -> Dict[str, Optional[Dict[str, object]]]:
    metrics: Dict[str, Optional[Dict[str, object]]] = {
        "hijack_success": None,
        "harvest_success": None,
        "pollute_success": None,
    }
    if not final_log.strip():
        return metrics

    last_line = final_log.strip().splitlines()[-1]
    for metric_name, token in (
        ("hijack_success", "HSR="),
        ("harvest_success", "HASR="),
        ("pollute_success", "PSR="),
    ):
        start = last_line.find(token)
        if start == -1:
            continue
        start += len(token)
        end = last_line.find(",", start)
        if end == -1:
            end = len(last_line)
        metrics[metric_name] = _parse_fraction(last_line[start:end].strip())
    return metrics


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _extract_case_metrics(log_dir: Path, case_prefix: str) -> Dict[str, object]:
    hijack_rows = _read_json_lines(log_dir / f"{case_prefix}_hijack.log_success_rate")
    harvest_rows = _read_json_lines(log_dir / f"{case_prefix}_harvest.log_success_rate")
    pollute_rows = _read_json_lines(log_dir / f"{case_prefix}_pollute.log_success_rate")
    pollute_details = _read_json_lines(log_dir / f"{case_prefix}_pollute.log")
    final_log = _read_text(log_dir / f"{case_prefix}_final.log")
    error_log = _read_text(log_dir / f"{case_prefix}_error.log")
    final_log_metrics = _extract_metrics_from_final_log(final_log)

    pollute_memory_writes = [row.get("memory_write", {}) for row in pollute_details if isinstance(row, dict)]
    written_count = sum(1 for row in pollute_memory_writes if row.get("written"))

    return {
        "hijack_success": (
            _parse_fraction(hijack_rows[-1]["success_rate"]) if hijack_rows else final_log_metrics["hijack_success"]
        ),
        "harvest_success": (
            _parse_fraction(harvest_rows[-1]["harvest_success"]) if harvest_rows else final_log_metrics["harvest_success"]
        ),
        "harvest_hijack_alignment": _parse_fraction(harvest_rows[-1]["hijack_success"]) if harvest_rows else None,
        "pollute_success": (
            _parse_fraction(pollute_rows[-1]["success_rate"]) if pollute_rows else final_log_metrics["pollute_success"]
        ),
        "pollute_detail_count": len(pollute_details),
        "memory_write_summary": {
            "attempted_count": len(pollute_memory_writes),
            "written_count": written_count,
            "failed_count": len(pollute_memory_writes) - written_count,
            "reasons": sorted(
                {
                    row.get("reason", "")
                    for row in pollute_memory_writes
                    if isinstance(row, dict) and row.get("reason")
                }
            ),
        },
        "final_log_excerpt": final_log.strip().splitlines()[-1] if final_log.strip() else "",
        "error_log_present": bool(error_log.strip()),
        "error_log_excerpt": error_log.strip()[-1000:] if error_log.strip() else "",
    }


def _select_cases(
    case_rows: List[Dict[str, object]],
    attack_surface: str,
    target_tools: Iterable[str],
    case_ids: Iterable[str],
    defense_ready_only: bool,
    max_cases: Optional[int],
) -> List[Dict[str, object]]:
    selected = case_rows
    target_filter = set(target_tools)
    case_id_filter = set(case_ids)

    if attack_surface != "all":
        selected = [case for case in selected if case.get("attack_surface") == attack_surface]
    if target_filter:
        selected = [case for case in selected if case.get("target_tool") in target_filter]
    if case_id_filter:
        selected = [case for case in selected if case.get("case_id") in case_id_filter]
    if defense_ready_only:
        selected = [case for case in selected if bool(case.get("defense_ready"))]
    if max_cases is not None:
        selected = selected[:max_cases]
    return selected


def _build_run_manifest(
    selected_cases: List[Dict[str, object]],
    args: argparse.Namespace,
    output_dir: Path,
) -> Dict[str, object]:
    return {
        "runner": "tmc_chordtools_attack_core",
        "generated_at_utc": _now_utc(),
        "case_file": str(args.case_file),
        "output_dir": str(output_dir),
        "selection": {
            "attack_surface": args.attack_surface,
            "target_tools": args.target_tools,
            "case_ids": args.case_ids,
            "defense_ready_only": args.defense_ready_only,
            "max_cases": args.max_cases,
        },
        "run_config": {
            "model": args.model,
            "temperature": args.temperature,
            "graph_limit": args.graph_limit,
            "tool_timewait": args.tool_timewait,
            "defense": args.defense,
            "safe_payload_mode": args.safe_payload_mode,
            "memory_store_path": args.memory_store_path,
            "dry_run": args.dry_run,
        },
        "selected_case_count": len(selected_cases),
        "selected_case_ids": [case["case_id"] for case in selected_cases],
    }


def _classify_validation_error(exc: Exception) -> Dict[str, str]:
    error_type = type(exc).__name__
    message = str(exc)
    lowered = message.lower()
    if "timeout" in lowered or "connection" in lowered or "httpsconnectionpool" in lowered:
        phase = "live_endpoint_validation"
    elif error_type in {"ImportError", "ModuleNotFoundError"}:
        phase = "dependency_import_validation"
    else:
        phase = "tool_instantiation_validation"
    return {
        "type": error_type,
        "message": message,
        "phase": phase,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--case-file",
        type=Path,
        default=ROOT_DIR / "benchmark" / "tmc_chordtools_v1.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT_DIR / "output" / "benchmark_runs" / datetime.now().strftime("%Y%m%d_%H%M%S"),
    )
    parser.add_argument(
        "--attack-surface",
        choices=["all", "predecessor", "successor"],
        default="all",
    )
    parser.add_argument("--target-tools", type=_csv_arg, default=[])
    parser.add_argument("--case-ids", type=_csv_arg, default=[])
    parser.add_argument("--defense-ready-only", action="store_true")
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--model", type=str, default="gpt-4o-mini")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--graph-limit", type=int, default=3)
    parser.add_argument(
        "--defense",
        type=str,
        default="none",
        choices=["none", "airgap", "spotlight", "pi_detector", "tool_filter"],
    )
    parser.add_argument("--tool-timewait", type=float, default=0.0)
    parser.add_argument("--safe-payload-mode", action="store_true")
    parser.add_argument("--memory-store-path", type=str, default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--validate-tools",
        action="store_true",
        help="When used with --dry-run, also instantiate the selected target tools.",
    )
    parser.add_argument(
        "--validate-imports",
        action="store_true",
        help="When used with --dry-run, validate Python/module dependencies without instantiating tools.",
    )
    args = parser.parse_args()

    case_rows = _read_jsonl(args.case_file)
    selected_cases = _select_cases(
        case_rows=case_rows,
        attack_surface=args.attack_surface,
        target_tools=args.target_tools,
        case_ids=args.case_ids,
        defense_ready_only=args.defense_ready_only,
        max_cases=args.max_cases,
    )
    if not selected_cases:
        raise ValueError("No benchmark cases matched the current selection.")

    output_dir = args.output_dir.resolve()
    results_path = output_dir / "results.jsonl"
    summary_path = output_dir / "summary.json"
    manifest_path = output_dir / "run_manifest.json"
    logs_root = output_dir / "case_logs"

    run_manifest = _build_run_manifest(selected_cases, args, output_dir)
    _write_json(manifest_path, run_manifest)

    requested_tools = sorted({case["target_tool"] for case in selected_cases})
    tool_registry: Dict[str, object] = {}
    tool_validation_error: Optional[Dict[str, str]] = None
    import_validation: Optional[Dict[str, Dict[str, str]]] = None

    if args.dry_run and args.validate_imports:
        import_validation = validate_langchain_tool_imports(requested_tools)

    if not args.dry_run or args.validate_tools:
        try:
            tool_registry = load_langchain_tools(requested_tools)
        except Exception as exc:
            tool_validation_error = _classify_validation_error(exc)
            if not args.dry_run:
                raise

    if args.dry_run:
        payload = {
            "status": "dry_run",
            "selected_case_count": len(selected_cases),
            "requested_tools": requested_tools,
            "loaded_tools": sorted(tool_registry.keys()),
            "import_validation_enabled": bool(args.validate_imports),
            "import_validation": import_validation,
            "tool_validation_enabled": bool(args.validate_tools),
            "tool_validation_error": tool_validation_error,
            "output_dir": str(output_dir),
        }
        _write_json(summary_path, payload)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    from chord.agent import Agent
    from chord.model_provider import create_chat_openai

    llm = create_chat_openai(model=args.model, temperature=args.temperature)
    results: List[Dict[str, object]] = []

    for case in selected_cases:
        case_id = str(case["case_id"])
        case_prefix = _sanitize_case_id(case_id)
        case_log_dir = logs_root / case_prefix
        case_log_dir.mkdir(parents=True, exist_ok=True)

        started_at = _now_utc()
        result_row: Dict[str, object] = {
            "case_id": case_id,
            "status": "running",
            "started_at_utc": started_at,
            "finished_at_utc": None,
            "case": case,
            "run_config": {
                "model": args.model,
                "temperature": args.temperature,
                "graph_limit": args.graph_limit,
                "defense": args.defense,
                "tool_timewait": args.tool_timewait,
                "safe_payload_mode": args.safe_payload_mode,
                "memory_store_path": args.memory_store_path,
            },
            "log_paths": {
                "case_log_dir": str(case_log_dir),
                "full_log": str(case_log_dir / f"{case_prefix}_full_log.log"),
                "error_log": str(case_log_dir / f"{case_prefix}_error.log"),
                "hijack_log": str(case_log_dir / f"{case_prefix}_hijack.log"),
                "harvest_log": str(case_log_dir / f"{case_prefix}_harvest.log"),
                "pollute_log": str(case_log_dir / f"{case_prefix}_pollute.log"),
                "final_log": str(case_log_dir / f"{case_prefix}_final.log"),
            },
        }

        try:
            target_tool = tool_registry[str(case["target_tool"])]
            agent = Agent(
                target_tool=target_tool,
                generation_model=llm,
                target_model=llm,
                queries=[str(case["user_query"])],
                predecessor=bool(case["attack_surface"] == "predecessor"),
                enable_hijack=True,
                enable_harvest=True,
                enable_pollute=True,
                attack_only=True,
                malicious_tool={
                    "name": str(case["malicious_tool_name"]),
                    "description": str(case["malicious_tool_description"]),
                },
                malicious_tool_params=dict(case.get("malicious_argument_schema", {})),
                defense=args.defense,
                safe_payload_mode=args.safe_payload_mode,
                memory_store_path=args.memory_store_path,
                tool_timewait=args.tool_timewait,
                log_folder=str(case_log_dir),
                log_prefix=case_prefix,
            )
            agent.run(args.graph_limit)
            result_row["status"] = "completed"
            result_row["metrics"] = _extract_case_metrics(case_log_dir, case_prefix)
        except Exception as exc:
            result_row["status"] = "failed"
            result_row["error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
        finally:
            result_row["finished_at_utc"] = _now_utc()
            results.append(result_row)
            _append_jsonl(results_path, result_row)

    completed = sum(1 for row in results if row["status"] == "completed")
    failed = sum(1 for row in results if row["status"] == "failed")
    pollute_rates = [
        row["metrics"]["pollute_success"]["rate"]
        for row in results
        if row.get("metrics", {}).get("pollute_success")
    ]
    summary = {
        "status": "completed",
        "generated_at_utc": _now_utc(),
        "total_cases": len(results),
        "completed_cases": completed,
        "failed_cases": failed,
        "successful_case_ids": [row["case_id"] for row in results if row["status"] == "completed"],
        "failed_case_ids": [row["case_id"] for row in results if row["status"] == "failed"],
        "pollute_success_rate_mean": round(sum(pollute_rates) / float(len(pollute_rates) or 1), 4),
    }
    _write_json(summary_path, summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
