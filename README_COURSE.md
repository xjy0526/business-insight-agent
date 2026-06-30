# 面向本地生活商户的商品级广告增长决策 Agent

基于 Tool Calling 与 RAG 的主推品挖掘、Query-SKU 召回与 ROI 守护。

## 1. 课程设计题目

中文题目：

面向本地生活商户的商品级广告增长决策 Agent：
基于 Tool Calling 与 RAG 的主推品挖掘、Query-SKU 召回与 ROI 守护。

英文题目：

Product-level Advertising Growth Agent for Local Commerce Merchants:
Tool-augmented RAG for SKU Mining, Query-SKU Recall and ROI Guardrails.

本仓库为忻纪元课程设计 GitHub 项目提交。
项目基于公开可运行的 `business-insight-agent` 代码框架进行课程场景扩展。
所有新增数据均为 synthetic demo data，不涉及真实平台、真实商户、
真实用户或敏感业务信息。

## 2. 研究背景

本地生活平台广告中，传统 POI 级广告更适合承接泛需求流量，
但难以精细化匹配用户的明确服务需求。
商户往往希望围绕爆品、团购套餐和服务项目做商品级投放，
例如皮肤管理、美甲、美发、健身私教、摄影和餐饮套餐。

商品级广告需要同时回答三个问题：

- 推什么商品或服务项目。
- 用什么 Query 召回。
- 出价是否守住 ROI。

本项目将这些问题抽象为一个可观测、可回测、可答辩的
Agentic Product Ads Decision System。

## 3. 问题定义

输入包括用户自然语言 query、商户/商品/订单/流量/广告实验/
Query-SKU 召回等结构化数据，以及本地 Markdown 策略知识库。

输出包括主推品候选排序、出价区间、Query-SKU 召回解释、
ROI 风险提示、证据对齐表和结构化投放建议报告。

## 4. 与数字经济/平台经济的关系

该问题属于平台经济中的商户增长、广告匹配效率、搜索广告机制设计
和数据驱动经营决策问题。

平台通过更细粒度的商品级匹配提升搜索流量分发效率，
商户通过可解释的主推品选择和 ROI 守护降低投放风险。

## 5. 与能力的对应关系

| 抽象能力 | 项目模块 |
| --- | --- |
| 主推品/爆品挖掘 | `mine_high_value_products`, Product Growth Score |
| PCVR、售价、历史 ROI 的出价约束 | `recommend_bid_range`, `simulate_bid_strategy` |
| CVR + GMV 占比的高价值商品筛选 | `local_ad_sku_candidates`, deterministic scorer |
| 关键词倒排、Query 扩展、向量匹配 | `recall_query_to_sku`, TF-IDF fallback |
| CTR、CVR、订单、ROI 实验评估 | `ad_bid_experiments`, `poi_level_ads_baseline` |
| 工程化评测与可观测性 | `evals/`, `TraceService`, ablation suite |

本项目是对本地生活商品级广告场景中通用方法的课程抽象实现，
仅用于课程展示、方法验证和工程练习。

## 6. 方法框架

系统由 Prompt Guard、Intent Router、Planner、Metrics Tool、
Product Ad Tool、RAG Retriever、Recommendation Scorer、
Reflection Checker、Final Report Generator、Trace 和 Eval 组成。

经营归因问题走指标拆解与 RAG 证据链路。
商品级广告问题走 `product_ad_tool` 的主推品评分、Query-SKU 召回、
ROI 出价守护和 POI vs Product Ad 对比。

## 7. 核心公式

### Product Growth Score

```text
Product Growth Score =
  0.25 * norm(CVR)
+ 0.25 * norm(GMV share)
+ 0.20 * norm(PCVR)
+ 0.15 * norm(historical ROI)
+ 0.05 * norm(available slots)
+ 0.05 * norm(rating)
+ 0.05 * norm(keyword coverage)
- 0.15 * norm(refund rate)
```

### max_cpc_by_revenue_roi

```text
expected_revenue_per_click = pcvr * price
max_cpc_by_revenue_roi = expected_revenue_per_click / target_roi
```

### max_cpc_by_profit_roi

```text
expected_profit_per_click = pcvr * price * margin_rate
max_cpc_by_profit_roi = expected_profit_per_click / target_roi
```

### final_score for Query-SKU ranking

```text
final_score =
  0.45 * product_growth_score
+ 0.35 * recall_score
+ 0.15 * roi_score
+ 0.05 * keyword_coverage_score
- refund_risk_penalty
- non_recall_penalty
```

## 8. 相关工作

Insight Agents 关注电商卖家数据洞察、多 Agent 协作、
plan-and-execute 风格分析和业务洞察生成。
它说明 LLM Agent 可以把自然语言问题拆解为数据访问、分析计划和洞察报告。

ProductAgent 聚焦商品搜索中的需求澄清、动态检索和商品推荐交互。
它更接近搜索/推荐链路中的对话式商品发现。

传统 BI / Dashboard 能展示指标和图表，但通常难以自动完成跨表归因、
策略证据检索、风险校验和结构化建议生成。
当问题涉及“为什么下降”“推什么商品”“出价是否安全”时，
只看 dashboard 往往还需要人工串联指标、规则和策略。

本项目差异：

- 聚焦本地生活商品级广告增长。
- 将经营归因、主推品挖掘、ROI guardrail、Query-SKU 召回和 Eval
  统一到可观测 Agent workflow。
- 关键数字由工具计算，报告由 RAG 和 evidence alignment 约束。

参考文献列表见 [docs/references.md](docs/references.md)。

## 9. 数据说明

所有新增数据均为 synthetic demo data，覆盖本地生活商户、团购套餐、
服务项目、广告实验、Query-SKU 召回和 POI 级广告对比。
不涉及真实平台、真实商户、真实用户或敏感业务信息。

P1001 在经营归因和商品级广告模块中均表示：

```text
水光补水体验套餐
```

更多说明见 [docs/data_card.md](docs/data_card.md)
和 [docs/model_card.md](docs/model_card.md)。

## 10. 实验设计

Baseline：原经营归因 Agent，只使用指标工具、RAG 和模板报告。

Ablation：比较 `llm_or_template_only`、`metrics_only`、
`product_ad_tools_only`、`rag_plus_metrics`、`full_product_ad_agent`
五种模式。

Eval cases：保留原经营归因评测，并新增商品级广告、主推品挖掘、
出价守护、Query-SKU 召回、POI vs Product Ad 对比、prompt injection
和模糊问题 hard cases。

指标体系包括 `intent_accuracy`、`keyword_coverage`、`tool_usage`、
`evidence_hit`、`entity_coverage`、`tool_result_key_coverage`、
`ad_recommendation_fields`、`bid_guardrail`、`sku_recall_fields`、
`poi_vs_product_comparison`、`claim_evidence_alignment`、
`numeric_bid_correctness`、`no_default_entity_leakage`、
`reflection_quality`、`security_flag` 和 `hard_case_uncertainty`。

## 11. 如何运行

```bash
python -m app.db.init_db
python scripts/validate_demo_data.py
pytest
ruff check app evals tests
python -m evals.run_eval --all-modes --fail-under 0.70
python -m evals.run_ablation
python scripts/execute_notebook.py
```

也可以运行课程检查：

```bash
make course-check
```

## 12. GitHub 提交说明

课程提交时应提交 Notebook、课程报告和 GitHub 链接。
Notebook 可通过以下命令执行并保存输出：

```bash
python scripts/execute_notebook.py
```

最终课程报告正文见 [docs/course_report_final.md](docs/course_report_final.md)。

本仓库为忻纪元课程设计 GitHub 项目提交。
项目新增商品级广告增长决策、主推品挖掘、Query-SKU 召回、
ROI 出价守护、广告投放评测、课程 Notebook 和报告正文。
所有数据均为 synthetic demo data，不涉及真实平台、真实商户、
真实用户或敏感业务信息。
