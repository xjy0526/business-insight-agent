# GitHub 提交说明

- 本仓库为忻纪元本人课程设计 GitHub 项目提交。
- 项目基于本人已有 business-insight-agent 仓库继续迭代。
- 本次课程新增功能清单：商品级广告增长决策、主推品挖掘、Query-SKU 召回、ROI 出价守护、POI 级广告 vs 商品级广告对比、广告投放评测、课程 Notebook 和报告草稿。
- 不含真实公司内部数据；所有新增数据均为 synthetic demo data。
- 与原始项目差异：原项目聚焦经营归因，本版本在保留原能力基础上新增本地生活商户商品级广告决策链路。
- 运行方式：

```bash
python -m app.db.init_db
pytest
ruff check app evals tests
python -m evals.run_eval
python -m evals.run_ablation
```

- 提交分支：`course-design-product-ad-agent`
- commit message：`feat(course): upgrade agent for product-level advertising decision support`

本仓库为忻纪元本人课程设计 GitHub 项目提交。项目基于本人已有 business-insight-agent 仓库继续迭代。本次课程新增商品级广告增长决策、主推品挖掘、Query-SKU 召回、ROI 出价守护、广告投放评测、课程 Notebook 和报告草稿。所有数据均为 synthetic demo data，不包含任何公司内部数据。
