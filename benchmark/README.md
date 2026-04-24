# TMC-ChordTools v1 Benchmark

这个目录把 `Chord-main` 里原本分散在 `data/` 和 `evaluation/` 的资源，整理成一个正式可验证的 benchmark 套件。

当前目标不是覆盖所有论文阶段，而是先把 `TMC-ChordTools v1` 做扎实：  
把 target tool、查询、恶意 predecessor/successor、参数语义和 defense-ready 子集固化成稳定的 case 文件。

## 设计原则

- 只收录已经同时具备 `query.json` 查询样本和 `malicious_tools.json` 攻击定义的工具。
- predecessor 和 successor 是两个独立 attack surface，同一个 target tool 在两种 surface 下会生成不同 case。
- 每条 case 只描述“实验对象与预期可观察现象”，不提前假定攻击一定成功。
- benchmark 本身不绑定某一个单独脚本；后续真实链、消融、参数扫描都应复用这一层 case 定义。

## Case Schema

每条 JSONL case 都至少包含这些字段：

- `case_id`: 稳定唯一标识，格式为 `tmc-chordtools-v1-{surface}-{tool}-qXX`
- `attack_surface`: `predecessor` 或 `successor`
- `attack_stage`: `pre_tool_dispatch` 或 `post_tool_output`
- `target_tool` / `target_tool_class`
- `target_tool_domain`: 如 `web_search`、`finance_data`、`filesystem_ops`
- `privilege_level`: 如 `external_read`、`local_write`、`network_write`
- `capability_tags`: 工具能力标签
- `defense_ready`: 该工具是否已经进入 `tools_in_defense`
- `recommended_tracks`: 当前建议实验轨道，默认至少含 `attack_core`
- `query_id` / `query_index` / `user_query`
- `malicious_tool_name` / `malicious_tool_description`
- `malicious_argument_schema`: 恶意工具参数语义
- `expected_outcomes.write_phase`
- `expected_outcomes.followup_phase`
- `source_refs`: 所有原始数据文件来源

## 默认覆盖范围

`v1` 默认从这些原始文件生成：

- [data/query.json](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/data/query.json)
- [data/malicious_tools.json](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/data/malicious_tools.json)
- [data/malicious_tool_arguments.json](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/data/malicious_tool_arguments.json)
- [data/langchain_tool_map.json](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/data/langchain_tool_map.json)
- [data/victim_tools](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/data/victim_tools)
- [data/tools_in_defense](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/data/tools_in_defense)

默认完整集会输出：

- `benchmark/tmc_chordtools_v1.jsonl`
- `benchmark/tmc_chordtools_v1_manifest.json`

当前还提供一个人工精选的在线 smoke 子集：

- [`benchmark/tmc_chordtools_online_smoke_v1.jsonl`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/benchmark/tmc_chordtools_online_smoke_v1.jsonl)
- [`benchmark/tmc_chordtools_online_smoke_v1_manifest.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/benchmark/tmc_chordtools_online_smoke_v1_manifest.json)

以及根据首轮 smoke run 结果收敛出的 `v2 shortlist`：

- [`benchmark/tmc_chordtools_smoke_v2_shortlist.jsonl`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/benchmark/tmc_chordtools_smoke_v2_shortlist.jsonl)
- [`benchmark/tmc_chordtools_smoke_v2_shortlist_manifest.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/benchmark/tmc_chordtools_smoke_v2_shortlist_manifest.json)

## 生成命令

在 `Chord-main` 根目录执行：

```powershell
python benchmark\export_tmc_chordtools.py
```

只导出 defense-ready 子集：

```powershell
python benchmark\export_tmc_chordtools.py --defense-ready-only --output-jsonl benchmark\tmc_chordtools_v1_defense.jsonl --output-manifest benchmark\tmc_chordtools_v1_defense_manifest.json
```

只导出 successor 攻击面，并把每个工具缩减成 2 条 query 作为 smoke set：

```powershell
python benchmark\export_tmc_chordtools.py --attack-surface successor --max-queries-per-tool 2 --output-jsonl benchmark\tmc_chordtools_smoke_successor.jsonl --output-manifest benchmark\tmc_chordtools_smoke_successor_manifest.json
```

导出人工精选 smoke 子集：

```powershell
python benchmark\export_curated_subset.py --subset tmc_chordtools_online_smoke_v1
```

导出 v2 shortlist：

```powershell
python benchmark\export_curated_subset.py --subset tmc_chordtools_smoke_v2_shortlist
```

## 当前用途

这套 benchmark 现在优先服务 4 件事：

- 固定 `TMC-ChordTools v1` 的 case 边界
- 为后续真实链 runner 提供统一输入
- 为消融实验提供稳定 case id
- 为参数扫描和 defense 评测提供可过滤子集

## Attack-Core Runner

现在已经提供一个正式 runner：

- [`benchmark/run_tmc_chordtools.py`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/benchmark/run_tmc_chordtools.py)

它会：

- 读取 `tmc_chordtools_v1.jsonl`
- 按需加载 target tool，而不是一次性把所有工具全实例化
- 逐 case 调用现有 `Agent`
- 为每个 case 生成独立日志目录
- 把结构化结果写入统一的 `results.jsonl`
- 生成一份 run-level `summary.json`

推荐先做 dry-run：

```powershell
python benchmark\run_tmc_chordtools.py --dry-run --max-cases 5
```

如果你想先只验证 Python 依赖导入，不触发任何联网初始化：

```powershell
python benchmark\run_tmc_chordtools.py --dry-run --validate-imports --max-cases 5
```

如果你想连工具实例化和活体联网检查也一起做，再加：

```powershell
python benchmark\run_tmc_chordtools.py --dry-run --validate-tools --max-cases 5
```

解释：

- `--validate-imports`: 检查包和模块是否可导入
- `--validate-tools`: 真正实例化工具，某些工具会在这一步访问外部服务或公共站点

只跑 successor 的 smoke set：

```powershell
python benchmark\run_tmc_chordtools.py --attack-surface successor --max-cases 3
```

只跑 defense-ready 子集中的 `wikipedia`：

```powershell
python benchmark\run_tmc_chordtools.py --defense-ready-only --target-tools wikipedia --max-cases 2
```

runner 默认输出到：

- `output/benchmark_runs/<timestamp>/run_manifest.json`
- `output/benchmark_runs/<timestamp>/results.jsonl`
- `output/benchmark_runs/<timestamp>/summary.json`
- `output/benchmark_runs/<timestamp>/case_logs/<case_id>/...`

推荐先跑这版人工精选 smoke set：

```powershell
python benchmark\run_tmc_chordtools.py --case-file benchmark\tmc_chordtools_online_smoke_v1.jsonl --dry-run --validate-imports
```

如果这一步正常，再做真实小规模执行：

```powershell
python benchmark\run_tmc_chordtools.py --case-file benchmark\tmc_chordtools_online_smoke_v1.jsonl --max-cases 2 --model gpt-4o-mini
```

在完成首轮 smoke run 之后，推荐切到 `v2 shortlist`：

```powershell
python benchmark\run_tmc_chordtools.py --case-file benchmark\tmc_chordtools_smoke_v2_shortlist.jsonl --dry-run --validate-imports
python benchmark\run_tmc_chordtools.py --case-file benchmark\tmc_chordtools_smoke_v2_shortlist.jsonl --max-cases 4 --model gpt-4o-mini
```

## Benchmark 依赖说明

你之前跑真实链主实验时装的是最小依赖；benchmark runner 覆盖的工具更多，通常还需要完整工具依赖。

最稳的方式是在 `Chord-main` 根目录安装项目依赖：

```powershell
pip install -e .
```

如果你不想整包安装，至少要补齐当前 benchmark 会用到的工具包，例如：

```powershell
pip install arxiv amadeus pyowm praw semanticscholar stackapi mediawikiapi wikibase-rest-api-client yfinance
```

## 下一步建议

这个 benchmark 完成后，后续应该按这个顺序推进：

1. 让真实链 runner 直接读 `tmc_chordtools_v1.jsonl`
2. 先做 `attack_core` 的小规模复现实验
3. 再补 `defense_ready` 子集的正式对照
4. 最后再做消融与参数扫描
