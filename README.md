# BusinessInsight Agent

BusinessInsight Agent 是一个面向电商经营场景的智能归因与决策 Agent 系统。用户输入自然语言问题，例如“商品 P1001 最近 GMV 为什么下降？”，系统会自动完成意图识别、任务规划、指标工具调用、RAG 知识检索、经营归因、反思校验、Trace 记录和结构化报告生成。

项目定位不是简单聊天 Demo，而是一个可本地运行、可观测、可评测、可降级的 AI 应用工程样板，适合用于展示 Agent + RAG + Tool Calling + Eval + Observability 的完整链路。

## 核心能力

- 业务归因：支持 GMV 下滑、点击率下降、转化率异常、退款率升高、差评高频问题等电商经营场景。
- Agent 状态机：包含 Intent Router、Planner、Metrics Tool、RAG Retriever、Diagnosis Generator、Reflection Checker、Final Report。
- 指标工具：基于 SQLite 计算 GMV、CTR、CVR、AOV、退款率、渠道拆解等指标。
- 本地 RAG：读取 Markdown 知识库，默认 TF-IDF 检索，可选 FAISS/Chroma 后端并自动 fallback。
- Trace 观测：每次 Agent 执行保存 trace_id、计划、工具结果、RAG 证据、per-node span、延迟、错误类型和最终回答。
- 自动化评测：内置 16 个 eval cases，覆盖基础异常、多商品对比、模糊商品名、跨时间段、证据冲突、指标缺失和证据不足场景。
- 稳定性机制：支持 Redis 优先缓存、内存 fallback、LLM/RAG/metrics fallback、节点级异常捕获和 timeout 参数预留。
- 工程质量：补充 ruff、mypy 和 GitHub Actions CI，CI 中包含 pytest 与 Docker build。
- 前端 Demo：原生 HTML/CSS/JS 页面，便于演示。

## 架构图文字版

```text
User Query
  -> FastAPI /api/agent/analyze
  -> CacheService
      -> cache hit: return cached response
      -> cache miss:
          -> Agent Graph
              -> Intent Router
              -> Planner
              -> Metrics Tool Node
                    -> SQLite products/orders/traffic/reviews/campaigns
              -> RAG Retriever Node
                    -> Markdown docs -> Splitter -> FAISS/Chroma(optional) or TF-IDF fallback
              -> Diagnosis Generator
                    -> LLMService mock/openai/qwen reserved
                    -> ReportService
                    -> FallbackService
              -> Reflection Checker
              -> Final Report
          -> TraceService saves agent_traces
          -> CacheService writes response
  -> JSON response + frontend rendering
```

## 技术栈

- Python 3.11+
- FastAPI
- Pydantic / pydantic-settings
- SQLite
- pandas
- scikit-learn，默认使用 TF-IDF 本地检索
- Redis，可选缓存后端；未配置时自动使用内存缓存
- sqlparse 可选解析 + SQLite read-only connection，用于安全只读 SQL 工具
- pytest
- ruff / mypy
- Docker / docker compose
- 原生 HTML / CSS / JavaScript
- LangGraph 预留：当前使用轻量顺序状态机，后续可替换为 LangGraph

## 项目结构

```text
business-insight-agent/
├── app/
│   ├── api/              # FastAPI routers
│   ├── agent/            # state, nodes, graph, prompts
│   ├── db/               # SQLite connection and init script
│   ├── rag/              # loader, splitter, vector store, retriever
│   ├── services/         # llm, trace, eval, cache, fallback, report
│   ├── tools/            # metrics, sql, rag tools
│   └── main.py
├── data/
│   ├── knowledge_docs/   # RAG markdown docs
│   ├── products.csv
│   ├── orders.csv
│   ├── traffic.csv
│   ├── reviews.csv
│   └── campaigns.csv
├── docs/
│   ├── architecture.md
│   ├── demo_cases.md
│   └── interview_notes.md
├── evals/
│   ├── eval_cases.json
│   ├── metrics.py
│   └── run_eval.py
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── tests/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements-integration.txt
├── requirements-dev.txt
└── requirements.txt
```

## 本地运行

```bash
cd /Users/xjy/Documents/GitHub/ali/business-insight-agent
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # 可选：本地运行 ruff/mypy
python -m app.db.init_db
uvicorn app.main:app --reload
```

启动后访问：

- 前端 Demo：http://localhost:8000
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## Docker 运行

```bash
cd /Users/xjy/Documents/GitHub/ali/business-insight-agent
docker compose up --build
```

服务默认监听：

```text
http://localhost:8000
```

## 数据初始化

项目内置模拟电商数据：

- `products.csv`：5 个商品，包括 P1001 无线蓝牙耳机 Pro
- `orders.csv`：覆盖 2026-03-01 到 2026-04-30 的订单数据
- `traffic.csv`：按商品、日期、渠道记录曝光、点击、加购、订单
- `reviews.csv`：评价与差评内容
- `campaigns.csv`：平台活动规则和参与情况

初始化 SQLite：

```bash
python -m app.db.init_db
```

人为设计的核心异常：

- P1001 在 2026 年 4 月 GMV 明显低于 3 月
- P1001 在 4 月退款率升高
- P1001 在 4 月 search 渠道点击率下降
- P1001 在 4 月差评集中在“续航不达预期”“物流慢”“佩戴不舒服”
- P1001 所在音频类目 4 月有活动，但参与不足

## API 示例

运行 Agent 分析：

```bash
curl -X POST http://127.0.0.1:8000/api/agent/analyze \
  -H "Content-Type: application/json" \
  -d '{"query":"商品 P1001 最近 GMV 为什么下降？"}'
```

关闭缓存：

```bash
curl -X POST http://127.0.0.1:8000/api/agent/analyze \
  -H "Content-Type: application/json" \
  -d '{"query":"商品 P1001 最近 GMV 为什么下降？","use_cache":false}'
```

查询指标对比：

```bash
curl "http://127.0.0.1:8000/api/metrics/product/P1001/compare?current_start=2026-04-01&current_end=2026-04-30&baseline_start=2026-03-01&baseline_end=2026-03-31"
```

查询 Trace：

```bash
curl http://127.0.0.1:8000/api/traces?limit=20
curl http://127.0.0.1:8000/api/traces/{trace_id}
```

运行评测：

```bash
curl -X POST http://127.0.0.1:8000/api/evals/run
```

## 自动化评测

评测 case 位于 `evals/eval_cases.json`，覆盖 16 类场景：

- P1001 GMV 下滑归因
- P1001 退款率异常
- P1001 search 渠道点击率下降
- P1002 经营表现分析
- 活动参与不足影响分析
- 差评高频问题分析
- 转化率下降分析
- 无效商品 ID 场景
- 多商品经营表现对比
- 模糊商品名识别
- 跨时间段异常分析
- 证据不足场景
- 证据冲突下的谨慎归因
- 未提供商品 ID 的指标缺失场景
- 多商品多指标混合分析
- 数据缺口下禁止强结论

命令行运行：

```bash
python -m evals.run_eval
```

输出总体指标：

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

## Trace 观测

`TraceService` 会把每次 Agent 执行写入 SQLite 表 `agent_traces`，字段包括：

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

复杂字段用 JSON 字符串存储，并使用 `ensure_ascii=False` 保留中文可读性。`node_spans` 记录每个节点的耗时、输入摘要、输出摘要和错误类型，Trace 可用于 case review、性能分析、错误定位和回测。

## 缓存与降级

`CacheService` 支持两种模式：

- `CACHE_BACKEND=memory`：默认本地内存缓存，适合 Demo 和单实例开发。
- `CACHE_BACKEND=redis` + `REDIS_URL=redis://...`：使用 Redis 共享缓存和连接池；Redis 不可用时自动回退内存缓存。

缓存 key 使用 query 的 SHA-256 摘要，Trace 中会记录 `cache_key`，API 响应包含 `cached` 和 `cache_key`，方便定位缓存命中行为。

缓存命中 trace 由 `CacheService` 统一写入，而不是散落在 API 路由中。命中时会写入一条轻量 trace，`cache_hit=true`，并用新的 `trace_id` 标识本次请求；报告正文中的 `trace_id` 会同步替换，便于按请求维度审计。

## RAG 后端

`RAG_BACKEND` 支持：

- `tfidf`：默认，无外部服务依赖。
- `faiss`：可选，使用本地 hashing embedding + FAISS index。
- `chroma`：可选，使用 Chroma collection。

如果 FAISS/Chroma 依赖未安装或初始化失败，系统会自动回退到 TF-IDF，保证本地测试和面试 Demo 不被复杂依赖卡住。

## 工程质量

```bash
ruff check app evals tests
mypy app evals
pytest
docker build -t business-insight-agent:local .
```

GitHub Actions 位于 `.github/workflows/ci.yml`，包含依赖安装、数据库初始化、ruff、mypy、pytest、Docker build，以及独立的 optional backend integration job。

## 集成测试

默认 `pytest` 会运行所有本地测试，并对不可用的可选后端自动 skip。若要验证真实后端：

```bash
pip install -r requirements-integration.txt
pytest -m integration
```

集成测试覆盖：

- Redis：通过 `testcontainers` 启动真实 Redis 容器，验证 `CacheService` 读写 Redis。
- FAISS：安装 `faiss-cpu` 后构建真实 FAISS index。
- Chroma：安装 `chromadb` 后构建真实 Chroma collection。

也可以用 Docker Compose 启动辅助服务：

```bash
docker compose --profile integration up -d redis chroma
```

## 示例问题

可以在前端或 API 中直接演示：

```text
商品 P1001 最近 GMV 为什么下降？
P1001 的退款率最近是不是异常？
P1001 搜索渠道点击率为什么下降？
商品 P1001 差评集中在哪些问题？
P1001 没有充分参加平台活动会怎样影响价格竞争力和 GMV？
P1001 转化率下降应该从哪些维度分析？
商品 P1002 4 月经营表现如何？
商品 P9999 最近 GMV 为什么下降？
```

## 面试讲解要点

- 这不是单轮问答，而是 Agent 工作流：先识别意图，再规划，再调用工具和 RAG，最后生成报告并反思校验。
- 指标计算由确定性工具完成，避免让 LLM 编造经营数字。
- RAG 提供业务规则、售后政策、商品运营指南和评价分析指南，用于支撑归因证据。
- Trace 记录完整执行链路，方便分析“为什么这么回答”和“哪里慢/哪里错”。
- Eval 模块把 Agent 输出变成可量化指标，体现 AI 应用的回测和质量评估能力。
- fallback 和 cache 体现稳定性意识：无 API Key、本地 mock、RAG 空结果、工具失败都不会让系统崩溃。
- 当前用轻量状态机控制复杂度；如果进入生产，可替换为 LangGraph、Redis、任务队列和真实模型服务。

## 后续优化方向

- 用 LangGraph 替换顺序状态机，支持条件边、重试和多轮补充工具调用。
- 接入真实 OpenAI/Qwen API，并为每个外部调用设置 timeout、retry、rate limit 和 circuit breaker。
- 为 FAISS 或 Chroma 增加持久化索引、真实 embedding 模型和增量索引。
- 将 Redis 缓存扩展为请求去重、热点 query 限流和结果版本管理。
- 增加异步任务队列，用于长耗时分析、批量评测和离线回测。
- 在 Trace span 中补充 token 成本、外部 API 状态码和重试次数。
- 扩展更多经营场景，例如库存异常、竞品价格冲击、渠道投放 ROI、会员复购下降。

## 测试

```bash
pytest
python -m app.db.init_db
python -m evals.run_eval
```

当前测试覆盖健康检查、数据库初始化、指标工具、RAG 检索、LLM mock、Agent graph、API、Trace、Eval、fallback 和 cache。
