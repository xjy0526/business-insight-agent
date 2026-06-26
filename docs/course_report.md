# 摘要

本文设计并实现了一个面向本地生活商户的商品级广告增长决策 Agent。系统基于 Tool Calling 与 RAG，将经营归因、主推品挖掘、Query-SKU 召回、ROI 出价守护和证据约束型报告生成整合在同一条可观测工作流中。项目使用 synthetic demo data，不包含任何公司内部数据。

# 背景

本地生活商户通常既关注门店整体曝光，也关注具体服务项目、团购套餐或爆品的投放效果。POI 级广告适合泛需求，但当用户搜索“水光补水”“美甲款式”“双人烤肉”等明确服务时，商品级广告能更直接承接用户意图。课程设计将该问题抽象为平台经济中的商户增长和搜索广告匹配效率问题。

# 问题建模

输入为用户自然语言 query、结构化经营数据、商品广告候选数据、广告实验数据、Query-SKU 召回数据和策略知识库。输出为主推品排序、出价区间、召回路径解释、ROI 风险提示和结构化建议报告。

核心任务包括经营归因、商品增长分计算、ROI 约束下 CPC 区间估计、Query-SKU 多路召回与融合排序、POI 级广告和商品级广告效果对比。

# 方法设计

系统工作流包括 Intent Router、Planner、Metrics Tool、Product Ad Tool、RAG Retriever、Recommendation Scorer、Reflection Checker 和 Final Report Generator。Product Growth Score 使用 CVR、GMV share、PCVR、historical ROI、available slots、rating、keyword coverage 和 refund rate 加权。出价工具使用 PCVR * price 估计单次点击预期成交额，并用 target ROI 和 margin rate 生成 CPC 区间。

# 系统实现

后端基于 FastAPI、SQLite 和 Python 工具函数实现。`app/tools/product_ad_tool.py` 提供主推品挖掘、出价区间估计、Query-SKU 召回、候选排序、加价模拟和 POI vs Product Ad 对比。RAG 文档位于 `data/knowledge_docs/`，Trace 和 Eval 继续复用原项目能力。

# 实验设计

评测集保留原经营归因 case，并新增商品级广告相关 case。指标包括 intent_accuracy、tool_usage、evidence_hit、ad_recommendation_fields、bid_guardrail、sku_recall_fields、poi_vs_product_comparison 和 claim_evidence_alignment。

消融实验包含 llm_or_template_only、metrics_only、product_ad_tools_only、rag_plus_metrics、full_product_ad_agent。预期完整 Agent 在证据一致性、ROI guardrail 和召回解释方面表现最好。

# 实验结果占位

运行以下命令后填入本地结果：

```bash
python -m app.db.init_db
pytest
ruff check app evals tests
python -m evals.run_eval
python -m evals.run_ablation
```

# 错误分析

潜在误差来源包括 synthetic data 与真实业务分布差异、Query 解析规则较简单、Product Growth Score 权重为课程展示设定、召回模拟未接入真实向量库。后续可通过真实公开数据、更多 query 标注和在线实验模拟提升可信度。

# 贡献说明

本项目贡献包括将经营归因与商品级广告决策结合，设计 Product Growth Score，设计 ROI 约束下 CPC 区间估计，设计 Query-SKU 多路召回与融合排序，并建立自动化 eval 与 ablation。

# 未来工作

未来可扩展更真实的预算分配模型、跨商户类目归一化、学习排序模型、向量检索后端、可视化投放实验面板和更细粒度的证据一致性检测。
