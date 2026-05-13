# Demo Cases

## Case 1：P1001 GMV 下滑归因

用户问题：

```text
商品 P1001 最近 GMV 为什么下降？
```

预期分析点：

- 识别意图为 `business_diagnosis`
- 对比 2026 年 4 月和 3 月 GMV
- 拆解 CTR、CVR、AOV、退款率
- 发现 P1001 4 月 GMV 下降、退款率升高、search 点击率下降
- RAG 引用活动规则、售后政策、商品运营指南

展示重点：

- 前端报告中有清晰的“指标拆解”和“主要归因”
- 调试区可以看到 `tool_results`
- Trace 中可以看到完整执行链路

## Case 2：P1001 退款率异常

用户问题：

```text
P1001 的退款率最近是不是异常？
```

预期分析点：

- 识别意图为 `refund_analysis`
- 对比 4 月和 3 月退款率
- RAG 命中 `after_sales_policy.md` 和 `review_analysis_guide.md`
- 结合差评高频词解释物流慢、续航不达预期、佩戴不舒服等可能原因

展示重点：

- 强调数字来自 metrics tool，不是 LLM 编造
- 强调 RAG evidence 只做证据支撑，不直接代替结论

## Case 3：搜索渠道点击率下降

用户问题：

```text
P1001 搜索渠道点击率为什么下降？
```

预期分析点：

- 识别意图为 `traffic_analysis`
- 重点关注 search 渠道 CTR
- 结合商品运营指南分析标题、主图、价格展示、活动利益点
- 给出主图、标题、到手价和竞品卡片对比建议

展示重点：

- 展示渠道拆解能力
- 展示 RAG 对“主图/标题影响 CTR”的解释

## Case 4：差评高频问题

用户问题：

```text
商品 P1001 差评集中在哪些问题？
```

预期分析点：

- 识别意图为 `review_analysis`
- RAG 命中评价分析指南
- 报告关注续航、物流、佩戴体验等高频问题
- 建议结合退款率和售后原因进一步验证

展示重点：

- 展示 Agent 不只看指标，还会检索业务知识
- 展示“证据不足时不编造”的报告风格

## Case 5：多商品对比

用户问题：

```text
请对比 P1001 和 P1002 四月 GMV 表现，判断 P1001 是否异常
```

预期分析点：

- 主分析对象为 `P1001`
- `related_entity_ids` 中保留 `P1002`
- `tool_results.peer_period_comparisons` 给出对比商品指标
- 报告中出现 P1002 作为参照，说明 P1001 是否更像个体异常

展示重点：

- 展示 AgentState 能承载多实体上下文
- 展示报告生成逻辑已经拆到 `ReportService`

## 演示路径

1. 启动服务：`uvicorn app.main:app --reload`
2. 打开前端：`http://localhost:8000`
3. 点击示例问题
4. 展示报告、trace_id、latency_ms
5. 展开 `tool_results` 和 `retrieved_docs`
6. 调用 `GET /api/traces/{trace_id}` 展示可观测性和 `node_spans`
7. 调用 `POST /api/evals/run` 展示自动化评测
