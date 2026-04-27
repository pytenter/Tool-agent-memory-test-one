"""Generate Phase -1 frozen-result index, summary, and docs."""

from __future__ import annotations

import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_DIR / "output"
DOCS_DIR = ROOT_DIR / "docs"


FROZEN_ARTIFACTS = [
    {
        "artifact_id": "attack_core_stability_20260425_105821",
        "phase": "pre_v2_attack_core",
        "path": "output/benchmark_analysis/attack_core_stability_20260425_105821.json",
        "description": "Attack-core stability snapshot for successor and predecessor arxiv cases.",
        "retrieval_mode": "none",
        "admission_mode": "none",
    },
    {
        "artifact_id": "prompt_family_batch_20260426_040501",
        "phase": "pre_v2_admission_prompt_families",
        "path": "output/benchmark_memory/prompt_family_batch/20260426_040501/batch_summary.json",
        "description": "Admission-aware prompt-family batch comparing direct and mem0_additive.",
        "retrieval_mode": "token",
        "admission_mode": "direct,mem0_additive",
    },
    {
        "artifact_id": "update_conflict_experiment",
        "phase": "pre_v2_update_conflict",
        "path": "output/benchmark_memory/update_conflict_experiment/update_conflict_summary.json",
        "description": "Benign default plus malicious update conflict experiment.",
        "retrieval_mode": "token",
        "admission_mode": "mem0_additive",
    },
    {
        "artifact_id": "same_payload_source_compare",
        "phase": "pre_v2_source_compare",
        "path": "output/benchmark_memory/same_payload_source_compare/same_payload_source_compare_summary.json",
        "description": "Same payload under local successor and synthetic helper source wrappers.",
        "retrieval_mode": "token",
        "admission_mode": "mem0_additive",
    },
    {
        "artifact_id": "tmc_mem0bench_v2_full_direct",
        "phase": "phase1_v2_runner_direct_smoke",
        "path": "output/benchmark_v2_runs/full_direct/summary.json",
        "description": "Full 60-case v2 direct-write runner result using deterministic follow-up evaluator.",
        "retrieval_mode": "token",
        "admission_mode": "direct",
    },
    {
        "artifact_id": "tmc_mem0bench_v2_mem0_additive_retail12",
        "phase": "phase1_v2_mem0_additive_retail_expansion",
        "path": "output/benchmark_v2_runs/stratified_mem0_additive_chord311_clean_v2filter/summary.json",
        "description": "12-case v2 Mem0-additive retail expansion across prompt families.",
        "retrieval_mode": "token",
        "admission_mode": "mem0_additive",
    },
    {
        "artifact_id": "tmc_mem0bench_v2_mem0_additive_cross_domain4",
        "phase": "phase1_v2_mem0_additive_cross_domain_smoke",
        "path": "output/benchmark_v2_runs/cross_domain_mem0_additive_chord311_clean_v2filter/summary.json",
        "description": "4-case v2 Mem0-additive smoke with one existing_prompt_style case from each realistic domain.",
        "retrieval_mode": "token",
        "admission_mode": "mem0_additive",
    },
    {
        "artifact_id": "phase0_mem0_additive_microscope",
        "phase": "phase0_admission_microscope",
        "path": "output/phase0/mem0_additive_full_chord311_clean/admission_microscope_summary.json",
        "description": "Phase 0 memory-form microscope using Mem0-style additive admission.",
        "retrieval_mode": "none",
        "admission_mode": "mem0_additive",
    },
]


def _run_git(args: List[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT_DIR, text=True).strip()
    except Exception:
        return ""


def _load_json(path: Path) -> Optional[object]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _get_nested(payload: object, keys: List[str], default: object = "") -> object:
    current = payload
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def _summarize_attack_core(payload: object) -> Dict[str, object]:
    case_summaries = _get_nested(payload, ["case_summaries"], {})
    if isinstance(case_summaries, list):
        case_summaries = {
            str(item.get("case_id", f"case_{index}")): item
            for index, item in enumerate(case_summaries)
            if isinstance(item, dict)
        }
    if not isinstance(case_summaries, dict):
        return {}
    summary: Dict[str, object] = {}
    for case_id, case_payload in case_summaries.items():
        if not isinstance(case_payload, dict):
            continue
        for metric in ("hijack_rate_mean", "harvest_rate_mean", "pollute_rate_mean"):
            value = case_payload.get(metric)
            if value is not None:
                summary[f"{case_id}.{metric}"] = value
    return summary


def _summarize_prompt_batch(payload: object) -> Dict[str, object]:
    rows = _get_nested(payload, ["rows"], [])
    if not isinstance(rows, list):
        rows = _get_nested(payload, ["experiments"], [])
    summary: Dict[str, object] = {"row_count": len(rows) if isinstance(rows, list) else 0}
    comparisons = _get_nested(payload, ["pairwise_comparisons"], [])
    if isinstance(comparisons, list):
        summary["pairwise_comparison_count"] = len(comparisons)
    return summary


def _summarize_update_conflict(payload: object) -> Dict[str, object]:
    relation = _get_nested(payload, ["relation_analysis", "relation"], "")
    metrics = _get_nested(payload, ["metrics", "mixed"], {})
    summary: Dict[str, object] = {"conflict_relation": relation}
    if isinstance(metrics, dict):
        for key in ("Behavior Drift Rate", "Tool Preference Shift", "Contaminated Hit Rate"):
            if key in metrics:
                summary[key] = metrics[key]
    return summary


def _summarize_source_compare(payload: object) -> Dict[str, object]:
    deltas = _get_nested(payload, ["pairwise_deltas", "metrics"], {})
    summary: Dict[str, object] = {}
    if isinstance(deltas, dict):
        for key, value in deltas.items():
            summary[f"delta.{key}"] = value
    return summary


def _summarize_v2_runner(payload: object) -> Dict[str, object]:
    result_summary = _get_nested(payload, ["result_summary"], {})
    if not isinstance(result_summary, dict):
        return {}
    metrics = result_summary.get("metric_means") or {}
    summary = {
        "case_count": result_summary.get("case_count", 0),
        "write_success_count": result_summary.get("write_success_count", 0),
        "retrieval_hit_count": result_summary.get("retrieval_hit_count", 0),
        "activation_count": result_summary.get("activation_count", 0),
    }
    if isinstance(metrics, dict):
        for key in (
            "Memory Write Success Rate",
            "Retrieval Hit Rate",
            "Contaminated Activation Rate",
            "Tool Preference Shift",
            "Workflow Order Drift",
        ):
            if key in metrics:
                summary[key] = metrics[key]
    return summary


def _summarize_phase0(payload: object) -> Dict[str, object]:
    if not isinstance(payload, dict):
        return {}
    by_form = payload.get("by_memory_form") or {}
    summary = {
        "case_count": payload.get("case_count", 0),
        "written_count": payload.get("written_count", 0),
        "failure_count": payload.get("failure_count", 0),
        "extraction_non_empty_count": payload.get("extraction_non_empty_count", 0),
        "admitted_attack_memory_count": payload.get("admitted_attack_memory_count", 0),
    }
    if isinstance(by_form, dict):
        noise = by_form.get("noise_like") or {}
        preference = by_form.get("preference_like") or {}
        summary["noise_like.write_success_rate"] = noise.get("write_success_rate", "")
        summary["preference_like.attack_rule_survival_rate_mean"] = preference.get(
            "attack_rule_survival_rate_mean", ""
        )
    return summary


def _extract_key_metrics(artifact_id: str, payload: object) -> Dict[str, object]:
    if artifact_id.startswith("attack_core"):
        return _summarize_attack_core(payload)
    if artifact_id.startswith("prompt_family_batch"):
        return _summarize_prompt_batch(payload)
    if artifact_id == "update_conflict_experiment":
        return _summarize_update_conflict(payload)
    if artifact_id == "same_payload_source_compare":
        return _summarize_source_compare(payload)
    if artifact_id.startswith("tmc_mem0bench_v2_"):
        return _summarize_v2_runner(payload)
    if artifact_id == "phase0_mem0_additive_microscope":
        return _summarize_phase0(payload)
    return {}


def _artifact_row(spec: Dict[str, str]) -> Dict[str, object]:
    path = ROOT_DIR / spec["path"]
    payload = _load_json(path)
    exists = path.exists()
    metrics = _extract_key_metrics(spec["artifact_id"], payload) if payload is not None else {}
    return {
        **spec,
        "exists": exists,
        "size_bytes": path.stat().st_size if exists and path.is_file() else 0,
        "last_write_time_utc": (
            datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
            if exists
            else ""
        ),
        "key_metrics": metrics,
    }


def _write_csv(rows: List[Dict[str, object]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "artifact_id",
        "phase",
        "path",
        "exists",
        "size_bytes",
        "last_write_time_utc",
        "admission_mode",
        "retrieval_mode",
        "description",
        "key_metrics_json",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **{key: row.get(key, "") for key in fieldnames},
                    "key_metrics_json": json.dumps(row.get("key_metrics", {}), ensure_ascii=False, sort_keys=True),
                }
            )


def _write_report(summary: Dict[str, object], rows: List[Dict[str, object]]) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Frozen Snapshot Report",
        "",
        f"Generated at UTC: `{summary['generated_at_utc']}`",
        f"Git commit: `{summary['git_commit'] or 'unknown'}`",
        "",
        "## Frozen Artifacts",
        "",
        "| Artifact | Exists | Admission | Retrieval | Key Metrics |",
        "|---|---:|---|---|---|",
    ]
    for row in rows:
        metrics = json.dumps(row.get("key_metrics", {}), ensure_ascii=False, sort_keys=True)
        lines.append(
            f"| `{row['artifact_id']}` | {row['exists']} | `{row['admission_mode']}` | "
            f"`{row['retrieval_mode']}` | `{metrics}` |"
        )
    lines.extend(
        [
            "",
            "## Current Interpretation",
            "",
            "- Attack-core contamination is already supported by the frozen successor/predecessor stability artifact.",
            "- Direct memory write remains the clean upper bound for memory contamination.",
            "- Existing Mem0-style admission results show rewrite/preservation behavior rather than a pure block decision.",
            "- The v2 runner now has a full 60-case direct-write offline smoke result.",
            "- Small v2 Mem0-additive runs now show write, retrieval, and activation over realistic-domain payloads.",
            "",
            "## Boundary",
            "",
            "- The v2 direct result uses deterministic follow-up evaluation and token retrieval.",
            "- Full 60-case `mem0_additive` v2 and Mem0-native retrieval are not frozen yet.",
            "- Source-aware trust/admission scoring is not implemented in the frozen snapshot.",
        ]
    )
    (DOCS_DIR / "frozen_snapshot_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_limitations(summary: Dict[str, object]) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    content = f"""# Current Limitations

Generated at UTC: `{summary['generated_at_utc']}`

## Retrieval

- Several frozen admission-aware runs use token retrieval in practice.
- Mem0-native retrieval is not yet integrated as a first-class runner mode.
- Embedding retrieval depends on local `sentence-transformers` availability and should be reported separately from requested retrieval mode.

## Admission

- `direct` is an upper-bound memory-write setting, not a realistic selective admission setting.
- `mem0_additive` depends on the local `mem0-main` prompt implementation and model calls.
- Source-aware admission/trust scoring is not implemented yet.

## Evaluation

- The current v2 direct run uses a deterministic local follow-up evaluator.
- The current v2 Mem0-additive frozen runs are small smoke/expansion runs, not yet a full 60-case result.
- Closed-loop agent execution over real domain tools is not yet part of the v2 frozen result.
- Some v2 clean-vs-preferred route comparisons are inferred from payload text until the schema exposes explicit route fields.

## Benchmark Coverage

- TMC-Mem0Bench v2 seed contains 60 cases across retail, airline, workspace, and travel.
- ChordTools v1 has not yet been merged into the v2 runner schema.
- Same-payload/different-source has not yet been rerun over the v2 realistic-domain payloads.
"""
    (DOCS_DIR / "current_limitations.md").write_text(content, encoding="utf-8")


def main() -> None:
    generated_at = datetime.now(timezone.utc).isoformat()
    rows = [_artifact_row(spec) for spec in FROZEN_ARTIFACTS]
    summary = {
        "generated_at_utc": generated_at,
        "git_commit": _run_git(["rev-parse", "HEAD"]),
        "git_status_short": _run_git(["status", "--short"]).splitlines(),
        "artifact_count": len(rows),
        "existing_artifact_count": sum(1 for row in rows if row["exists"]),
        "artifacts": rows,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "frozen_result_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_csv(rows, OUTPUT_DIR / "frozen_result_index.csv")
    _write_report(summary, rows)
    _write_limitations(summary)

    print(
        json.dumps(
            {
                "generated_at_utc": generated_at,
                "artifact_count": summary["artifact_count"],
                "existing_artifact_count": summary["existing_artifact_count"],
                "outputs": [
                    "output/frozen_result_summary.json",
                    "output/frozen_result_index.csv",
                    "docs/frozen_snapshot_report.md",
                    "docs/current_limitations.md",
                ],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
