# 面向本地生活商户的商品级广告增长决策 Agent：基于 Tool Calling 与 RAG 的主推品挖掘、Query-SKU 召回与 ROI 守护

## 1. 课程设计题目

中文题目：面向本地生活商户的商品级广告增长决策 Agent：基于 Tool Calling 与 RAG 的主推品挖掘、Query-SKU 召回与 ROI 守护

英文题目：Product-level Advertising Growth Agent for Local Commerce Merchants: Tool-augmented RAG for SKU Mining, Query-SKU Recall and ROI Guardrails

## 2. 研究背景

本地生活平台广告中，传统 POI 级广告更适合承接泛需求流量，但难以精细化匹配用户的明确服务需求。商户往往希望围绕爆品、团购套餐、服务项目做商品级投放，例如皮肤管理、美甲、美发、健身私教、摄影和餐饮套餐。商品级广告需要同时解决“推什么商品”“用什么 Query 召回”“出价是否守住 ROI”三个问题。

## 3. 问题定义

输入包括用户自然语言问题 query；商户、商品、订单、流量、广告实验、Query-SKU 召回等结构化数据；商品级广告策略知识库。

输出包括主推品候选排序、出价区间、Query-SKU 召回解释、ROI 风险提示和结构化投放建议报告。

## 4. 与数字经济/平台经济的关系

该问题属于平台经济中的商户增长、广告匹配效率、搜索广告机制设计和数据驱动经营决策问题。平台通过更精细的商品级匹配提升搜索流量分发效率，商户通过可解释的主推品选择和 ROI 守护降低投放风险。

## 5. 与本人美团实习经历的抽象对应关系

- 商品级广告对应主推品挖掘。
- PCVR、售价、历史 ROI 对应出价区间估计。
- CVR + GMV 占比对应高价值商品筛选。
- 关键词倒排、Query 扩展、向量匹配对应 Query-SKU 召回。
- CTR、CVR、订单、ROI 对应实验评估指标。

本项目不是复刻公司内部系统，而是对实习中通用方法的公开数据抽象实现，所有数据均为 synthetic demo data，不包含任何公司内部数据。项目仅可表述为 inspired by local commerce product-level advertising scenarios。

## 6. 方法框架

系统由 Intent Router、Planner、Metrics Tool、Product Ad Tool、RAG Retriever、Attribution / Recommendation Scorer、Reflection Checker、Final Report Generator、Trace & Eval 组成。经营归因问题走指标拆解与 RAG 证据链路，商品级广告问题走 product_ad_tool 的主推品评分、Query-SKU 召回、ROI 出价守护和 POI vs Product Ad 对比。

## 7. 方法创新点

- 将经营归因与商品级广告决策结合。
- 设计商品增长分数 Product Growth Score。
- 设计 ROI 约束下的 CPC/出价区间估计。
- 设计 Query-SKU 多路召回与融合排序。
- 设计证据约束型报告生成，降低大模型幻觉。
- 设计自动化 Eval，对意图识别、工具调用、召回命中、ROI guardrail、证据一致性进行评估。

## 8. 数据说明

所有新增数据均为 synthetic demo data，覆盖本地生活商户、团购套餐、服务项目、广告实验、Query-SKU 召回和 POI 级广告对比。不包含任何真实公司内部数据、真实商户数据或敏感业务信息。

## 9. 实验设计

baseline：原经营归因 Agent，只使用指标工具、RAG 和模板报告。

ablation：比较 llm_or_template_only、metrics_only、product_ad_tools_only、rag_plus_metrics、full_product_ad_agent 五种模式。

eval cases：保留原经营归因评测，并新增商品级广告、主推品挖掘、出价守护、Query-SKU 召回、POI vs Product Ad 对比和模糊问题 case。

指标体系：intent_accuracy、keyword_coverage、tool_usage、evidence_hit、entity_coverage、tool_result_key_coverage、ad_recommendation_fields、bid_guardrail、sku_recall_fields、poi_vs_product_comparison、claim_evidence_alignment、forbidden_keyword_pass。

## 10. 如何运行

```bash
python -m app.db.init_db
uvicorn app.main:app --reload
python -m evals.run_eval
pytest
```

可选运行消融实验：

```bash
python -m evals.run_ablation
```

## 11. GitHub 提交说明

这是忻纪元本人课程设计 GitHub 项目提交。

本仓库为忻纪元本人课程设计 GitHub 项目提交。项目基于本人已有 business-insight-agent 仓库继续迭代。本次课程新增内容包括商品级广告增长决策、主推品挖掘、Query-SKU 召回、ROI 出价守护、广告投放评测、课程 Notebook 和报告草稿。所有数据均为 synthetic demo data，不包含任何公司内部数据。
