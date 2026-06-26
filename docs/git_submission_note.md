# GitHub 提交说明

- 本仓库为忻纪元本人课程设计 GitHub 项目提交。
- 项目基于本人已有 `business-insight-agent` 仓库继续迭代。
- 当前提交分支：`course-design-product-ad-agent-hardening`。
- 最新 hardening commit message：`fix(course): harden product ad agent evaluation and submission artifacts`。
- 最新 eval case_count：44。
- 最新 eval command：`python -m evals.run_eval --all-modes --fail-under 0.70`。
- 最新 full_agent avg_score：0.999432。
- threshold gate：enabled=true, pass=true。

## 本次 Hardening 新增内容

- 修复 README、README_COURSE 和课程报告中的旧评测描述与占位内容。
- 新增 Notebook 执行脚本，并保存 `notebooks/course_design_demo.ipynb` 执行输出。
- 增强 Eval 可信度：hard cases、数值正确性、默认实体泄漏、不确定性表达、all-modes threshold gate。
- 修复 ROI guardrail，使 `simulate_bid_strategy` 按用户 `target_roi` 判断 pass/watch/risk。
- 修复 Query + merchant_id 场景下的 Query-SKU 融合排序，避免未召回商品混入直接召回排序。
- 新增集中实体解析、TF-IDF deterministic recall fallback、数据一致性校验、Product Ad API 和前端 Product Ads tab。
- 新增 `docs/data_card.md`、`docs/model_card.md`、`docs/llm_provider_optional.md`、Makefile 和 CI hardening。

## 课程提交材料

课程提交时应提交：

- GitHub 仓库链接。
- 已执行并保存输出的 `notebooks/course_design_demo.ipynb`。
- 课程报告 `docs/course_report.md`。
- README / README_COURSE 中的运行命令和最新 evaluation 结果。

本次 hardening commit 主要修复课程提交材料、Notebook 执行输出、Eval 可信度、ROI guardrail、Query-SKU 融合排序、实体解析、数据校验和文档一致性。该仓库为忻纪元本人课程设计 GitHub 项目提交，所有数据均为 synthetic demo data，不包含任何公司内部数据。
