# 摘要

本文设计并实现了一个面向本地生活商户的商品级广告增长决策 Agent。系统基于 Tool Calling 与 RAG，将经营归因、主推品挖掘、Query-SKU 召回、ROI 出价守护和证据约束型报告生成整合在同一条可观测工作流中。项目使用 synthetic demo data，不包含任何公司内部数据、真实商户数据或敏感业务策略。

# 背景

本地生活商户既关注门店整体曝光，也关注具体服务项目、团购套餐或爆品的投放效果。POI 级广告适合泛需求，但当用户搜索“水光补水”“美甲款式”“双人烤肉”等明确服务时，商品级广告能更直接承接用户意图。

课程设计将该问题抽象为平台经济中的商户增长和搜索广告匹配效率问题：系统需要回答“推什么商品”“哪些 Query 可以召回”“加价是否守住 ROI”“结论是否有工具或知识证据支撑”。

# 问题建模

输入包括用户自然语言 query、结构化经营数据、商品广告候选数据、广告实验数据、Query-SKU 召回数据和策略知识库。输出为主推品排序、出价区间、召回路径解释、ROI 风险提示、证据对齐表和结构化建议报告。

核心任务包括：

- 经营归因：解释 GMV、CTR、CVR、退款率、活动参与等变化。
- 商品增长评分：基于 CVR、GMV share、PCVR、historical ROI、档期、评分、关键词覆盖和退款风险生成 Product Growth Score。
- ROI 出价守护：基于 `pcvr * price / target_roi` 和 `pcvr * price * margin_rate / target_roi` 计算 CPC 上限。
- Query-SKU 召回：先使用 exact demo rows，再使用 deterministic TF-IDF fallback。
- 证据对齐：强结论必须能映射到 tool result 或 RAG 文档。

# 相关工作

Insight Agents 更偏向电商卖家数据洞察、多 Agent 协作和 plan-and-execute 风格的经营分析。ProductAgent 聚焦商品搜索中的需求澄清和动态检索，更接近搜索/推荐交互链路。

本项目差异在于聚焦本地生活商品级广告增长，把经营归因、主推品挖掘、ROI 守护、Query-SKU 召回和 Eval 统一到可观测 Agent Workflow 中，并强调 deterministic demo、trace、ablation 和课程提交可复现性。

# 方法设计

系统工作流包括 Prompt Guard、Intent Router、Planner、Metrics Tool、Product Ad Tool、RAG Retriever、Recommendation Scorer、Reflection Checker 和 Final Report Generator。

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

高目标 ROI、商品不存在、商户不存在、Query 未命中、退款率偏高等 hard cases 必须输出谨慎表达，禁止“保证提升”“一定安全”等强结论。

# 系统实现

后端基于 FastAPI、SQLite 和 Python 工具函数实现。`app/tools/product_ad_tool.py` 提供主推品挖掘、出价区间估计、Query-SKU 召回、候选排序、加价模拟、POI vs Product Ad 对比和数据一致性校验。

`app/agent/entity_parser.py` 集中解析 `merchant_id`、`product_id`、`poi_id`、`target_roi`、`bid_multiplier`、`search_query`、预算受限、退款风险和对比意图，避免规则散落。`ReportService` 在商品级广告报告中输出证据对齐表，标注 fallback candidate 和 synthetic data 不确定性。

前端新增 Product Ads tab，展示主推品排序、出价区间、Query-SKU 召回、POI vs 商品级广告对比和 JSON trace。课程 Notebook 通过 `python scripts/execute_notebook.py` 执行并保存输出。

# 实验设计

评测集保留原经营归因 case，并新增商品级广告、主推品挖掘、出价守护、Query-SKU 召回、POI vs Product Ad 对比、prompt injection、商品不存在、商户不存在、Query 未命中、高目标 ROI 和退款率风险 hard cases。

运行命令：

```bash
python -m evals.run_eval --all-modes --fail-under 0.70
python -m evals.run_ablation
```

指标包括 `intent_accuracy`、`keyword_coverage`、`tool_usage`、`evidence_hit`、`ad_recommendation_fields`、`bid_guardrail`、`sku_recall_fields`、`claim_evidence_alignment`、`numeric_bid_correctness`、`no_default_entity_leakage` 和 `hard_case_uncertainty`。

# 实验结果

最新运行时间：`2026-06-26T20:08:06.154443+00:00`。

case_count：44。

full_agent overall_metrics：

| Metric | Value |
| --- | ---: |
| `avg_score` | 0.999432 |
| `intent_accuracy` | 1.0 |
| `evidence_hit_rate` | 1.0 |
| `avg_tool_result_key_coverage` | 1.0 |
| `avg_ad_recommendation_fields` | 1.0 |
| `avg_bid_guardrail` | 1.0 |
| `avg_sku_recall_fields` | 1.0 |
| `avg_claim_evidence_alignment` | 1.0 |
| `avg_numeric_bid_correctness` | 1.0 |
| `avg_no_default_entity_leakage` | 0.909091 |
| `avg_hard_case_uncertainty` | 0.977273 |
| `avg_reflection_quality` | 0.503788 |
| `security_flag_pass_rate` | 0.977273 |
| `avg_latency_ms` | 3.80 |
| `p95_latency_ms` | 8 |

threshold gate：`enabled=true`，`threshold=0.70`，`pass=true`。

# 消融实验

| Mode | Avg Score | Evidence Hit | Bid Guardrail | SKU Recall Fields | Claim Alignment | Avg Latency ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `full_product_ad_agent` | 0.999432 | 1.0 | 1.0 | 1.0 | 1.0 | 3.59 |
| `llm_or_template_only` | 0.892803 | 0.590909 | 0.867045 | 0.931818 | 1.0 | 0.0 |
| `metrics_only` | 0.957830 | 0.590909 | 0.948864 | 0.977273 | 1.0 | 1.82 |
| `product_ad_tools_only` | 0.916769 | 0.590909 | 0.945455 | 0.995455 | 1.0 | 0.09 |
| `rag_plus_metrics` | 0.987958 | 1.0 | 1.0 | 1.0 | 1.0 | 2.25 |

结果说明：完整 Agent 在证据命中、ROI guardrail 和召回解释方面最稳定；仅模板模式缺少工具证据；仅 product_ad 工具模式可以展示工具贡献，但缺少 RAG 支撑。

# Case Study

1. 主推品挖掘：`商户 M001 应该优先推哪些商品做搜索广告？`

系统识别为 `product_ad_strategy`，调用 `mine_high_value_products` 和 `rank_ad_candidates`。P1001 因 CVR、GMV 占比、PCVR 和历史 ROI 较高成为候选主推品，但报告同时提示退款率和履约风险，避免只看增长分。

2. ROI 出价守护：`目标 ROI 为 4.5 时，P1001 加价 20% 还安全吗？`

系统识别 `target_roi=4.5`、`product_id=P1001`、`bid_multiplier=1.2`。工具重新计算 `max_cpc_by_revenue_roi` 和 `max_cpc_by_profit_roi`，并在模拟结果中给出 `roi_status=risk`、`guardrail_action=down_bid`，报告输出“不建议盲目加价”和智能调价/A/B test 建议。

3. Query-SKU 召回：`用户搜索 水光补水 时，应该召回哪些商品，为什么？`

系统调用 `recall_query_to_sku`，展示 `keyword_inverted`、`query_expansion`、`vector_match` 等召回路径，并在融合排序中结合 `recall_score`、Product Growth Score、ROI 和退款风险输出候选顺序。

# 错误分析

风险 case 1：商品不存在。

`P9999 如果做主推品加价，合理出价区间是多少？` 返回商品 ID 未找到，无法计算出价区间，需要补充有效商品 ID。系统不输出推荐出价，避免默认泄漏到 P1001。

风险 case 2：Query 模糊或未命中。

`用户搜索 火星露营套餐 时，应该召回哪些商品？` 会先说明未命中 exact demo rows，再尝试 TF-IDF fallback；若相似度不足，返回空结果和不确定性说明。

风险 case 3：高目标 ROI。

当目标 ROI 为 4.5 时，即使 P1001 有 GMV 占比优势，也会因为模拟 ROI 低于目标而输出 risk/down_bid，不建议继续加价。

风险 case 4：退款率偏高。

`P1001 退款率偏高但 GMV 占比高，还应该提高出价吗？` 会同时调用 metrics 和 product_ad 工具，将 GMV 占比与退款率风险放在同一证据表中，输出谨慎建议。

主要误差来源包括 synthetic data 与真实业务分布差异、Query 解析规则较简单、Product Growth Score 权重为课程展示设定、召回模拟未接入真实线上向量库，以及 Eval 中关键词/结构化指标无法完全替代人工业务评审。

# 贡献说明

本项目贡献包括：

- 将经营归因与商品级广告决策结合到同一 Agent workflow。
- 设计 Product Growth Score、Query-SKU 融合排序和 ROI 约束 CPC 区间。
- 增强 hard case eval，加入数值正确性、默认实体泄漏和不确定性表达检查。
- 新增数据卡、模型卡、Notebook 执行脚本、Makefile、CI hardening 和课程提交说明。

本仓库为忻纪元本人课程设计 GitHub 项目提交，所有新增数据均为 synthetic demo data，不包含任何公司内部数据。

# 未来工作

未来可扩展更真实的预算分配模型、跨商户类目归一化、学习排序模型、向量检索后端、可视化投放实验面板、更细粒度的证据一致性检测和更大规模人工标注 eval。
