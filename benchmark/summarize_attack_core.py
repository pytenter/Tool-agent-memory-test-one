from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_RUNS_ROOT = ROOT_DIR / "output" / "benchmark_runs"
DEFAULT_OUTPUT_ROOT = ROOT_DIR / "output" / "benchmark_analysis"


def _csv_arg(value: str) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_fraction(value: Optional[object]) -> Optional[Dict[str, object]]:
    if not value:
        return None
    raw = str(value)
    if "/" not in raw:
        return None
    left, right = raw.split("/", 1)
    try:
        success = int(left)
        total = int(right)
    except ValueError:
        return None
    return {
        "success": success,
        "total": total,
        "rate": round(success / float(total or 1), 4),
        "raw": raw,
    }


def _extract_from_final_log(final_log_excerpt: str) -> Dict[str, Optional[Dict[str, object]]]:
    metrics: Dict[str, Optional[Dict[str, object]]] = {
        "hijack_success": None,
        "harvest_success": None,
        "pollute_success": None,
    }
    for metric_name, token in (
        ("hijack_success", "HSR="),
        ("harvest_success", "HASR="),
        ("pollute_success", "PSR="),
    ):
        start = final_log_excerpt.find(token)
        if start == -1:
            continue
        start += len(token)
        end = final_log_excerpt.find(",", start)
        if end == -1:
            end = len(final_log_excerpt)
        metrics[metric_name] = _parse_fraction(final_log_excerpt[start:end].strip())
    return metrics


def _normalize_metric(value: object) -> Optional[Dict[str, object]]:
    if isinstance(value, dict):
        raw = value.get("raw")
        if raw:
            return _parse_fraction(raw)
        success = value.get("success")
        total = value.get("total")
        if isinstance(success, int) and isinstance(total, int):
            return _parse_fraction(f"{success}/{total}")
        return None
    return _parse_fraction(value)


def _read_results(path: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _load_run_rows(runs_root: Path, case_ids: List[str], max_runs: Optional[int]) -> List[Dict[str, object]]:
    selected_runs = sorted(
        [path for path in runs_root.iterdir() if path.is_dir()],
        key=lambda path: path.name,
    )
    if max_runs is not None:
        selected_runs = selected_runs[-max_runs:]

    rows: List[Dict[str, object]] = []
    for run_dir in selected_runs:
        results_path = run_dir / "results.jsonl"
        for row in _read_results(results_path):
            case_id = str(row.get("case_id", ""))
            if case_ids and case_id not in case_ids:
                continue
            metrics = dict(row.get("metrics", {}))
            final_log_excerpt = str(metrics.get("final_log_excerpt", ""))
            fallback = _extract_from_final_log(final_log_excerpt)

            hijack_success = _normalize_metric(metrics.get("hijack_success")) or fallback["hijack_success"]
            harvest_success = _normalize_metric(metrics.get("harvest_success")) or fallback["harvest_success"]
            pollute_success = _normalize_metric(metrics.get("pollute_success")) or fallback["pollute_success"]

            rows.append(
                {
                    "run_id": run_dir.name,
                    "case_id": case_id,
                    "status": str(row.get("status", "")),
                    "attack_surface": str(row.get("case", {}).get("attack_surface", "")),
                    "target_tool": str(row.get("case", {}).get("target_tool", "")),
                    "malicious_tool": str(row.get("case", {}).get("malicious_tool_name", "")),
                    "user_query": str(row.get("case", {}).get("user_query", "")),
                    "hijack_success": hijack_success,
                    "harvest_success": harvest_success,
                    "pollute_success": pollute_success,
                    "error_type": str(row.get("error", {}).get("type", "")),
                    "error_message": str(row.get("error", {}).get("message", "")),
                    "final_log_excerpt": final_log_excerpt,
                }
            )
    return rows


def _mean_rate(rows: List[Dict[str, object]], metric_name: str) -> Optional[float]:
    rates = [
        float(row[metric_name]["rate"])
        for row in rows
        if isinstance(row.get(metric_name), dict) and row[metric_name].get("rate") is not None
    ]
    if not rates:
        return None
    return round(sum(rates) / len(rates), 4)


def _build_summary(rows: List[Dict[str, object]]) -> Dict[str, object]:
    grouped: Dict[str, List[Dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault(row["case_id"], []).append(row)

    case_summaries: List[Dict[str, object]] = []
    for case_id, case_rows in sorted(grouped.items()):
        completed_rows = [row for row in case_rows if row["status"] == "completed"]
        failed_rows = [row for row in case_rows if row["status"] == "failed"]
        first_row = case_rows[0]
        case_summaries.append(
            {
                "case_id": case_id,
                "attack_surface": first_row["attack_surface"],
                "target_tool": first_row["target_tool"],
                "malicious_tool": first_row["malicious_tool"],
                "total_runs": len(case_rows),
                "completed_runs": len(completed_rows),
                "failed_runs": len(failed_rows),
                "hijack_rate_mean": _mean_rate(completed_rows, "hijack_success"),
                "harvest_rate_mean": _mean_rate(completed_rows, "harvest_success"),
                "pollute_rate_mean": _mean_rate(completed_rows, "pollute_success"),
                "run_ids": [row["run_id"] for row in case_rows],
                "failure_types": sorted({row["error_type"] for row in failed_rows if row["error_type"]}),
            }
        )

    return {
        "generated_at_utc": datetime.utcnow().isoformat() + "Z",
        "runs_root": str(DEFAULT_RUNS_ROOT),
        "case_count": len(case_summaries),
        "case_summaries": case_summaries,
    }


def _write_outputs(rows: List[Dict[str, object]], summary: Dict[str, object], output_stem: Path) -> None:
    output_stem.parent.mkdir(parents=True, exist_ok=True)

    summary_path = output_stem.with_suffix(".json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_path = output_stem.with_suffix(".csv")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "run_id",
                "case_id",
                "status",
                "attack_surface",
                "target_tool",
                "malicious_tool",
                "hijack_raw",
                "harvest_raw",
                "pollute_raw",
                "hijack_rate",
                "harvest_rate",
                "pollute_rate",
                "error_type",
                "error_message",
                "final_log_excerpt",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "run_id": row["run_id"],
                    "case_id": row["case_id"],
                    "status": row["status"],
                    "attack_surface": row["attack_surface"],
                    "target_tool": row["target_tool"],
                    "malicious_tool": row["malicious_tool"],
                    "hijack_raw": row["hijack_success"]["raw"] if row["hijack_success"] else "",
                    "harvest_raw": row["harvest_success"]["raw"] if row["harvest_success"] else "",
                    "pollute_raw": row["pollute_success"]["raw"] if row["pollute_success"] else "",
                    "hijack_rate": row["hijack_success"]["rate"] if row["hijack_success"] else "",
                    "harvest_rate": row["harvest_success"]["rate"] if row["harvest_success"] else "",
                    "pollute_rate": row["pollute_success"]["rate"] if row["pollute_success"] else "",
                    "error_type": row["error_type"],
                    "error_message": row["error_message"],
                    "final_log_excerpt": row["final_log_excerpt"],
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-root", type=Path, default=DEFAULT_RUNS_ROOT)
    parser.add_argument("--case-ids", type=_csv_arg, default=[])
    parser.add_argument("--max-runs", type=int, default=None)
    parser.add_argument(
        "--output-stem",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT / f"attack_core_stability_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
    )
    args = parser.parse_args()

    rows = _load_run_rows(args.runs_root, args.case_ids, args.max_runs)
    summary = _build_summary(rows)
    summary["runs_root"] = str(args.runs_root)
    summary["selected_case_ids"] = args.case_ids
    summary["selected_run_count"] = len(sorted({row["run_id"] for row in rows}))
    _write_outputs(rows, summary, args.output_stem)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
