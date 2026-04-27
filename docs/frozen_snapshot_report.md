# Frozen Snapshot Report

Generated at UTC: `2026-04-27T06:42:33.195722+00:00`
Git commit: `e65975db4ab65a8cf5a0aade490db2c7d5fb4ca9`

## Frozen Artifacts

| Artifact | Exists | Admission | Retrieval | Key Metrics |
|---|---:|---|---|---|
| `attack_core_stability_20260425_105821` | True | `none` | `none` | `{"tmc-chordtools-v1-predecessor-arxiv-q01.harvest_rate_mean": 1.0, "tmc-chordtools-v1-predecessor-arxiv-q01.hijack_rate_mean": 0.1429, "tmc-chordtools-v1-predecessor-arxiv-q01.pollute_rate_mean": 0.0, "tmc-chordtools-v1-successor-arxiv-q01.harvest_rate_mean": 0.5, "tmc-chordtools-v1-successor-arxiv-q01.hijack_rate_mean": 1.0, "tmc-chordtools-v1-successor-arxiv-q01.pollute_rate_mean": 1.0}` |
| `prompt_family_batch_20260426_040501` | True | `direct,mem0_additive` | `token` | `{"pairwise_comparison_count": 8, "row_count": 0}` |
| `update_conflict_experiment` | True | `mem0_additive` | `token` | `{"conflict_relation": "coexist"}` |
| `same_payload_source_compare` | True | `mem0_additive` | `token` | `{"delta.contaminated_only": {"Behavior Drift Rate": 0.0, "Contaminated Activation Rate": 0.0, "Contaminated Hit Rate": 0.0, "Tool Preference Shift": 0.0}, "delta.defense_mixed": {"Behavior Drift Rate": 0.0, "Contaminated Activation Rate": 0.0, "Contaminated Hit Rate": 0.0, "Tool Preference Shift": 0.0}, "delta.mixed": {"Behavior Drift Rate": 0.0, "Contaminated Activation Rate": 0.0, "Contaminated Hit Rate": 0.0, "Tool Preference Shift": 0.0}}` |
| `tmc_mem0bench_v2_full_direct` | True | `direct` | `token` | `{"Contaminated Activation Rate": 1.0, "Memory Write Success Rate": 1.0, "Retrieval Hit Rate": 1.0, "Tool Preference Shift": 0.8, "Workflow Order Drift": 0.8, "activation_count": 60, "case_count": 60, "retrieval_hit_count": 60, "write_success_count": 60}` |

## Current Interpretation

- Attack-core contamination is already supported by the frozen successor/predecessor stability artifact.
- Direct memory write remains the clean upper bound for memory contamination.
- Existing Mem0-style admission results show rewrite/preservation behavior rather than a pure block decision.
- The v2 runner now has a full 60-case direct-write offline smoke result.

## Boundary

- The v2 direct result uses deterministic follow-up evaluation and token retrieval.
- Full `mem0_additive` v2 runs and Mem0-native retrieval are not frozen yet.
- Source-aware trust/admission scoring is not implemented in the frozen snapshot.
