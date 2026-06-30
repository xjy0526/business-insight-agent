# 项目报告摘要版

本文设计并实现了一个面向本地生活商户的商品级广告增长决策 Agent。
系统基于 Tool Calling 与 RAG，将经营归因、主推品挖掘、Query-SKU 召回、
ROI 出价守护和证据约束型报告生成整合在同一条可观测工作流中。

项目使用 synthetic demo data，不涉及真实平台、真实商户、真实用户或敏感业务信息。
完整项目报告正文见 [final_report.md](final_report.md)。

## 问题建模

输入包括用户自然语言 query、结构化经营数据、商品广告候选数据、
广告实验数据、Query-SKU 召回数据和策略知识库。

输出为主推品排序、出价区间、召回路径解释、ROI 风险提示、
证据对齐表和结构化建议报告。

核心任务包括：

- 经营归因：解释 GMV、CTR、CVR、退款率、活动参与等变化。
- 商品增长评分：基于 CVR、GMV share、PCVR、historical ROI、
  档期、评分、关键词覆盖和退款风险生成 Product Growth Score。
- ROI 出价守护：基于 `pcvr * price / target_roi` 和
  `pcvr * price * margin_rate / target_roi` 计算 CPC 上限。
- Query-SKU 召回：先使用 exact demo rows，再使用 deterministic TF-IDF fallback。
- 证据对齐：强结论必须能映射到 tool result 或 RAG 文档。

## 方法设计

系统工作流包括 Prompt Guard、Intent Router、Planner、Metrics Tool、
Product Ad Tool、RAG Retriever、Recommendation Scorer、
Reflection Checker 和 Final Report Generator。

Product Growth Score 使用加权规则：

```text
0.25 * norm(CVR)
+ 0.25 * norm(GMV share)
+ 0.20 * norm(PCVR)
+ 0.15 * norm(historical ROI)
+ 0.05 * norm(available slots)
+ 0.05 * norm(rating)
+ 0.05 * norm(keyword coverage)
- 0.15 * norm(refund rate)
```

Query 场景下的融合排序：

```text
final_score =
  0.45 * product_growth_score
+ 0.35 * recall_score
+ 0.15 * roi_score
+ 0.05 * keyword_coverage_score
- refund_risk_penalty
- non_recall_penalty
```

## 实验设计

评测集保留原经营归因 case，并新增商品级广告、主推品挖掘、
出价守护、Query-SKU 召回、POI vs Product Ad 对比、prompt injection、
商品不存在、商户不存在、Query 未命中、高目标 ROI 和退款率风险 hard cases。

运行命令：

```bash
python -m evals.run_eval --all-modes --fail-under 0.70
python -m evals.run_ablation
```

指标包括 `intent_accuracy`、`keyword_coverage`、`tool_usage`、
`evidence_hit`、`ad_recommendation_fields`、`bid_guardrail`、
`sku_recall_fields`、`claim_evidence_alignment`、`numeric_bid_correctness`、
`reflection_quality`、`security_flag`、`no_default_entity_leakage`
和 `hard_case_uncertainty`。

## Reflection 作用与局限

Reflection Checker 主要用于 trace/evidence repair/safety audit。
在当前 deterministic demo 中，报告模板和工具输出已经较稳定，
因此 `no_reflection` 与 `full_agent` 的主分差异可能有限。

它的价值更多体现在真实 LLM 输出场景：
当模型生成更自由的自然语言报告时，Reflection 可以检查 claim 是否有证据、
数字是否与工具一致、是否出现绝对化结论，并在必要时触发补证。

最新评测摘要：

| Mode | Avg Score | Evidence Hit Rate | Reflection Quality |
| --- | ---: | ---: | ---: |
| `full_agent` | 0.974587 | 1.0 | 0.485606 |
| `no_rag` | 0.938718 | 0.590909 | 0.480303 |
| `no_reflection` | 0.965735 | 1.0 | 0.2 |
| `no_metrics_tool` | 0.899390 | 0.977273 | 0.2 |

`no_reflection` 相比 `full_agent` 的 `avg_score_delta=-0.008852`，
`reflection_quality_delta=-0.285606`。

## Case Study

`商户 M001 应该优先推哪些商品做搜索广告？`

系统识别为 `product_ad_strategy`，调用 `mine_high_value_products`
和 `rank_ad_candidates`。P1001 表示“水光补水体验套餐”，
因 CVR、GMV 占比、PCVR 和历史 ROI 较高成为候选主推品。
报告同时提示退款率、预约履约和服务体验风险，避免只看增长分。

`目标 ROI 为 4.5 时，P1001 加价 20% 还安全吗？`

系统识别 `target_roi=4.5`、`product_id=P1001`、`bid_multiplier=1.2`。
工具重新计算 CPC 上限，并在模拟结果中给出 `roi_status=risk`
和 `guardrail_action=down_bid`。

`用户搜索 水光补水 时，应该召回哪些商品，为什么？`

系统调用 `recall_query_to_sku`，展示 `keyword_inverted`、
`query_expansion`、`vector_match` 等召回路径，并结合增长分、
ROI 和退款风险输出候选顺序。

## 未来工作

未来可扩展更真实的预算分配模型、跨商户类目归一化、学习排序模型、
向量检索后端、可视化投放实验面板、更细粒度的证据一致性检测
和更大规模人工标注 eval。
