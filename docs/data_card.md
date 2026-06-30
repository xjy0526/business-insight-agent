# Data Card

## 数据定位

本项目所有商品级广告新增数据均为 synthetic demo data。
数据只用于 pytest、eval、Notebook 和本地演示。

数据不涉及真实平台、真实商户、真实用户或敏感业务信息。
## 数据表

| 表 | 用途 | 关键字段 |
| --- | --- | --- |
| `products` | 经营归因商品/服务项目基础信息 | `product_id`, `product_name`, `category`, `brand`, `price` |
| `orders` | 订单、GMV、退款率和渠道归因 | `order_id`, `product_id`, `payment_amount`, `refund_flag`, `channel` |
| `traffic` | 曝光、点击、加购、订单漏斗 | `date`, `product_id`, `channel`, `exposure`, `clicks`, `orders` |
| `reviews` | 评价主题和差评分析 | `review_id`, `product_id`, `rating`, `content`, `review_date` |
| `campaigns` | 类目活动机会和活动参与分析 | `campaign_id`, `eligible_category`, `discount_rule` |
| `local_ad_sku_candidates` | 商品级广告主推品候选与增长评分输入 | `merchant_id`, `product_id`, `cvr`, `gmv_share`, `pcvr`, `historical_roi` |
| `query_sku_recall` | Query-SKU 召回解释 | `query`, `product_id`, `recall_path`, `recall_score`, `matched_terms` |
| `ad_bid_experiments` | 合成出价实验与 ROI guardrail 示例 | `product_id`, `bid_multiplier`, `cpc`, `roi`, `group_name` |
| `poi_level_ads_baseline` | POI 级广告与商品级广告对比基线 | `merchant_id`, `campaign_type`, `ctr`, `cvr`, `roi` |

## P1001 语义

P1001 在经营归因和商品广告模块中统一表示：

```text
水光补水体验套餐
```

P1001 不再表示其他非本地生活商品。

## 生成与约束

数据以可复现 CSV 形式存放在 `data/` 下。
`python -m app.db.init_db` 会将 CSV 重新导入 SQLite。

商品级广告字段用于 deterministic scorer、ROI guardrail、Query-SKU 召回和
Notebook 展示。评分权重用于方法验证，不能直接用于生产投放。

## 局限性

- 数据规模小，分布简单，不代表实际线上分布。
- Query-SKU 召回只覆盖少量本地生活服务词。
- 出价实验是 deterministic synthetic table，不代表线上真实 A/B 实验。
- 评分权重用于工程演示，不能直接用于生产投放。
