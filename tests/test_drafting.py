import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import drafting
import main
from drafting import (
    DraftCandidate,
    generate_draft_candidate,
    merge_required_materials,
    revise_draft_candidate,
)
from schemas import (
    PlatformEnum,
    ReviewResult,
    RiskLevel,
    ViolationItem,
    ViolationSeverity,
)


class DraftingTest(unittest.TestCase):
    def test_generation_uses_verified_facts_and_rule_whitelist(self):
        class FakeClient:
            messages = []

            async def chat(self, messages):
                self.messages = messages
                return (
                    '{"draft_text":"活动价99元，限指定商品。",'
                    '"missing_materials":["活动期限"],'
                    '"excluded_claims":["全网最低"],'
                    '"rule_ids":["PROMO-PRICE-001","FAKE-001"]}'
                )

        fake = FakeClient()
        previous = drafting.get_llm_client
        drafting.get_llm_client = lambda: fake
        try:
            candidate = asyncio.run(
                generate_draft_candidate(
                    industry="电商促销",
                    medium="详情页",
                    product_name="测试商品",
                    product_type="普通商品",
                    verified_facts="活动价99元",
                    desired_message="说明优惠",
                    proof_materials="活动方案",
                    structured_facts="宣传价格：99元",
                    required_materials=["活动期限"],
                    rule_context="- [PROMO-PRICE-001] 促销信息应真实准确",
                    allowed_rule_ids={"PROMO-PRICE-001"},
                )
            )
        finally:
            drafting.get_llm_client = previous

        self.assertIn("活动价99元", fake.messages[1]["content"])
        self.assertEqual(candidate.rule_ids, ["PROMO-PRICE-001"])
        self.assertEqual(candidate.missing_materials, ["活动期限"])

    def test_revision_preserves_existing_missing_materials(self):
        class FakeClient:
            async def chat(self, _messages):
                return (
                    '{"draft_text":"修订稿",'
                    '"missing_materials":["价格依据"],'
                    '"excluded_claims":["销量第一"],'
                    '"rule_ids":["PROMO-PRICE-001"]}'
                )

        previous = drafting.get_llm_client
        drafting.get_llm_client = lambda: FakeClient()
        try:
            revised = asyncio.run(
                revise_draft_candidate(
                    DraftCandidate("原稿", ["活动期限"], [], []),
                    review_risks=[{"content": "全网最低"}],
                    rule_context="- [PROMO-PRICE-001] 规则",
                    allowed_rule_ids={"PROMO-PRICE-001"},
                )
            )
        finally:
            drafting.get_llm_client = previous

        self.assertEqual(revised.draft_text, "修订稿")
        self.assertEqual(revised.missing_materials, ["活动期限", "价格依据"])

    def test_deterministic_required_materials_cannot_be_dropped_by_model(self):
        merged = merge_required_materials(
            DraftCandidate("待审稿", [], [], []),
            ["活动期限", "优惠适用范围"],
        )

        self.assertEqual(merged.missing_materials, ["活动期限", "优惠适用范围"])

    def test_industry_preflight_lists_missing_ecommerce_facts(self):
        missing = main._draft_required_materials(
            "ecommerce",
            {"sale_price": "99元"},
            "突出原价和折扣",
        )

        self.assertIn("促销活动起止时间", missing)
        self.assertIn("原价、比较价格或折扣计算依据", missing)

    def test_general_health_product_does_not_require_approved_ad_text(self):
        missing = main._draft_required_materials(
            "medical",
            {"regulatory_category": "general_health_product"},
            "介绍产品特点",
        )

        self.assertEqual(missing, [])

    def test_version_changes_when_evidence_changes(self):
        snapshot = {
            "industry": "电商促销",
            "verified_facts": "活动价99元",
            "proof_materials": "活动方案A",
        }
        first = main._draft_version("活动价99元。", "规则V1", snapshot)
        second = main._draft_version(
            "活动价99元。",
            "规则V1",
            {**snapshot, "proof_materials": "活动方案B"},
        )

        self.assertNotEqual(first, second)

    def test_endpoint_repairs_and_rechecks_before_returning_draft(self):
        initial = DraftCandidate(
            "全网最低价",
            [],
            [],
            ["PROMO-PRICE-001"],
        )
        revised = DraftCandidate(
            "活动价99元，限指定商品。",
            [],
            ["全网最低价"],
            ["PROMO-PRICE-001"],
        )
        high_review = ReviewResult(
            id="HIGH",
            channel="upload",
            platform=PlatformEnum.MANUAL,
            risk_level=RiskLevel.HIGH,
            violation_items=[
                ViolationItem(
                    dimension="价格",
                    content="全网最低价",
                    severity=ViolationSeverity.CRITICAL,
                    law_basis="价格促销规则",
                    suggestion="删除无依据比较",
                    rule_ids=["PROMO-PRICE-001"],
                )
            ],
        )
        low_review = ReviewResult(
            id="LOW",
            channel="upload",
            platform=PlatformEnum.MANUAL,
            risk_level=RiskLevel.LOW,
            missing_materials=["活动适用范围"],
        )
        request = main.DraftRequest(
            industry="ecommerce",
            medium="详情页",
            product_name="测试商品",
            product_type="普通商品",
            verified_facts="活动价99元",
            desired_message="说明优惠",
            proof_materials="活动方案",
            details={
                "sale_price": "99元",
                "promotion_period": "6月1日至6月3日",
                "applicable_scope": "指定商品",
                "promotion_conditions": "每人限购2件",
            },
            terms_accepted=True,
        )

        with (
            patch.object(
                main,
                "_rule_context_for",
                return_value=("- [PROMO-PRICE-001] 促销规则", {"PROMO-PRICE-001"}),
            ),
            patch.object(
                main,
                "generate_draft_candidate",
                new=AsyncMock(return_value=initial),
            ),
            patch.object(
                main,
                "revise_draft_candidate",
                new=AsyncMock(return_value=revised),
            ) as revise_mock,
            patch.object(
                main,
                "review_ad_copy",
                new=AsyncMock(side_effect=[high_review, low_review]),
            ) as review_mock,
        ):
            response = asyncio.run(main.draft_ad_copy(request))

        self.assertEqual(response["status"], "pending_materials")
        self.assertEqual(response["draft_text"], revised.draft_text)
        self.assertTrue(response["auto_repaired"])
        self.assertEqual(response["internal_review"]["risk_level"], "低风险")
        self.assertIn("活动适用范围", response["missing_materials"])
        self.assertIn("人工智能辅助生成", response["ai_generation_notice"])
        self.assertEqual(len(response["draft_version"]), 12)
        revise_mock.assert_awaited_once()
        self.assertEqual(review_mock.await_count, 2)

    def test_draft_requires_terms_acceptance(self):
        request = main.DraftRequest(
            industry="ecommerce",
            medium="图文",
            product_name="测试商品",
            product_type="普通商品",
            verified_facts="活动价99元",
            desired_message="说明优惠",
        )

        response = asyncio.run(main.draft_ad_copy(request))

        self.assertFalse(response["ok"])
        self.assertEqual(response["status"], "incomplete")
        self.assertIn("使用规则", response["error"])

    def test_check_requires_terms_acceptance(self):
        response = asyncio.run(main.check_ad_copy(main.AdCopyRequest(text="测试文案")))

        self.assertFalse(response["ok"])
        self.assertEqual(response["status"], "incomplete")
        self.assertIn("隐私规则", response["error"])


if __name__ == "__main__":
    unittest.main()
