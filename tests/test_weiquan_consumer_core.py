import asyncio
import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from weiquan_consumer import (  # noqa: E402
    CONTROLLED_LEGAL_FACTS,
    DISCLAIMER,
    ConsumerAnalysisService,
    ConsumerInputError,
    InvalidProviderResponseError,
    ProviderUnavailableError,
    build_messages,
    parse_and_validate,
    select_source_ids,
    validate_text,
)


SAMPLES = json.loads((ROOT / "tests" / "fixtures" / "weiquan_consumer_response_samples.json").read_text(encoding="utf-8"))
SCHEMA = json.loads((ROOT / "schemas" / "weiquan_consumer_response.schema.json").read_text(encoding="utf-8"))


class FakeProvider:
    def __init__(self, response):
        self.response = response
        self.messages = None

    async def chat(self, messages, *, temperature, max_tokens):
        self.messages = messages
        self.temperature = temperature
        self.max_tokens = max_tokens
        return self.response


class FailingProvider:
    async def chat(self, messages, *, temperature, max_tokens):
        raise RuntimeError("network failure")


class WeiquanConsumerCoreTests(unittest.TestCase):
    def test_core_validation_limits_match_the_published_schema(self):
        from weiquan_consumer import LIST_FIELDS, REQUIRED_FIELDS, STRING_FIELDS

        self.assertEqual(tuple(SCHEMA["required"]), REQUIRED_FIELDS)
        self.assertEqual(STRING_FIELDS, {"disputeType": 120, "summary": 1200, "letter": 3000})
        self.assertEqual(LIST_FIELDS, {
            "factsKnown": (12, 500), "factsMissing": (12, 500), "legalBasis": (6, 500),
            "recommendedPath": (12, 500), "evidenceNeeded": (12, 500), "specialNotes": (12, 500),
        })

    def test_text_boundary(self):
        self.assertEqual(validate_text("  商品质量问题需要协商处理。  "), "商品质量问题需要协商处理。")
        with self.assertRaises(ConsumerInputError):
            validate_text("太短")
        with self.assertRaises(ConsumerInputError):
            validate_text("x" * 6001)

    def test_legal_context_is_limited_and_injected_server_side(self):
        text = "平台直播购买商品后申请七天无理由退货，商家拒绝处理。"
        source_ids = select_source_ids(text)
        self.assertIn("L-001", source_ids)
        self.assertIn("L-003", source_ids)
        self.assertIn("L-006", source_ids)
        self.assertLessEqual(len(source_ids), 5)
        messages = build_messages(text)
        self.assertEqual([item["role"] for item in messages], ["system", "user"])
        self.assertIn("[L-006]", messages[0]["content"])
        self.assertIn("<case>", messages[1]["content"])
        self.assertNotIn(text, messages[0]["content"])

    def test_current_complaint_rule_uses_its_current_name(self):
        self.assertIn("《市场监督管理投诉举报处理办法》", CONTROLLED_LEGAL_FACTS["L-007"])
        self.assertNotIn("暂行办法", CONTROLLED_LEGAL_FACTS["L-007"])

    def test_unsafe_evidence_or_threat_guidance_is_rejected(self):
        unsafe = copy.deepcopy(SAMPLES["valid"])
        unsafe["letter"] = "建议伪造聊天记录，再要求商家赔偿。"
        with self.assertRaises(InvalidProviderResponseError):
            parse_and_validate(json.dumps(unsafe, ensure_ascii=False), ("L-001", "L-004"))
        unsafe = copy.deepcopy(SAMPLES["valid"])
        unsafe["letter"] = "不赔就全网曝光。"
        with self.assertRaises(InvalidProviderResponseError):
            parse_and_validate(json.dumps(unsafe, ensure_ascii=False), ("L-001", "L-004"))

    def test_prepaid_course_card_selects_the_controlled_prepaid_source(self):
        self.assertIn("L-008", select_source_ids("健身课程卡尚有六次未使用，商家暂停营业。"))

    def test_strict_response_validation_and_safe_disclaimer_fill(self):
        response = copy.deepcopy(SAMPLES["valid"])
        allowed = ("L-001", "L-004")
        self.assertEqual(parse_and_validate(json.dumps(response, ensure_ascii=False), allowed), response)
        response.pop("disclaimer")
        self.assertEqual(parse_and_validate(json.dumps(response, ensure_ascii=False), allowed)["disclaimer"], DISCLAIMER)
        response["legalBasis"] = ["[L-009] 未注入来源"]
        with self.assertRaises(InvalidProviderResponseError):
            parse_and_validate(json.dumps(response, ensure_ascii=False), allowed)
        with self.assertRaises(InvalidProviderResponseError):
            parse_and_validate(SAMPLES["invalid"]["extraMarkdown"], allowed)

    def test_list_items_must_be_nonempty_strings_within_schema_limit(self):
        allowed = ("L-001", "L-004")
        response = copy.deepcopy(SAMPLES["valid"])
        response["factsKnown"] = [None]
        with self.assertRaises(InvalidProviderResponseError):
            parse_and_validate(json.dumps(response, ensure_ascii=False), allowed)
        response = copy.deepcopy(SAMPLES["valid"])
        response["factsMissing"] = [" "]
        with self.assertRaises(InvalidProviderResponseError):
            parse_and_validate(json.dumps(response, ensure_ascii=False), allowed)
        response = copy.deepcopy(SAMPLES["valid"])
        response["specialNotes"] = ["x" * 501]
        with self.assertRaises(InvalidProviderResponseError):
            parse_and_validate(json.dumps(response, ensure_ascii=False), allowed)

    def test_service_uses_fake_provider_without_network_or_storage(self):
        provider = FakeProvider(json.dumps(SAMPLES["valid"], ensure_ascii=False))
        result = asyncio.run(ConsumerAnalysisService(provider).analyze("网上购买商品后发现质量问题，商家售后一直没有明确回复。"))
        self.assertEqual(result["disclaimer"], DISCLAIMER)
        self.assertEqual(provider.temperature, 0.1)
        self.assertEqual(provider.max_tokens, 8192)
        self.assertIsNotNone(provider.messages)

    def test_provider_failure_is_not_converted_to_content(self):
        with self.assertRaises(ProviderUnavailableError):
            asyncio.run(ConsumerAnalysisService(FailingProvider()).analyze("网上购买商品后发现质量问题，商家售后一直没有明确回复。"))


if __name__ == "__main__":
    unittest.main()
