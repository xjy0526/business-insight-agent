"""Tests for claim-level evidence reflection checks."""

from app.services.evidence_checker import EvidenceChecker


def test_extract_claims_from_report() -> None:
    """The checker should extract numbered attribution claims."""

    report = (
        "## 问题概述\nP1001 GMV 下滑。\n\n"
        "## 指标拆解\nGMV 和 CTR 已计算。\n\n"
        "## 主要归因\n"
        "1. search 渠道点击率明显走弱，说明商品在搜索场景吸引力下降。\n"
        "2. 活动参与不足可能削弱价格竞争力。\n\n"
        "## 证据来源\n工具。\n\n"
        "## 优化建议\n优化搜索和活动。"
    )

    claims = EvidenceChecker().extract_claims(report)

    assert len(claims) == 2
    assert claims[0]["claim_type"] == "traffic"
    assert claims[1]["claim_type"] == "campaign"


def test_map_traffic_claim_to_channel_evidence() -> None:
    """Traffic claims mentioning search should map to channel breakdown evidence."""

    claim = {
        "claim_id": "claim_001",
        "claim_type": "traffic",
        "text": "search 渠道点击率明显走弱。",
    }
    tool_results = {
        "current_channel_breakdown": {
            "channels": [{"channel": "search", "ctr": 0.029}],
        }
    }

    result = EvidenceChecker().map_claim_to_evidence(claim, tool_results, [])

    assert result["supported"] is True
    assert "current_channel_breakdown" in result["supporting_keys"]


def test_map_campaign_claim_to_campaign_tool_or_rag() -> None:
    """Campaign claims can be supported by Campaign Tool or campaign RAG evidence."""

    claim = {
        "claim_id": "claim_001",
        "claim_type": "campaign",
        "text": "活动参与不足可能削弱价格竞争力。",
    }

    tool_result = EvidenceChecker().map_claim_to_evidence(
        claim,
        {"campaign_participation": {"risk_level": "high"}},
        [],
    )
    rag_result = EvidenceChecker().map_claim_to_evidence(
        claim,
        {},
        [{"source": "campaign_rules.md", "content": "活动规则"}],
    )

    assert tool_result["supported"] is True
    assert rag_result["supported"] is True


def test_numeric_consistency_does_not_fail_on_supported_numbers() -> None:
    """Percentages from report text should match ratio values in tool results."""

    report = "## 指标拆解\n点击率 CTR：当前 5.18%，退款率：当前 33.33%。"
    tool_results = {
        "current_traffic": {"ctr": 0.051806},
        "current_refund": {"refund_rate": 0.333333},
    }

    result = EvidenceChecker().check_numeric_consistency(report, tool_results)

    assert result["pass"] is True
    assert result["warnings"] == []


def test_forbidden_absolute_claims_detected_when_evidence_low() -> None:
    """Absolute wording should be flagged when evidence is unavailable."""

    result = EvidenceChecker().check_unsupported_absolute_claims(
        "活动参与不足是唯一原因，无需进一步验证。",
        evidence_available=False,
    )

    assert result["pass"] is False
    assert result["forbidden_terms_found"]
