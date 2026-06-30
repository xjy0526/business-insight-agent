# 面向本地生活商户的商品级广告增长决策 Agent

## 1. 摘要

本文设计并实现了一个面向本地生活商户的商品级广告增长决策 Agent。
系统基于 Tool Calling 与 RAG，将经营归因、主推品挖掘、Query-SKU 召回、
ROI 出价守护和证据约束型报告生成整合在同一条可观测工作流中。

项目使用 synthetic demo data，不涉及真实平台、真实商户、
真实用户或敏感业务信息。本仓库为忻纪元课程设计 GitHub 项目提交。

## 2. 背景

本地生活商户既关注门店整体曝光，也关注具体服务项目、团购套餐或爆品的投放效果。
POI 级广告适合泛需求，但当用户搜索“水光补水”“美甲款式”“双人烤肉”等明确服务时，
商品级广告能更直接承接用户意图。

课程设计将该问题抽象为平台经济中的商户增长和搜索广告匹配效率问题。
系统需要回答“推什么商品”“哪些 Query 可以召回”“加价是否守住 ROI”
以及“结论是否有工具或知识证据支撑”。

## 3. 问题建模

输入包括：

- 用户自然语言 query。
- 结构化经营数据、商品广告候选数据、广告实验数据和 Query-SKU 召回数据。
- 本地 Markdown 策略知识库。

输出包括：

- 主推品排序。
- 出价区间和 ROI guardrail。
- 召回路径解释。
- 风险提示。
- 证据对齐表和结构化建议报告。

核心任务包括经营归因、商品增长评分、ROI 出价守护、Query-SKU 召回和证据对齐。

## 4. 相关工作

Insight Agents 关注电商卖家数据洞察、多 Agent 协作、plan-and-execute
风格分析和业务洞察生成。它说明 LLM Agent 可以把自然语言问题拆解为
数据访问、分析计划和洞察报告。

ProductAgent 聚焦商品搜索中的需求澄清、动态检索和商品推荐交互。
它更接近搜索/推荐链路中的对话式商品发现。

传统 BI / Dashboard 能展示指标和图表，但通常难以自动完成跨表归因、
策略证据检索、风险校验和结构化建议生成。当问题涉及“为什么下降”
“推什么商品”“出价是否安全”时，只看 dashboard 往往还需要人工串联指标、
规则和策略。

本项目差异在于：

- 聚焦本地生活商品级广告增长。
- 将经营归因、主推品挖掘、ROI guardrail、Query-SKU 召回和 Eval
  统一到可观测 Agent workflow。
- 关键数字由工具计算，报告由 RAG 和 evidence alignment 约束。

## 5. 方法设计

系统工作流包括 Prompt Guard、Intent Router、Planner、Metrics Tool、
Product Ad Tool、RAG Retriever、Recommendation Scorer、Reflection Checker
和 Final Report Generator。

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

ROI 出价上限：

```text
expected_revenue_per_click = pcvr * price
max_cpc_by_revenue_roi = expected_revenue_per_click / target_roi

expected_profit_per_click = pcvr * price * margin_rate
max_cpc_by_profit_roi = expected_profit_per_click / target_roi
```

## 6. 系统实现

后端基于 FastAPI、SQLite 和 Python 工具函数实现。
`app/tools/product_ad_tool.py` 提供主推品挖掘、出价区间估计、
Query-SKU 召回、候选排序、加价模拟、POI vs Product Ad 对比
和数据一致性校验。

`app/agent/entity_parser.py` 集中解析 `merchant_id`、`product_id`、
`poi_id`、`target_roi`、`bid_multiplier`、`search_query`、预算受限、
退款风险和对比意图，避免规则散落。

`ReportService` 在商品级广告报告中输出证据对齐表，标注 fallback candidate
和 synthetic data 不确定性。

前端 Product Ads tab 展示主推品排序、出价区间、Query-SKU 召回、
POI vs 商品级广告对比和 JSON trace。

## 7. 实验设计

评测集保留原经营归因 case，并新增商品级广告、主推品挖掘、出价守护、
Query-SKU 召回、POI vs Product Ad 对比、prompt injection、商品不存在、
商户不存在、Query 未命中、高目标 ROI 和退款率风险 hard cases。

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

## 8. 实验结果

最新结果由 `python -m evals.run_eval --all-modes --fail-under 0.70`
重新生成，并写入 `evals/eval_latest_summary.json`。

报告关注：

- `full_agent` 的平均分和阈值门禁。
- `no_rag` 与 `full_agent` 的 evidence hit 差异。
- `no_metrics_tool` 与 `full_agent` 的数字可靠性差异。
- `no_reflection` 与 `full_agent` 的 reflection quality 差异。

| Mode | Avg Score | Evidence Hit Rate | Reflection Quality |
| --- | ---: | ---: | ---: |
| `full_agent` | 0.974587 | 1.0 | 0.485606 |
| `no_rag` | 0.938718 | 0.590909 | 0.480303 |
| `no_reflection` | 0.965735 | 1.0 | 0.2 |
| `no_metrics_tool` | 0.899390 | 0.977273 | 0.2 |
| `mock_only` | 0.839828 | 0.590909 | 0.2 |

Reflection Checker 主要用于 trace/evidence repair/safety audit。
在当前 deterministic demo 中，报告模板和工具输出已经较稳定，
因此 `no_reflection` 与 `full_agent` 的主分差异可能有限。

`no_reflection` 相比 `full_agent` 的 `avg_score_delta=-0.008852`，
`reflection_quality_delta=-0.285606`。

这不是设计缺陷，而是 demo 环境的边界：
真实 LLM 输出更自由时，Reflection 对绝对化结论、证据缺失和数字不一致
会更重要。

## 9. 消融实验

课程消融实验包括：

| Mode | 说明 |
| --- | --- |
| `full_product_ad_agent` | 完整 Agent：metrics + product_ad_tool + RAG + recommendation + reflection |
| `llm_or_template_only` | 不调用指标、商品广告工具、RAG 或 Reflection，仅保留模板链路 |
| `metrics_only` | 只调用经营指标工具，不调用商品广告工具和 RAG |
| `product_ad_tools_only` | 调用商品广告工具，但不使用 RAG |
| `rag_plus_metrics` | 使用指标工具和 RAG，但禁用商品广告推荐分数 |

消融的目标不是证明某个组件单独“万能”，而是观察组件组合对证据命中、
数字可靠性、ROI guardrail 和召回解释的贡献。

## 10. Case Study

### 主推品挖掘

用户问题：

```text
商户 M001 应该优先推哪些商品做搜索广告？
```

系统识别为 `product_ad_strategy`，调用 `mine_high_value_products`
和 `rank_ad_candidates`。P1001 表示“水光补水体验套餐”，
因 CVR、GMV 占比、PCVR 和历史 ROI 较高成为候选主推品。
报告同时提示退款率、预约履约和服务体验风险，避免只看增长分。

### ROI 出价守护

用户问题：

```text
目标 ROI 为 4.5 时，P1001 加价 20% 还安全吗？
```

系统识别 `target_roi=4.5`、`product_id=P1001`、`bid_multiplier=1.2`。
工具重新计算 `max_cpc_by_revenue_roi` 和 `max_cpc_by_profit_roi`，
并在模拟结果中给出 `roi_status=risk`、`guardrail_action=down_bid`。

### Query-SKU 召回

用户问题：

```text
用户搜索 水光补水 时，应该召回哪些商品，为什么？
```

系统调用 `recall_query_to_sku`，展示 `keyword_inverted`、
`query_expansion`、`vector_match` 等召回路径，并在融合排序中结合
`recall_score`、Product Growth Score、ROI 和退款风险输出候选顺序。

## 11. 错误分析

风险 case 1：商品不存在。

`P9999 如果做主推品加价，合理出价区间是多少？`
返回商品 ID 未找到，无法计算出价区间，需要补充有效商品 ID。
系统不输出推荐出价，避免默认泄漏到 P1001。

风险 case 2：Query 模糊或未命中。

`用户搜索 火星露营套餐 时，应该召回哪些商品？`
会先说明未命中 exact demo rows，再尝试 TF-IDF fallback。
若相似度不足，返回空结果和不确定性说明。

风险 case 3：高目标 ROI。

当目标 ROI 为 4.5 时，即使 P1001 有 GMV 占比优势，
也会因为模拟 ROI 低于目标而输出 risk/down_bid，不建议继续加价。

风险 case 4：退款率偏高。

`P1001 退款率偏高但 GMV 占比高，还应该提高出价吗？`
会同时调用 metrics 和 product_ad 工具，将 GMV 占比与退款率风险
放在同一证据表中，输出谨慎建议。

主要误差来源包括 synthetic data 与实际线上分布差异、Query 解析规则较简单、
Product Growth Score 权重为课程展示设定、召回模拟未接入线上向量库，
以及 Eval 中关键词/结构化指标无法完全替代人工评审。

## 12. 贡献说明

本项目贡献包括：

- 将经营归因与商品级广告决策结合到同一 Agent workflow。
- 设计 Product Growth Score、Query-SKU 融合排序和 ROI 约束 CPC 区间。
- 增强 hard case eval，加入数值正确性、默认实体泄漏、不确定性表达、
  reflection quality 和 security flag 检查。
- 统一 P1001 在经营归因和商品广告模块中的语义，
  使其均表示“水光补水体验套餐”。
- 新增数据卡、模型卡、Notebook 执行脚本、Makefile、CI hardening
  和课程提交说明。

## 13. 未来工作

未来可扩展更真实的预算分配模型、跨商户类目归一化、学习排序模型、
向量检索后端、可视化投放实验面板、更细粒度的证据一致性检测
和更大规模人工标注 eval。

## 14. 参考文献

参考文献列表和链接见 [references.md](references.md)。
