from app.agent.entity_parser import parse_ad_entities


def test_parse_target_roi_product_and_bid_multiplier():
    parsed = parse_ad_entities("目标 ROI 为 4.5 时，P1001 加价 20% 还安全吗？")

    assert parsed.product_id == "P1001"
    assert parsed.target_roi == 4.5
    assert parsed.bid_multiplier == 1.2


def test_parse_search_query():
    parsed = parse_ad_entities("用户搜索 水光补水 时，应该召回哪些商品？")

    assert parsed.search_query == "水光补水"


def test_parse_quoted_search_query():
    parsed = parse_ad_entities("用户搜索“水光补水”时应该召回哪些商品？")

    assert parsed.search_query == "水光补水"


def test_parse_spaced_search_query():
    parsed = parse_ad_entities("用户搜索 水 光 补 水 时，应该召回哪些商品？")

    assert parsed.search_query == "水光补水"


def test_parse_search_term_phrase():
    parsed = parse_ad_entities("搜索词是 双人 烤肉 套餐")

    assert parsed.search_query == "双人烤肉套餐"


def test_parse_keyword_phrase():
    parsed = parse_ad_entities("关键词：美甲款式")

    assert parsed.search_query == "美甲款式"


def test_parse_merchant_and_search_query():
    parsed = parse_ad_entities("商户 M001 下，用户搜索 美甲款式 时，应该召回哪些商品？")

    assert parsed.merchant_id == "M001"
    assert parsed.search_query == "美甲款式"


def test_parse_budget_flags_without_default_entities():
    parsed = parse_ad_entities("预算有限，应该优先投高 CVR 还是高 GMV 占比？")

    assert parsed.budget_limited is True
    assert parsed.merchant_id is None
    assert parsed.product_id is None


def test_parse_vague_store_question():
    parsed = parse_ad_entities("帮我看看这个店应该投哪些商品。")

    assert parsed.merchant_id is None
    assert parsed.product_id is None
    assert parsed.search_query is None
