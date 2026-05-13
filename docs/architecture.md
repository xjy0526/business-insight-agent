# BusinessInsight Agent 架构说明

## 总体架构

BusinessInsight Agent 面向电商经营诊断场景，将用户自然语言问题转化为可执行的分析链路。

```text
用户问题
  -> FastAPI
  -> CacheService
  -> Agent Graph
      -> Intent Router
      -> Planner
      -> Metrics Tool Node
      -> RAG Retriever Node
      -> Diagnosis Generator
      -> ReportService
      -> Reflection Checker
      -> Final Report
  -> TraceService
  -> API / Frontend
```

当前版本使用轻量顺序状态机实现，便于本地运行和面试展示。`build_langgraph()` 已预留，后续可替换为 LangGraph。

## AgentState

`AgentState` 是贯穿所有节点的状态对象，核心字段包括：

- `trace_id`：单次执行链路 ID
- `user_query`：用户原始问题
- `intent`、`entity_type`、`entity_id`、`related_entity_ids`、`metric`：意图和实体识别结果
- `time_range`：当前期和基准期
- `plan_steps`：任务规划步骤
- `tool_results`：指标工具和 RAG 工具输出
- `retrieved_docs`：RAG evidence
- `diagnosis`：诊断报告正文
- `reflection_result`：反思校验结果
- `final_answer`：最终返回结果
- `errors`：节点级错误
- `node_spans`：每个节点的耗时、输入摘要、输出摘要和错误类型
- `cache_key`、`cache_hit`：缓存关联字段
- `started_at`、`finished_at`：执行时间

## 节点职责

### Intent Router

识别用户问题中的业务意图、商品 ID、指标和时间范围。支持 GMV、退款率、点击率、转化率、差评等意图。若用户没有明确商品 ID，但提到商品名称，会尝试映射到 `product_id`。

### Planner

根据 intent 和 query 生成计划步骤。当前计划以规则和 mock LLM 为主，覆盖指标计算、RAG 检索、报告生成和反思校验。

### Metrics Tool Node

调用 `app/tools/metrics_tool.py` 中的指标工具：

- `get_product_basic_info`
- `calculate_gmv`
- `calculate_traffic_metrics`
- `calculate_refund_rate`
- `calculate_aov`
- `compare_periods`
- `analyze_channel_breakdown`

默认比较 2026-04-01 至 2026-04-30 与 2026-03-01 至 2026-03-31。若商品 ID 不存在，节点会写入 `state.errors` 并触发 fallback 报告，避免用全 0 指标误导用户。

### RAG Retriever Node

根据用户 query、intent、metric 和指标异常信号构造检索 query，调用 `search_business_knowledge()`。检索结果写入 `retrieved_docs`，并在 `tool_results.rag_search` 中保存 evidence summary。

### Diagnosis Generator

节点本身只负责调用 `ReportService`，真正的报告拼装已经从 `nodes.py` 拆出，避免状态机节点承载过多展示逻辑。报告基于指标结果和 RAG evidence 生成，包含：

1. 问题概述
2. 指标拆解
3. 主要归因
4. 证据来源
5. 优化建议

mock 模式下使用确定性规则报告，避免依赖真实 API Key。

### Reflection Checker

检查报告是否包含关键结构，是否有 `tool_results` 和 `retrieved_docs`。当前阶段不做循环重试，只记录 issues 和 suggestions。

### Final Report

将诊断报告、trace_id、执行步骤摘要和反思校验结果组合成最终回答。

## 工具调用流程

指标工具全部基于 SQLite，避免 LLM 编造数字：

```text
orders.csv / traffic.csv / reviews.csv / campaigns.csv
  -> python -m app.db.init_db
  -> data/business_insight.db
  -> metrics_tool
  -> Agent tool_results
```

这使得 GMV、CTR、CVR、AOV、退款率等指标可复现、可测试、可审计。

## RAG 流程

本地知识库位于 `data/knowledge_docs/`：

- `campaign_rules.md`
- `after_sales_policy.md`
- `product_operation_guide.md`
- `review_analysis_guide.md`

流程如下：

```text
Markdown docs
  -> loader.py
  -> splitter.py
  -> vector_store.py
       -> FAISS optional backend
       -> Chroma optional backend
       -> TF-IDF fallback
  -> retriever.py
  -> rag_tool.py
  -> Agent retrieved_docs
```

默认使用 TF-IDF，便于无外部依赖本地演示。若设置 `RAG_BACKEND=faiss` 或 `RAG_BACKEND=chroma`，系统会尝试启用对应后端；依赖缺失或初始化失败时自动回退 TF-IDF。

RAG 的作用是为经营归因提供业务规则证据，例如活动参与不足影响价格竞争力、退款率升高可能与物流慢/描述不符/质量问题有关。

## SQL 安全

`sql_tool.execute_readonly_query()` 使用两层防护：

1. 优先使用 `sqlparse` 校验只允许单条 `SELECT`；依赖缺失时回退到保守规则校验。
2. SQLite 以 `mode=ro` 打开数据库，底层连接也是只读。

这比单纯正则拦截更稳，后续仍可替换为 SQL allowlist、AST parser 或指标 DSL。

## Trace 机制

`TraceService` 将每次 Agent 执行保存到 `agent_traces` 表，记录：

- 用户问题和识别意图
- 计划步骤
- 工具调用结果
- RAG evidence
- 最终报告
- 反思结果
- node_spans
- cache_key / cache_hit
- latency_ms
- error_type

Trace API：

```text
GET /api/traces?limit=20
GET /api/traces/{trace_id}
```

`node_spans` 中包含每个节点的耗时、输入摘要、输出摘要和错误类型，用于定位是意图识别慢、指标查询慢、RAG 慢，还是报告生成失败。

Trace 用于 case review、性能分析和线上问题定位。

## Eval 机制

评测 case 位于 `evals/eval_cases.json`。`evals/run_eval.py` 会逐个调用 `run_agent()`，并计算：

- `intent_accuracy`
- `keyword_coverage`
- `tool_usage`
- `evidence_hit`
- `entity_coverage`
- `tool_result_key_coverage`
- `trace_field_coverage`
- `error_expectation`
- `forbidden_keyword_pass`
- `score`

总体输出：

- `intent_accuracy`
- `avg_keyword_coverage`
- `evidence_hit_rate`
- `avg_entity_coverage`
- `avg_tool_result_key_coverage`
- `avg_trace_field_coverage`
- `error_expectation_accuracy`
- `forbidden_keyword_pass_rate`
- `avg_latency_ms`
- `avg_score`

当前评测集覆盖基础业务异常，也加入了多商品对比、模糊商品名、跨时间段问题、证据冲突、指标缺失、多指标混合和证据不足场景，避免只测“P1001 GMV 下滑”这类单一路径。

Eval API：

```text
POST /api/evals/run
```

## 稳定性设计

- API 层支持 5 分钟缓存，优先 Redis 连接池，可自动回退内存缓存。
- 缓存命中 trace 下沉到 `CacheService`，会生成轻量 trace，记录 `cache_hit=true`、`cache_key` 和 `cache_hit` span。
- LLMService 支持 mock/openai/qwen provider，缺少 API Key 自动回退 mock。
- FallbackService 在 LLM/RAG/metrics 不可用时生成降级报告。
- 每个节点捕获异常并写入 `state.errors`，尽可能继续执行。
- `LLMService.generate()` 预留 timeout 参数，真实服务应为每个外部依赖设置 timeout、retry 和熔断。

## CI 与质量门禁

`.github/workflows/ci.yml` 会执行：

- `python -m app.db.init_db`
- `ruff check app evals tests`
- `mypy app evals`
- `pytest`
- `docker build`
- `pytest -m integration`

这保证项目不仅能本地跑，也具备基础持续集成能力。

## 可选后端集成测试

`tests/test_optional_backends_integration.py` 使用 `pytest.mark.integration` 标记真实后端测试：

- Redis：通过 `testcontainers` 启动真实 Redis 容器，验证缓存读写。
- FAISS：安装 `faiss-cpu` 后构建真实 FAISS index。
- Chroma：安装 `chromadb` 后构建真实 Chroma collection。

默认测试会在依赖或 Docker 不可用时 skip，避免阻塞本地开发。需要强验证时运行：

```bash
pip install -r requirements-integration.txt
pytest -m integration
```
