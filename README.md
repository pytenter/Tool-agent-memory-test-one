# Chord-main 实验说明

这个仓库当前聚焦一条明确的研究主线：

`successor/post-processor tool return -> memory write -> persistent memory -> future retrieval -> agent behavior drift`

当前版本已经跑通两条实验线：

- 本地无 API 的最小原型
- 接入 `Chord Agent / TestingAgent` 的真实链 memory contamination 评估

这份 README 的目标不是介绍所有历史代码，而是**固定当前可复现的实验里程碑**。默认推荐环境是 `conda`，默认推荐 retrieval 配置是 `embedding`。

## 1. 当前里程碑

当前已经稳定落地的内容：

- 安全占位 payload 经 successor/post-processor 写入 memory store
- follow-up 任务通过 retrieval 命中 memory
- 观察 tool preference / workflow / output / reasoning drift
- 比较 `clean / contaminated_only / mixed / defense_mixed`
- defense 组默认启用：
  - provenance-aware retrieval
  - memory type isolation

当前占位符标记：

- `RULE_X`
- `TOOL_PREF_Y`
- `MEMORY_MARKER_Z`
- `SAFE_PLACEHOLDER_NOTE`

## 2. 关键文件

- [`demo/chord_real_chain_memory_eval.py`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/demo/chord_real_chain_memory_eval.py)
  - 真实链主实验入口
- [`demo/safe_memory_pollution_eval.py`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/demo/safe_memory_pollution_eval.py)
  - 本地无 API 最小原型
- [`chord/agent.py`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/chord/agent.py)
  - write phase 主流程
- [`chord/testing_agent.py`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/chord/testing_agent.py)
  - follow-up retrieval 与 tool choice 执行
- [`chord/model_provider.py`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/chord/model_provider.py)
  - OpenAI 兼容模型入口，默认适配 API 易
- [`bridge/memory_writer.py`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/bridge/memory_writer.py)
  - memory write
- [`bridge/retrieval_adapter.py`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/bridge/retrieval_adapter.py)
  - retrieval 实现，支持 embedding / token
- [`bridge/chord_real_chain.py`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/bridge/chord_real_chain.py)
  - trace 提取和指标汇总

## 3. 推荐环境

要求：

- Python `>= 3.11`
- 推荐使用单独的 `conda` 环境

推荐环境名：

```powershell
conda create -n chord311_clean python=3.11 pip -y
conda activate chord311_clean
python --version
```

## 4. 安装依赖

当前主实验实际验证过的一组最小依赖如下：

```powershell
pip install langchain==0.3.23 langchain-core==0.3.51 langchain-community==0.3.21 langchain-openai==0.2.2 langgraph==0.2.34 langgraph-checkpoint==2.0.0 llama-index==0.11.19 python-dotenv sentence-transformers==5.1.1 transformers==4.57.1 torch
```

说明：

- 代码里使用 `from dotenv import load_dotenv`，对应包名是 `python-dotenv`
- `sentence-transformers` 安装成功后，还需要首次下载 embedding 模型

## 5. API 易配置

当前默认走 API 易兼容接口：

- `OPENAI_BASE_URL=https://api.apiyi.com/v1`
- `OPENAI_API_KEY=<你的 token>`

推荐在仓库根目录使用 [`.env.example`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/.env.example) 复制出 `.env`：

```powershell
Copy-Item .env.example .env
```

`.env` 典型内容：

```env
OPENAI_API_KEY=your_token_here
OPENAI_BASE_URL=https://api.apiyi.com/v1
OPENAI_MODEL=gpt-4o-mini
```

[`chord/model_provider.py`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/chord/model_provider.py) 会自动加载仓库根目录下的 `.env`。

## 6. Hugging Face 模型准备

embedding retrieval 默认使用：

- `sentence-transformers/all-MiniLM-L6-v2`

首次运行前建议先手动下载并写入本地缓存：

```powershell
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); print('HF model OK')"
```

如果你所在网络环境需要代理，请先在当前终端里设置：

```powershell
$env:HTTP_PROXY="http://127.0.0.1:7890"
$env:HTTPS_PROXY="http://127.0.0.1:7890"
$env:HF_HUB_DOWNLOAD_TIMEOUT="60"
```

端口按你的代理实际端口修改。

## 7. 连通性检查

在跑真实链之前，先验证模型接口：

```powershell
python -c "from chord.model_provider import create_chat_openai; llm=create_chat_openai(model='gpt-4o-mini', temperature=0); print(llm.invoke('Reply with OK').content)"
```

如果输出 `OK` 或类似短回复，说明：

- `.env` 生效
- API token 正常
- `OPENAI_BASE_URL` 正常
- `langchain_openai` 可用

## 8. 实验 1：本地无 API 原型

这个实验适合先验证机制闭环：

```powershell
python demo\safe_memory_pollution_eval.py
```

输出文件：

- [`output/safe_memory_pollution_summary.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/output/safe_memory_pollution_summary.json)
- [`output/baseline_memory_store.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/output/baseline_memory_store.json)
- [`output/benign_memory_store.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/output/benign_memory_store.json)
- [`output/contaminated_memory_store.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/output/contaminated_memory_store.json)
- [`output/defense_memory_store.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/output/defense_memory_store.json)

这条线的目标是：

- 验证 `successor output -> memory write -> retrieval -> drift`
- 不验证真实模型随机性

## 9. 实验 2：真实链 embedding 主实验

推荐主命令：

```powershell
python demo\chord_real_chain_memory_eval.py --model gpt-4o-mini --task-count 10 --benign-memory-count 8 --retrieval-mode embedding
```

当前推荐配置：

- `model = gpt-4o-mini`
- `task-count = 10`
- `benign-memory-count = 8`
- `retrieval-mode = embedding`
- `retrieval-top-k = 3`
- `retrieval-min-score = 0.05`
- `embedding-model = sentence-transformers/all-MiniLM-L6-v2`

常用对照：

词面对照组：

```powershell
python demo\chord_real_chain_memory_eval.py --model gpt-4o-mini --task-count 10 --benign-memory-count 8 --retrieval-mode token
```

提高 benign background：

```powershell
python demo\chord_real_chain_memory_eval.py --model gpt-4o-mini --task-count 10 --benign-memory-count 20 --retrieval-mode embedding
```

调大候选：

```powershell
python demo\chord_real_chain_memory_eval.py --model gpt-4o-mini --task-count 10 --benign-memory-count 8 --retrieval-mode embedding --retrieval-top-k 5
```

## 10. 如何确认这次真的是 embedding 实验

真实链输出目录：

- [`output/real_chain`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/output/real_chain)

核心文件：

- [`output/real_chain/real_chain_summary.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/output/real_chain/real_chain_summary.json)
- [`output/real_chain/baseline_runs.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/output/real_chain/baseline_runs.json)
- [`output/real_chain/contaminated_only_runs.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/output/real_chain/contaminated_only_runs.json)
- [`output/real_chain/mixed_runs.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/output/real_chain/mixed_runs.json)
- [`output/real_chain/defense_runs.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/output/real_chain/defense_runs.json)

现在结果文件中会同时记录：

- `retrieval_config.requested_mode`
- `retrieval_config.actual_mode_summary`
- 每条 run trace 的 `retrieval_mode`
- `runtime` 元数据，包括 Python 路径、版本和关键依赖版本

建议先检查：

- `retrieval_config.requested_mode == "embedding"`
- `actual_mode_summary` 中主导模式是 `embedding`
- 每组 runs 里多数 `retrieval_mode` 为 `embedding`

说明：

- 个别 run 的 `retrieval_mode = ""` 不表示 fallback
- 它表示该条 run 根本没有走到 `memory_lookup` 工具消息

## 11. 重点指标

建议优先看：

- `Memory Write Success Rate`
- `Retrieval Hit Rate`
- `Contaminated Hit Rate`
- `Contaminated Activation Rate`
- `Tool Preference Shift`
- `Behavior Drift Rate`
- `Provenance Detection Rate`

解释建议：

- `contaminated_only`
  - 看污染 memory 在低竞争环境下能否命中并触发
- `mixed`
  - 看 benign background 是否压制污染 memory
- `defense_mixed`
  - 看 defense 是否把污染命中和激活压回去

## 12. 当前 retrieval 行为

[`bridge/retrieval_adapter.py`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/bridge/retrieval_adapter.py) 当前实现：

- embedding 可用时优先走 `sentence-transformers`
- embedding 不可用时回退到 token overlap

因此如果你看到：

- `requested_mode = embedding`
- 实际 run trace 大量显示 `retrieval_mode = token`

那就意味着：

- embedding 模型没成功加载
- 或运行时回退到了 token

如果 run trace 中主导模式是 `embedding`，才可以把这次结果称为 embedding retrieval 实验结果。

## 13. 当前 defense 设置

真实链 defense 组默认同时启用：

- provenance-aware retrieval
- memory type isolation

也就是：

- 对低信任来源 memory 降权
- 对不可信 `WriteReason` 记录做隔离

## 14. 常见问题

### 14.1 `openai.APIConnectionError`

检查：

- `.env` 中 `OPENAI_API_KEY` 是否有效
- `OPENAI_BASE_URL` 是否可访问
- 当前网络是否能访问 API 易

### 14.2 Hugging Face 模型下载超时

说明终端无法访问 `huggingface.co`。优先检查：

- 代理是否开启
- `HTTP_PROXY / HTTPS_PROXY` 是否设置到当前终端

模型只要成功下载一次，后续通常可直接走本地缓存。

### 14.3 `Retrieval Hit Rate` 高，但 `Contaminated Hit Rate` 低

说明 mixed store 中命中的大多是 benign background memory，而不是污染 memory。

### 14.4 `Memory Write Success Rate = 1.0`，但 `Retrieval Hit Rate < 1.0`

写入成功不等于每个 follow-up 任务都会：

- 调用 `memory_lookup`
- 命中相关 memory
- 使用它做决策

## 15. 推荐复现顺序

从零复现当前 embedding 里程碑，建议严格按下面顺序：

```powershell
conda activate chord311_clean
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); print('HF model OK')"
python -c "from chord.model_provider import create_chat_openai; llm=create_chat_openai(model='gpt-4o-mini', temperature=0); print(llm.invoke('Reply with OK').content)"
python demo\safe_memory_pollution_eval.py
python demo\chord_real_chain_memory_eval.py --model gpt-4o-mini --task-count 10 --benign-memory-count 8 --retrieval-mode embedding
python demo\chord_real_chain_memory_eval.py --model gpt-4o-mini --task-count 10 --benign-memory-count 8 --retrieval-mode token
```

## 16. 说明

原始 Chord demo 仍然保留，但它们不是当前 memory contamination 主线的重点：

- `demo/semantic_targeted_hooking.py`
- `demo/semantic_untargeted_hooking.py`
- `demo/syntax_format_hooking.py`
- `demo/dynamic_tool_creation.py`

## 17. Benchmark

`TMC-ChordTools v1` 现已整理到 [`benchmark/README.md`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/benchmark/README.md)。

默认产物：

- [`benchmark/tmc_chordtools_v1.jsonl`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/benchmark/tmc_chordtools_v1.jsonl)
- [`benchmark/tmc_chordtools_v1_manifest.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/benchmark/tmc_chordtools_v1_manifest.json)
- [`benchmark/tmc_chordtools_v1_defense.jsonl`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/benchmark/tmc_chordtools_v1_defense.jsonl)
- [`benchmark/tmc_chordtools_v1_defense_manifest.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/benchmark/tmc_chordtools_v1_defense_manifest.json)
- [`benchmark/tmc_chordtools_online_smoke_v1.jsonl`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/benchmark/tmc_chordtools_online_smoke_v1.jsonl)
- [`benchmark/tmc_chordtools_online_smoke_v1_manifest.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/benchmark/tmc_chordtools_online_smoke_v1_manifest.json)
- [`benchmark/tmc_chordtools_smoke_v2_shortlist.jsonl`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/benchmark/tmc_chordtools_smoke_v2_shortlist.jsonl)
- [`benchmark/tmc_chordtools_smoke_v2_shortlist_manifest.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/benchmark/tmc_chordtools_smoke_v2_shortlist_manifest.json)

重新导出完整 benchmark：

```powershell
python benchmark\export_tmc_chordtools.py
```

导出人工精选 smoke set：

```powershell
python benchmark\export_curated_subset.py --subset tmc_chordtools_online_smoke_v1
```

导出收敛后的 v2 shortlist：

```powershell
python benchmark\export_curated_subset.py --subset tmc_chordtools_smoke_v2_shortlist
```

先做 benchmark dry-run：

```powershell
python benchmark\run_tmc_chordtools.py --dry-run --max-cases 5
```

如果要先检查 benchmark Python 依赖是否齐全：

```powershell
python benchmark\run_tmc_chordtools.py --dry-run --validate-imports --max-cases 5
```

如果要顺便检查 benchmark tool 实例化和联网连通性：

```powershell
python benchmark\run_tmc_chordtools.py --dry-run --validate-tools --max-cases 5
```

如果要先跑推荐的 5 条 smoke case：

```powershell
python benchmark\run_tmc_chordtools.py --case-file benchmark\tmc_chordtools_online_smoke_v1.jsonl --dry-run --validate-imports
```

在完成首轮 smoke run 后，建议切到新的 shortlist：

```powershell
python benchmark\run_tmc_chordtools.py --case-file benchmark\tmc_chordtools_smoke_v2_shortlist.jsonl --dry-run --validate-imports
python benchmark\run_tmc_chordtools.py --case-file benchmark\tmc_chordtools_smoke_v2_shortlist.jsonl --max-cases 4 --model gpt-4o-mini
```
