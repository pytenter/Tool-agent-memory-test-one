# Current Limitations

Generated at UTC: `2026-04-27T08:14:27.816944+00:00`

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
- The current v2 Mem0-additive full run uses deterministic local follow-up evaluation and token retrieval.
- Closed-loop agent execution over real domain tools is not yet part of the v2 frozen result.
- Some v2 clean-vs-preferred route comparisons are inferred from payload text until the schema exposes explicit route fields.

## Benchmark Coverage

- TMC-Mem0Bench v2 seed contains 60 cases across retail, airline, workspace, and travel.
- ChordTools v1 has not yet been merged into the v2 runner schema.
- Same-payload/different-source has not yet been rerun over the v2 realistic-domain payloads.
