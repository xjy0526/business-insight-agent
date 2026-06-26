# Resume Snippets

## 简历项目标题

BusinessInsight Agent：基于 RAG 与工具调用的电商经营归因 Agent 系统

## 技术栈版本一

Python、FastAPI、SQLite、Pydantic、scikit-learn/TF-IDF、Redis、Docker、pytest、ruff、mypy、GitHub Actions

## 技术栈版本二

Python、FastAPI、LangGraph、Qwen API、SQLite、RAG、Redis、Docker、pytest、GitHub Actions

说明：当前项目默认使用轻量 sequential runner，并提供可选 LangGraph adapter；简历中如果写 LangGraph，建议面试时说明“默认 runner 保证无依赖可运行，设置 `AGENT_RUNNER=langgraph` 并安装 integration 依赖后可启用 LangGraph 条件图”。

## 简历详细版 bullet

- 设计并实现电商经营诊断 Agent，将自然语言问题转化为意图识别、任务规划、工具调用、RAG 检索、经营归因、反思校验和结构化报告生成，覆盖 GMV 下滑、退款率异常、CTR/CVR 异常、差评主题和活动参与不足等场景。
- 构建确定性 Metrics Tool，基于 SQLite 计算 GMV、CTR、CVR、AOV、退款率、渠道拆解和周期对比，并实现 `GMV ≈ Exposure × CTR × CVR × AOV` 的贡献度分解，避免 LLM 编造关键经营数字。
- 新增 Review Tool 与 Campaign Tool，分别从评论表和活动表抽取差评主题、评分变化、活动机会、参与状态和价格竞争力风险，把用户体验和运营动作沉淀为可追踪工具证据。
- 搭建本地 RAG 检索链路，支持 Markdown loader、splitter、TF-IDF 默认检索、FAISS/Chroma 可选 fallback，用售后政策、活动规则、商品运营指南和评价分析指南支撑业务归因。
- 实现 Claim-level Reflection Evidence Checker，对报告结构、claim-evidence 映射、数字一致性和绝对化表达进行规则化校验，降低幻觉并将校验结果写入 Trace/Eval。
- 建设 TraceService 与 Trace Stats 聚合接口，记录 trace_id、tool_results、retrieved_docs、node_spans、latency、error_type、cache_hit，并在前端展示请求量、P95 延迟、intent 分布、慢节点和错误节点。
- 建立自动化 Eval 体系，覆盖 20 个业务与安全 case，计算 intent accuracy、evidence hit、tool result coverage、reflection quality、security flag、avg score，并支持 `full_agent/no_rag/no_review_campaign/no_reflection/no_metrics_tool/mock_only` 消融实验和 CI `fail-under` 门禁。
- 完成 OpenAI/Qwen OpenAI-compatible Provider、Prompt Injection 防护、工具白名单、SQL read-only、Redis/内存缓存 fallback、Docker、pytest、ruff、mypy 和 GitHub Actions CI，保证无 API Key 和可选依赖缺失时仍可本地运行。

## 简历压缩版 bullet

- 实现电商经营归因 Agent，串联 Intent Router、Planner、Metrics/Review/Campaign Tool、RAG、Reflection Evidence Checker、Trace 和 Eval，支持 GMV 下滑、退款率异常、CTR/CVR 异常等诊断场景。
- 基于 SQLite 构建确定性指标工具，计算 GMV、CTR、CVR、AOV、退款率、渠道拆解和 GMV 贡献度，确保关键数字不由 LLM 编造。
- 搭建本地 RAG 与安全防护链路，支持 TF-IDF 默认检索、FAISS/Chroma fallback、Prompt Injection 检测、工具白名单和 SQL read-only。
- 建设 Trace Stats、Eval case、消融实验和 CI 阈值门禁，用 20 个 case 回测 Agent 质量并量化 RAG/工具/Reflection 的组件贡献。

## 1 分钟项目介绍

BusinessInsight Agent 是一个面向电商经营诊断的 Agent 系统。用户可以直接问“商品 P1001 最近 GMV 为什么下降？”，系统会先识别意图和商品，再调用 Metrics Tool 计算 GMV、CTR、CVR、AOV、退款率和渠道拆解，同时用 Review Tool 分析差评主题，用 Campaign Tool 判断活动参与状态，再通过 RAG 检索活动规则、售后政策和运营指南。

这个项目的重点不是让 LLM 自由回答，而是让关键数字来自确定性工具，RAG 提供业务证据，LLM 或模板负责组织报告。最后用 Reflection Evidence Checker 校验每个归因结论是否有证据，并用 Trace 和 Eval 做观测与回测，形成 AI 应用工程闭环。

## 2 分钟项目介绍

BusinessInsight Agent 是我做的一个电商经营归因 Agent 系统，目标是模拟真实业务里“经营问题诊断”的链路。比如用户问“P1001 最近 GMV 为什么下降”，系统不会直接让大模型猜原因，而是进入 Agent 工作流：Prompt Guard 先做安全检查，Intent Router 识别业务意图，Planner 规划工具调用，Metrics Tool 计算 GMV、CTR、CVR、AOV、退款率和渠道拆解。

在指标之外，我还做了 Review Tool 和 Campaign Tool。Review Tool 从评论表统计差评率、评分变化、续航/物流/佩戴等差评主题；Campaign Tool 从活动表判断商品所在类目是否有活动机会、参与是否不足、价格竞争力风险是否高。RAG 负责检索活动规则、售后政策、商品运营指南和评价分析指南，给报告提供业务规则证据。

工程上我重点做了三件事。第一是 Reflection Evidence Checker，它会抽取主要归因 claim，检查这些结论是否有工具或 RAG 支撑，并检查百分比数字和绝对化表达。第二是 Trace Observability，每次 Agent 执行都会保存 trace_id、tool_results、retrieved_docs、node_spans、latency 和 error_type，并提供聚合 stats 和前端 Dashboard。第三是 Eval & Ablation，用 20 个 case 回测 intent、evidence、tool coverage、reflection 和 security，并支持 no_rag、no_metrics_tool、mock_only 等消融模式，证明每个组件的价值。

这个项目适合展示 AI 应用工程能力：不是简单套一个聊天接口，而是把 Tool Calling、RAG、Trace、Eval、Fallback、安全防护和 CI 串成完整闭环。

## 项目 GitHub 展示关键词

`Agent`、`RAG`、`Tool Calling`、`Business Diagnosis`、`E-commerce Analytics`、`Trace Observability`、`Evaluation`、`Ablation Study`、`Fallback`、`Prompt Injection Defense`、`FastAPI`、`SQLite`、`Redis`、`Docker`、`CI`

## 面试中可强调的数字

- Eval cases：20 个
- Full agent avg_score：0.991733
- Full agent evidence_hit_rate：1.0
- no_rag evidence_hit_rate：0.1
- mock_only avg_score：0.681883
- 测试覆盖：pytest 本地 100 passed, 2 skipped

这些数字来自本地 demo 数据和规则评测，适合作品集展示；如果接入真实业务，应替换为真实历史 case 和人工标注集。
