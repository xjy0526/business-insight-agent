# BusinessInsight Agent 项目基线审计

审计日期：2026-06-01

## 一句话介绍

BusinessInsight Agent 是一个面向电商经营诊断场景的 AI 应用工程样板，将自然语言问题转化为 Agent 编排、指标工具调用、RAG 证据检索、反思校验、Trace 记录和 Eval 回测。

## 当前核心能力清单

- FastAPI 后端与原生前端 Demo，入口包括 `/api/agent/analyze`、`/api/metrics/*`、`/api/traces/*`、`/api/evals/run`。
- SQLite 模拟电商数据，覆盖商品、订单、流量、评论、活动等表。
- Metrics Tool：支持 GMV、CTR、CVR、AOV、退款率、渠道拆解，以及 GMV driver 贡献度拆解。
- Review Tool：基于评论表做负面评论主题分析，当前主题包括预约履约、服务效果、到店体验、销售体验和描述不符。
- Campaign Tool：基于商品类目和活动规则分析活动匹配、参与等级和低参与信号。
- 本地 RAG：读取 `data/knowledge_docs` Markdown，默认 TF-IDF，FAISS/Chroma 为可选后端并自动 fallback。
- LLMService：默认 mock；配置 OpenAI/Qwen Key 后走 OpenAI-compatible chat completions，失败时回退 mock。
- Prompt Guard：识别忽略规则、泄露系统提示词、绕过工具、危险 SQL、密钥索取等注入式指令。
- ReportService：mock 模式下生成确定性中文经营诊断报告，真实模型模式下基于 prompt 调用 LLM。
- Evidence Checker：检查报告结构和关键结论是否有 Tool 或 RAG 证据支撑。
- TraceService：持久化 trace，并提供最近 trace 聚合统计。
- EvalService：运行本地 eval cases，支持阈值门禁和组件消融实验。
- 缓存：Redis 优先，Redis 不可用时内存 fallback；缓存命中也写入轻量 trace。
- 工程质量：pytest、ruff、mypy、Docker、GitHub Actions CI。

## 当前 Agent 执行链路

```text
用户问题
  -> FastAPI /api/agent/analyze
  -> CacheService
      -> 命中缓存：返回缓存 payload，并写入 cache_hit trace
      -> 未命中：
          -> ConditionalAgentGraph
              -> prompt_guard_node
              -> intent_router_node
              -> planner_node
              -> metrics_tool_node
              -> review_tool_node
              -> campaign_tool_node
              -> rag_retriever_node
              -> diagnosis_generator_node
              -> reflection_checker_node
              -> 可选 Evidence Repair 二次补证
              -> final_report_node
          -> TraceService.save_trace
          -> CacheService.set_cache
  -> AnalyzeResponse
```

当前 `build_langgraph()` 返回本地 `ConditionalAgentGraph` fallback，尚未接入真实 LangGraph runtime。

## 当前 RAG 方案

- 文档来源：`data/knowledge_docs/*.md`，跳过知识库 README。
- 加载：`app/rag/loader.py` 读取 Markdown。
- 切分：`app/rag/splitter.py` 使用字符长度切分，默认 `chunk_size=500`、`overlap=80`。
- 检索 facade：`app/rag/retriever.py` 使用 `@lru_cache` 缓存本地索引。
- 默认后端：`TfidfVectorStore`，字符级 ngram TF-IDF。
- 可选后端：`FaissVectorStore`、`ChromaVectorStore`，缺依赖或初始化失败自动回退 TF-IDF。
- 工具封装：`app/tools/rag_tool.py` 返回 `query`、`results` 和 `evidence_summary`。

## 当前 Trace 字段

SQLite 表：`agent_traces`

- `trace_id`
- `user_query`
- `intent`
- `entity_id`
- `plan_steps`
- `tool_results`
- `retrieved_docs`
- `final_answer`
- `reflection_result`
- `node_spans`
- `cache_key`
- `cache_hit`
- `latency_ms`
- `error_type`
- `created_at`

其中 `plan_steps`、`tool_results`、`retrieved_docs`、`reflection_result`、`node_spans` 为 JSON 字符串存储。Trace Stats 当前聚合 `trace_count`、`avg_latency_ms`、`p95_latency_ms`、`error_rate`、`cache_hit_rate`、`intent_counts`、`error_type_counts`、`node_latency_ms`。

## 当前 Eval 指标

Eval cases 位于 `evals/eval_cases.json`，当前共 20 个 case。单 case 指标包括：

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

聚合指标包括：

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
- `gate`

门禁阈值来自配置：`eval_min_avg_score=0.72`、`eval_min_intent_accuracy=0.7`。消融实验当前包括 `full_agent`、`no_rag`、`no_review_campaign`、`no_reflection`、`no_metrics_tool`、`mock_only`。

## 当前 fallback 机制

- LLM fallback：默认 mock；真实 OpenAI/Qwen Provider 缺 Key、缺 openai SDK 或请求失败时回退 mock。
- RAG fallback：FAISS/Chroma 初始化失败时回退 TF-IDF；检索异常时返回空证据摘要但不中断流程。
- Metrics fallback：商品缺失或工具异常会写入 `state.errors`，ReportService 使用 FallbackService 生成降级报告。
- Cache fallback：Redis 未配置、不可用或运行异常时使用进程内内存缓存。
- Graph fallback：未使用真实 LangGraph runtime，本地 `ConditionalAgentGraph` 保证无额外依赖可运行。
- Trace fallback：缓存命中 trace 写入失败不会影响接口返回；Agent 主流程保存 trace 失败会记录错误。

## 当前 CI 流程

`.github/workflows/ci.yml` 包含两个 job：

- `test`
  - checkout
  - Python 3.11
  - 安装 `requirements.txt` 和 `requirements-dev.txt`
  - `python -m app.db.init_db`
  - `ruff check app evals tests`
  - `mypy app evals`
  - `pytest`
  - `python -m evals.run_eval --all-modes --fail-under 0.70`
  - `docker build -t business-insight-agent:ci .`
- `integration`
  - 安装 `requirements.txt` 和 `requirements-integration.txt`
  - 初始化数据库
  - `docker compose --profile integration config`
  - `pytest -m integration`

## 测试覆盖基线

当前 `tests/` 覆盖：

- API 与健康检查
- Agent graph 主链路、未知商品、Prompt Injection、build_langgraph fallback
- Metrics Tool、只读 SQL Tool、GMV 贡献度
- Review Tool 与 Campaign Tool
- RAG retriever 与后端 fallback
- LLM mock、Qwen/OpenAI-compatible adapter mock、provider 失败 fallback
- ReportService
- TraceService、Trace Stats、schema migration
- CacheService、cache hit trace、fallback 报告
- EvalService、消融实验
- optional backend integration tests

## 当前明确待升级点

以下清单按“原定待升级点”和“当前核验状态”记录，避免后续开发误判基线。

1. `build_langgraph` 仍未真正使用 LangGraph runtime。
   - 当前状态：本地 `ConditionalAgentGraph` 已实现条件执行与 Evidence Repair fallback，但没有接入 `langgraph` 包、条件边持久化或 graph 可视化。
   - 后续建议：在保持 fallback 的前提下新增真实 LangGraph adapter。

2. LLMService OpenAI/Qwen adapter 不再是纯 mock fallback，但仍不是生产级 Provider。
   - 当前状态：已接入 OpenAI-compatible chat completions；测试通过 monkeypatch 验证，不依赖真实 API Key。
   - 后续建议：增加 retry、rate limit、token usage、状态码 trace、模型池和真实集成 smoke。

3. Reflection Checker 已从结构检查升级为 Evidence Checker，但 claim-level 仍较粗。
   - 当前状态：按关键词触发证据检查，能覆盖 GMV、CTR/CVR、退款率、评价、活动、贡献度等类别。
   - 后续建议：升级为句子级 claim extraction、证据引用定位和冲突证据处理。

4. Metrics Tool 已有 GMV 贡献度分解，但口径仍是轻量估算。
   - 当前状态：使用曝光、CTR、CVR、AOV 的 Shapley-style driver 分解，并保留 residual。
   - 后续建议：支持渠道级贡献、价格/活动/退款影响拆分，以及线上口径配置。

5. 评论分析已有专门 Review Tool，但主题体系仍是规则词典。
   - 当前状态：支持负面评论主题、样例评论、负面率和评分分布。
   - 后续建议：引入可配置主题词典、聚类/embedding 主题发现和跨期主题变化。

6. 活动参与已有专门 Campaign Tool，但活动状态判断仍依赖规则文本。
   - 当前状态：支持类目匹配、活动窗口、低参与/活跃参与状态。
   - 后续建议：增加活动报名表、曝光资源位、券核销、活动 GMV uplift 等结构化字段。

7. Trace 已有聚合统计接口，但可观测性还不完整。
   - 当前状态：`/api/traces/stats` 聚合延迟、错误率、缓存命中率、intent 和节点耗时。
   - 后续建议：增加 token 成本、外部 provider 状态码、重试次数、RAG 命中分布和慢 trace 样本。

8. Eval 已有消融实验和阈值门禁，但还缺更真实的质量评估。
   - 当前状态：20 个规则 eval cases，支持评分阈值门禁和 full/no_rag/no_review_campaign/no_reflection/no_metrics_tool/mock_only ablation。
   - 后续建议：增加 golden answer diff、人工标注集、LLM-as-judge 离线评测和 CI 趋势报告。

9. Prompt Injection 防护已有基础规则，但还不够系统。
   - 当前状态：检测并清洗常见注入式文本，结果写入 `tool_results.prompt_guard`。
   - 后续建议：增加分层策略、拒答边界、工具参数安全策略、RAG 文档注入检测和红队测试集。

10. README 与 docs 已比较完整，但仍需保持和代码同步。
    - 当前状态：已发现并修正文档中的本机绝对路径和旧“顺序状态机”表述。
    - 后续建议：把核心 API 示例、eval 输出示例和 trace 样例固化成可复现文档片段。
