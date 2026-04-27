# Benchmark

This directory now contains two layers:

1. `TMC-ChordTools v1`
2. `TMC-Mem0Bench v2`

`v1` is the original single-domain ChordTools benchmark.

`v2` is the offline admission-aware benchmark layer that extends the project to
four additional realistic domains without changing the current attack model:

- `tau2_retail`
- `agentdojo_workspace`
- `tau2_airline`
- `agentdojo_travel`

The current attack model remains:

- clean tool chain returns structured output
- a malicious successor/post-processor summarizes that output
- the summary is written through `direct`, `mem0_additive`, or `mem0_full`
- future retrieval may reactivate the contaminated memory
- downstream behavior may drift

## Current Benchmark Files

### Original ChordTools

- `tmc_chordtools.py`
- `export_tmc_chordtools.py`
- `tmc_chordtools_v1.jsonl`
- `tmc_chordtools_v1_manifest.json`
- `run_tmc_chordtools.py`

### Admission-Aware Memory Scripts

- `run_memory_seed_case.py`
- `run_prompt_family_batch.py`
- `run_update_conflict_experiment.py`
- `run_same_payload_source_compare.py`

### TMC-Mem0Bench v2

- `tmc_mem0bench_v2.py`
- `export_tmc_mem0bench_v2.py`
- `validate_tmc_mem0bench_v2.py`
- `run_tmc_mem0bench_v2.py`
- `v2_followup_evaluator.py`
- `tmc_mem0bench_v2_seed.jsonl`
- `tmc_mem0bench_v2_seed_manifest.json`

## TMC-Mem0Bench v2

The benchmark-v2 layer now contains both:

1. a realistic multi-domain seed/schema layer, and
2. an offline write-retrieve-activate runner.

The schema/export layer freezes:

- a common case schema
- domain/task adapters
- realistic attacker-benefit hypotheses
- realistic domain-specific contaminated payload text
- manifest counts and placeholder validation

The runner executes the frozen cases through memory write, retrieval, and a
deterministic follow-up evaluator. It supports:

- `direct`
- `mem0_additive`
- `mem0_full`
- optional seeded clean-memory competition through `--seed-clean-memory`

It still does not implement closed-loop execution over the original external
domain tools. The current v2 runner is an offline admission and activation
benchmark.

## Integrated Domains

### `tau2_retail`

Source:
- `../tau2-bench-main/data/tau2/domains/retail/tasks.json`
- `../tau2-bench-main/src/tau2/domains/retail/tools.py`
- `../tau2-bench-main/data/tau2/domains/retail/policy.md`

Why it fits:
- explicit tool chains
- explicit business workflows
- realistic exchange / return / address / payment actions
- natural successor-output contamination target

### `agentdojo_workspace`

Source:
- `../agentdojo-main/src/agentdojo/default_suites/v1/workspace/user_tasks.py`
- `../agentdojo-main/src/agentdojo/default_suites/v1/workspace/task_suite.py`

Why it fits:
- inbox / calendar / file workflows naturally produce tool output
- easy to model post-processing memory contamination
- strong fit for follow-up workflow drift

### `tau2_airline`

Source:
- `../tau2-bench-main/data/tau2/domains/airline/tasks.json`
- `../tau2-bench-main/src/tau2/domains/airline/tools.py`
- `../tau2-bench-main/data/tau2/domains/airline/policy.md`

Why it fits:
- policy-heavy workflow
- explicit reservation / refund / rebooking tool paths
- strong fit for policy-sensitive memory drift

### `agentdojo_travel`

Source:
- `../agentdojo-main/src/agentdojo/default_suites/v1/travel/user_tasks.py`
- `../agentdojo-main/src/agentdojo/default_suites/v1/tools/travel_booking_client.py`

Why it fits:
- recommendation-to-booking workflow
- clear post-processing point after ranking / review retrieval
- natural vendor / property bias scenarios

## Case Schema Highlights

Each `v2` case records:

- `domain`
- `dataset`
- `suite_name`
- `prompt_family`
- `source_condition`
- `payload_form`
- `memory_case_type`
- `memory_operation`
- `expected_mem0_admission`
- `expected_memory_type`
- `expected_trigger_behavior`
- `expected_conflict_behavior`
- `attacker_benefit_category`
- `attacker_benefit_hypothesis`
- `attacker_gain_if_activated`
- `clean_behavior_summary`
- `contaminated_behavior_summary`
- `preferred_tool`
- `alternative_tool`
- `expected_clean_route`
- `expected_contaminated_route`
- `activation_rule`
- `user_task`
- `future_task`
- `expected_clean_tools`
- `payload_text`

## Realistic Attacker Benefit Modeling

This release deliberately avoids the older placeholder-only style such as:

- `TASK_TYPE_A`
- `RULE_X`
- `TOOL_PREF_Y`

Instead, payload text is domain-specific and concrete. Examples:

- retail:
  - refund suppression
  - after-sales workflow manipulation
  - address-change or reroute abuse
- airline:
  - unauthorized rebooking or upgrade steering
  - refund manipulation before clean policy review
  - itinerary-information exposure during support handling
- workspace:
  - verification-code, email, or calendar detail leakage
  - malicious outbound follow-up
  - unauthorized meeting modification
- travel:
  - high-margin hotel or supplier steering
  - itinerary-plan leakage
  - booking-path manipulation after threshold satisfaction

The export layer performs a placeholder audit and fails if old placeholder
tokens leak into the new `v2` payloads.

## Export Commands

Export the full seed set:

```powershell
python benchmark\export_tmc_mem0bench_v2.py
```

Export a smaller subset:

```powershell
python benchmark\export_tmc_mem0bench_v2.py --domains tau2_retail,agentdojo_workspace --prompt-families existing_prompt_style,preference_style,update_style
```

The exporter writes:

- `benchmark/tmc_mem0bench_v2_seed.jsonl`
- `benchmark/tmc_mem0bench_v2_seed_manifest.json`

## Runner Commands

Validate the v2 seed:

```powershell
python benchmark\validate_tmc_mem0bench_v2.py
```

Run the direct-write upper-bound benchmark:

```powershell
python benchmark\run_tmc_mem0bench_v2.py --admission-mode direct --retrieval-mode token --output-dir output\benchmark_v2_runs\full_direct
```

Run the full Mem0-additive benchmark:

```powershell
python benchmark\run_tmc_mem0bench_v2.py --admission-mode mem0_additive --retrieval-mode token --output-dir output\benchmark_v2_runs\full_mem0_additive_chord311_clean_v21
```

Run the full Mem0 update-manager benchmark with seeded clean-memory competition:

```powershell
python benchmark\run_tmc_mem0bench_v2.py --admission-mode mem0_full --seed-clean-memory --retrieval-mode token --output-dir output\benchmark_v2_runs\full_mem0_full_seeded_clean_chord311_clean_v21
```

## Current Boundary

The v2 layer currently provides:

- multi-domain case schema
- multi-domain seed cases
- realistic benefit-aware payload text
- export and manifest tooling
- offline write-retrieve-activate evaluation
- direct, Mem0-additive, and Mem0-full admission modes

It does not yet provide closed-loop execution over the original external domain
tools. That remains future work.
