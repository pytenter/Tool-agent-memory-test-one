# Chord-main 实验说明

这个仓库现在有两条可直接运行的实验线：

- 本地无 API 的最小原型
- 接入 `Chord Agent / TestingAgent` 真实执行链的 memory contamination 评估

当前默认使用 OpenAI 兼容接口，已适配 API易。

## 1. 当前实验目标

当前新增原型聚焦下面这条链路：

1. 正常目标工具先返回结果
2. 一个 successor/post-processor 工具返回安全占位 payload
3. payload 被写入 persistent memory
4. 后续任务通过 retrieval 命中该 memory
5. 观察 agent 是否出现：
   - tool preference shift
   - workflow order drift
   - output drift
   - reasoning drift
6. 再对比 defense 是否能压制这种影响

所有污染内容都使用无害占位符：

- `RULE_X`
- `TOOL_PREF_Y`
- `MEMORY_MARKER_Z`
- `SAFE_PLACEHOLDER_NOTE`

## 2. 目录重点

- [`chord/agent.py`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/chord/agent.py)
  - Chord 主工作流，已接入安全 successor payload 和 memory write
- [`chord/testing_agent.py`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/chord/testing_agent.py)
  - 真实工具链执行与消息轨迹记录
- [`chord/model_provider.py`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/chord/model_provider.py)
  - 统一模型入口，默认走 API易
- [`bridge/memory_writer.py`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/bridge/memory_writer.py)
  - successor 输出写入 memory store
- [`bridge/retrieval_adapter.py`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/bridge/retrieval_adapter.py)
  - MINJA 风格语义检索，默认 `sentence-transformers` embedding
- [`bridge/chord_real_chain.py`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/bridge/chord_real_chain.py)
  - 真实链结果提取与指标计算
- [`demo/safe_memory_pollution_eval.py`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/demo/safe_memory_pollution_eval.py)
  - 本地无 API 的最小原型
- [`demo/chord_real_chain_memory_eval.py`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/demo/chord_real_chain_memory_eval.py)
  - 真实链实验入口

## 3. 环境准备

要求：

- Python `>= 3.11`
- 推荐使用独立虚拟环境

### 3.1 创建环境

如果你用 conda：

```powershell
conda create -n chord311 python=3.11 -y
conda activate chord311
python --version
```

### 3.2 安装依赖

优先使用 `uv`：

```powershell
python -m pip install uv
uv sync
```

如果 `uv` 因网络或代理不可用，可以退回 `pip`：

```powershell
python -m pip install -e .
```

当前真实链实验额外依赖：

- `langgraph`
- `langchain`
- `langchain-openai`
- `torch`
- `transformers`
- `sentence-transformers`

这些已经包含在 [`pyproject.toml`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/pyproject.toml) 里。

## 4. API易 配置

当前代码默认走 API易：

- 默认 `base_url`：`https://api.apiyi.com/v1`
- 读取环境变量：`OPENAI_API_KEY`

推荐在仓库根目录使用 `.env`：

1. 复制模板

```powershell
Copy-Item .env.example .env
```

2. 编辑 [`.env`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/.env)

```env
OPENAI_API_KEY=你的API易令牌
OPENAI_BASE_URL=https://api.apiyi.com/v1
OPENAI_MODEL=gpt-4o-mini
```

[`chord/model_provider.py`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/chord/model_provider.py) 会自动加载这个文件。

## 5. 先做连通性测试

在跑真实链之前，先确认模型能通：

```powershell
python -c "from chord.model_provider import create_chat_openai; llm=create_chat_openai(model='gpt-4o-mini', temperature=0); print(llm.invoke('Reply with OK').content)"
```

如果输出 `OK` 或类似短回复，说明：

- `.env` 已生效
- API易 token 正常
- `base_url` 正常
- `langchain_openai` 可用

## 6. 实验 1：本地无 API 最小原型

这个实验不依赖真实 LLM API，适合先验证整条机制：

```powershell
python demo\safe_memory_pollution_eval.py
```

输出文件：

- [`output/safe_memory_pollution_summary.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/output/safe_memory_pollution_summary.json)
- [`output/benign_memory_store.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/output/benign_memory_store.json)
- [`output/contaminated_memory_store.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/output/contaminated_memory_store.json)
- [`output/defense_memory_store.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/output/defense_memory_store.json)

这条线的用途是：

- 验证 `successor output -> memory write -> retrieval -> behavior drift`
- 不验证真实模型随机性

## 7. 实验 2：真实链 memory contamination 评估

这个实验会真正使用：

- `Chord Agent` 做 write phase
- `TestingAgent` 做 follow-up retrieval 和 tool choice
- MINJA 风格语义检索做 memory matching

### 7.1 标准运行命令

```powershell
python demo\chord_real_chain_memory_eval.py --model gpt-4o-mini --task-count 10 --benign-memory-count 8 --retrieval-mode embedding
```

这是当前最推荐的配置：

- `task-count=10`
- `benign-memory-count=8`
- `retrieval-mode=embedding`

### 7.2 常用参数

- `--model`
  - 例如 `gpt-4o-mini`
- `--task-count`
  - follow-up 任务数
- `--benign-memory-count`
  - benign background memory 数量
- `--retrieval-mode`
  - `embedding`：默认，MINJA 风格语义检索
  - `token`：词面重叠对照组
  - `auto`：有 embedding 就用 embedding，否则回退 token
- `--retrieval-top-k`
  - 当前默认 `3`
- `--retrieval-min-score`
  - 当前默认 `0.05`
- `--embedding-model`
  - 当前默认 `sentence-transformers/all-MiniLM-L6-v2`

### 7.3 建议的几组对照

语义检索主实验：

```powershell
python demo\chord_real_chain_memory_eval.py --model gpt-4o-mini --task-count 10 --benign-memory-count 8 --retrieval-mode embedding
```

词面对照组：

```powershell
python demo\chord_real_chain_memory_eval.py --model gpt-4o-mini --task-count 10 --benign-memory-count 8 --retrieval-mode token
```

提高 benign background：

```powershell
python demo\chord_real_chain_memory_eval.py --model gpt-4o-mini --task-count 10 --benign-memory-count 20 --retrieval-mode embedding
```

调大检索候选：

```powershell
python demo\chord_real_chain_memory_eval.py --model gpt-4o-mini --task-count 10 --benign-memory-count 8 --retrieval-mode embedding --retrieval-top-k 5
```

## 8. 真实链实验输出怎么看

真实链输出目录默认在：

- [`output/real_chain`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/output/real_chain)

重点文件：

- [`output/real_chain/real_chain_summary.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/output/real_chain/real_chain_summary.json)
- [`output/real_chain/baseline_runs.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/output/real_chain/baseline_runs.json)
- [`output/real_chain/contaminated_only_runs.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/output/real_chain/contaminated_only_runs.json)
- [`output/real_chain/mixed_runs.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/output/real_chain/mixed_runs.json)
- [`output/real_chain/defense_runs.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/output/real_chain/defense_runs.json)

memory store：

- [`output/real_chain/clean_memory_store.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/output/real_chain/clean_memory_store.json)
- [`output/real_chain/contaminated_only_memory_store.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/output/real_chain/contaminated_only_memory_store.json)
- [`output/real_chain/mixed_memory_store.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/output/real_chain/mixed_memory_store.json)
- [`output/real_chain/defense_mixed_memory_store.json`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/output/real_chain/defense_mixed_memory_store.json)

### 8.1 你最应该先看哪些指标

- `Memory Write Success Rate`
- `Retrieval Hit Rate`
- `Contaminated Hit Rate`
- `Contaminated Activation Rate`
- `Tool Preference Shift`
- `Behavior Drift Rate`
- `Provenance Detection Rate`

### 8.2 结果解释建议

- `contaminated_only`
  - 看污染记忆在低竞争环境下能否命中并触发
- `mixed`
  - 看 benign background 是否把污染记忆竞争下去
- `defense_mixed`
  - 看 defense 是否把污染命中和污染激活压回去

## 9. 当前检索实现

当前 retrieval 在 [`bridge/retrieval_adapter.py`](/c:/Users/admin/Desktop/对抗攻击/Tool-memory的实验/Chord-main/bridge/retrieval_adapter.py)。

默认是 MINJA/RAP 风格的语义路径：

- 主信号：`Instruction`
- 辅助信号：`SanitizedMemoryText`
- 轨迹信号：`Actions`
- 额外信号：完整 record 文本

当前做法是：

- 优先使用 `sentence-transformers` embedding
- 若 embedding 不可用，则回退到 token overlap

如果你跑完后发现 trace 里 `retrieval_mode` 是 `token`，通常说明：

- `sentence-transformers` 没装成功
- 或 embedding 模型没加载起来

## 10. 当前防御设置

真实链实验里的 defense 组默认同时打开：

- provenance-aware retrieval
- memory type isolation

也就是：

- 对非可信来源 memory 做降权或隔离
- 只让可信 `WriteReason` 的 background memory 保持正常检索优先级

## 11. 常见问题

### 11.1 `uv` 不存在

```powershell
python -m pip install uv
```

如果还是装不上，就直接：

```powershell
python -m pip install -e .
```

### 11.2 `ModuleNotFoundError: langgraph`

说明依赖没有装完整。重新执行：

```powershell
uv sync
```

或：

```powershell
python -m pip install -e .
```

### 11.3 `openai.APIConnectionError`

先确认：

- `.env` 里的 `OPENAI_API_KEY` 不为空
- `OPENAI_BASE_URL=https://api.apiyi.com/v1`
- 你的网络能访问 API易

### 11.4 为什么 `Memory Write Success Rate = 1.0` 但 `Retrieval Hit Rate < 1.0`

因为写进 memory 不等于每个 follow-up 任务都会：

- 调用 `memory_lookup`
- 命中相关 memory
- 或真正使用它做决策

### 11.5 为什么 `Retrieval Hit Rate` 很高但 `Contaminated Hit Rate` 不高

因为在 mixed store 下，agent 可能经常命中的是 benign background memory，而不是污染 memory。

## 12. 原始 Chord demo

原始仓库里的 demo 仍然可用，但它们不是你当前这条 memory contamination 研究主线的重点：

- `demo/semantic_targeted_hooking.py`
- `demo/semantic_untargeted_hooking.py`
- `demo/syntax_format_hooking.py`
- `demo/dynamic_tool_creation.py`

## 13. 当前最推荐的运行顺序

如果你要从头严谨地跑一遍，建议顺序是：

1. 配好 `.env`
2. 做连通性测试
3. 先跑本地无 API 原型
4. 再跑真实链语义检索实验
5. 再做 token 对照组
6. 再调 `benign-memory-count / retrieval-top-k / retrieval-min-score`

对应命令：

```powershell
python -c "from chord.model_provider import create_chat_openai; llm=create_chat_openai(model='gpt-4o-mini', temperature=0); print(llm.invoke('Reply with OK').content)"
python demo\safe_memory_pollution_eval.py
python demo\chord_real_chain_memory_eval.py --model gpt-4o-mini --task-count 10 --benign-memory-count 8 --retrieval-mode embedding
python demo\chord_real_chain_memory_eval.py --model gpt-4o-mini --task-count 10 --benign-memory-count 8 --retrieval-mode token
```
