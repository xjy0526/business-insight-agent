# Data Card

## 数据来源

本项目所有商品级广告新增数据均为 synthetic demo data，只用于课程设计、pytest、eval 和本地演示。不包含真实公司数据、真实商户数据、真实用户数据、真实投放策略或敏感信息。

## 数据表

| 表 | 用途 | 关键字段 |
| --- | --- | --- |
| `local_ad_sku_candidates` | 商品级广告主推品候选与增长评分输入 | `merchant_id`, `product_id`, `product_name`, `category`, `service_type`, `price`, `cvr`, `gmv_share`, `pcvr`, `historical_roi`, `margin_rate`, `available_slots`, `rating`, `refund_rate`, `keyword_coverage` |
| `query_sku_recall` | Query-SKU demo 召回种子 | `query`, `product_id`, `recall_path`, `recall_score`, `matched_terms`, `query_intent` |
| `ad_bid_experiments` | 合成出价实验与 ROI guardrail 示例 | `experiment_id`, `product_id`, `group_name`, `bid_multiplier`, `cpc`, `impressions`, `clicks`, `orders`, `revenue`, `ad_cost`, `ctr`, `cvr`, `roi` |
| `poi_level_ads_baseline` | POI 级广告与商品级广告对比基线 | `merchant_id`, `campaign_type`, `impressions`, `clicks`, `orders`, `revenue`, `ad_cost`, `ctr`, `cvr`, `roi`, `notes` |

## 字段含义

- `merchant_id` / `poi_id` / `product_id`：合成商户、门店和商品标识。
- `cvr`、`pcvr`、`ctr`、`roi`：课程演示用转化、预估转化、点击和投入产出指标。
- `gmv_share`：商品在合成商户 GMV 中的占比。
- `margin_rate`：用于利润 ROI 约束的合成毛利率。
- `refund_rate`、`rating`、`available_slots`：履约与承接风险信号。
- `recall_path`、`recall_score`、`matched_terms`：Query-SKU 召回解释字段。

## 局限性

- 数据规模小，分布简单，不代表真实业务分布。
- Query-SKU 召回只覆盖少量本地生活服务词。
- 出价实验是 deterministic synthetic table，不代表线上真实 A/B 实验。
- 评分权重用于课程展示，不能直接用于生产投放。
