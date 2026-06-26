# Query SKU Recall Guide

Query-SKU 召回可以使用多路策略。keyword_inverted 适合强词面匹配，例如 Query 与服务名、套餐名或类目词高度一致。query_expansion 适合同义词、服务词、类目词和用户口语表达扩展。vector_match 适合语义相近但词面不同的 Query。

最终排序不应只看文本相似度，还需要结合商品增长分、历史 ROI、关键词覆盖、退款风险和履约能力。召回路径用于解释“为什么被召回”，融合排序用于解释“为什么排在前面”。

当 keyword_inverted、query_expansion 和 vector_match 同时命中时，报告需要展示不同路径的 matched_terms 和 recall_score，并说明每条路径的适用边界。
