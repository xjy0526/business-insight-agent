# Interview Notes

这份材料用于面试前复习。回答可以按自己的表达习惯调整，但建议始终强调三点：关键数字由确定性工具计算，LLM 负责理解和表达，Trace/Eval/Fallback 是 AI 应用工程闭环。

## 1. 这个项目解决了什么问题？

这个项目解决的是电商经营诊断中的“归因和决策辅助”问题。比如业务同学问“商品 P1001 最近 GMV 为什么下降？”，系统不能只给一段泛泛建议，而要拆解 GMV、CTR、CVR、AOV、退款率、差评主题、活动参与等证据，再给出有依据的分析报告。

我把它做成一个 Agent + RAG + Tool Calling 系统。Agent 负责理解问题和编排任务，工具负责计算确定性指标，RAG 负责补充业务规则，Reflection 负责证据校验，Trace 和 Eval 负责观测与回测。

## 2. 为什么要用 Agent，而不是直接问 LLM？

直接问 LLM 的问题是不可控：它可能猜数字、漏掉关键指标，也很难解释每个结论来自哪里。经营诊断是多步骤任务，需要先识别商品和指标，再调用工具算数，再检索业务知识，最后做证据校验和结构化报告。

Agent 的价值是把这条链路拆成可测试、可追踪的节点。这样每一步都能看输入输出、能做 fallback、能进 Eval，而不是把所有逻辑塞进一个 prompt。

## 3. Agent 架构怎么设计？

当前链路是 Prompt Guard、Intent Router、Planner、Metrics/Review/Campaign Tool、RAG Retriever、Diagnosis Generator、Reflection Evidence Checker、Evidence Repair、Final Report。每个节点只做一类事情，状态通过 `AgentState` 传递。

这个设计的好处是职责清楚。工具节点只负责拿事实，RAG 节点只负责拿知识证据，报告节点只负责组织表达，Reflection 节点只负责检查结论是否有证据。Trace 会记录每个节点的耗时、输入摘要、输出摘要和错误类型。

## 4. 为什么第一版使用顺序状态机？如何升级 LangGraph？

第一版我优先保证本地可运行和 CI 稳定，所以默认使用轻量顺序/条件 runner。这样没有 LangGraph、Redis、FAISS、Chroma 或真实 API Key 时，项目仍然能完整跑通，适合作品集和面试演示。

现在项目已经有可选 LangGraph adapter：设置 `AGENT_RUNNER=langgraph` 并安装 integration 依赖后，会用 `tool_router` 条件边选择 Metrics Tool 或 RAG；Reflection 不通过且 `retry_count < 1` 时，会回到 RAG Retriever 补充证据后重新生成报告。业务节点没有重写，只是通过 `state_to_dict()` / `dict_to_state()` 适配 LangGraph 的 dict state。

如果 LangGraph 没安装或执行失败，会自动 fallback 到 sequential，并在 `tool_results.runner_fallback` 里记录原因。后续真正生产化可以在这个 adapter 上继续加 checkpoint、子图和可视化 tracing。

## 5. Metrics Tool 解决什么问题？

Metrics Tool 解决“关键业务数字必须可信”的问题。GMV、CTR、CVR、AOV、退款率、渠道拆解这些指标都来自 SQLite 数据表，由工具确定性计算，不能让 LLM 自由生成。

在报告里，LLM 或模板只是解释这些数字，不负责创造这些数字。这样做能显著降低幻觉，也方便 Trace、Eval 和 Evidence Checker 校验每个结论有没有来源。

## 6. GMV 为什么拆成 Exposure × CTR × CVR × AOV？

GMV 下降本身只是结果，业务真正关心的是下降来自哪里。`Exposure × CTR × CVR × AOV` 对应电商漏斗的关键环节：曝光代表流量供给，CTR 代表点击吸引力，CVR 代表转化承接，AOV 代表客单结构。

项目里用单因子替换法做近似贡献度分解。它不追求严格经济学归因，但解释成本低，能让报告从“GMV 降了”推进到“优先修搜索点击率、转化承接还是客单结构”。

## 7. Review Tool 和 Campaign Tool 为什么有必要？

Metrics Tool 能回答“发生了什么”，但不一定能回答“为什么可能发生”。Review Tool 从评论表里统计差评率、评分变化、差评主题和样例评论，能把退款率和转化问题连接到续航、物流、佩戴体验等用户体验因素。

Campaign Tool 则把活动参与状态做成结构化工具结果。它会判断商品所在类目是否有活动机会、商品参与是否不足、价格竞争力风险是否高。这样“活动参与不足”不再只是 RAG 里的泛泛解释，而是可追踪的业务事实。

## 8. RAG 在项目里起什么作用？

RAG 负责提供业务规则和方法论证据，比如活动规则、售后政策、商品运营指南、评价分析指南。它适合处理非结构化知识，帮助解释为什么活动参与、主图标题、物流体验会影响 CTR、CVR 或退款率。

但 RAG 不替代工具事实。工具回答“P1001 四月 CTR 降了多少”，RAG 解释“主图、标题、价格利益点可能影响点击率”。这个边界很重要。

## 9. 如何评价 RAG 效果？

我用 eval case 中的 `expected_evidence_sources` 和 `evidence_hit_rate` 来评价 RAG 是否命中正确证据。比如 GMV 下滑和活动参与不足 case 应该命中 `campaign_rules.md`，退款率和差评 case 应该命中售后政策或评价分析指南。

另外我做了 `no_rag` 消融实验。完整链路 evidence hit rate 是 1.0，禁用 RAG 后降到 0.1，这能说明 RAG 对证据命中确实有贡献，而不是只在架构图里画了一层。

## 10. 如何降低幻觉？

第一，关键数字全部来自工具，不让 LLM 编造 GMV、CTR、CVR、退款率。第二，RAG 只作为证据上下文，不能覆盖系统指令。第三，Reflection Evidence Checker 会检查报告结构、数字一致性、claim 是否有工具或 RAG 支撑。

另外还有 fallback 和 eval。证据不足时报告会明确写“待确认”或说明缺少指标证据；Eval 会检查 forbidden keywords，避免模型输出“唯一原因”“必然”等绝对化表达。

## 11. Reflection Evidence Checker 如何工作？

它不是让 LLM 自我反思，而是规则化证据校验。第一层检查报告结构是否包含问题概述、指标拆解、主要归因、证据来源和优化建议。第二层从“主要归因”中抽取 claim，并按关键词归类为 GMV、traffic、conversion、after_sales、campaign。

然后把每个 claim 映射到证据。比如 traffic claim 需要渠道拆解或周期对比，campaign claim 需要 Campaign Tool 或 `campaign_rules.md`，after-sales claim 需要退款指标、Review Tool 或售后文档。最后还会检查百分比数字是否能在 tool_results 中找到近似来源，以及证据不足时是否出现绝对化措辞。

## 12. Trace 记录什么？怎么用？

Trace 记录单次 Agent 的完整执行链路，包括 `trace_id`、用户问题、意图、计划步骤、工具结果、RAG evidence、最终回答、Reflection 结果、node spans、缓存命中、延迟和错误类型。

单次 Trace 用于复盘“这次为什么这么回答”，聚合 Trace Stats 用于看请求量、P95 延迟、缓存命中率、intent 分布、错误节点和慢节点排行。这样 Trace 不只是日志，而是可以变成可观测指标。

## 13. Eval 怎么设计？

Eval 是 case-based 的。每个 case 写清楚 expected intent、expected tools、expected keywords、expected evidence sources、expected entity ids、expected tool result keys、expected trace fields、forbidden keywords 等。

运行 `python -m evals.run_eval` 会逐个调用真实 Agent 链路，计算 intent accuracy、keyword coverage、evidence hit、tool result coverage、trace field coverage、reflection quality、security flag 和 avg score。CI 里用 `--fail-under` 做阈值门禁。

## 14. 为什么要做 ablation？

只看 full_agent 分数，无法证明每个组件真的有用。消融实验会禁用 RAG、Review/Campaign Tool、Reflection、Metrics Tool 或尽量只用 mock/fallback，再对比分数和 evidence hit。

比如 `no_rag` 后 evidence hit 明显下降，说明 RAG 对证据命中有贡献；`no_metrics_tool` 后工具结果覆盖率和总分下降，说明确定性工具对数字可靠性有贡献。这个比“我觉得架构合理”更有说服力。

## 15. 缓存和 fallback 怎么设计？

缓存层优先 Redis，Redis 不可用时自动回退内存缓存。缓存命中也会写轻量 Trace，避免因为缓存绕过观测链路。缓存 key 使用 query 摘要，响应里也会返回 cache 信息。

Fallback 分多层：LLM 没有 API Key 或调用失败时走 mock；RAG 后端 FAISS/Chroma 不可用时回退 TF-IDF；指标工具失败或被消融禁用时，报告会说明缺少指标证据而不是编造结论。这个设计保证本地、CI 和面试演示都稳定。

## 16. 高并发场景怎么优化？

当前项目是本地 Demo，但升级路径比较清晰。API 可以改成 async，数据库从 SQLite 替换为指标服务或数仓 API，缓存用 Redis 做热点 query 和请求去重，长任务放到 Celery、RQ、Kafka consumer 或云函数任务队列。

另外要对 LLM、RAG、DB 调用设置 timeout、限流、重试和熔断。现在 Trace 里已经有 node span、latency、token usage、provider status、retry count 和轻量告警，用 P95、slowest node、provider status 分布可以定位瓶颈和外部服务波动。

## 17. Prompt Injection 怎么防？

我把用户输入和 RAG 文档都当成不可信上下文。用户问题先经过 Prompt Guard，检测“忽略之前指令”“输出系统提示词”“drop table”“bypass safety”等模式，保留合法业务问题，忽略或标记注入式片段。

RAG chunk 返回前也会做同样检测，后续 LLM 输入优先使用 `sanitized_content`。工具层还有 allowlist，SQL Tool 只允许 read-only SELECT，最终输出还会过滤 API Key 和 Bearer token。

## 18. 如果接入真实阿里业务，你会怎么改？

第一，把 SQLite seed 数据替换成真实指标服务或数仓接口。项目里已经有 `MetricsGateway`，可以通过 `METRICS_BACKEND=http` 和 `METRICS_SERVICE_URL` 接入指标服务，同时保留 SQLite fallback；真正生产化时再加鉴权、指标 DSL、口径版本和灰度路由。第二，把 Campaign Tool 接入真实活动报名、资源位曝光、券核销、活动 GMV uplift 等字段。

第三，RAG 要接入真实知识库和 embedding 服务。当前已经有 source allowlist、index manifest 和增量刷新入口，后续可以替换为企业知识库权限、文档版本和向量索引持久化；Trace 要接入公司内部观测平台；Eval 要加入真实历史 case、人工标注和线上回归集。模型层可以接 Qwen/DashScope，并加限流、成本统计和多模型 fallback。

## 19. 这个项目和普通套壳 Demo 有什么区别？

普通套壳 Demo 通常是一个 prompt 加一个聊天界面，很难解释数字从哪里来，也很难做回归测试。这个项目从一开始就把工具、RAG、Trace、Eval、Fallback 和 Safety 做成工程闭环。

面试时我会强调：它不是“让模型回答经营问题”，而是“让 Agent 编排可审计工具和证据”。关键数字可复现，证据可追踪，失败可降级，质量可回测，这些才是 AI 应用工程真正落地时需要的能力。

## 20. 你如何使用 AI 编程工具完成这个项目？

我把 AI 编程工具当成工程协作助手，而不是一次性代码生成器。每一轮都先限定目标，例如先做基线审计，再做 Provider、GMV 分解、Review/Campaign Tool、Evidence Checker、Safety、Trace Stats、Eval Ablation，最后补文档和面试材料。

关键做法是小步增量、每步补测试、每步跑 ruff/mypy/pytest/eval。AI 可以提高编码和文档速度，但指标口径、fallback 策略、安全边界、eval 权重这些关键设计需要人工审查。这个项目本身也体现了这种工作方式：不是追求生成很多代码，而是形成可运行、可验证、可讲解的系统。
