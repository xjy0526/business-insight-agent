# Model Card

## 系统类型

BusinessInsight Agent 不是端到端大模型自动决策系统。
它是 Tool Calling + RAG + deterministic scorer + report generation 的工程演示系统。

关键数字由 SQLite 工具计算，包括 GMV、CTR、CVR、退款率、
Product Growth Score、Query-SKU recall score、CPC 上限和 ROI guardrail。

LLM 或 mock LLM 只负责意图理解、报告组织和表达，
不允许覆盖工具计算出的事实数字。

## 决策链路

1. `Intent Router` 识别经营归因、主推品挖掘、Query-SKU 召回、出价守护等意图。
2. `Product Ad Tool` 读取 synthetic demo data，执行主推品评分、召回、排序和出价模拟。
3. `RAG Retriever` 检索本地 Markdown 策略知识，作为报告证据。
4. `Recommendation Scorer` 汇总工具结果和证据来源。
5. `Report Generator` 生成结构化中文报告，并标注不确定性。
6. `Reflection Checker` 做证据一致性、数字一致性和绝对化表达检查。

## Reflection 作用

Reflection Checker 主要用于 trace/evidence repair/safety audit。
在当前 deterministic demo 中，报告模板和工具输出已经较稳定，
因此它对主分数的提升可能有限。

在真实 LLM 输出更自由的场景中，Reflection 更重要：
它可以发现缺少证据的 claim、工具数字不一致、绝对化表达和安全风险，
并触发补证或降级。

## 适用场景

- GitHub 项目展示、工程方案讲解。
- 演示 Agentic workflow、Tool Calling、RAG、Eval、Trace、Ablation 和 fallback。
- 使用 synthetic demo data 说明本地生活商品级广告增长决策抽象。

## 不适用场景

- 真实商户投放决策。
- 真实预算分配、线上竞价、智能调价生产策略。
- 任何需要真实平台数据、实时竞价数据或线上实验结论的场景。

## 风险与限制

- 数据为 synthetic demo data，规模和分布均被简化。
- 实体解析、Query 解析和关键词评测是规则化实现，可能漏召回或误判模糊问题。
- Eval 使用关键词、结构字段和数值一致性检查，不能完全替代人工业务评审。
- 无真实线上 A/B 实验，ROI 结论只能作为工程演示中的 guardrail 示例。
- 可选真实 LLM 只用于 phrasing，不应生成或修改工具事实。
