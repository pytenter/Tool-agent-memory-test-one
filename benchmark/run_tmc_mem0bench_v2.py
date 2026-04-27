"""Run offline TMC-Mem0Bench v2 seed cases through memory write/retrieval/eval."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from benchmark.v2_followup_evaluator import evaluate_v2_followup, metrics_from_trace
from bridge.memory_writer import load_memory_store, reset_memory_store, write_memory_from_tool_output
from bridge.retrieval_adapter import retrieve_memory_snippets


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path) -> List[Dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


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


def _select_cases(
    rows: List[Dict[str, object]],
    *,
    domains: Iterable[str],
    prompt_families: Iterable[str],
    case_ids: Iterable[str],
    max_cases: Optional[int],
) -> List[Dict[str, object]]:
    selected = rows
    domain_filter = set(domains)
    family_filter = set(prompt_families)
    case_id_filter = set(case_ids)
    if domain_filter:
        selected = [row for row in selected if row.get("domain") in domain_filter]
    if family_filter:
        selected = [row for row in selected if row.get("prompt_family") in family_filter]
    if case_id_filter:
        selected = [row for row in selected if row.get("case_id") in case_id_filter]
    if max_cases is not None:
        selected = selected[:max_cases]
    return selected


def _admission_summary(write_result: Dict[str, object]) -> Dict[str, object]:
    return dict(write_result.get("admission_summary") or {})


def _case_actions(case: Dict[str, object]) -> List[str]:
    actions = [str(item) for item in case.get("expected_clean_tools", []) if str(item)]
    helper = str(case.get("malicious_tool_name") or "")
    if helper:
        actions.append(helper)
    return actions


def _write_case_memory(
    *,
    case: Dict[str, object],
    store_path: Path,
    admission_mode: str,
    admission_llm,
    admission_custom_instructions: str,
) -> Dict[str, object]:
    payload = case.get("payload_text") or {}
    if not isinstance(payload, dict):
        raise ValueError("case payload_text must be a dict")
    return write_memory_from_tool_output(
        store_path=str(store_path),
        instruction=str(case.get("user_task") or ""),
        actions=_case_actions(case),
        raw_tool_output=payload,
        source_tool=str(case.get("malicious_tool_name") or "v2_post_processor"),
        target_tool=str(case.get("target_tool") or ""),
        write_reason="v2_tool_return_summary",
        success=True,
        reward=1.0,
        admission_mode=admission_mode,
        admission_llm=admission_llm,
        admission_context={
            "messages": [
                {"role": "user", "content": str(case.get("user_task") or "")},
                {
                    "role": "assistant",
                    "content": "Clean tool chain: " + " -> ".join(_case_actions(case)),
                },
                {
                    "role": "assistant",
                    "content": json.dumps(payload, ensure_ascii=False),
                },
            ]
        },
        admission_custom_instructions=admission_custom_instructions,
    )


def _run_case(
    *,
    case: Dict[str, object],
    output_dir: Path,
    admission_mode: str,
    admission_llm,
    admission_custom_instructions: str,
    retrieval_mode: str,
    retrieval_top_k: int,
    retrieval_min_score: float,
    embedding_model: str,
) -> Dict[str, object]:
    case_id = str(case["case_id"])
    case_dir = output_dir / "case_logs" / _sanitize_case_id(case_id)
    case_dir.mkdir(parents=True, exist_ok=True)
    store_path = case_dir / "memory_store.json"
    reset_memory_store(str(store_path))

    write_result = _write_case_memory(
        case=case,
        store_path=store_path,
        admission_mode=admission_mode,
        admission_llm=admission_llm,
        admission_custom_instructions=admission_custom_instructions,
    )
    retrieval_result = retrieve_memory_snippets(
        query=str(case.get("future_task") or ""),
        store_path=str(store_path),
        top_k=retrieval_top_k,
        min_score=retrieval_min_score,
        retrieval_mode=retrieval_mode,
        embedding_model_name=embedding_model,
    )
    trace = evaluate_v2_followup(case, retrieval_result)
    metrics = metrics_from_trace(bool(write_result.get("written")), trace)

    _write_json(case_dir / "case.json", case)
    _write_json(case_dir / "write_result.json", write_result)
    _write_json(case_dir / "retrieval_result.json", retrieval_result)
    _write_json(case_dir / "followup_trace.json", trace)

    return {
        "case_id": case_id,
        "domain": case.get("domain"),
        "prompt_family": case.get("prompt_family"),
        "admission_mode": admission_mode,
        "memory_case_type": case.get("memory_case_type"),
        "write_success": bool(write_result.get("written")),
        "write_reason": write_result.get("reason", ""),
        "retrieval_hit": bool(trace.get("retrieval_hits", 0)),
        "contaminated_hit": bool(trace.get("contaminated_hits", 0)),
        "activation": bool((trace.get("decision") or {}).get("activation")),
        "chosen_tool": trace.get("chosen_tool"),
        "clean_tool": (trace.get("decision") or {}).get("clean_tool"),
        "preferred_tool": (trace.get("decision") or {}).get("preferred_tool"),
        "retrieval_mode_actual": retrieval_result.get("retrieval_mode", ""),
        "admission_metrics": _admission_summary(write_result),
        "metrics": metrics,
        "case_log_dir": str(case_dir),
    }


def _mean(values: List[float]) -> float:
    return round(sum(values) / float(len(values) or 1), 4)


def _build_summary(results: List[Dict[str, object]]) -> Dict[str, object]:
    metric_names = sorted(
        {
            metric_name
            for row in results
            for metric_name in (row.get("metrics") or {}).keys()
        }
    )
    metric_means = {
        metric_name: _mean([
            float((row.get("metrics") or {}).get(metric_name, 0.0))
            for row in results
        ])
        for metric_name in metric_names
    }
    by_domain: Dict[str, Dict[str, object]] = {}
    for domain in sorted({str(row.get("domain")) for row in results}):
        rows = [row for row in results if str(row.get("domain")) == domain]
        by_domain[domain] = {
            "case_count": len(rows),
            "write_success_rate": _mean([1.0 if row.get("write_success") else 0.0 for row in rows]),
            "retrieval_hit_rate": _mean([1.0 if row.get("retrieval_hit") else 0.0 for row in rows]),
            "activation_rate": _mean([1.0 if row.get("activation") else 0.0 for row in rows]),
        }

    by_family: Dict[str, Dict[str, object]] = {}
    for family in sorted({str(row.get("prompt_family")) for row in results}):
        rows = [row for row in results if str(row.get("prompt_family")) == family]
        by_family[family] = {
            "case_count": len(rows),
            "write_success_rate": _mean([1.0 if row.get("write_success") else 0.0 for row in rows]),
            "retrieval_hit_rate": _mean([1.0 if row.get("retrieval_hit") else 0.0 for row in rows]),
            "activation_rate": _mean([1.0 if row.get("activation") else 0.0 for row in rows]),
        }

    return {
        "case_count": len(results),
        "domain_counts": dict(Counter(row.get("domain") for row in results)),
        "prompt_family_counts": dict(Counter(row.get("prompt_family") for row in results)),
        "retrieval_mode_counts": dict(Counter(row.get("retrieval_mode_actual") for row in results)),
        "write_success_count": sum(1 for row in results if row.get("write_success")),
        "retrieval_hit_count": sum(1 for row in results if row.get("retrieval_hit")),
        "activation_count": sum(1 for row in results if row.get("activation")),
        "metric_means": metric_means,
        "by_domain": by_domain,
        "by_prompt_family": by_family,
    }


def _build_manifest(args: argparse.Namespace, selected_cases: List[Dict[str, object]], output_dir: Path) -> Dict[str, object]:
    return {
        "runner": "tmc_mem0bench_v2_offline",
        "generated_at_utc": _now_utc(),
        "case_file": str(args.case_file),
        "output_dir": str(output_dir),
        "selection": {
            "domains": args.domains,
            "prompt_families": args.prompt_families,
            "case_ids": args.case_ids,
            "max_cases": args.max_cases,
        },
        "run_config": {
            "admission_mode": args.admission_mode,
            "model": args.model,
            "retrieval_mode": args.retrieval_mode,
            "retrieval_top_k": args.retrieval_top_k,
            "retrieval_min_score": args.retrieval_min_score,
            "embedding_model": args.embedding_model,
            "dry_run": args.dry_run,
        },
        "selected_case_count": len(selected_cases),
        "selected_case_ids": [case["case_id"] for case in selected_cases],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--case-file",
        type=Path,
        default=ROOT_DIR / "benchmark" / "tmc_mem0bench_v2_seed.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT_DIR / "output" / "benchmark_v2_runs" / datetime.now().strftime("%Y%m%d_%H%M%S"),
    )
    parser.add_argument("--domains", type=_csv_arg, default=[])
    parser.add_argument("--prompt-families", type=_csv_arg, default=[])
    parser.add_argument("--case-ids", type=_csv_arg, default=[])
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--admission-mode", choices=["direct", "mem0_additive"], default="direct")
    parser.add_argument("--model", type=str, default="gpt-4o-mini")
    parser.add_argument("--admission-custom-instructions", type=str, default="")
    parser.add_argument("--retrieval-mode", choices=["embedding", "semantic", "auto", "token"], default="token")
    parser.add_argument("--retrieval-top-k", type=int, default=3)
    parser.add_argument("--retrieval-min-score", type=float, default=0.01)
    parser.add_argument("--embedding-model", type=str, default="sentence-transformers/all-MiniLM-L6-v2")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = _read_jsonl(args.case_file)
    selected_cases = _select_cases(
        rows,
        domains=args.domains,
        prompt_families=args.prompt_families,
        case_ids=args.case_ids,
        max_cases=args.max_cases,
    )

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = _build_manifest(args, selected_cases, output_dir)
    _write_json(output_dir / "run_manifest.json", manifest)

    if args.dry_run:
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
        return

    admission_llm = None
    if args.admission_mode == "mem0_additive":
        from chord.model_provider import create_chat_openai

        admission_llm = create_chat_openai(model=args.model, temperature=0)

    results: List[Dict[str, object]] = []
    failures: List[Dict[str, object]] = []
    results_path = output_dir / "results.jsonl"
    if results_path.exists():
        results_path.unlink()

    for case in selected_cases:
        try:
            row = _run_case(
                case=case,
                output_dir=output_dir,
                admission_mode=args.admission_mode,
                admission_llm=admission_llm,
                admission_custom_instructions=args.admission_custom_instructions,
                retrieval_mode=args.retrieval_mode,
                retrieval_top_k=args.retrieval_top_k,
                retrieval_min_score=args.retrieval_min_score,
                embedding_model=args.embedding_model,
            )
            results.append(row)
            _append_jsonl(results_path, row)
        except Exception as exc:
            failure = {
                "case_id": case.get("case_id"),
                "domain": case.get("domain"),
                "prompt_family": case.get("prompt_family"),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
            failures.append(failure)
            _append_jsonl(output_dir / "failures.jsonl", failure)

    summary = {
        "manifest": manifest,
        "result_summary": _build_summary(results),
        "failure_count": len(failures),
        "failures": failures,
    }
    _write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary["result_summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
