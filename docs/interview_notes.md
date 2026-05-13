# Interview Notes

## 项目如何对齐阿里 AI 应用 JD

这个项目覆盖 AI 应用工程中常见的核心能力：

- Agent 编排：将自然语言问题拆成意图识别、计划、工具调用、RAG、报告和反思。
- Tool Calling：用确定性指标工具计算 GMV、CTR、CVR、退款率，而不是让模型猜数字。
- RAG：用本地业务知识库为归因报告提供 evidence。
- 可观测性：保存 trace，记录计划、工具结果、RAG 证据、per-node span、延迟和错误类型。
- 自动化评测：用 eval cases 回测意图、工具、证据和回答完整性。
- 稳定性：支持 Redis/内存缓存、fallback、mock 模式、异常捕获和 timeout 预留。
- 工程交付：FastAPI、SQLite、pytest、ruff、mypy、Docker、CI、前端 Demo、文档齐全。

## 1. 为什么要用 Agent？

因为经营诊断不是单轮问答，而是一个多步骤决策流程。用户问“GMV 为什么下降”，系统需要先识别商品和指标，再拆解 GMV、点击率、转化率、客单价、退款率，还要检索活动规则和售后政策，最后生成有证据的报告。

Agent 的价值是把复杂任务拆成可观测、可测试、可复用的节点，而不是把全部逻辑塞进一个 prompt。

## 2. RAG 在项目中起什么作用？

RAG 提供业务知识证据。比如：

- 平台活动规则解释“未参与活动可能影响价格竞争力”
- 售后政策解释“退款率升高可能与物流慢、描述不符、质量问题有关”
- 商品运营指南解释“标题、主图、价格会影响 CTR/CVR”
- 评价分析指南解释“如何从差评中识别续航、物流、佩戴体验等高频问题”

RAG 不直接替代指标结论，而是和 metrics tool 的结果交叉验证。

## 3. 如何降低幻觉？

项目里用了几种方式：

- 指标由 SQLite 工具计算，LLM 不负责生成数字。
- 报告要求引用 `tool_results` 和 `retrieved_docs`。
- Reflection Checker 检查是否缺少关键部分或证据。
- fallback 报告明确标注证据不足，不编造强结论。
- 自动化评测检查关键词、工具调用和 evidence source 命中。
- Trace span 记录每个节点输入/输出摘要，便于审计“结论从哪里来”。

## 4. 如何做 Agent 评测？

`evals/eval_cases.json` 定义典型业务问题，每个 case 包含：

- expected_intent
- expected_tools
- expected_keywords
- expected_evidence_sources
- expected_entity_ids
- expected_tool_result_keys
- expected_trace_fields
- expected_error_nodes
- forbidden_keywords

运行 `python -m evals.run_eval` 后输出：

- intent_accuracy
- avg_keyword_coverage
- evidence_hit_rate
- avg_entity_coverage
- avg_tool_result_key_coverage
- avg_trace_field_coverage
- error_expectation_accuracy
- forbidden_keyword_pass_rate
- avg_latency_ms
- avg_score

新增 case 会覆盖证据冲突、指标缺失、模糊时间范围、多商品多指标混合和证据不足场景。这能把 Agent 输出质量从“看起来不错”变成可量化回测，也能防止 mock 规则只适配单一路径。

## 5. 如何做 fallback？

当前 fallback 分三层：

- LLM 不可用：使用规则模板生成结构化诊断报告。
- RAG 空结果：返回“未检索到足够知识证据”，但流程不中断。
- metrics tool 失败：在 final_answer 中说明数据分析失败原因，并给出降级建议。

生产环境可继续加入重试、熔断、备用模型和任务降级队列。当前缓存层已支持 Redis 连接池优先、内存回退，缓存命中 trace 已下沉到 `CacheService` 统一生成，适合从单机 Demo 平滑升级到多实例部署。

## 6. 如何处理高并发？

当前项目是本地 Demo，但设计上预留了升级路径：

- Redis 连接池缓存热点 query；Redis 不可用时回退内存缓存，避免依赖故障扩大化。
- FastAPI 可改成 async endpoint，数据库层使用连接池。
- 长任务可放入队列，例如 Celery、RQ、Kafka consumer 或云函数任务。
- LLM/RAG/DB 调用设置 timeout、限流和熔断。
- Trace 中记录每个节点耗时、输入摘要、输出摘要和错误类型，用于定位瓶颈。
- Eval 可作为回归测试，避免高并发优化时破坏质量。

## 7. 如何使用 AI 编程工具提升效率？

这个项目适合展示 AI 编程工具的工程化用法：

- 先让 AI 生成项目骨架，再逐步加数据库、工具、RAG、Agent、API、Trace、Eval。
- 每一步都写测试，避免“只生成代码但不能跑”。
- 用 AI 快速生成 mock 数据、文档和面试材料。
- 通过小步迭代让 AI 修失败测试，而不是一次性生成大而不可控的系统。
- 对关键业务逻辑保持人工审查，例如指标口径、异常设计、fallback 和评测规则。

## 可能追问与回答

### 如果真实模型接入后不稳定怎么办？

使用 timeout、retry、fallback、多模型路由和缓存。当前 `LLMService` 已预留 provider 和 timeout，缺少 API Key 自动走 mock。

### 为什么不用模型直接查数据库？

数据库查询和指标计算是高可信任务，应该由工具负责。模型负责理解问题、组织计划和生成解释，不应该凭空生成经营数字。

### 为什么现在用 TF-IDF，不直接用向量数据库？

TF-IDF 无需外部 API，便于本地稳定演示。当前 `vector_store.py` 已经提供 FAISS/Chroma 可选后端，依赖缺失时自动 fallback 到 TF-IDF。这样既能展示生产升级路径，也不牺牲本地可运行性。

### 如何证明 Redis/FAISS/Chroma 不是只写了适配层？

项目补了 `pytest.mark.integration` 集成测试和 CI integration job。Redis 通过 testcontainers 拉起真实 Redis 容器并验证 `CacheService` 写入和读取；FAISS 和 Chroma 在安装对应依赖后会真实构建索引并检索。默认本地没有 Docker 或重依赖时会 skip，不影响日常测试。

### 为什么要做 per-node span？

Agent 失败通常不是“整个系统失败”，而是某个节点慢、某个工具失败或某个检索为空。per-node span 能记录节点耗时、输入摘要、输出摘要和错误类型，方便做 case review、性能分析和后续告警。

### 为什么要把报告生成拆到 ReportService？

状态机节点应该负责状态流转和调用服务，不应该承载大段展示逻辑。拆出 `ReportService` 后，`nodes.py` 更薄，后续可以独立测试报告模板，也方便替换成真实 LLM 或多模板报告生成。

### 这个项目最像真实业务的地方是什么？

指标、知识证据、trace、eval 和 fallback 都具备真实 AI 应用的工程特征。它不是只把问题发给大模型，而是围绕业务诊断建立完整闭环。
