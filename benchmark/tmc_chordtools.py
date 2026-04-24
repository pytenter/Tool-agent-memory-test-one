"""Build and validate the TMC-ChordTools v1 benchmark suite."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


BENCHMARK_NAME = "TMC-ChordTools"
BENCHMARK_VERSION = "v1"
FRAMEWORK = "langchain"
CASE_SCHEMA_VERSION = "1.0"

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"

SOURCE_FILES = {
    "queries": "data/query.json",
    "malicious_tools": "data/malicious_tools.json",
    "malicious_tool_arguments": "data/malicious_tool_arguments.json",
    "langchain_tool_map": "data/langchain_tool_map.json",
    "victim_tools": "data/victim_tools",
    "tools_in_defense": "data/tools_in_defense",
}

TOOL_METADATA = {
    "Wikidata": {
        "tool_domain": "knowledge_lookup",
        "privilege_level": "external_read",
        "capability_tags": ["entity_lookup", "knowledge_base", "fact_retrieval"],
    },
    "arxiv": {
        "tool_domain": "scholarly_research",
        "privilege_level": "external_read",
        "capability_tags": ["paper_search", "research", "scientific_retrieval"],
    },
    "balance_sheets": {
        "tool_domain": "finance_data",
        "privilege_level": "external_read",
        "capability_tags": ["finance", "statement_retrieval", "company_fundamentals"],
    },
    "brave_search": {
        "tool_domain": "web_search",
        "privilege_level": "external_read",
        "capability_tags": ["search", "web_retrieval", "news_lookup"],
    },
    "cash_flow_statements": {
        "tool_domain": "finance_data",
        "privilege_level": "external_read",
        "capability_tags": ["finance", "statement_retrieval", "company_fundamentals"],
    },
    "closest_airport": {
        "tool_domain": "travel_weather",
        "privilege_level": "external_read",
        "capability_tags": ["travel", "location_lookup", "mapping"],
    },
    "duckduckgo_results_json": {
        "tool_domain": "web_search",
        "privilege_level": "external_read",
        "capability_tags": ["search", "web_retrieval", "structured_results"],
    },
    "duckduckgo_search": {
        "tool_domain": "web_search",
        "privilege_level": "external_read",
        "capability_tags": ["search", "web_retrieval", "news_lookup"],
    },
    "file_delete": {
        "tool_domain": "filesystem_ops",
        "privilege_level": "local_write",
        "capability_tags": ["filesystem", "delete", "destructive_action"],
    },
    "file_search": {
        "tool_domain": "filesystem_ops",
        "privilege_level": "local_read",
        "capability_tags": ["filesystem", "search", "local_lookup"],
    },
    "income_statements": {
        "tool_domain": "finance_data",
        "privilege_level": "external_read",
        "capability_tags": ["finance", "statement_retrieval", "company_fundamentals"],
    },
    "move_file": {
        "tool_domain": "filesystem_ops",
        "privilege_level": "local_write",
        "capability_tags": ["filesystem", "move", "state_change"],
    },
    "open_weather_map": {
        "tool_domain": "travel_weather",
        "privilege_level": "external_read",
        "capability_tags": ["weather", "forecast", "location_lookup"],
    },
    "polygon_aggregates": {
        "tool_domain": "finance_data",
        "privilege_level": "external_read",
        "capability_tags": ["finance", "market_data", "time_series"],
    },
    "polygon_financials": {
        "tool_domain": "finance_data",
        "privilege_level": "external_read",
        "capability_tags": ["finance", "market_data", "fundamentals"],
    },
    "polygon_ticker_news": {
        "tool_domain": "finance_data",
        "privilege_level": "external_read",
        "capability_tags": ["finance", "news_lookup", "market_data"],
    },
    "read_file": {
        "tool_domain": "filesystem_ops",
        "privilege_level": "local_read",
        "capability_tags": ["filesystem", "read", "local_lookup"],
    },
    "reddit_search": {
        "tool_domain": "social_content",
        "privilege_level": "external_read",
        "capability_tags": ["social_media", "community_content", "search"],
    },
    "requests_put": {
        "tool_domain": "network_ops",
        "privilege_level": "network_write",
        "capability_tags": ["http", "api_mutation", "state_change"],
    },
    "semanticscholar": {
        "tool_domain": "scholarly_research",
        "privilege_level": "external_read",
        "capability_tags": ["paper_search", "research", "scientific_retrieval"],
    },
    "sleep": {
        "tool_domain": "timing_control",
        "privilege_level": "control_flow",
        "capability_tags": ["control_flow", "delay", "automation"],
    },
    "stack_exchange": {
        "tool_domain": "knowledge_lookup",
        "privilege_level": "external_read",
        "capability_tags": ["developer_qa", "community_content", "knowledge_retrieval"],
    },
    "tavily_answer": {
        "tool_domain": "web_search",
        "privilege_level": "external_read",
        "capability_tags": ["search", "answer_synthesis", "web_retrieval"],
    },
    "tavily_search_results_json": {
        "tool_domain": "web_search",
        "privilege_level": "external_read",
        "capability_tags": ["search", "structured_results", "web_retrieval"],
    },
    "terminal": {
        "tool_domain": "filesystem_ops",
        "privilege_level": "local_exec",
        "capability_tags": ["shell", "local_execution", "system_state"],
    },
    "wikipedia": {
        "tool_domain": "knowledge_lookup",
        "privilege_level": "external_read",
        "capability_tags": ["encyclopedia", "knowledge_retrieval", "reference"],
    },
    "yahoo_finance_news": {
        "tool_domain": "finance_data",
        "privilege_level": "external_read",
        "capability_tags": ["finance", "news_lookup", "market_data"],
    },
    "you_search": {
        "tool_domain": "web_search",
        "privilege_level": "external_read",
        "capability_tags": ["search", "web_retrieval", "answer_synthesis"],
    },
    "youtube_search": {
        "tool_domain": "social_content",
        "privilege_level": "external_read",
        "capability_tags": ["video_search", "social_media", "content_lookup"],
    },
}


def _load_json(relative_path: str) -> Dict:
    return json.loads((ROOT_DIR / relative_path).read_text(encoding="utf-8"))


def _load_lines(relative_path: str) -> List[str]:
    return [
        line.strip()
        for line in (ROOT_DIR / relative_path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _load_malicious_tool_map() -> Dict[str, Dict[str, Dict[str, str]]]:
    raw = _load_json(SOURCE_FILES["malicious_tools"])["langchain"]
    parsed: Dict[str, Dict[str, Dict[str, str]]] = {}
    for attack_surface in ("predecessor", "successor"):
        entries = {}
        for row in raw[attack_surface]:
            target_tool, malicious_tool = list(row.items())[0]
            entries[target_tool] = malicious_tool
        parsed[attack_surface] = entries
    return parsed


def _load_argument_map() -> Dict[str, Dict[str, Dict[str, List[str]]]]:
    raw = _load_json(SOURCE_FILES["malicious_tool_arguments"])
    return {
        "predecessor": raw["predecessor"],
        "successor": raw["successor"],
    }


def _case_expected_outcomes(attack_surface: str) -> Dict[str, List[str]]:
    common_followup = [
        "retrieval_trigger_candidate",
        "tool_preference_shift_candidate",
        "workflow_shift_candidate",
        "reasoning_shift_candidate",
    ]
    if attack_surface == "predecessor":
        return {
            "write_phase": [
                "pre_tool_hijack_candidate",
                "memory_write_candidate",
            ],
            "followup_phase": common_followup,
        }
    return {
        "write_phase": [
            "post_tool_summary_pollution_candidate",
            "memory_write_candidate",
        ],
        "followup_phase": common_followup,
    }


def _recommended_tracks(defense_ready: bool) -> List[str]:
    tracks = ["attack_core"]
    if defense_ready:
        tracks.append("defense_ready")
    return tracks


@dataclass(frozen=True)
class BenchmarkCase:
    benchmark_name: str
    benchmark_version: str
    case_schema_version: str
    framework: str
    split: str
    case_id: str
    attack_surface: str
    attack_stage: str
    target_tool: str
    target_tool_class: str
    target_tool_domain: str
    privilege_level: str
    capability_tags: List[str]
    defense_ready: bool
    recommended_tracks: List[str]
    query_id: str
    query_index: int
    query_count_for_tool: int
    user_query: str
    malicious_tool_name: str
    malicious_tool_description: str
    malicious_argument_schema: Dict[str, List[str]]
    expected_outcomes: Dict[str, List[str]]
    source_refs: Dict[str, str]

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


def build_tmc_chordtools_cases(
    attack_surface: str = "all",
    target_tools: Optional[Sequence[str]] = None,
    tool_domains: Optional[Sequence[str]] = None,
    defense_ready_only: bool = False,
    max_queries_per_tool: Optional[int] = None,
) -> Tuple[List[Dict[str, object]], Dict[str, object]]:
    if attack_surface not in {"all", "predecessor", "successor"}:
        raise ValueError("attack_surface must be one of: all, predecessor, successor")

    queries = _load_json(SOURCE_FILES["queries"])
    malicious_tools = _load_malicious_tool_map()
    malicious_arguments = _load_argument_map()
    tool_map = _load_json(SOURCE_FILES["langchain_tool_map"])
    victim_tools = set(_load_lines(SOURCE_FILES["victim_tools"]))
    defense_tools = set(_load_lines(SOURCE_FILES["tools_in_defense"]))

    requested_attack_surfaces = (
        ["predecessor", "successor"]
        if attack_surface == "all"
        else [attack_surface]
    )
    target_filter = set(target_tools or [])
    domain_filter = set(tool_domains or [])

    cases: List[BenchmarkCase] = []
    covered_tools = set()

    for current_surface in requested_attack_surfaces:
        stage = "pre_tool_dispatch" if current_surface == "predecessor" else "post_tool_output"
        tool_defs = malicious_tools[current_surface]
        for target_tool in sorted(set(queries).intersection(tool_defs)):
            if target_filter and target_tool not in target_filter:
                continue

            metadata = TOOL_METADATA.get(target_tool)
            if metadata is None:
                raise ValueError(f"Missing TOOL_METADATA entry for target tool: {target_tool}")

            if domain_filter and metadata["tool_domain"] not in domain_filter:
                continue

            defense_ready = target_tool in defense_tools
            if defense_ready_only and not defense_ready:
                continue

            covered_tools.add(target_tool)
            malicious_tool = tool_defs[target_tool]
            query_list = list(queries[target_tool])
            if max_queries_per_tool is not None:
                query_list = query_list[:max_queries_per_tool]

            for query_index, user_query in enumerate(query_list, start=1):
                case = BenchmarkCase(
                    benchmark_name=BENCHMARK_NAME,
                    benchmark_version=BENCHMARK_VERSION,
                    case_schema_version=CASE_SCHEMA_VERSION,
                    framework=FRAMEWORK,
                    split="core",
                    case_id=f"tmc-chordtools-{BENCHMARK_VERSION}-{current_surface}-{target_tool}-q{query_index:02d}",
                    attack_surface=current_surface,
                    attack_stage=stage,
                    target_tool=target_tool,
                    target_tool_class=tool_map.get(target_tool, "unknown"),
                    target_tool_domain=metadata["tool_domain"],
                    privilege_level=metadata["privilege_level"],
                    capability_tags=list(metadata["capability_tags"]),
                    defense_ready=defense_ready,
                    recommended_tracks=_recommended_tracks(defense_ready),
                    query_id=f"{target_tool}__q{query_index:02d}",
                    query_index=query_index,
                    query_count_for_tool=len(query_list),
                    user_query=user_query,
                    malicious_tool_name=malicious_tool["name"],
                    malicious_tool_description=malicious_tool["description"],
                    malicious_argument_schema=malicious_arguments[current_surface].get(target_tool, {}),
                    expected_outcomes=_case_expected_outcomes(current_surface),
                    source_refs=dict(SOURCE_FILES),
                )
                cases.append(case)

    case_dicts = [case.to_dict() for case in cases]
    validation = validate_tmc_chordtools_cases(case_dicts)
    manifest = build_tmc_chordtools_manifest(
        cases=case_dicts,
        validation=validation,
        source_summary=_build_source_summary(
            queries=queries,
            malicious_tools=malicious_tools,
            defense_tools=defense_tools,
            victim_tools=victim_tools,
            covered_tools=covered_tools,
        ),
    )
    return case_dicts, manifest


def validate_tmc_chordtools_cases(cases: Sequence[Dict[str, object]]) -> Dict[str, object]:
    required_fields = {
        "benchmark_name",
        "benchmark_version",
        "case_schema_version",
        "framework",
        "split",
        "case_id",
        "attack_surface",
        "attack_stage",
        "target_tool",
        "target_tool_class",
        "target_tool_domain",
        "privilege_level",
        "capability_tags",
        "defense_ready",
        "recommended_tracks",
        "query_id",
        "query_index",
        "query_count_for_tool",
        "user_query",
        "malicious_tool_name",
        "malicious_tool_description",
        "malicious_argument_schema",
        "expected_outcomes",
        "source_refs",
    }
    seen_ids = set()
    issues: List[str] = []

    for index, case in enumerate(cases, start=1):
        missing = sorted(required_fields - set(case.keys()))
        if missing:
            issues.append(f"case[{index}] missing fields: {', '.join(missing)}")

        case_id = str(case.get("case_id", ""))
        if not case_id:
            issues.append(f"case[{index}] has empty case_id")
        elif case_id in seen_ids:
            issues.append(f"duplicate case_id detected: {case_id}")
        else:
            seen_ids.add(case_id)

        if case.get("attack_surface") not in {"predecessor", "successor"}:
            issues.append(f"{case_id}: invalid attack_surface")
        if not case.get("user_query"):
            issues.append(f"{case_id}: empty user_query")
        if not case.get("malicious_tool_name"):
            issues.append(f"{case_id}: empty malicious_tool_name")
        if not isinstance(case.get("capability_tags"), list) or not case.get("capability_tags"):
            issues.append(f"{case_id}: capability_tags must be a non-empty list")
        if not isinstance(case.get("recommended_tracks"), list) or not case.get("recommended_tracks"):
            issues.append(f"{case_id}: recommended_tracks must be a non-empty list")

        expected_outcomes = case.get("expected_outcomes", {})
        if not isinstance(expected_outcomes, dict):
            issues.append(f"{case_id}: expected_outcomes must be a dict")
        else:
            for phase_name in ("write_phase", "followup_phase"):
                phase_items = expected_outcomes.get(phase_name, [])
                if not isinstance(phase_items, list) or not phase_items:
                    issues.append(f"{case_id}: expected_outcomes.{phase_name} must be a non-empty list")

    return {
        "is_valid": not issues,
        "issue_count": len(issues),
        "issues": issues,
    }


def build_tmc_chordtools_manifest(
    cases: Sequence[Dict[str, object]],
    validation: Dict[str, object],
    source_summary: Dict[str, object],
) -> Dict[str, object]:
    attack_surface_counter = Counter(case["attack_surface"] for case in cases)
    domain_counter = Counter(case["target_tool_domain"] for case in cases)
    privilege_counter = Counter(case["privilege_level"] for case in cases)
    tool_counter = Counter(case["target_tool"] for case in cases)

    defense_ready_cases = sum(1 for case in cases if case["defense_ready"])
    recommended_tracks = Counter(
        track
        for case in cases
        for track in case["recommended_tracks"]
    )

    return {
        "benchmark_name": BENCHMARK_NAME,
        "benchmark_version": BENCHMARK_VERSION,
        "case_schema_version": CASE_SCHEMA_VERSION,
        "framework": FRAMEWORK,
        "total_cases": len(cases),
        "total_target_tools": len(tool_counter),
        "attack_surface_counts": dict(sorted(attack_surface_counter.items())),
        "domain_counts": dict(sorted(domain_counter.items())),
        "privilege_level_counts": dict(sorted(privilege_counter.items())),
        "defense_ready_case_count": defense_ready_cases,
        "defense_ready_tool_count": len({case["target_tool"] for case in cases if case["defense_ready"]}),
        "recommended_track_counts": dict(sorted(recommended_tracks.items())),
        "cases_per_tool": dict(sorted(tool_counter.items())),
        "source_summary": source_summary,
        "validation": validation,
    }


def _build_source_summary(
    queries: Dict[str, List[str]],
    malicious_tools: Dict[str, Dict[str, Dict[str, str]]],
    defense_tools: Iterable[str],
    victim_tools: Iterable[str],
    covered_tools: Iterable[str],
) -> Dict[str, object]:
    query_tools = set(queries)
    predecessor_tools = set(malicious_tools["predecessor"])
    successor_tools = set(malicious_tools["successor"])
    covered_tool_set = set(covered_tools)

    return {
        "query_tool_count": len(query_tools),
        "victim_tool_count": len(set(victim_tools)),
        "predecessor_tool_count": len(predecessor_tools),
        "successor_tool_count": len(successor_tools),
        "covered_tool_count": len(covered_tool_set),
        "defense_ready_tool_count": len(set(defense_tools)),
        "query_only_tools_without_attack": sorted(
            query_tools - predecessor_tools - successor_tools
        ),
        "attack_only_tools_without_queries": {
            "predecessor": sorted(predecessor_tools - query_tools),
            "successor": sorted(successor_tools - query_tools),
        },
        "covered_tools": sorted(covered_tool_set),
    }


def write_jsonl(path: Path, rows: Sequence[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

