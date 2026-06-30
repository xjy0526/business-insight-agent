# GitHub 提交说明

- 最新 hardening 内容：product ad agent evaluation and submission artifacts。
- 最新 eval case_count：44。
- 最新 eval command：`python -m evals.run_eval --all-modes --fail-under 0.70`。
- 最新 full_agent avg_score：0.999432。
- threshold gate：enabled=true, pass=true。

## 本次新增内容

- 新增 Notebook 执行脚本，并保存 `notebooks/product_ad_demo.ipynb` 执行输出。
- 增强 Eval 可信度：hard cases、数值正确性、默认实体泄漏、不确定性表达、all-modes threshold gate。
- 修复 ROI guardrail，使 `simulate_bid_strategy` 按用户 `target_roi` 判断 pass/watch/risk。
- 修复 Query + merchant_id 场景下的 Query-SKU 融合排序，避免未召回商品混入直接召回排序。
- 新增集中实体解析、TF-IDF deterministic recall fallback、数据一致性校验、Product Ad API 和前端 Product Ads tab。
- 新增 `docs/data_card.md`、`docs/model_card.md`、`docs/llm_provider_optional.md`、Makefile 和 CI hardening。
